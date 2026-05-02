<!--
  One-step Purchase Invoice page.

  Layout mirrors `PurchaseOrders.vue` (item picker on the left, cart-
  style form on the right) but the right column is intentionally
  trimmed:
    - No warehouse picker — warehouse comes from the active POS
      Profile and is stamped server-side.
    - No cost-center picker — same reason.
    - No "Receive Now" / "Create Invoice" toggles — this flow IS the
      invoice, with `update_stock = 1` always on.
    - Schedule date dropped; posting_date defaults to today server-
      side.

  After the server returns, we open `BarcodeLabelPrintDialog` with
  the `labels` array (one entry per unit purchased) so the operator
  can route them to a thermal label printer via QZ Tray.
-->
<template>
	<div class="pa-0 h-100">
		<v-row class="h-100 ma-0">
			<!-- Left Column: Item Selector -->
			<v-col cols="12" md="5" class="h-100 pa-0 border-e">
				<ItemsSelector context="purchase" @add-item="onAddItem" />
			</v-col>

			<!-- Right Column: Purchase Invoice Form -->
			<v-col cols="12" md="7" class="h-100 pa-0">
				<v-card class="h-100 d-flex flex-column purchase-invoice-card" flat>
					<div class="purchase-invoice-header">
						<div class="purchase-invoice-header__icon-wrap">
							<v-icon class="purchase-invoice-header__icon">
								mdi-receipt-text-plus-outline
							</v-icon>
						</div>
						<div class="purchase-invoice-header__copy">
							<span class="purchase-invoice-header__eyebrow">
								{{ __("Stock-update purchase") }}
							</span>
							<h3 class="purchase-invoice-header__title">
								{{ __("Create Purchase Invoice") }}
							</h3>
						</div>
						<v-spacer></v-spacer>
						<button
							type="button"
							class="purchase-invoice-header__clear"
							@click="resetForm"
							:title="__('Clear All')"
							:aria-label="__('Clear all purchase invoice items')"
						>
							<v-icon size="20">mdi-trash-can-outline</v-icon>
						</button>
					</div>

					<v-card-text
						class="flex-grow-1 overflow-y-auto pa-4 purchase-invoice-card__body"
					>
						<!-- Profile-stamped facts: cashier sees what'll be on
						     the invoice but cannot edit it. Source of truth
						     is the POS Profile. -->
						<div class="profile-facts mb-4">
							<div class="profile-fact">
								<v-icon size="16" color="primary" class="mr-2">
									mdi-warehouse
								</v-icon>
								<span class="profile-fact__label">{{ __("Warehouse") }}:</span>
								<span class="profile-fact__value">
									{{ pos_profile.warehouse || __("(profile missing)") }}
								</span>
							</div>
							<div v-if="pos_profile.cost_center" class="profile-fact">
								<v-icon size="16" color="primary" class="mr-2">
									mdi-bank-outline
								</v-icon>
								<span class="profile-fact__label">{{ __("Cost Center") }}:</span>
								<span class="profile-fact__value">
									{{ pos_profile.cost_center }}
								</span>
							</div>
						</div>

						<!-- Supplier picker + bill-no shortcut. -->
						<v-row dense>
							<v-col cols="12" md="7">
								<v-autocomplete
									v-model="supplier"
									:items="supplierOptions"
									item-title="supplier_name"
									item-value="name"
									:label="__('Supplier')"
									density="compact"
									variant="outlined"
									hide-details
									:loading="supplierLoading"
									@update:search="handleSupplierSearch"
									class="pos-themed-input"
								>
									<template #append>
										<v-btn
											v-if="allowCreateSupplier"
											size="small"
											variant="text"
											@click="supplierDialog = true"
											:title="__('New Supplier')"
										>
											<v-icon>mdi-plus</v-icon>
										</v-btn>
									</template>
								</v-autocomplete>
							</v-col>
							<v-col cols="12" md="5">
								<v-text-field
									v-model="billNo"
									:label="__('Supplier Invoice No (optional)')"
									density="compact"
									variant="outlined"
									hide-details
									class="pos-themed-input"
								></v-text-field>
							</v-col>
						</v-row>

						<v-divider class="my-4 purchase-invoice-divider"></v-divider>

						<PurchaseItemsTable
							:headers="itemHeaders"
							:items="purchaseItems"
							:currencySymbol="
								currencySymbol(priceListCurrency || supplierCurrency)
							"
							:totalAmount="totalAmount"
							:receiveNow="false"
							:formatCurrency="formatCurrency"
							:formatNumber="formatNumber"
							@update-uom="({ item, value }) => updateItemUom(item, value)"
							@update-qty="({ item, value }) => updateItemQty(item, value)"
							@update-rate="({ item, value }) => updateItemRate(item, value)"
							@remove-item="removeItem"
						/>

						<v-alert
							v-if="errorMessage"
							type="error"
							density="compact"
							class="mt-4"
						>
							{{ errorMessage }}
						</v-alert>
					</v-card-text>

					<v-card-actions class="pa-4 purchase-invoice-actions">
						<v-spacer></v-spacer>
						<v-btn
							:loading="submitLoading"
							:disabled="submitLoading || !purchaseItems.length"
							@click="submitInvoice"
							class="purchase-invoice-submit-btn"
							size="large"
							block
						>
							<v-icon start>mdi-check-circle-outline</v-icon>
							{{ __("Submit & Print Labels") }}
						</v-btn>
					</v-card-actions>
				</v-card>
			</v-col>
		</v-row>

		<!-- Supplier Dialog (reuse existing one). -->
		<SupplierDialog
			v-model="supplierDialog"
			:groups="supplierGroups"
			:posProfile="pos_profile"
			@created="handleSupplierCreated"
			@error="(msg) => toastStore.show({ title: msg, color: 'error' })"
		/>

		<!-- Barcode Label Print Dialog (auto-opens after submit). -->
		<BarcodeLabelPrintDialog
			v-model="labelDialog"
			:labels="pendingLabels"
			@close="onLabelDialogClose"
		/>
	</div>
</template>

<script>
import format from "../../../format";
import { useUIStore } from "../../../stores/uiStore.js";
import { getOpeningStorage } from "../../../../offline/index";
import { useItemsStore } from "../../../stores/itemsStore";
import { useToastStore } from "../../../stores/toastStore";
import { usePurchaseInvoice } from "../../../composables/pos/payments/usePurchaseInvoice";
import ItemsSelector from "../items/ItemsSelector.vue";
import SupplierDialog from "../dialogs/purchase/SupplierDialog.vue";
import PurchaseItemsTable from "./PurchaseItemsTable.vue";
import BarcodeLabelPrintDialog from "./BarcodeLabelPrintDialog.vue";
import { ref, watch, onMounted, onBeforeUnmount, inject } from "vue";

export default {
	mixins: [format],
	components: {
		ItemsSelector,
		SupplierDialog,
		PurchaseItemsTable,
		BarcodeLabelPrintDialog,
	},
	setup() {
		const uiStore = useUIStore();
		const toastStore = useToastStore();
		const itemsStore = useItemsStore();
		const eventBus = inject("eventBus");

		const pos_profile = ref({});

		const {
			purchaseItems,
			supplier,
			supplierCurrency,
			supplierPriceList,
			priceListCurrency,
			billNo,
			totalAmount,
			submitLoading,
			errorMessage,
			onAddItem,
			fetchSupplierInfo,
			updateItemUom,
			updateItemQty,
			updateItemRate,
			removeItem,
			resetForm: resetComposableForm,
		} = usePurchaseInvoice({ posProfile: pos_profile });

		const supplierOptions = ref([]);
		const supplierLoading = ref(false);
		const supplierDialog = ref(false);
		const supplierGroups = ref([]);
		const labelDialog = ref(false);
		const pendingLabels = ref([]);

		const supplierSearchTimeout = ref(null);

		const handleSupplierSearch = (term) => {
			if (supplierSearchTimeout.value) clearTimeout(supplierSearchTimeout.value);
			supplierSearchTimeout.value = setTimeout(
				() => searchSuppliers(term),
				300,
			);
		};

		const searchSuppliers = async (searchText = "") => {
			supplierLoading.value = true;
			try {
				const { message } = await frappe.call({
					method: "posawesome.mizan.api.purchase_orders.search_suppliers",
					args: { search_text: searchText, limit: 20 },
				});
				supplierOptions.value = Array.isArray(message) ? message : [];
				if (supplier.value) {
					const s = supplierOptions.value.find(
						(opt) => opt.name === supplier.value,
					);
					supplierCurrency.value =
						s?.default_currency || pos_profile.value.currency;
				}
			} catch (error) {
				console.error("Failed to fetch suppliers:", error);
			} finally {
				supplierLoading.value = false;
			}
		};

		const loadSupplierGroups = async () => {
			try {
				const { message } = await frappe.call({
					method: "frappe.client.get_list",
					args: {
						doctype: "Supplier Group",
						fields: ["name"],
						filters: { is_group: 0 },
						limit_page_length: 500,
					},
				});
				supplierGroups.value = (message || []).map((row) => row.name);
			} catch (error) {
				console.error("Failed to load groups:", error);
			}
		};

		const handleSupplierCreated = (message) => {
			supplierOptions.value.unshift(message);
			supplier.value = message.name;
			supplierDialog.value = false;
		};

		const extractServerError = (error) => {
			const parseServerMessages = (raw) => {
				if (!raw) return "";
				try {
					const parsed = JSON.parse(raw);
					if (Array.isArray(parsed) && parsed.length) {
						const first = parsed[0];
						if (typeof first === "string") {
							return first.replace(/<[^>]*>/g, "").trim();
						}
					}
				} catch {
					return String(raw);
				}
				return "";
			};

			return (
				parseServerMessages(error?._server_messages) ||
				parseServerMessages(error?.responseJSON?._server_messages) ||
				error?.message ||
				error?.responseJSON?.message ||
				__("Unable to create purchase invoice")
			);
		};

		const submitInvoice = async () => {
			if (!supplier.value) {
				errorMessage.value = __("Supplier is required.");
				return;
			}
			if (!purchaseItems.value.length) {
				errorMessage.value = __("Please add at least one item.");
				return;
			}
			if (!pos_profile.value?.warehouse) {
				errorMessage.value = __(
					"POS Profile has no warehouse. Set one before submitting purchase invoices.",
				);
				return;
			}
			errorMessage.value = "";
			submitLoading.value = true;

			try {
				const resolvedSupplier =
					typeof supplier.value === "object" && supplier.value !== null
						? supplier.value.name || supplier.value.supplier_name || ""
						: supplier.value;

				const payload = {
					supplier: resolvedSupplier,
					company: pos_profile.value.company,
					currency: supplierCurrency.value,
					bill_no: billNo.value || null,
					pos_profile: pos_profile.value,
					items: purchaseItems.value.map((item) => ({
						item_code: item.item_code,
						item_name: item.item_name,
						stock_uom: item.stock_uom,
						uom: item.uom,
						conversion_factor: item.conversion_factor,
						qty: item.qty,
						rate: item.rate,
					})),
				};

				const { message } = await frappe.call({
					method: "posawesome.mizan.api.purchase_invoices.create_purchase_invoice",
					args: { data: payload },
				});

				if (message?.purchase_invoice) {
					toastStore.show({
						title: __("Purchase Invoice {0} created", [
							message.purchase_invoice,
						]),
						color: "success",
					});
					pendingLabels.value = Array.isArray(message.labels)
						? message.labels
						: [];
					if (pendingLabels.value.length) {
						labelDialog.value = true;
					} else {
						resetForm();
					}
				}
			} catch (error) {
				errorMessage.value = extractServerError(error);
				toastStore.show({ title: errorMessage.value, color: "error" });
			} finally {
				submitLoading.value = false;
			}
		};

		const onLabelDialogClose = () => {
			// After the user closes the label dialog (whether they
			// printed or not), wipe the form so the next purchase
			// starts blank. Keeping the cart around after submit
			// risks a re-submit of the same line set.
			pendingLabels.value = [];
			resetForm();
		};

		const resetForm = () => {
			resetComposableForm();
		};

		onMounted(async () => {
			const cachedData = getOpeningStorage();
			if (cachedData?.pos_profile) pos_profile.value = cachedData.pos_profile;

			watch(
				() => uiStore.posProfile,
				(p) => {
					if (p) pos_profile.value = p;
				},
				{ immediate: true },
			);
			watch(supplier, async (val) => {
				if (val) {
					const info = await fetchSupplierInfo(val);
					if (info?.buying_price_list) {
						await itemsStore.updatePriceList(info.buying_price_list);
					}
					eventBus?.emit?.("update_buying_price_list", {
						price_list: info?.buying_price_list || null,
						supplier: val,
					});
				} else {
					supplierCurrency.value = pos_profile.value.currency;
					eventBus?.emit?.("update_buying_price_list", null);
				}
			});

			try {
				const { message } = await frappe.call({
					method: "posawesome.mizan.api.purchase_orders.get_buying_price_list",
				});
				if (message) await itemsStore.updatePriceList(message);
			} catch (e) {
				console.error("Failed price list load", e);
			}

			resetForm();
			await Promise.all([searchSuppliers(""), loadSupplierGroups()]);
		});

		onBeforeUnmount(() => {
			eventBus?.emit?.("update_buying_price_list", null);
			if (pos_profile.value?.selling_price_list)
				itemsStore.updatePriceList(pos_profile.value.selling_price_list);
		});

		return {
			pos_profile,
			purchaseItems,
			supplier,
			supplierCurrency,
			supplierPriceList,
			priceListCurrency,
			billNo,
			totalAmount,
			submitLoading,
			errorMessage,
			onAddItem,
			updateItemUom,
			updateItemQty,
			updateItemRate,
			removeItem,
			resetForm,
			supplierOptions,
			supplierLoading,
			supplierDialog,
			supplierGroups,
			handleSupplierSearch,
			handleSupplierCreated,
			submitInvoice,
			toastStore,
			labelDialog,
			pendingLabels,
			onLabelDialogClose,
		};
	},
	computed: {
		allowCreateSupplier() {
			return !!this.pos_profile?.posa_allow_create_purchase_suppliers;
		},
		itemHeaders() {
			return [
				{ title: __("Item"), key: "item_name", align: "start", width: "38%" },
				{ title: __("UOM"), key: "uom", align: "center", width: "16%" },
				{ title: __("Qty"), key: "qty", align: "center", width: "16%" },
				{ title: __("Rate"), key: "rate", align: "center", width: "16%" },
				{ title: __("Amount"), key: "amount", align: "end", width: "10%" },
				{ title: "", key: "actions", align: "center", width: "50px" },
			];
		},
	},
	methods: {
		formatNumber(v) {
			return this.formatFloat(v, 2);
		},
		currencySymbol(c) {
			return get_currency_symbol(c || this.pos_profile.currency);
		},
	},
};
</script>

<style scoped>
.purchase-invoice-card {
	background: var(--pos-card-bg, #0e131e) !important;
	border-left: 1px solid rgba(139, 92, 246, 0.18);
	font-family: var(--posa-font-family, "Space Grotesk", sans-serif);
	color: var(--pos-text-primary, #e7ebf3);
}

.purchase-invoice-card,
.purchase-invoice-card :deep(*) {
	font-family: var(--posa-font-family, "Space Grotesk", sans-serif);
}

.purchase-invoice-card__body {
	background: var(--pos-card-bg, #0e131e);
}

.purchase-invoice-header {
	display: flex;
	align-items: center;
	gap: 14px;
	padding: 14px 18px;
	background:
		linear-gradient(
			135deg,
			rgba(139, 92, 246, 0.18),
			rgba(226, 54, 112, 0.1)
		),
		var(--pos-surface-muted, #161c27);
	border-bottom: 1px solid rgba(139, 92, 246, 0.28);
}

.purchase-invoice-header__icon-wrap {
	width: 44px;
	height: 44px;
	display: grid;
	place-items: center;
	border-radius: 12px;
	flex-shrink: 0;
	background: linear-gradient(
		135deg,
		rgba(139, 92, 246, 0.32),
		rgba(226, 54, 112, 0.22)
	);
	border: 1px solid rgba(139, 92, 246, 0.5);
	box-shadow: 0 6px 18px rgba(139, 92, 246, 0.22);
}

.purchase-invoice-header__icon {
	font-size: 24px !important;
	color: #c4b5fd !important;
}

.purchase-invoice-header__copy {
	display: flex;
	flex-direction: column;
	gap: 2px;
	min-width: 0;
}

.purchase-invoice-header__eyebrow {
	font-size: 0.66rem;
	font-weight: 700;
	letter-spacing: 0.16em;
	text-transform: uppercase;
	color: rgba(231, 235, 243, 0.65);
}

.purchase-invoice-header__title {
	margin: 0;
	font-size: 1.1rem;
	font-weight: 700;
	letter-spacing: 0.01em;
	background: linear-gradient(135deg, #f5d0fe 0%, #fb7185 100%);
	background-clip: text;
	-webkit-background-clip: text;
	color: transparent;
	-webkit-text-fill-color: transparent;
}

.purchase-invoice-header__clear {
	all: unset;
	width: 36px;
	height: 36px;
	display: grid;
	place-items: center;
	border-radius: 10px;
	cursor: pointer;
	color: rgba(231, 235, 243, 0.7);
	border: 1px solid rgba(244, 63, 94, 0.28);
	background: rgba(244, 63, 94, 0.08);
	transition:
		background-color 0.18s ease,
		color 0.18s ease,
		box-shadow 0.18s ease;
}

.purchase-invoice-header__clear:hover {
	background: rgba(244, 63, 94, 0.18);
	color: #fb7185;
	box-shadow: 0 0 0 3px rgba(244, 63, 94, 0.14);
}

.purchase-invoice-divider {
	border-color: rgba(139, 92, 246, 0.18) !important;
	opacity: 1 !important;
}

.purchase-invoice-actions {
	background: var(--pos-surface-muted, #161c27);
	border-top: 1px solid rgba(139, 92, 246, 0.18);
}

.purchase-invoice-submit-btn {
	background: linear-gradient(135deg, #8b5cf6 0%, #e23670 100%) !important;
	color: #ffffff !important;
	font-weight: 700 !important;
	letter-spacing: 0.04em !important;
	border-radius: 12px !important;
	min-height: 48px !important;
	box-shadow:
		0 12px 28px rgba(139, 92, 246, 0.28),
		0 0 0 1px rgba(244, 114, 182, 0.32) inset !important;
	text-transform: none !important;
	transition:
		filter 0.18s ease,
		box-shadow 0.18s ease,
		transform 0.18s ease !important;
}

.purchase-invoice-submit-btn:hover:not(:disabled) {
	filter: brightness(1.08);
	box-shadow:
		0 14px 32px rgba(226, 54, 112, 0.34),
		0 0 0 1px rgba(244, 114, 182, 0.42) inset !important;
	transform: translateY(-1px);
}

.purchase-invoice-submit-btn:disabled,
.purchase-invoice-submit-btn.v-btn--disabled {
	opacity: 0.55 !important;
	background: linear-gradient(135deg, #4c4561 0%, #5b3149 100%) !important;
	box-shadow: none !important;
}

.profile-facts {
	display: flex;
	flex-wrap: wrap;
	gap: 16px;
	padding: 10px 14px;
	background: rgba(139, 92, 246, 0.06);
	border: 1px solid rgba(139, 92, 246, 0.18);
	border-radius: 10px;
	font-size: 0.85rem;
}

.profile-fact {
	display: inline-flex;
	align-items: center;
}

.profile-fact__label {
	color: rgba(231, 235, 243, 0.65);
	margin-right: 6px;
	letter-spacing: 0.02em;
}

.profile-fact__value {
	color: #e7ebf3;
	font-weight: 600;
}
</style>
