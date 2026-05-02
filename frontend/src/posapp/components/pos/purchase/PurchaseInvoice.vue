<!--
  One-step Purchase Invoice page.

  Mirrors `PurchaseReceipts.vue` layout 1:1 — full-width single
  column with an inline item search bar and the same items table
  (`PurchaseReceiptItemsTable.vue` reused, not cloned, so the batch /
  expiry / serial UI stays identical). The two screens are siblings:
    - PR receives stock without booking the payable
    - PI receives stock AND books the payable (`update_stock = 1`)

  Warehouse + cost center default from the POS Profile but stay
  operator-editable so multi-warehouse / multi-cost-centre stores can
  override per shipment. Same pattern as PR.

  Post-submit, opens `BarcodeLabelPrintDialog` with the `labels[]`
  payload so the operator can print barcode labels for each unit of
  the just-received stock via QZ Tray.
-->
<template>
	<div class="pa-0 h-100 pi-shell">
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
						{{ __("New Purchase Invoice") }}
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
				<!-- Form header (supplier / warehouse / cost center / posting date / bill no) -->
				<div class="pi-form-grid">
					<div class="pi-form-field">
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
							:no-data-text="
								supplierLoading
									? __('Loading suppliers...')
									: __('Suppliers not found')
							"
							class="pos-themed-input pi-themed-field"
							menu-icon="mdi-chevron-down"
							clearable
						>
							<template #prepend-inner>
								<v-icon size="18" class="pi-field-icon">
									mdi-account-tie-outline
								</v-icon>
							</template>
							<template #append-inner>
								<v-tooltip
									v-if="allowCreateSupplier"
									:text="__('Add new supplier')"
								>
									<template #activator="{ props }">
										<v-icon
											v-bind="props"
											class="cursor-pointer pi-field-add"
											@mousedown.prevent.stop
											@click.stop="supplierDialog = true"
										>
											mdi-plus-circle-outline
										</v-icon>
									</template>
								</v-tooltip>
							</template>
						</v-autocomplete>
					</div>

					<div class="pi-form-field">
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
							class="pos-themed-input pi-themed-field"
							menu-icon="mdi-chevron-down"
						>
							<template #prepend-inner>
								<v-icon size="18" class="pi-field-icon">
									mdi-warehouse
								</v-icon>
							</template>
						</v-autocomplete>
					</div>

					<div class="pi-form-field">
						<v-autocomplete
							v-model="costCenter"
							:items="costCenterOptions"
							item-title="cost_center_name"
							item-value="name"
							:label="__('Cost Center')"
							density="compact"
							variant="outlined"
							color="primary"
							hide-details="auto"
							clearable
							:loading="costCenterLoading"
							class="pos-themed-input pi-themed-field"
							menu-icon="mdi-chevron-down"
						>
							<template #prepend-inner>
								<v-icon size="18" class="pi-field-icon">
									mdi-bank-outline
								</v-icon>
							</template>
						</v-autocomplete>
					</div>

					<div class="pi-form-field">
						<div class="pi-date-wrap">
							<v-icon size="18" class="pi-field-icon pi-date-icon">
								mdi-calendar-month-outline
							</v-icon>
							<VueDatePicker
								v-model="postingDate"
								model-type="format"
								format="dd-MM-yyyy"
								:enable-time-picker="false"
								auto-apply
								text-input
								:text-input-options="{
									format: ['dd-MM-yyyy', 'dd/MM/yyyy', 'd/M/yyyy'],
									enterSubmit: true,
									tabSubmit: true,
								}"
								:placeholder="__('Posting Date')"
								hide-input-icon
								class="pos-themed-input pi-date-picker"
							/>
						</div>
					</div>
				</div>

				<!-- Bill No (supplier's invoice reference) — optional, full-width row -->
				<div class="pi-bill-row">
					<v-text-field
						v-model="billNo"
						:label="__('Supplier Invoice No (optional)')"
						density="compact"
						variant="outlined"
						hide-details
						class="pos-themed-input pi-themed-field"
					>
						<template #prepend-inner>
							<v-icon size="18" class="pi-field-icon">
								mdi-file-document-outline
							</v-icon>
						</template>
					</v-text-field>
				</div>

				<!-- Buying-price-list pill -->
				<div class="pi-meta-row">
					<div
						class="pi-meta-pill"
						:class="{ 'pi-meta-pill--muted': !supplierPriceList }"
					>
						<v-icon size="14">mdi-tag-outline</v-icon>
						<span v-if="supplierPriceList">
							{{ __("Buying price list:") }}
							<strong>{{ supplierPriceList }}</strong>
						</span>
						<span v-else>{{ __("No buying price list resolved.") }}</span>
					</div>
				</div>

				<v-divider class="my-3 purchase-invoice-divider"></v-divider>

				<!-- Inline item search bar -->
				<div class="pi-search-bar">
					<v-autocomplete
						v-model="itemSearchSelection"
						:items="itemSearchResults"
						item-title="item_name"
						item-value="item_code"
						:label="__('Search & add an item (name or code)')"
						density="compact"
						variant="outlined"
						hide-details="auto"
						return-object
						clearable
						:loading="itemSearchLoading"
						@update:search="handleItemSearch"
						@update:model-value="onItemSelected"
						:custom-filter="() => true"
						:no-data-text="
							itemSearchLoading
								? __('Searching items...')
								: __('Type to search items')
						"
						class="pos-themed-input pi-themed-field pi-search-bar__input"
						menu-icon=""
					>
						<template #prepend-inner>
							<v-icon size="20" class="pi-field-icon">mdi-magnify</v-icon>
						</template>
						<template #item="{ props, item: opt }">
							<v-list-item
								v-bind="props"
								:title="opt.raw.item_name"
								:subtitle="opt.raw.item_code"
							>
								<template #append>
									<span class="pi-search-bar__rate">
										{{
											currencySymbol(
												priceListCurrency || supplierCurrency,
											)
										}}{{ formatNumber(opt.raw.standard_rate || 0) }}
									</span>
								</template>
							</v-list-item>
						</template>
					</v-autocomplete>
				</div>

				<!-- Reuse the PR items table — same batch/expiry/serial UI. -->
				<PurchaseReceiptItemsTable
					:headers="itemHeaders"
					:items="invoiceItems"
					:currencySymbol="
						currencySymbol(priceListCurrency || supplierCurrency)
					"
					:totalAmount="totalAmount"
					:formatCurrency="formatCurrency"
					:formatNumber="formatNumber"
					@update-uom="({ item, value }) => updateItemUom(item, value)"
					@update-qty="({ item, value }) => updateItemQty(item, value)"
					@update-rate="({ item, value }) => updateItemRate(item, value)"
					@update-discount="
						({ item, value }) => updateItemDiscount(item, value)
					"
					@update-serial="({ item, value }) => onUpdateSerial(item, value)"
					@set-batch="({ item, value }) => setBatch(item, value)"
					@set-batch-expiry="
						({ item, value }) => onSetBatchExpiry(item, value)
					"
					@ensure-batches="(item) => loadBatchOptions(item)"
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
					:disabled="
						submitLoading || !invoiceItems.length || !supplier || !warehouse
					"
					@click="onSubmit"
					class="purchase-invoice-submit-btn"
					size="large"
					block
				>
					<v-icon start>mdi-check-circle-outline</v-icon>
					{{ __("Submit & Print Labels") }}
				</v-btn>
			</v-card-actions>
		</v-card>

		<!-- Supplier Dialog -->
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
import format, { formatUtils } from "../../../format";
import { useUIStore } from "../../../stores/uiStore.js";
import { getOpeningStorage } from "../../../../offline/index";
import { useToastStore } from "../../../stores/toastStore";
import { usePurchaseInvoice } from "../../../composables/pos/payments/usePurchaseInvoice";
import SupplierDialog from "../dialogs/purchase/SupplierDialog.vue";
import PurchaseReceiptItemsTable from "./PurchaseReceiptItemsTable.vue";
import BarcodeLabelPrintDialog from "./BarcodeLabelPrintDialog.vue";
import { ref, watch, onMounted } from "vue";

export default {
	mixins: [format],
	components: {
		SupplierDialog,
		PurchaseReceiptItemsTable,
		BarcodeLabelPrintDialog,
	},
	setup() {
		const uiStore = useUIStore();
		const toastStore = useToastStore();

		const pos_profile = ref({});

		const {
			invoiceItems,
			supplier,
			warehouse,
			costCenter,
			postingDate,
			billNo,
			supplierCurrency,
			supplierPriceList,
			priceListCurrency,
			updatePriceList,
			totalAmount,
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
			resetForm: resetComposableForm,
			submitInvoice,
		} = usePurchaseInvoice({
			posProfile: pos_profile,
			formatFloat: (val, prec) =>
				format.methods.formatFloat.call(
					{ currency_precision: 2 },
					val,
					prec,
				),
		});

		const supplierOptions = ref([]);
		const supplierLoading = ref(false);
		const supplierDialog = ref(false);
		const supplierGroups = ref([]);
		const warehouseOptions = ref([]);
		const warehouseLoading = ref(false);
		const costCenterOptions = ref([]);
		const costCenterLoading = ref(false);
		const labelDialog = ref(false);
		const pendingLabels = ref([]);

		// Inline item search ---------------------------------------------------
		const itemSearchSelection = ref(null);
		const itemSearchResults = ref([]);
		const itemSearchLoading = ref(false);
		const itemSearchTimeout = ref(null);

		const supplierSearchTimeout = ref(null);

		const handleSupplierSearch = (term) => {
			if (supplierSearchTimeout.value)
				clearTimeout(supplierSearchTimeout.value);
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
						"posawesome.mizan.api.purchase_orders.search_suppliers",
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

		const loadCostCenters = async () => {
			costCenterLoading.value = true;
			try {
				const { message } = await frappe.call({
					method: "frappe.client.get_list",
					args: {
						doctype: "Cost Center",
						fields: ["name", "cost_center_name"],
						filters: {
							company: pos_profile.value.company,
							is_group: 0,
							disabled: 0,
						},
						limit_page_length: 500,
						order_by: "cost_center_name asc",
					},
				});
				costCenterOptions.value = message || [];
			} catch (error) {
				console.error("Failed to load cost centers:", error);
			} finally {
				costCenterLoading.value = false;
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

		// Inline item search ---------------------------------------------------
		const handleItemSearch = (term) => {
			if (itemSearchTimeout.value) clearTimeout(itemSearchTimeout.value);
			itemSearchTimeout.value = setTimeout(() => searchItems(term), 250);
		};

		const searchItems = async (searchText = "") => {
			if (!searchText || searchText.trim().length < 1) {
				itemSearchResults.value = [];
				return;
			}
			itemSearchLoading.value = true;
			try {
				const { message } = await frappe.call({
					method: "posawesome.mizan.api.purchase_orders.search_items",
					args: { search_text: searchText, limit: 20 },
				});
				itemSearchResults.value = Array.isArray(message) ? message : [];
			} catch (error) {
				console.error("Failed to search items:", error);
				itemSearchResults.value = [];
			} finally {
				itemSearchLoading.value = false;
			}
		};

		const onItemSelected = async (selected) => {
			if (!selected) return;
			await onAddItem(selected);
			itemSearchSelection.value = null;
			itemSearchResults.value = [];
		};

		const formatDateForBackend = (date) => {
			if (!date) return null;
			const western = formatUtils.fromArabicNumerals(String(date));
			if (/^\d{4}-\d{2}-\d{2}$/.test(western)) return western;
			const m = western.match(/^(\d{2})-(\d{2})-(\d{4})$/);
			if (m) return `${m[3]}-${m[2]}-${m[1]}`;
			const d = new Date(western);
			if (isNaN(d.getTime())) return western;
			return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
		};

		const onSubmit = async () => {
			try {
				postingDate.value = postingDate.value
					? formatDateForBackend(postingDate.value)
					: null;
				const result = await submitInvoice();
				if (result?.purchase_invoice) {
					toastStore.show({
						title: __("Purchase Invoice {0} created", [
							result.purchase_invoice,
						]),
						color: "success",
					});
					pendingLabels.value = Array.isArray(result.labels)
						? result.labels
						: [];
					if (pendingLabels.value.length) {
						labelDialog.value = true;
					} else {
						resetForm();
					}
				}
			} catch (error) {
				const msg =
					error?.message ||
					error?.responseJSON?.message ||
					__("Unable to create purchase invoice");
				errorMessage.value = msg;
				toastStore.show({ title: msg, color: "error" });
			}
		};

		const onLabelDialogClose = () => {
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
					await fetchSupplierInfo(val);
				} else {
					supplierCurrency.value = pos_profile.value.currency || null;
					supplierPriceList.value = null;
					priceListCurrency.value = null;
				}
			});

			try {
				const { message } = await frappe.call({
					method:
						"posawesome.mizan.api.purchase_orders.get_buying_price_list",
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
				loadCostCenters(),
			]);
		});

		return {
			pos_profile,
			invoiceItems,
			supplier,
			warehouse,
			costCenter,
			postingDate,
			billNo,
			supplierCurrency,
			supplierPriceList,
			priceListCurrency,
			updatePriceList,
			totalAmount,
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
			supplierOptions,
			supplierLoading,
			supplierDialog,
			supplierGroups,
			warehouseOptions,
			warehouseLoading,
			costCenterOptions,
			costCenterLoading,
			labelDialog,
			pendingLabels,
			handleSupplierSearch,
			handleSupplierCreated,
			onUpdateSerial,
			onSetBatchExpiry,
			onSubmit,
			onLabelDialogClose,
			toastStore,
			itemSearchSelection,
			itemSearchResults,
			itemSearchLoading,
			handleItemSearch,
			onItemSelected,
		};
	},
	computed: {
		allowCreateSupplier() {
			return !!this.pos_profile?.posa_allow_create_purchase_suppliers;
		},
		anyItemHasBatch() {
			return this.invoiceItems.some((row) => row.has_batch_no);
		},
		anyItemHasSerial() {
			return this.invoiceItems.some((row) => row.has_serial_no);
		},
		itemHeaders() {
			const headers = [
				{ title: __("Item"), key: "item_name", align: "start", width: "20%" },
				{ title: __("UOM"), key: "uom", align: "center", width: "9%" },
			];
			if (this.anyItemHasBatch) {
				headers.push({
					title: __("Batch / Expiry"),
					key: "batch",
					align: "start",
					width: "22%",
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
				{
					title: __("Disc %"),
					key: "discount_percentage",
					align: "center",
					width: "8%",
				},
				{ title: __("Amount"), key: "amount", align: "end", width: "10%" },
				{
					title: "",
					key: "actions",
					align: "center",
					width: "50px",
					sortable: false,
				},
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

.pi-shell {
	background: var(--pos-surface-bg, #0a0e17);
}

.purchase-invoice-card {
	background: var(--pos-card-bg, #0e131e) !important;
	border: 1px solid rgba(139, 92, 246, 0.18);
	border-radius: 14px !important;
	font-family: var(--posa-font-family, "Space Grotesk", sans-serif);
	color: var(--pos-text-primary, #e7ebf3);
	overflow: hidden;
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

/* Form metadata grid: supplier | warehouse | cost center | posting date */
.pi-form-grid {
	display: grid;
	grid-template-columns: repeat(4, minmax(0, 1fr));
	gap: 12px;
	margin-bottom: 8px;
}
@media (max-width: 1280px) {
	.pi-form-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
}
@media (max-width: 700px) {
	.pi-form-grid {
		grid-template-columns: 1fr;
	}
}

.pi-form-field {
	min-width: 0;
}

.pi-bill-row {
	margin-top: 10px;
}

.pi-field-icon {
	color: #c4b5fd !important;
	margin-right: 6px;
}
.pi-field-add {
	color: #c4b5fd !important;
	transition: transform 0.18s ease, color 0.18s ease;
}
.pi-field-add:hover {
	color: #fb7185 !important;
	transform: scale(1.1);
}

/* Themed field — purple/pink border + glow on focus */
.pi-themed-field :deep(.v-field) {
	border-radius: 10px !important;
	background: rgba(139, 92, 246, 0.05) !important;
	transition: border-color 0.18s ease, box-shadow 0.18s ease,
		background-color 0.18s ease;
}
.pi-themed-field :deep(.v-field__outline__start),
.pi-themed-field :deep(.v-field__outline__end),
.pi-themed-field :deep(.v-field__outline__notch::before),
.pi-themed-field :deep(.v-field__outline__notch::after) {
	border-color: rgba(139, 92, 246, 0.32) !important;
}
.pi-themed-field :deep(.v-field--focused) {
	background: rgba(139, 92, 246, 0.10) !important;
	box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.22) !important;
}
.pi-themed-field :deep(.v-field--focused .v-field__outline__start),
.pi-themed-field :deep(.v-field--focused .v-field__outline__end),
.pi-themed-field :deep(.v-field--focused .v-field__outline__notch::before),
.pi-themed-field :deep(.v-field--focused .v-field__outline__notch::after) {
	border-color: #e23670 !important;
}
.pi-themed-field :deep(.v-label) {
	color: rgba(231, 235, 243, 0.7) !important;
}
.pi-themed-field :deep(.v-field--focused .v-label) {
	color: #f5d0fe !important;
}

/* Posting Date wrapper to give it the same chrome */
.pi-date-wrap {
	display: flex;
	align-items: center;
	gap: 6px;
	padding: 4px 10px;
	border-radius: 10px;
	background: rgba(139, 92, 246, 0.05);
	border: 1px solid rgba(139, 92, 246, 0.32);
	min-height: 40px;
	transition: border-color 0.18s ease, box-shadow 0.18s ease,
		background-color 0.18s ease;
}
.pi-date-wrap:focus-within {
	background: rgba(139, 92, 246, 0.10);
	border-color: #e23670;
	box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.22);
}
.pi-date-icon {
	margin-right: 0;
}
.pi-date-picker {
	flex: 1;
	min-width: 0;
}
.pi-date-picker :deep(.dp__input) {
	border: none !important;
	background: transparent !important;
	color: var(--pos-text-primary, #e7ebf3) !important;
	font-family: var(--posa-font-family, "Space Grotesk", sans-serif);
	font-size: 0.875rem;
	padding-left: 4px !important;
}
.pi-date-picker :deep(.dp__input_icon),
.pi-date-picker :deep(.dp__input_icon_pad) {
	display: none !important;
	padding-left: 0 !important;
}
.pi-date-picker :deep(.dp__input:focus) {
	box-shadow: none !important;
	outline: none !important;
}

/* Buying-price-list pill */
.pi-meta-row {
	display: flex;
	gap: 8px;
	flex-wrap: wrap;
	margin-top: 4px;
}
.pi-meta-pill {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	font-size: 0.72rem;
	color: #f5d0fe;
	background: rgba(139, 92, 246, 0.12);
	border: 1px solid rgba(139, 92, 246, 0.28);
	padding: 4px 10px;
	border-radius: 999px;
}
.pi-meta-pill--muted {
	color: rgba(231, 235, 243, 0.6);
	background: rgba(255, 255, 255, 0.03);
	border-color: rgba(255, 255, 255, 0.08);
}

.purchase-invoice-divider {
	border-color: rgba(139, 92, 246, 0.18) !important;
	opacity: 1 !important;
}

.pi-search-bar {
	margin-bottom: 12px;
}
.pi-search-bar__input :deep(.v-field) {
	border-radius: 12px !important;
	background: linear-gradient(
		180deg,
		rgba(139, 92, 246, 0.10),
		rgba(226, 54, 112, 0.06)
	) !important;
	border: 1px solid rgba(139, 92, 246, 0.32) !important;
}
.pi-search-bar__input :deep(.v-field--focused) {
	background: linear-gradient(
		180deg,
		rgba(139, 92, 246, 0.18),
		rgba(226, 54, 112, 0.10)
	) !important;
	border-color: #e23670 !important;
	box-shadow: 0 0 0 3px rgba(226, 54, 112, 0.22) !important;
}
.pi-search-bar__rate {
	font-size: 0.72rem;
	color: #c4b5fd;
	font-weight: 600;
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
</style>
