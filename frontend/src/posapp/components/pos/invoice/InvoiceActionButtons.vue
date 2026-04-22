<template>
	<v-row dense class="action-grid">
		<v-col cols="6" sm="4">
			<v-btn
				block
				theme="dark"
				prepend-icon="mdi-content-save"
				@click="$emit('save-and-clear')"
				class="summary-btn summary-btn--save"
				:loading="saveLoading"
				:title="__('Save & Clear (Alt+S)')"
			>
				<span class="summary-btn__label">{{ __("Save & Clear") }}</span>
				<ShortcutHint combo="Alt+S" />
			</v-btn>
		</v-col>
		<v-col cols="6" sm="4">
			<v-btn
				block
				theme="dark"
				prepend-icon="mdi-tray-full"
				@click="$emit('load-drafts')"
				class="white-text-btn summary-btn summary-btn--drafts"
				:loading="loadDraftsLoading"
				:title="__('Drafts (Alt+L)')"
			>
				<span class="summary-btn__label">{{ __("Drafts") }}</span>
				<ShortcutHint combo="Alt+L" />
			</v-btn>
		</v-col>
		<v-col cols="6" sm="4">
			<v-btn
				block
				theme="dark"
				prepend-icon="mdi-folder-search-outline"
				@click="$emit('open-invoice-management')"
				class="summary-btn summary-btn--invoice"
				:loading="invoiceManagementLoading"
			>
				<span class="summary-btn__label">{{ __("Invoice Mgmt") }}</span>
			</v-btn>
		</v-col>
		<v-col cols="6" sm="4">
			<v-btn
				block
				theme="dark"
				prepend-icon="mdi-close-circle"
				@click="$emit('cancel-sale')"
				class="summary-btn summary-btn--cancel"
				:loading="cancelLoading"
				:title="__('Cancel Sale (Alt+2)')"
			>
				<span class="summary-btn__label">{{ __("Cancel Sale") }}</span>
				<ShortcutHint combo="Alt+2" />
			</v-btn>
		</v-col>
		<v-col cols="6" sm="4" v-if="pos_profile.posa_allow_return == 1">
			<v-btn
				block
				theme="dark"
				prepend-icon="mdi-backup-restore"
				@click="$emit('open-returns')"
				class="summary-btn summary-btn--return"
				:loading="returnsLoading"
				:title="__('Sales Return (Alt+8)')"
			>
				<span class="summary-btn__label">{{ __("Sales Return") }}</span>
				<ShortcutHint combo="Alt+8" />
			</v-btn>
		</v-col>
		<v-col cols="6" sm="4">
			<v-btn
				block
				theme="dark"
				prepend-icon="mdi-credit-card"
				@click="$emit('show-payment')"
				class="summary-btn pay-btn summary-btn--pay"
				:loading="paymentLoading"
				:title="__('Open payment (Alt+D) — submit + print (Alt+P) — submit only (Alt+X)')"
			>
				<span class="summary-btn__label">{{ __("PAY") }}</span>
				<ShortcutHint combo="Alt+D" tone="light" />
			</v-btn>
		</v-col>
		<v-col cols="6" sm="4" v-if="pos_profile.custom_allow_select_sales_order == 1">
			<v-btn
				block
				color="info"
				theme="dark"
				prepend-icon="mdi-book-search"
				@click="$emit('select-order')"
				class="summary-btn"
				:loading="selectOrderLoading"
				:title="__('Select S.O (Alt+7)')"
			>
				<span class="summary-btn__label">{{ __("Select S.O") }}</span>
				<ShortcutHint combo="Alt+7" />
			</v-btn>
		</v-col>
		<v-col cols="6" sm="4" v-if="pos_profile.posa_allow_print_draft_invoices">
			<v-btn
				block
				color="primary"
				theme="dark"
				prepend-icon="mdi-printer"
				@click="$emit('print-draft')"
				class="summary-btn"
				:loading="printLoading"
			>
				<span class="summary-btn__label">{{ __("Print Draft") }}</span>
			</v-btn>
		</v-col>
		<v-col cols="6" sm="4" v-if="showCustomerDisplayButton">
			<v-btn
				block
				color="indigo"
				theme="dark"
				prepend-icon="mdi-monitor"
				@click="$emit('open-customer-display')"
				class="summary-btn"
				:loading="customerDisplayLoading"
			>
				<span class="summary-btn__label">{{ __("Customer Screen") }}</span>
			</v-btn>
		</v-col>
	</v-row>
</template>

<script setup>
import { computed } from "vue";
import { parseBooleanSetting } from "../../../utils/stock";
import ShortcutHint from "./ShortcutHint.vue";

const props = defineProps({
	pos_profile: {
		type: Object,
		required: true,
		default: () => ({}),
	},
	saveLoading: Boolean,
	loadDraftsLoading: Boolean,
	selectOrderLoading: Boolean,
	cancelLoading: Boolean,
	invoiceManagementLoading: Boolean,
	returnsLoading: Boolean,
	printLoading: Boolean,
	paymentLoading: Boolean,
	customerDisplayLoading: Boolean,
});

defineEmits([
	"save-and-clear",
	"load-drafts",
	"select-order",
	"cancel-sale",
	"open-invoice-management",
	"open-returns",
	"print-draft",
	"show-payment",
	"open-customer-display",
]);

const __ = window.__;
const showCustomerDisplayButton = computed(() =>
	parseBooleanSetting(props.pos_profile?.posa_enable_customer_display),
);
</script>

<style scoped>
.white-text-btn {
	color: var(--pos-text-primary) !important;
}

.white-text-btn :deep(.v-btn__content) {
	color: var(--pos-text-primary) !important;
}

.action-grid {
	row-gap: 6px;
}

/* Enhanced button styling with better performance */
.summary-btn {
	transition: transform 0.18s ease, box-shadow 0.18s ease !important;
	position: relative;
	overflow: hidden;
	min-height: 44px !important;
	text-transform: none !important;
	font-size: 0.82rem !important;
	letter-spacing: 0 !important;
	touch-action: manipulation;
	-webkit-tap-highlight-color: transparent;
	cursor: pointer;
}

.summary-btn :deep(.v-btn__content) {
	white-space: normal !important;
	pointer-events: none;
	display: inline-flex;
	align-items: center;
	gap: 4px;
	min-width: 0;
}

.summary-btn__label {
	display: inline-flex;
	align-items: center;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
}

.summary-btn :deep(.v-btn__prepend),
.summary-btn :deep(.v-btn__append) {
	pointer-events: none;
}

.summary-btn:hover {
	transform: translateY(-1px);
	box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15) !important;
}

.summary-btn:active {
	transform: translateY(0);
}

/* ── Command-Center action button palette ─────────────────────────
   Each button gets a 135° gradient + colour-matched shadow halo so
   the row reads like the CC dashboard tiles (Top Selling Items,
   Stock Alerts, Payments by Store) instead of flat Vuetify chips.
   The gradient is painted on .v-btn__overlay-replacement (created
   by overriding the underlying surface) — we set background on the
   button itself + override Vuetify's color overlay. */
.summary-btn {
	color: #ffffff !important;
}

.summary-btn :deep(.v-btn__overlay) {
	background: transparent !important;
}

/* Save & Clear — magenta → orange (CC top revenue tile) */
.summary-btn--save {
	background: linear-gradient(135deg, #ec4899 0%, #f97316 100%) !important;
	box-shadow:
		0 6px 16px rgba(236, 72, 153, 0.3),
		0 2px 4px rgba(249, 115, 22, 0.2) !important;
}
.summary-btn--save:hover {
	background: linear-gradient(135deg, #db2777 0%, #ea580c 100%) !important;
	box-shadow:
		0 10px 24px rgba(236, 72, 153, 0.4),
		0 4px 8px rgba(249, 115, 22, 0.25) !important;
}

/* Drafts — amber → orange (CC second revenue tile) */
.summary-btn--drafts {
	background: linear-gradient(135deg, #f59e0b 0%, #f97316 100%) !important;
	box-shadow:
		0 6px 16px rgba(245, 158, 11, 0.32),
		0 2px 4px rgba(249, 115, 22, 0.18) !important;
}
.summary-btn--drafts:hover {
	background: linear-gradient(135deg, #d97706 0%, #ea580c 100%) !important;
	box-shadow:
		0 10px 24px rgba(245, 158, 11, 0.42),
		0 4px 8px rgba(249, 115, 22, 0.25) !important;
}

/* Invoice Mgmt — indigo → violet */
.summary-btn--invoice {
	background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
	box-shadow:
		0 6px 16px rgba(99, 102, 241, 0.3),
		0 2px 4px rgba(139, 92, 246, 0.2) !important;
}
.summary-btn--invoice:hover {
	background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%) !important;
	box-shadow:
		0 10px 24px rgba(99, 102, 241, 0.4),
		0 4px 8px rgba(139, 92, 246, 0.25) !important;
}

/* Cancel Sale — coral → red (matches our brand pink family) */
.summary-btn--cancel {
	background: linear-gradient(135deg, #f43f5e 0%, #e11d48 100%) !important;
	box-shadow:
		0 6px 16px rgba(244, 63, 94, 0.32),
		0 2px 4px rgba(225, 29, 72, 0.2) !important;
}
.summary-btn--cancel:hover {
	background: linear-gradient(135deg, #e11d48 0%, #be123c 100%) !important;
	box-shadow:
		0 10px 24px rgba(244, 63, 94, 0.42),
		0 4px 8px rgba(225, 29, 72, 0.25) !important;
}

/* Sales Return — teal → emerald (CC third revenue tile) */
.summary-btn--return {
	background: linear-gradient(135deg, #14b8a6 0%, #10b981 100%) !important;
	box-shadow:
		0 6px 16px rgba(20, 184, 166, 0.3),
		0 2px 4px rgba(16, 185, 129, 0.2) !important;
}
.summary-btn--return:hover {
	background: linear-gradient(135deg, #0d9488 0%, #059669 100%) !important;
	box-shadow:
		0 10px 24px rgba(20, 184, 166, 0.4),
		0 4px 8px rgba(16, 185, 129, 0.25) !important;
}

/* PAY — emerald hero, slightly bigger + heavier than its siblings */
.pay-btn,
.summary-btn--pay {
	font-weight: 700 !important;
	font-size: 0.95rem !important;
	min-height: 48px !important;
	background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%) !important;
	box-shadow:
		0 8px 20px rgba(34, 197, 94, 0.35),
		0 2px 4px rgba(22, 163, 74, 0.25) !important;
	letter-spacing: 0.04em !important;
}

.pay-btn:hover,
.summary-btn--pay:hover {
	background: linear-gradient(135deg, #16a34a 0%, #15803d 100%) !important;
	box-shadow:
		0 12px 28px rgba(34, 197, 94, 0.45),
		0 4px 8px rgba(22, 163, 74, 0.3) !important;
	transform: translateY(-2px);
}

/* Responsive optimizations */
@media (max-width: 768px) {
	.summary-btn {
		font-size: 0.78rem !important;
		padding: 4px 8px !important;
		min-height: 44px !important;
	}

	.pay-btn {
		font-size: 0.95rem !important;
		min-height: 48px !important;
	}
}

@media (max-width: 480px) {
	.summary-btn {
		font-size: 0.74rem !important;
		padding: 3px 6px !important;
		min-height: 42px !important;
	}

	.pay-btn {
		font-size: 0.9rem !important;
		min-height: 46px !important;
	}
}

/* Loading state animations */
.summary-btn:deep(.v-btn__loader) {
	opacity: 0.8;
}

/* Dark theme enhancements */
:deep([data-theme="dark"]) .summary-btn,
:deep(.v-theme--dark) .summary-btn {
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3) !important;
}

:deep([data-theme="dark"]) .summary-btn:hover,
:deep(.v-theme--dark) .summary-btn:hover {
	box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4) !important;
}
</style>
