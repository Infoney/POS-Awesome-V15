<template>
	<div class="pa-0 h-100">
		<v-row class="h-100 ma-0">
			<!-- Left Column: Item Selector -->
			<v-col cols="12" md="5" class="h-100 pa-0 border-e">
				<ItemsSelector context="purchase" @add-item="onAddItem" />
			</v-col>

			<!-- Right Column: Receipt Form -->
			<v-col cols="12" md="7" class="h-100 pa-0">
				<v-card class="h-100 d-flex flex-column purchase-receipt-card" flat>
					<div class="purchase-receipt-header">
						<div class="purchase-receipt-header__icon-wrap">
							<v-icon class="purchase-receipt-header__icon">mdi-package-variant-closed-plus</v-icon>
						</div>
						<div class="purchase-receipt-header__copy">
							<span class="purchase-receipt-header__eyebrow">{{ __("Receive stock") }}</span>
							<h3 class="purchase-receipt-header__title">{{ __("New Purchase Receipt") }}</h3>
						</div>
						<v-spacer></v-spacer>
						<button
							type="button"
							class="purchase-receipt-header__clear"
							@click="resetForm"
							:title="__('Clear All')"
							:aria-label="__('Clear all receipt items')"
						>
							<v-icon size="20">mdi-trash-can-outline</v-icon>
						</button>
					</div>

					<v-card-text class="flex-grow-1 overflow-y-auto pa-4 purchase-receipt-card__body">
						<!-- Header (supplier / warehouse / posting date) -->
						<v-container class="pa-0">
							<v-row dense class="mb-2">
								<v-col cols="12" md="6">
									<v-autocomplete
										v-model="supplier"
										:items="supplierOptions"
										item-title="supplier_name"
										item-value="name"
										:label="__('Supplier')"
										density="compact"
										variant="outlined"
										color="primary"
										hide-details="auto"
										:loading="supplierLoading"
										@update:search="handleSupplierSearch"
										:custom-filter="() => true"
										:no-data-text="supplierLoading ? __('Loading suppliers...') : __('Suppliers not found')"
										class="pos-themed-input"
										clearable
									>
										<template #append-inner>
											<v-tooltip v-if="allowCreateSupplier" :text="__('Add new supplier')">
												<template #activator="{ props }">
													<v-icon
														v-bind="props"
														class="cursor-pointer"
														@mousedown.prevent.stop
														@click.stop="supplierDialog = true"
													>
														mdi-plus
													</v-icon>
												</template>
											</v-tooltip>
										</template>
									</v-autocomplete>
								</v-col>
								<v-col cols="12" md="6">
									<v-autocomplete
										v-model="warehouse"
										:items="warehouseOptions"
										item-title="warehouse_name"
										item-value="name"
										:label="__('Warehouse')"
										density="compact"
										variant="outlined"
										color="primary"
										hide-details="auto"
										clearable
										:loading="warehouseLoading"
										class="pos-themed-input"
									/>
								</v-col>
							</v-row>

							<v-row dense class="mb-2">
								<v-col cols="6">
									<VueDatePicker
										v-model="postingDate"
										model-type="format"
										format="dd-MM-yyyy"
										:enable-time-picker="false"
										auto-apply
										:placeholder="__('Posting Date')"
										class="pos-themed-input"
									/>
								</v-col>
								<v-col cols="6" class="d-flex align-center">
									<div class="text-caption text-medium-emphasis pl-2">
										<span v-if="supplierPriceList">
											{{ __("Buying price list:") }}
											<strong>{{ supplierPriceList }}</strong>
										</span>
										<span v-else>{{ __("No buying price list resolved.") }}</span>
									</div>
								</v-col>
							</v-row>
						</v-container>

						<v-divider class="mb-4 purchase-receipt-divider"></v-divider>

						<PurchaseReceiptItemsTable
							:headers="itemHeaders"
							:items="receiptItems"
							:currencySymbol="currencySymbol(priceListCurrency || supplierCurrency)"
							:totalAmount="totalAmount"
							:formatCurrency="formatCurrency"
							:formatNumber="formatNumber"
							@update-uom="({ item, value }) => updateItemUom(item, value)"
							@update-qty="({ item, value }) => updateItemQty(item, value)"
							@update-rate="({ item, value }) => updateItemRate(item, value)"
							@update-discount="({ item, value }) => updateItemDiscount(item, value)"
							@update-serial="({ item, value }) => onUpdateSerial(item, value)"
							@set-batch="({ item, value }) => setBatch(item, value)"
							@set-batch-expiry="({ item, value }) => onSetBatchExpiry(item, value)"
							@ensure-batches="(item) => loadBatchOptions(item)"
							@remove-item="removeItem"
						/>

						<v-alert v-if="errorMessage" type="error" density="compact" class="mt-4">
							{{ errorMessage }}
						</v-alert>
					</v-card-text>

					<v-card-actions class="pa-4 purchase-receipt-actions">
						<v-spacer></v-spacer>
						<v-btn
							:loading="submitLoading"
							:disabled="submitLoading || !receiptItems.length || !supplier"
							@click="openConfirmDialog"
							class="purchase-receipt-submit-btn"
							size="large"
							block
						>
							<v-icon start>mdi-package-variant-closed-check</v-icon>
							{{ __("Review & Submit") }}
						</v-btn>
					</v-card-actions>
				</v-card>
			</v-col>
		</v-row>

		<!-- Confirm Dialog -->
		<PurchaseReceiptConfirmDialog
			v-model="confirmDialog"
			:supplier-label="resolvedSupplierLabel"
			:warehouse="warehouse"
			:posting-date="postingDate"
			:line-count="receiptItems.length"
			:total-qty="totalQty"
			:total-amount="totalAmount"
			:currency-symbol="currencySymbol(priceListCurrency || supplierCurrency)"
			:update-price-list="updatePriceList"
			:buying-price-list="supplierPriceList"
			:loading="submitLoading"
			:can-submit="!!supplier && !!warehouse && receiptItems.length > 0"
			:format-currency="formatCurrency"
			:format-number="formatNumber"
			@update:updatePriceList="(val) => (updatePriceList = val)"
			@confirm="handleConfirmedSubmit"
		/>

		<!-- Supplier Dialog -->
		<SupplierDialog
			v-model="supplierDialog"
			:groups="supplierGroups"
			:posProfile="pos_profile"
			@created="handleSupplierCreated"
			@error="(msg) => toastStore.show({ title: msg, color: 'error' })"
		/>
	</div>
</template>

<script>
import format, { formatUtils } from "../../../format";
import { useUIStore } from "../../../stores/uiStore.js";
import { getOpeningStorage } from "../../../../offline/index";
import { useToastStore } from "../../../stores/toastStore";
import { usePurchaseReceipt } from "../../../composables/pos/purchase/usePurchaseReceipt";
import ItemsSelector from "../items/ItemsSelector.vue";
import SupplierDialog from "../dialogs/purchase/SupplierDialog.vue";
import PurchaseReceiptItemsTable from "./PurchaseReceiptItemsTable.vue";
import PurchaseReceiptConfirmDialog from "./PurchaseReceiptConfirmDialog.vue";
import { ref, watch, onMounted } from "vue";

export default {
	mixins: [format],
	components: {
		ItemsSelector,
		SupplierDialog,
		PurchaseReceiptItemsTable,
		PurchaseReceiptConfirmDialog,
	},
	setup() {
		const uiStore = useUIStore();
		const toastStore = useToastStore();

		const pos_profile = ref({});

		const {
			receiptItems,
			supplier,
			warehouse,
			postingDate,
			supplierCurrency,
			supplierPriceList,
			priceListCurrency,
			updatePriceList,
			totalAmount,
			totalQty,
			submitLoading,
			errorMessage,
			onAddItem,
			fetchSupplierInfo,
			loadBatchOptions,
			setBatch,
			updateItemUom,
			updateItemQty,
			updateItemRate,
			updateItemDiscount,
			removeItem,
			resetForm,
			submitReceipt,
		} = usePurchaseReceipt({
			posProfile: pos_profile,
			formatFloat: (val, prec) =>
				format.methods.formatFloat.call({ currency_precision: 2 }, val, prec),
		});

		const supplierOptions = ref([]);
		const supplierLoading = ref(false);
		const supplierDialog = ref(false);
		const supplierGroups = ref([]);
		const warehouseOptions = ref([]);
		const warehouseLoading = ref(false);
		const confirmDialog = ref(false);

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
					method:
						"posawesome.posawesome.api.purchase_orders.search_suppliers",
					args: { search_text: searchText, limit: 20 },
				});
				supplierOptions.value = Array.isArray(message) ? message : [];
				if (supplier.value) {
					const s = supplierOptions.value.find(
						(item) => item.name === supplier.value,
					);
					if (s)
						supplierCurrency.value =
							s.default_currency || pos_profile.value.currency || null;
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
				console.error("Failed to load supplier groups:", error);
			}
		};

		const loadWarehouses = async () => {
			warehouseLoading.value = true;
			try {
				const { message } = await frappe.call({
					method: "frappe.client.get_list",
					args: {
						doctype: "Warehouse",
						fields: ["name", "warehouse_name"],
						filters: {
							company: pos_profile.value.company,
							is_group: 0,
							disabled: 0,
						},
						limit_page_length: 500,
					},
				});
				warehouseOptions.value = message || [];
			} catch (error) {
				console.error("Failed to load warehouses:", error);
			} finally {
				warehouseLoading.value = false;
			}
		};

		const handleSupplierCreated = (message) => {
			supplierOptions.value.unshift(message);
			supplier.value = message.name;
			supplierDialog.value = false;
		};

		const onUpdateSerial = (row, value) => {
			row.serial_no = value || "";
		};

		const onSetBatchExpiry = (row, value) => {
			row.batch_expiry_date = value || null;
		};

		const openConfirmDialog = () => {
			if (!supplier.value) {
				errorMessage.value = __("Supplier is required.");
				return;
			}
			if (!warehouse.value) {
				errorMessage.value = __("Warehouse is required.");
				return;
			}
			if (!receiptItems.value.length) {
				errorMessage.value = __("Add at least one item.");
				return;
			}
			errorMessage.value = "";
			confirmDialog.value = true;
		};

		const formatDateForBackend = (date) => {
			if (!date) return null;
			const western = formatUtils.fromArabicNumerals(String(date));
			if (/^\d{4}-\d{2}-\d{2}$/.test(western)) return western;
			// Date pickers emit dd-MM-yyyy
			const m = western.match(/^(\d{2})-(\d{2})-(\d{4})$/);
			if (m) return `${m[3]}-${m[2]}-${m[1]}`;
			const d = new Date(western);
			if (isNaN(d.getTime())) return western;
			return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
		};

		const handleConfirmedSubmit = async () => {
			try {
				// Make sure dates are normalised before sending.
				postingDate.value = postingDate.value
					? formatDateForBackend(postingDate.value)
					: null;
				const result = await submitReceipt();
				if (result?.purchase_receipt) {
					toastStore.show({
						title: __("Purchase Receipt {0} created", [result.purchase_receipt]),
						color: "success",
					});
					confirmDialog.value = false;
					resetForm();
				}
			} catch (error) {
				const msg =
					error?.message ||
					error?.responseJSON?.message ||
					__("Unable to create purchase receipt");
				errorMessage.value = msg;
				toastStore.show({ title: msg, color: "error" });
			}
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

			// Items are not linked to suppliers — switching suppliers should NOT
			// reload the items grid or repaint last-buying rates. We just pull
			// supplier currency + buying price list so per-row rate lookups can
			// resolve a buying price when the user adds an item.
			watch(supplier, async (val) => {
				if (val) {
					await fetchSupplierInfo(val);
				} else {
					supplierCurrency.value = pos_profile.value.currency || null;
					supplierPriceList.value = null;
					priceListCurrency.value = null;
				}
			});

			// Seed a default buying price list (used as fallback when no supplier
			// is selected yet). This is a single light call — no items reload.
			try {
				const { message } = await frappe.call({
					method:
						"posawesome.posawesome.api.purchase_orders.get_buying_price_list",
				});
				if (message && !supplierPriceList.value) {
					supplierPriceList.value = message;
				}
			} catch (e) {
				console.error("Failed to load buying price list", e);
			}

			resetForm();
			await Promise.all([
				searchSuppliers(""),
				loadSupplierGroups(),
				loadWarehouses(),
			]);
		});

		return {
			pos_profile,
			receiptItems,
			supplier,
			warehouse,
			postingDate,
			supplierCurrency,
			supplierPriceList,
			priceListCurrency,
			updatePriceList,
			totalAmount,
			totalQty,
			submitLoading,
			errorMessage,
			onAddItem,
			fetchSupplierInfo,
			loadBatchOptions,
			setBatch,
			updateItemUom,
			updateItemQty,
			updateItemRate,
			updateItemDiscount,
			removeItem,
			resetForm,
			submitReceipt,
			supplierOptions,
			supplierLoading,
			supplierDialog,
			supplierGroups,
			warehouseOptions,
			warehouseLoading,
			confirmDialog,
			handleSupplierSearch,
			handleSupplierCreated,
			onUpdateSerial,
			onSetBatchExpiry,
			openConfirmDialog,
			handleConfirmedSubmit,
			toastStore,
		};
	},
	computed: {
		allowCreateSupplier() {
			return !!this.pos_profile?.posa_allow_create_purchase_suppliers;
		},
		resolvedSupplierLabel() {
			if (!this.supplier) return "";
			const found = this.supplierOptions.find(
				(s) => s.name === this.supplier,
			);
			return found?.supplier_name || this.supplier;
		},
		anyItemHasBatch() {
			return this.receiptItems.some((row) => row.has_batch_no);
		},
		anyItemHasSerial() {
			return this.receiptItems.some((row) => row.has_serial_no);
		},
		itemHeaders() {
			const headers = [
				{ title: __("Item"), key: "item_name", align: "start", width: "22%" },
				{ title: __("UOM"), key: "uom", align: "center", width: "10%" },
			];
			if (this.anyItemHasBatch) {
				headers.push({
					title: __("Batch / Expiry"),
					key: "batch",
					align: "start",
					width: "20%",
					sortable: false,
				});
			}
			if (this.anyItemHasSerial) {
				headers.push({
					title: __("Serials"),
					key: "serial_no",
					align: "start",
					width: "16%",
					sortable: false,
				});
			}
			headers.push(
				{ title: __("Qty"), key: "qty", align: "center", width: "10%" },
				{ title: __("Rate"), key: "rate", align: "center", width: "10%" },
				{ title: __("Disc %"), key: "discount_percentage", align: "center", width: "8%" },
				{ title: __("Amount"), key: "amount", align: "end", width: "10%" },
				{ title: "", key: "actions", align: "center", width: "50px", sortable: false },
			);
			return headers;
		},
	},
	methods: {
		formatNumber(v) {
			return this.formatFloat(v, 2);
		},
		currencySymbol(c) {
			try {
				return get_currency_symbol(c || this.pos_profile?.currency);
			} catch {
				return "";
			}
		},
	},
};
</script>

<style scoped>
.cursor-pointer {
	cursor: pointer;
}

.purchase-receipt-card {
	background: var(--pos-card-bg, #0e131e) !important;
	border-left: 1px solid rgba(139, 92, 246, 0.18);
	font-family: var(--posa-font-family, "Space Grotesk", sans-serif);
	color: var(--pos-text-primary, #e7ebf3);
}
.purchase-receipt-card,
.purchase-receipt-card :deep(*) {
	font-family: var(--posa-font-family, "Space Grotesk", sans-serif);
}
.purchase-receipt-card__body {
	background: var(--pos-card-bg, #0e131e);
}

.purchase-receipt-header {
	display: flex;
	align-items: center;
	gap: 14px;
	padding: 14px 18px;
	background:
		linear-gradient(
			135deg,
			rgba(139, 92, 246, 0.18),
			rgba(226, 54, 112, 0.10)
		),
		var(--pos-surface-muted, #161c27);
	border-bottom: 1px solid rgba(139, 92, 246, 0.28);
}

.purchase-receipt-header__icon-wrap {
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

.purchase-receipt-header__icon {
	font-size: 24px !important;
	color: #c4b5fd !important;
}

.purchase-receipt-header__copy {
	display: flex;
	flex-direction: column;
	gap: 2px;
	min-width: 0;
}

.purchase-receipt-header__eyebrow {
	font-size: 0.66rem;
	font-weight: 700;
	letter-spacing: 0.16em;
	text-transform: uppercase;
	color: rgba(231, 235, 243, 0.65);
}

.purchase-receipt-header__title {
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

.purchase-receipt-header__clear {
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
	transition: background-color 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;
}
.purchase-receipt-header__clear:hover {
	background: rgba(244, 63, 94, 0.18);
	color: #fb7185;
	box-shadow: 0 0 0 3px rgba(244, 63, 94, 0.14);
}

.purchase-receipt-divider {
	border-color: rgba(139, 92, 246, 0.18) !important;
	opacity: 1 !important;
}

.purchase-receipt-actions {
	background: var(--pos-surface-muted, #161c27);
	border-top: 1px solid rgba(139, 92, 246, 0.18);
}

.purchase-receipt-submit-btn {
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
	transition: filter 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease !important;
}
.purchase-receipt-submit-btn:hover:not(:disabled) {
	filter: brightness(1.08);
	box-shadow:
		0 14px 32px rgba(226, 54, 112, 0.34),
		0 0 0 1px rgba(244, 114, 182, 0.42) inset !important;
	transform: translateY(-1px);
}
.purchase-receipt-submit-btn:disabled,
.purchase-receipt-submit-btn.v-btn--disabled {
	opacity: 0.55 !important;
	background: linear-gradient(135deg, #4c4561 0%, #5b3149 100%) !important;
	box-shadow: none !important;
}
</style>
