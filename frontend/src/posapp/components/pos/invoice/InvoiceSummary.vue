<template>
	<v-card
		class="cards sticky-summary-card mb-0 py-1 px-2 rounded-lg pos-themed-card"
		:class="{ 'sticky-summary-card--dock-safe': useCompactSaleDock }"
	>
		<v-alert
			v-if="showReturnDiscountAlert"
			density="compact"
			type="info"
			variant="tonal"
			class="summary-field summary-field--alert"
		>
			{{ __("Prorated return discount") }}:
			{{ formatRatio(return_discount_meta.ratio) }} -
			{{ __("Original") }}:
			{{ formatCurrency(return_discount_meta.original_discount) }},
			{{ __("Applied") }}:
			{{ formatCurrency(return_discount_meta.prorated_discount) }}
		</v-alert>

		<div
			v-if="!useCompactSaleDock"
			class="summary-hero summary-hero--top"
			:class="{ 'summary-hero--active': hasActiveSaleValue }"
		>
			<div class="summary-hero__copy">
				<span class="summary-hero__eyebrow">{{ __("Active sale") }}</span>
				<strong class="summary-hero__amount">
					<span class="summary-hero__currency">{{ currencySymbol(displayCurrency) }}</span>
					<span class="summary-hero__number">{{ formatCurrency(subtotal) }}</span>
				</strong>
				<div class="summary-hero__meta">
					<span>{{ formatFloat(total_qty, hide_qty_decimals ? 0 : undefined) }} {{ __("qty") }}</span>
					<span>
						{{ currencySymbol(displayCurrency) }} {{ formatCurrency(combinedDiscountAmount) }}
						{{ __("discount") }}
					</span>
				</div>
			</div>

			<div class="summary-hero__field-wrap">
				<v-text-field
					v-if="!pos_profile.posa_use_percentage_discount"
					ref="additionalDiscountField"
					v-model="additionalDiscountDisplay"
					@update:model-value="handleAdditionalDiscountUpdate"
					@focus="handleAdditionalDiscountFocus"
					@blur="handleAdditionalDiscountBlur"
					:label="frappe._('Additional Discount')"
					prepend-inner-icon="mdi-cash-minus"
					variant="outlined"
					density="compact"
					color="primary"
					hide-details
					:prefix="currencySymbol(pos_profile.currency)"
					:disabled="
						!pos_profile.posa_allow_user_to_edit_additional_discount ||
						!!discount_percentage_offer_name
					"
					class="summary-field summary-field--pill"
				/>

				<v-text-field
					v-else
					ref="additionalDiscountField"
					v-model="additionalDiscountPercentageDisplay"
					@update:model-value="handleAdditionalDiscountPercentageUpdate"
					@change="$emit('update_discount_umount')"
					@focus="handleAdditionalDiscountPercentageFocus"
					@blur="handleAdditionalDiscountPercentageBlur"
					:rules="[isNumber]"
					:label="frappe._('Additional Discount %')"
					suffix="%"
					prepend-inner-icon="mdi-percent"
					variant="outlined"
					density="compact"
					color="primary"
					hide-details
					:disabled="
						!pos_profile.posa_allow_user_to_edit_additional_discount ||
						!!discount_percentage_offer_name
					"
					class="summary-field summary-field--pill"
				/>
			</div>
		</div>

		<div class="summary-actions-block">
			<InvoiceActionButtons
				:pos_profile="pos_profile"
				:saveLoading="saveLoading"
				:loadDraftsLoading="loadDraftsLoading"
				:selectOrderLoading="selectOrderLoading"
				:selectPurchaseOrderLoading="selectPurchaseOrderLoading"
				:cancelLoading="cancelLoading"
				:invoiceManagementLoading="invoiceManagementLoading"
				:returnsLoading="returnsLoading"
				:printLoading="printLoading"
				:paymentLoading="paymentLoading"
				:customerDisplayLoading="customerDisplayLoading"
				@save-and-clear="handleSaveAndClear"
				@load-drafts="handleLoadDrafts"
				@select-order="handleSelectOrder"
				@cancel-sale="handleCancelSale"
				@open-invoice-management="handleOpenInvoiceManagement"
				@open-returns="handleOpenReturns"
				@print-draft="handlePrintDraft"
				@show-payment="handleShowPayment"
				@open-customer-display="handleOpenCustomerDisplay"
			/>
		</div>
	</v-card>

	<v-navigation-drawer
		v-if="showDesktopDrafts && allDrafts.length"
		v-model="desktopDraftsDrawer"
		location="right"
		temporary
		width="360"
		class="drafts-drawer"
	>
		<div class="drafts-drawer__body">
			<ParkedOrdersList
				:parked-orders="allDrafts"
				:format-currency="formatCurrency"
				:currency-symbol="currencySymbol"
				:show-manage-all="true"
				@resume="handleResumeDraft"
				@manage-all="handleManageAllDrafts"
			/>
		</div>
	</v-navigation-drawer>

	<v-dialog
		v-else-if="allDrafts.length"
		v-model="mobileDraftsDialog"
		max-width="680"
		scrollable
		data-test="mobile-drafts-dialog"
	>
		<v-card class="pos-themed-card">
			<v-card-title class="d-flex align-center justify-space-between">
				<span>{{ __("Drafts") }}</span>
				<v-btn variant="text" size="small" @click="mobileDraftsDialog = false">
					{{ __("Close") }}
				</v-btn>
			</v-card-title>
			<v-card-text class="pt-0">
				<ParkedOrdersList
					:parked-orders="allDrafts"
					:format-currency="formatCurrency"
					:currency-symbol="currencySymbol"
					:show-manage-all="true"
					@resume="handleResumeDraft"
					@manage-all="handleManageAllDrafts"
				/>
			</v-card-text>
		</v-card>
	</v-dialog>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { loadItemSelectorSettings } from "../../../utils/itemSelectorSettings";
import { useResponsive } from "../../../composables/core/useResponsive";
import { useUIStore } from "../../../stores/uiStore";
import InvoiceActionButtons from "./InvoiceActionButtons.vue";
import ParkedOrdersList from "./ParkedOrdersList.vue";

defineOptions({
	name: "InvoiceSummary",
});

const props = defineProps({
	pos_profile: Object,
	total_qty: [Number, String],
	additional_discount: Number,
	additional_discount_percentage: Number,
	total_items_discount_amount: Number,
	subtotal: Number,
	displayCurrency: String,
	formatFloat: Function,
	formatCurrency: Function,
	currencySymbol: Function,
	discount_percentage_offer_name: [String, Number],
	isNumber: Function,
	return_discount_meta: Object,
});

const emit = defineEmits([
	"update:additional_discount",
	"update:additional_discount_percentage",
	"update_discount_umount",
	"save-and-clear",
	"load-drafts",
	"select-order",
	"cancel-sale",
	"open-invoice-management",
	"open-returns",
	"print-draft",
	"show-payment",
	"open-customer-display",
	"resume-parked-order",
]);

const saveLoading = ref(false);
const loadDraftsLoading = ref(false);
const selectOrderLoading = ref(false);
const cancelLoading = ref(false);
const invoiceManagementLoading = ref(false);
const returnsLoading = ref(false);
const printLoading = ref(false);
const paymentLoading = ref(false);
const customerDisplayLoading = ref(false);
const isEditingAdditionalDiscount = ref(false);
const isEditingAdditionalDiscountPercentage = ref(false);
const additionalDiscountField = ref(null);
const desktopDraftsDrawer = ref(false);
const mobileDraftsDialog = ref(false);
const responsive = useResponsive();
const uiStore = useUIStore();
const { parkedOrders } = storeToRefs(uiStore);

const additionalDiscountDisplay = ref(normalizeDiscountDisplay(props.additional_discount));
const additionalDiscountPercentageDisplay = ref(
	normalizeDiscountDisplay(props.additional_discount_percentage),
);
const useCompactSaleDock = computed(() => responsive.windowWidth.value < 1100);
// Drives the pink glowing ring on the Active Sale hero. Subtotal is the
// source of truth so the ring lights up as soon as any item is in the
// cart and fades the moment the cart is cleared.
const hasActiveSaleValue = computed(() => {
	const n = Number(props.subtotal);
	return Number.isFinite(n) && Math.abs(n) > 0;
});

// "KWD X discount" line under the Active Sale hero — combines per-item
// discounts (`total_items_discount_amount`) with the invoice-level
// additional discount so the cashier sees the full reduction at a
// glance. Previously only line-level discounts were shown, so typing
// "5%" in the additional-discount pill left the meta line stuck at
// "KWD 0.000 discount" while the subtotal had clearly dropped.
const combinedDiscountAmount = computed(() => {
	const items = Number(props.total_items_discount_amount) || 0;
	const additional = Math.abs(Number(props.additional_discount) || 0);
	return items + additional;
});
const showDesktopDrafts = computed(() => Boolean(responsive.isDesktop.value));
const showReturnDiscountAlert = computed(
	() =>
		!!props.return_discount_meta &&
		!props.pos_profile?.posa_use_percentage_discount &&
		!isFullReturnDiscount(props.return_discount_meta?.ratio),
);
const allDrafts = computed(() => (Array.isArray(parkedOrders.value) ? parkedOrders.value : []));

const hide_qty_decimals = computed(() => {
	const opts = loadItemSelectorSettings();
	return !!opts?.hide_qty_decimals;
});

watch(
	() => props.additional_discount,
	(value) => {
		if (!isEditingAdditionalDiscount.value) {
			additionalDiscountDisplay.value = normalizeDiscountDisplay(value);
		}
	},
);

watch(
	() => props.additional_discount_percentage,
	(value) => {
		if (!isEditingAdditionalDiscountPercentage.value) {
			additionalDiscountPercentageDisplay.value = normalizeDiscountDisplay(value);
		}
	},
);

function normalizeDiscountDisplay(value) {
	if (value === 0 || value === "0") {
		return "";
	}
	return value;
}

function handleAdditionalDiscountUpdate(value) {
	emit("update:additional_discount", value);
}

function handleAdditionalDiscountFocus() {
	isEditingAdditionalDiscount.value = true;
}

function handleAdditionalDiscountBlur() {
	isEditingAdditionalDiscount.value = false;
}

function handleAdditionalDiscountPercentageUpdate(value) {
	emit("update:additional_discount_percentage", value);
}

function handleAdditionalDiscountPercentageFocus() {
	isEditingAdditionalDiscountPercentage.value = true;
}

function handleAdditionalDiscountPercentageBlur() {
	isEditingAdditionalDiscountPercentage.value = false;
}

function focusAdditionalDiscountField() {
	const field = additionalDiscountField.value;
	field?.focus?.();
	field?.$el?.querySelector?.("input")?.focus?.();
}

function formatRatio(value) {
	const ratio = Number.isFinite(Number(value)) ? Number(value) : 0;
	const percent = Math.round(ratio * 10000) / 100;
	return `${percent}%`;
}

function isFullReturnDiscount(value) {
	const ratio = Number.isFinite(Number(value)) ? Number(value) : 0;
	return Math.abs(ratio - 1) < 0.0001;
}

async function handleSaveAndClear() {
	saveLoading.value = true;
	try {
		await emit("save-and-clear");
	} finally {
		saveLoading.value = false;
	}
}

async function handleLoadDrafts() {
	if (allDrafts.value.length) {
		openDraftsSurface();
		return;
	}

	loadDraftsLoading.value = true;
	try {
		await emit("load-drafts");
	} finally {
		loadDraftsLoading.value = false;
	}
}

function openDraftsSurface() {
	if (!allDrafts.value.length) {
		return;
	}

	if (showDesktopDrafts.value) {
		desktopDraftsDrawer.value = true;
		return;
	}

	mobileDraftsDialog.value = true;
}

async function handleSelectOrder() {
	selectOrderLoading.value = true;
	try {
		await emit("select-order");
	} finally {
		selectOrderLoading.value = false;
	}
}

async function handleCancelSale() {
	cancelLoading.value = true;
	try {
		await emit("cancel-sale");
	} finally {
		cancelLoading.value = false;
	}
}

async function handleOpenInvoiceManagement() {
	invoiceManagementLoading.value = true;
	try {
		await emit("open-invoice-management");
	} finally {
		invoiceManagementLoading.value = false;
	}
}

function handleManageAllDrafts() {
	desktopDraftsDrawer.value = false;
	mobileDraftsDialog.value = false;
	emit("open-invoice-management", "drafts");
}

async function handleOpenReturns() {
	returnsLoading.value = true;
	try {
		await emit("open-returns");
	} finally {
		returnsLoading.value = false;
	}
}

async function handlePrintDraft() {
	printLoading.value = true;
	try {
		await emit("print-draft");
	} finally {
		printLoading.value = false;
	}
}

async function handleShowPayment() {
	paymentLoading.value = true;
	try {
		await emit("show-payment");
	} finally {
		paymentLoading.value = false;
	}
}

async function handleOpenCustomerDisplay() {
	customerDisplayLoading.value = true;
	try {
		await emit("open-customer-display");
	} finally {
		customerDisplayLoading.value = false;
	}
}

function handleResumeDraft(draft) {
	desktopDraftsDrawer.value = false;
	mobileDraftsDialog.value = false;
	emit("resume-parked-order", draft);
}

defineExpose({
	focusAdditionalDiscountField,
	handleManageAllDrafts,
	openDraftsSurface,
});
</script>

<style scoped>
.drafts-drawer :deep(.v-navigation-drawer__content) {
	padding: 12px;
	background: var(--pos-surface-muted);
}

.drafts-drawer__body {
	padding: 4px;
}

.cards {
	background-color: var(--pos-card-bg) !important;
	transition: all 0.3s ease;
}

.sticky-summary-card {
	position: sticky;
	bottom: 0;
	z-index: 9;
	box-shadow: 0 -8px 24px rgba(15, 23, 42, 0.08);
}

.sticky-summary-card--dock-safe {
	margin-bottom: calc(var(--bottom-safe-space) + 8px);
}

.summary-content {
	row-gap: 4px;
}

.summary-actions-block {
	margin-top: 6px;
}

.summary-hero--top {
	margin-bottom: 6px;
}

.summary-hero {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 10px;
	padding: 6px 12px;
	border-radius: 14px;
	/* Match the deep-navy empty-cart panel: a soft radial vignette of the
	   brand pink anchored at the top, layered on the same vertical
	   surface-raised → surface-muted gradient used by the empty cart. */
	background:
		radial-gradient(
			circle at top,
			color-mix(in srgb, var(--pos-primary) 8%, transparent),
			transparent 55%
		),
		linear-gradient(
			180deg,
			var(--pos-surface-raised) 0%,
			var(--pos-surface-muted) 100%
		);
	border: 1px solid var(--pos-border, rgba(255, 255, 255, 0.06));
	position: relative;
	transition:
		border-color 0.3s ease,
		box-shadow 0.3s ease;
}

/* Command-Center "Active Missions" style pink glow when the cart has a
   value. Keeps the same surface but lights up the outline + casts a
   soft 3-stop halo so it reads as a live, live-value panel. */
.summary-hero--active {
	border-color: rgba(226, 54, 112, 0.55);
	box-shadow:
		inset 0 0 0 1px rgba(226, 54, 112, 0.35),
		0 0 0 3px rgba(226, 54, 112, 0.12),
		0 0 18px rgba(226, 54, 112, 0.28),
		0 0 42px rgba(226, 54, 112, 0.15);
	animation: summary-hero-pulse 2.8s ease-in-out infinite;
}

@keyframes summary-hero-pulse {
	0%,
	100% {
		box-shadow:
			inset 0 0 0 1px rgba(226, 54, 112, 0.35),
			0 0 0 3px rgba(226, 54, 112, 0.12),
			0 0 18px rgba(226, 54, 112, 0.28),
			0 0 42px rgba(226, 54, 112, 0.12);
	}
	50% {
		box-shadow:
			inset 0 0 0 1px rgba(226, 54, 112, 0.55),
			0 0 0 3px rgba(226, 54, 112, 0.18),
			0 0 22px rgba(226, 54, 112, 0.4),
			0 0 60px rgba(226, 54, 112, 0.22);
	}
}

.summary-hero__currency {
	font-weight: 600;
	font-size: 0.78em;
	color: var(--pos-text-secondary);
	letter-spacing: 0.04em;
	margin-inline-end: 0.35em;
}

.summary-hero__number {
	font-weight: 700;
	font-variant-numeric: tabular-nums;
}

.summary-hero__copy {
	display: flex;
	flex-direction: column;
	gap: 1px;
	min-width: 0;
}

.summary-hero__eyebrow {
	font-size: 0.62rem;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: 0.06em;
	color: var(--pos-text-secondary);
}

.summary-hero__amount {
	font-size: clamp(0.95rem, 1.3vw, 1.2rem);
	line-height: 1.1;
	color: var(--pos-text-primary);
	font-weight: 700;
}

.summary-hero__meta {
	display: flex;
	flex-wrap: wrap;
	gap: 4px 10px;
	font-size: 0.72rem;
	color: var(--pos-text-secondary);
}

.summary-hero__field-wrap {
	width: min(220px, 100%);
}

.invoice-summary-actions {
	position: sticky;
	bottom: 0;
}

.summary-field {
	transition: all 0.2s ease;
}

.summary-field:hover {
	transform: translateY(-1px);
	box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.summary-field--alert {
	margin-bottom: 10px;
}

.summary-field--dock :deep(.v-field) {
	background: rgba(var(--v-theme-surface), 0.92);
}

/* Mirror the cart Rate / QTY pill: rounded rectangle, hairline pink
   outline, same dense height. The three Vuetify outlined segments are
   zeroed out so the border reads as one continuous hairline instead of
   three meeting slabs. */
.summary-field--pill :deep(.v-field) {
	border-radius: 8px !important;
	background: var(--pos-primary-container, rgba(226, 54, 112, 0.05)) !important;
	min-height: 36px !important;
	box-shadow: inset 0 0 0 1px var(--pos-primary-variant, rgba(226, 54, 112, 0.4)) !important;
	transition: box-shadow 0.2s ease, background-color 0.2s ease;
}

.summary-field--pill :deep(.v-field__overlay) {
	background: transparent !important;
	opacity: 0 !important;
}

.summary-field--pill :deep(.v-field__outline) {
	display: none !important;
}

.summary-field--pill :deep(.v-field__outline__start),
.summary-field--pill :deep(.v-field__outline__end),
.summary-field--pill :deep(.v-field__outline__notch),
.summary-field--pill :deep(.v-field__outline__notch::before),
.summary-field--pill :deep(.v-field__outline__notch::after) {
	border: 0 !important;
	border-width: 0 !important;
}

.summary-field--pill :deep(.v-field--focused) {
	box-shadow:
		inset 0 0 0 1.5px var(--pos-primary, rgba(226, 54, 112, 0.85)),
		0 0 0 3px rgba(226, 54, 112, 0.15) !important;
}

.summary-field--pill :deep(.v-field__input) {
	min-height: 36px !important;
	padding-top: 0 !important;
	padding-bottom: 0 !important;
	font-weight: 500;
	font-size: 0.88rem;
	font-variant-numeric: tabular-nums;
}

.summary-field--pill :deep(.v-field__prepend-inner .v-icon) {
	color: var(--pos-primary, #e23670);
	opacity: 0.85;
	font-size: 18px;
}

.summary-field--pill :deep(.v-field__prefix),
.summary-field--pill :deep(.v-field__suffix) {
	color: var(--pos-text-secondary);
	font-weight: 600;
	font-size: 0.78rem;
}

.summary-field--pill :deep(.v-field--disabled) {
	opacity: 0.55;
}

@media (max-width: 1279px) {
	.sticky-summary-card {
		position: static;
		bottom: auto;
		box-shadow: none;
	}

	.invoice-summary-actions {
		position: static;
	}
}

@media (max-width: 1099px) {
	.sticky-summary-card--dock-safe {
		margin-bottom: calc(var(--bottom-safe-space) + 12px);
	}
}

@media (max-width: 768px) {
	.sticky-summary-card {
		position: static;
		bottom: auto;
		box-shadow: none;
	}

	.summary-hero {
		flex-direction: column;
		align-items: stretch;
		padding: 12px;
	}

	.summary-hero__field-wrap {
		width: 100%;
	}

	.invoice-summary-actions {
		position: static;
	}

	.cards {
		padding: 10px 12px !important;
	}

	.summary-field {
		font-size: 0.875rem;
	}

	.sticky-summary-card--dock-safe {
		margin-bottom: calc(var(--bottom-safe-space) + 8px);
	}
}
</style>
