<template>
	<component
		:is="rootElement"
		v-bind="rootAttrs"
		class="ma-0 pa-0 posa-expanded-row-cell"
		:class="{ 'posa-expanded-row-cell--bare': renderAs !== 'td' }"
	>
		<div
			v-if="isExpanded"
			class="posa-cc-form responsive-expanded-content"
			:class="expandedContentClasses"
		>
			<!-- Identity strip: SKU, Barcode, Stock status, ERPNext link -->
			<div class="posa-cc-identity">
				<div class="posa-cc-identity__pills">
					<span class="posa-cc-pill" :title="__('Item Code')">
						<v-icon size="12">mdi-barcode</v-icon>
						<span class="posa-cc-pill__label">{{ __("SKU") }}</span>
						<strong class="posa-cc-pill__value">{{ item.item_code }}</strong>
					</span>
					<span v-if="primaryBarcode" class="posa-cc-pill" :title="__('Barcode')">
						<v-icon size="12">mdi-barcode-scan</v-icon>
						<span class="posa-cc-pill__label">{{ __("Barcode") }}</span>
						<strong class="posa-cc-pill__value">{{ primaryBarcode }}</strong>
					</span>
					<span class="posa-cc-status" :class="`posa-cc-status--${stockStatus.tone}`">
						<span class="posa-cc-status__dot" />
						{{ stockStatus.label }}
					</span>
				</div>
				<a
					v-if="erpUrl"
					:href="erpUrl"
					target="_blank"
					rel="noopener"
					class="posa-cc-erp-link"
				>
					{{ __("Open in ERPNext") }}
					<v-icon size="14">mdi-arrow-top-right</v-icon>
				</a>
			</div>

			<!-- EDIT row: only the inputs that actually mutate the line -->
			<div class="posa-cc-section">
				<span class="posa-cc-eyebrow">{{ __("Edit") }}</span>
				<div class="posa-cc-edit-grid">
					<div class="posa-cc-field">
						<label class="posa-cc-field__label">{{ __("QTY") }}</label>
						<v-text-field
							density="compact"
							variant="outlined"
							hide-details
							class="pos-themed-input posa-cc-input"
							:model-value="formatFloat(item.qty, hide_qty_decimals ? 0 : undefined)"
							@change="onQtyChange(item, $event)"
							:rules="[isNumber]"
							:disabled="!!item.posa_is_replace"
						/>
					</div>
					<div class="posa-cc-field">
						<label class="posa-cc-field__label">{{ __("UOM") }}</label>
						<v-select
							density="compact"
							variant="outlined"
							hide-details
							class="pos-themed-input posa-cc-input"
							v-model="item.uom"
							:items="item.item_uoms"
							item-title="uom"
							item-value="uom"
							@update:model-value="calcUom(item, $event)"
							:disabled="!!item.posa_is_replace || (isReturnInvoice && invoice_doc.return_against)"
						/>
					</div>
					<div class="posa-cc-field">
						<label class="posa-cc-field__label">
							{{ __("Rate") }}
							<v-icon
								v-if="canChangeListRate"
								size="11"
								class="posa-cc-field__hint-icon"
								:title="__('Click to change list price')"
							>
								mdi-pencil-outline
							</v-icon>
						</label>
						<v-text-field
							density="compact"
							variant="outlined"
							hide-details
							class="pos-themed-input posa-cc-input"
							:class="{ 'posa-cc-input--clickable': canChangeListRate }"
							:model-value="formatCurrency(item.rate)"
							@change="[
								setFormatedCurrency(item, 'rate', null, false, $event),
								calcPrices(item, $event.target.value, $event),
							]"
							@click="onRateClick"
							:disabled="!canEditRate"
						/>
					</div>
					<div class="posa-cc-field">
						<label class="posa-cc-field__label">{{ __("Disc %") }}</label>
						<v-text-field
							density="compact"
							variant="outlined"
							hide-details
							class="pos-themed-input posa-cc-input"
							:model-value="formatFloat(Math.abs(item.discount_percentage || 0))"
							@change="[
								setFormatedCurrency(item, 'discount_percentage', null, false, $event),
								calcPrices(item, $event.target.value, $event),
							]"
							:disabled="!canEditDiscount"
						/>
					</div>
					<div class="posa-cc-field">
						<label class="posa-cc-field__label">
							{{ __("Disc") }} {{ currencyCode }}
						</label>
						<v-text-field
							density="compact"
							variant="outlined"
							hide-details
							class="pos-themed-input posa-cc-input"
							:model-value="formatCurrency(Math.abs(item.discount_amount || 0))"
							@change="[
								setFormatedCurrency(item, 'discount_amount', null, false, $event),
								calcPrices(item, $event.target.value, $event),
							]"
							:disabled="!canEditDiscount"
						/>
					</div>
				</div>
			</div>

			<!-- AT A GLANCE: read-only metric tiles -->
			<div class="posa-cc-section">
				<span class="posa-cc-eyebrow">{{ __("At a glance") }}</span>
				<div class="posa-cc-tiles">
					<div
						class="posa-cc-tile"
						:title="__('Available stock in your POS warehouse')"
					>
						<span class="posa-cc-tile__label">{{ __("In Stock") }}</span>
						<span class="posa-cc-tile__value">{{ formatFloat(item._base_actual_qty) }}</span>
						<span class="posa-cc-tile__unit">{{ item.stock_uom }}</span>
					</div>
					<div class="posa-cc-tile" :title="__('Catalog price (price list rate)')">
						<span class="posa-cc-tile__label">{{ __("List Price") }}</span>
						<span class="posa-cc-tile__value">{{ formatCurrency(item.price_list_rate ?? 0) }}</span>
						<span class="posa-cc-tile__unit">{{ currencyCode }}</span>
					</div>
					<div class="posa-cc-tile" :title="__('Line total — qty × rate after discount')">
						<span class="posa-cc-tile__label">{{ __("Line Total") }}</span>
						<span class="posa-cc-tile__value">{{ formatCurrency(item.amount ?? item.qty * item.rate) }}</span>
						<span class="posa-cc-tile__unit">{{ currencyCode }}</span>
					</div>
				</div>
			</div>

			<!-- Batches: always visible for batched items -->
			<div v-if="item.has_batch_no || item.batch_no" class="posa-cc-section">
				<span class="posa-cc-eyebrow">{{ __("Batch") }}</span>
				<div class="posa-cc-batch-grid">
					<div class="posa-cc-field posa-cc-field--wide">
						<label class="posa-cc-field__label">{{ __("Batch No") }}</label>
						<v-autocomplete
							v-model="item.batch_no"
							:items="getBatchOptions(item)"
							item-title="batch_no"
							variant="outlined"
							density="compact"
							hide-details
							class="pos-themed-input posa-cc-input"
							@update:model-value="setBatchQty(item, $event)"
						>
							<template v-slot:item="{ props, item }">
								<v-list-item v-bind="props">
									<v-list-item-title v-html="getRaw(item).batch_no" />
									<v-list-item-subtitle class="d-flex align-center">
										<span
											v-html="
												`Available QTY '${
													getRaw(item).available_qty ?? getRaw(item).batch_qty
												}' — Expiry ${getRaw(item).expiry_date}`
											"
										/>
										<v-chip
											v-if="getRaw(item).is_expired"
											color="error"
											size="x-small"
											variant="flat"
											class="ml-2"
										>
											{{ __("Expired") }}
										</v-chip>
									</v-list-item-subtitle>
								</v-list-item>
							</template>
						</v-autocomplete>
					</div>
					<div class="posa-cc-tile posa-cc-tile--inline">
						<span class="posa-cc-tile__label">{{ __("Batch Avail.") }}</span>
						<span class="posa-cc-tile__value">{{ formatFloat(item.actual_batch_qty) }}</span>
					</div>
					<div class="posa-cc-tile posa-cc-tile--inline">
						<span class="posa-cc-tile__label">{{ __("Expiry") }}</span>
						<span class="posa-cc-tile__value posa-cc-tile__value--text">
							{{ item.batch_no_expiry_date || "—" }}
						</span>
					</div>
				</div>
			</div>

			<!-- Serial Numbers: always visible for serialized items -->
			<div v-if="item.has_serial_no || item.serial_no" class="posa-cc-section">
				<span class="posa-cc-eyebrow">
					{{ __("Serial Numbers") }}
					<span class="posa-cc-eyebrow__count">{{ item.serial_no_selected_count || 0 }}</span>
				</span>
				<v-autocomplete
					v-model="item.serial_no_selected"
					:items="getSerialOptions(item)"
					item-title="serial_no"
					item-value="serial_no"
					variant="outlined"
					density="compact"
					chips
					hide-details
					class="pos-themed-input posa-cc-input"
					multiple
					@update:model-value="setSerialNo(item)"
				/>
			</div>

			<!-- Delivery Date: only for SO / Quotation -->
			<div
				v-if="
					pos_profile.posa_allow_sales_order &&
					['Order', 'Quotation'].includes(invoiceType || '')
				"
				class="posa-cc-section"
			>
				<span class="posa-cc-eyebrow">{{ __("Delivery") }}</span>
				<VueDatePicker
					v-model="item.posa_delivery_date"
					model-type="format"
					format="dd-MM-yyyy"
					:min-date="new Date()"
					auto-apply
					@update:model-value="validateDueDate(item)"
				/>
			</div>

			<!-- Offer applied indicator -->
			<div v-if="item.posa_offer_applied" class="posa-cc-offer-flag">
				<v-icon size="14" color="success">mdi-tag-check</v-icon>
				<span>{{ __("Offer applied") }}</span>
			</div>
		</div>
		<!-- Lazy placeholder -->
		<div v-else class="expanded-placeholder">
			<div class="text-center pa-4">
				<v-progress-circular indeterminate size="small" />
				<div class="text-caption mt-2">{{ __("Loading details...") }}</div>
			</div>
		</div>
	</component>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { getDisplayableBatchOptions } from "../../../composables/pos/shared/useBatchSerial";
import type { CartItem, POSProfile, InvoiceDoc } from "../../../types/models";

interface Props {
	item: CartItem | any;
	isExpanded: boolean;
	colspan?: number;
	renderAs?: "td" | "div";
	pos_profile: POSProfile | any;
	invoiceType?: string;
	isReturnInvoice?: boolean;
	invoice_doc?: InvoiceDoc | any;
	hide_qty_decimals: boolean;
	expandedContentClasses: any;

	// Formatters
	formatFloat: (_val: any, _precision?: number) => string;
	formatCurrency: (_val: any, _precision?: number) => string;
	currencySymbol: (_currency?: string) => string;
	isNumber: (_val: any) => boolean | string;

	// Actions
	setFormatedCurrency: (_item: any, _field: string, _value: any, _force?: boolean, _event?: any) => void;
	calcPrices: (_item: any, _value: any, _event?: any) => void;
	calcUom: (_item: any, _uom: string) => void;
	changePriceListRate: (_item: any) => void;
	getSerialOptions: (_item: any) => any[];
	setSerialNo: (_item: any) => void;
	setBatchQty: (_item: any, _event: any) => void;
	validateDueDate: (_item: any) => void;
}

const props = withDefaults(defineProps<Props>(), {
	renderAs: "td",
	colspan: 1,
});

const rootElement = computed(() => (props.renderAs === "div" ? "div" : "td"));
const rootAttrs = computed(() =>
	props.renderAs === "td" ? { colspan: props.colspan } : {},
);

const emit = defineEmits<{
	"qty-change": [item: CartItem, event: any];
}>();

const __ = (window as any).__ || ((s: string) => s);

const onQtyChange = (item: CartItem, event: any) => {
	emit("qty-change", item, event);
};

const getRaw = (item: any) => item?.raw || {};
const getBatchOptions = (item: any) =>
	getDisplayableBatchOptions(item?.batch_no_data);

const currencyCode = computed(
	() => props.pos_profile?.currency || props.invoice_doc?.currency || "",
);

const primaryBarcode = computed(() => {
	const i = props.item || {};
	return (
		i.barcode ||
		i.posa_primary_barcode ||
		(Array.isArray(i.item_barcode) && i.item_barcode[0]?.barcode) ||
		""
	);
});

const stockStatus = computed(() => {
	const qty = Number(props.item?._base_actual_qty ?? 0);
	if (qty > 0) return { tone: "in", label: __("In Stock") };
	if (qty === 0) return { tone: "out", label: __("Out of Stock") };
	return { tone: "neg", label: __("Negative") };
});

const erpUrl = computed(() => {
	const code = props.item?.item_code;
	return code ? `/app/item/${encodeURIComponent(code)}` : "";
});

const canEditRate = computed(
	() => props.pos_profile?.posa_allow_user_to_edit_rate && !props.item?.posa_is_replace,
);

const canChangeListRate = computed(
	() => !!props.pos_profile?.posa_allow_price_list_rate_change,
);

const canEditDiscount = computed(
	() =>
		props.pos_profile?.posa_allow_user_to_edit_item_discount &&
		!props.item?.posa_is_replace &&
		!props.item?.posa_offer_applied,
);

const onRateClick = () => {
	if (canChangeListRate.value) {
		props.changePriceListRate(props.item);
	}
};
</script>

<style scoped>
.posa-expanded-row-cell--bare {
	display: block;
	width: 100%;
}

/* ── Command-center compact form ────────────────────────────── */
.posa-cc-form {
	display: flex;
	flex-direction: column;
	gap: 14px;
	padding: 4px 2px 8px;
}

/* Identity strip */
.posa-cc-identity {
	display: flex;
	align-items: center;
	justify-content: space-between;
	flex-wrap: wrap;
	gap: 8px;
}

.posa-cc-identity__pills {
	display: flex;
	flex-wrap: wrap;
	align-items: center;
	gap: 6px;
}

.posa-cc-pill {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	padding: 4px 10px;
	border-radius: 999px;
	background: var(--pos-surface-muted, rgba(148, 163, 184, 0.1));
	border: 1px solid var(--pos-border-light, rgba(148, 163, 184, 0.2));
	font-size: 0.74rem;
	color: var(--pos-text-secondary);
	line-height: 1.1;
}

.posa-cc-pill__label {
	text-transform: uppercase;
	letter-spacing: 0.04em;
	font-weight: 600;
	opacity: 0.75;
}

.posa-cc-pill__value {
	font-weight: 700;
	color: var(--pos-text-primary);
	font-variant-numeric: tabular-nums;
}

.posa-cc-status {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	padding: 4px 10px;
	border-radius: 999px;
	font-size: 0.74rem;
	font-weight: 600;
	border: 1px solid currentColor;
	background: rgba(0, 0, 0, 0);
}

.posa-cc-status__dot {
	width: 6px;
	height: 6px;
	border-radius: 50%;
	background: currentColor;
}

.posa-cc-status--in {
	color: #22c55e;
}

.posa-cc-status--out {
	color: #f59e0b;
}

.posa-cc-status--neg {
	color: #ef4444;
}

.posa-cc-erp-link {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	font-size: 0.78rem;
	font-weight: 600;
	color: var(--pos-primary);
	text-decoration: none;
}

.posa-cc-erp-link:hover {
	text-decoration: underline;
}

/* Sections */
.posa-cc-section {
	display: flex;
	flex-direction: column;
	gap: 6px;
}

.posa-cc-eyebrow {
	display: inline-flex;
	align-items: center;
	gap: 8px;
	font-size: 0.66rem;
	font-weight: 700;
	letter-spacing: 0.12em;
	text-transform: uppercase;
	color: var(--pos-text-secondary);
	opacity: 0.85;
}

.posa-cc-eyebrow__count {
	background: var(--pos-primary-container, rgba(0, 151, 167, 0.15));
	color: var(--pos-primary);
	padding: 1px 8px;
	border-radius: 999px;
	font-size: 0.7rem;
	letter-spacing: 0;
}

/* Edit grid: 5 inputs in one row, wraps gracefully */
.posa-cc-edit-grid {
	display: grid;
	grid-template-columns: repeat(5, minmax(0, 1fr));
	gap: 8px;
}

.posa-cc-batch-grid {
	display: grid;
	grid-template-columns: minmax(220px, 2fr) 1fr 1fr;
	gap: 8px;
	align-items: end;
}

.posa-cc-field {
	display: flex;
	flex-direction: column;
	gap: 2px;
	min-width: 0;
}

.posa-cc-field--wide {
	grid-column: 1 / -1;
}

.posa-cc-field__label {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	font-size: 0.66rem;
	font-weight: 700;
	letter-spacing: 0.06em;
	text-transform: uppercase;
	color: var(--pos-text-secondary);
}

.posa-cc-field__hint-icon {
	opacity: 0.7;
}

/* Compact input override — kills the 56px Vuetify default */
.posa-cc-input :deep(.v-field) {
	min-height: 36px;
	border-radius: 8px;
	font-size: 0.88rem;
	font-variant-numeric: tabular-nums;
}

.posa-cc-input :deep(.v-field__field) {
	min-height: 36px;
}

.posa-cc-input :deep(.v-field__input) {
	padding: 6px 10px;
	min-height: 36px;
	font-weight: 600;
}

.posa-cc-input :deep(.v-field__append-inner) {
	padding-top: 6px;
}

.posa-cc-input--clickable :deep(.v-field) {
	cursor: pointer;
}

/* Tiles */
.posa-cc-tiles {
	display: grid;
	grid-template-columns: repeat(3, minmax(0, 1fr));
	gap: 8px;
}

.posa-cc-tile {
	display: flex;
	flex-direction: column;
	gap: 2px;
	padding: 8px 10px;
	border-radius: 10px;
	background: var(--pos-surface-muted, rgba(148, 163, 184, 0.08));
	border: 1px solid var(--pos-border-light, rgba(148, 163, 184, 0.16));
	min-width: 0;
}

.posa-cc-tile--inline {
	min-height: 56px;
}

.posa-cc-tile__label {
	font-size: 0.62rem;
	font-weight: 700;
	letter-spacing: 0.08em;
	text-transform: uppercase;
	color: var(--pos-text-secondary);
	opacity: 0.85;
}

.posa-cc-tile__value {
	font-size: 1.05rem;
	font-weight: 700;
	color: var(--pos-text-primary);
	font-variant-numeric: tabular-nums;
	line-height: 1.15;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.posa-cc-tile__value--text {
	font-size: 0.86rem;
	font-weight: 600;
	font-variant-numeric: normal;
}

.posa-cc-tile__unit {
	font-size: 0.62rem;
	color: var(--pos-text-secondary);
	opacity: 0.85;
}

/* Offer flag */
.posa-cc-offer-flag {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	padding: 4px 10px;
	border-radius: 999px;
	background: rgba(34, 197, 94, 0.12);
	color: #22c55e;
	font-size: 0.78rem;
	font-weight: 600;
	width: fit-content;
}

/* Responsive: edit grid wraps, tiles stay readable */
@media (max-width: 900px) {
	.posa-cc-edit-grid {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}
	.posa-cc-batch-grid {
		grid-template-columns: 1fr 1fr;
	}
}

@media (max-width: 560px) {
	.posa-cc-tiles {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
	.posa-cc-edit-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
	.posa-cc-batch-grid {
		grid-template-columns: 1fr;
	}
}
</style>
