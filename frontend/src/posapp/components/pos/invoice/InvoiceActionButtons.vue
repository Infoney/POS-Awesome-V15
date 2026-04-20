<template>
	<v-row dense class="action-grid">
		<v-col cols="6" sm="4">
			<v-btn
				block
				color="accent"
				theme="dark"
				prepend-icon="mdi-content-save"
				@click="$emit('save-and-clear')"
				class="summary-btn"
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
				color="warning"
				theme="dark"
				prepend-icon="mdi-tray-full"
				@click="$emit('load-drafts')"
				class="white-text-btn summary-btn"
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
				color="deep-purple"
				theme="dark"
				prepend-icon="mdi-folder-search-outline"
				@click="$emit('open-invoice-management')"
				class="summary-btn"
				:loading="invoiceManagementLoading"
			>
				<span class="summary-btn__label">{{ __("Invoice Mgmt") }}</span>
			</v-btn>
		</v-col>
		<v-col cols="6" sm="4">
			<v-btn
				block
				color="error"
				theme="dark"
				prepend-icon="mdi-close-circle"
				@click="$emit('cancel-sale')"
				class="summary-btn"
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
				color="secondary"
				theme="dark"
				prepend-icon="mdi-backup-restore"
				@click="$emit('open-returns')"
				class="summary-btn"
				:loading="returnsLoading"
				:title="__('Sales Return (Alt+8)')"
			>
				<span class="summary-btn__label">{{ __("Sales Return") }}</span>
				<ShortcutHint combo="Alt+8" />
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
		<v-col cols="12">
			<v-btn
				block
				color="success"
				theme="dark"
				prepend-icon="mdi-credit-card"
				@click="$emit('show-payment')"
				class="summary-btn pay-btn"
				:loading="paymentLoading"
				:title="__('Open payment (Alt+D) — submit + print (Alt+P) — submit only (Alt+X)')"
			>
				<span class="summary-btn__label">{{ __("PAY") }}</span>
				<ShortcutHint combo="Alt+D" tone="light" />
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

/* Special styling for the PAY button */
.pay-btn {
	font-weight: 700 !important;
	font-size: 1rem !important;
	min-height: 50px !important;
	background: linear-gradient(135deg, #4caf50, #45a049) !important;
	box-shadow: 0 4px 12px rgba(76, 175, 80, 0.3) !important;
	letter-spacing: 0.04em !important;
}

.pay-btn:hover {
	background: linear-gradient(135deg, #45a049, #3d8b40) !important;
	box-shadow: 0 6px 16px rgba(76, 175, 80, 0.4) !important;
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
