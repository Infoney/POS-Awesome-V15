<template>
	<div class="reconciliation-section">
		<div class="table-header mb-4 d-flex flex-wrap align-center justify-space-between ga-3">
			<div>
				<h4 class="text-h6 text-grey-darken-2 mb-1">
					{{ __("Payment Reconciliation") }}
				</h4>
				<p class="text-body-2 text-grey">
					{{ __("Verify closing amounts for each payment method") }}
				</p>
			</div>

			<!--
				Closing-currency selector. Only renders when the shift had
				payments in 2+ currencies (the parent passes a singleton
				list otherwise). Picking a currency changes what the
				Opening / Closing / Expected / Difference columns DISPLAY
				and what UNIT the cashier types into the closing amount
				input — DB storage stays in company currency, the UI
				converts on the way in/out using `closingExchangeRate`.
			-->
			<div
				v-if="hasMultipleCurrencies"
				class="closing-currency-picker"
				:title="__('Choose the currency the cashier is closing in (counted cash / receipts).')"
			>
				<v-select
					:model-value="closingCurrency"
					@update:model-value="onChangeCurrency"
					:items="availableClosingCurrencies"
					:label="__('Closing in')"
					:hide-details="true"
					density="compact"
					variant="outlined"
					color="primary"
					class="closing-currency-picker__select"
				/>
				<div v-if="!isCompanyCurrency" class="closing-currency-picker__rate text-caption text-grey">
					1 {{ companyCurrency }} ≈ {{ formatCurrency(closingExchangeRate, 4) }} {{ closingCurrency }}
				</div>
			</div>
		</div>

		<v-data-table
			:headers="headers"
			:items="payments"
			item-key="mode_of_payment"
			class="elevation-0 rounded-lg white-table"
			:items-per-page="itemsPerPage"
			hide-default-footer
			density="compact"
		>
			<template v-slot:item.closing_amount="props">
				<v-text-field
					:model-value="closingDisplayValue(props.item)"
					@update:model-value="(value) => onClosingInput(props.item, value)"
					:rules="[closingAmountRule]"
					:label="$frappe._('Edit')"
					single-line
					counter
					type="number"
					density="compact"
					variant="outlined"
					color="primary"
					class="pos-themed-input"
					hide-details
					:prefix="effectiveSymbol"
				></v-text-field>
			</template>
			<template v-slot:item.difference="{ item }">
				{{ effectiveSymbol }}
				{{ formatCurrency(displayDifference(item)) }}
			</template>
			<template v-slot:item.opening_amount="{ item }">
				{{ effectiveSymbol }}
				{{ formatCurrency(displayConvert(item.opening_amount)) }}</template
			>
			<template v-slot:item.expected_amount="{ item }">
				{{ effectiveSymbol }}
				{{ formatCurrency(displayConvert(item.expected_amount)) }}</template
			>
			<template v-slot:item.variance_percent="{ item }">
				<span :class="['variance-chip', varianceClass(item)]">
					{{ formatVariancePercent(item) }}
				</span>
			</template>
		</v-data-table>
	</div>
</template>

<script setup>
import { computed, inject } from "vue";

const props = defineProps({
	payments: Array,
	headers: Array,
	itemsPerPage: {
		type: Number,
		default: 20,
	},
	companyCurrencySymbol: String,
	// New (multi-currency closing). When the closing currency matches the
	// company currency the props become no-ops — display stays in company
	// currency, exchange rate is 1, no conversion happens. The selector
	// dropdown is hidden whenever `availableClosingCurrencies` has 1
	// entry (the singleton company-currency case).
	companyCurrency: { type: String, default: "" },
	closingCurrency: { type: String, default: "" },
	closingCurrencySymbol: { type: String, default: "" },
	closingExchangeRate: { type: Number, default: 1 },
	availableClosingCurrencies: { type: Array, default: () => [] },
	// Formatters
	formatCurrency: Function,
	formatFloat: Function,
});

const emit = defineEmits(["update:closing-currency"]);

const $frappe = inject("frappe", window.frappe);
const __ = window.__ || ((t) => t);

const hasMultipleCurrencies = computed(() => {
	return Array.isArray(props.availableClosingCurrencies) && props.availableClosingCurrencies.length > 1;
});

const isCompanyCurrency = computed(() => {
	return !props.closingCurrency || props.closingCurrency === props.companyCurrency;
});

// What symbol to render in front of every monetary cell. Falls back through
// closingCurrencySymbol → companyCurrencySymbol so the table stays prefixed
// even when the parent hasn't wired the closing-currency props yet.
const effectiveSymbol = computed(() => {
	if (isCompanyCurrency.value) return props.companyCurrencySymbol || "";
	return props.closingCurrencySymbol || props.closingCurrency || props.companyCurrencySymbol || "";
});

const safeRate = computed(() => {
	const rate = Number(props.closingExchangeRate);
	if (!Number.isFinite(rate) || rate <= 0) return 1;
	return rate;
});

// Convert a company-currency value (Opening / Expected / Difference DB
// figures, all stored as company currency) into the closing-currency
// display. When closing in company currency, rate=1 → identity.
const displayConvert = (value) => {
	const num = Number(value) || 0;
	return num * safeRate.value;
};

// `closing_amount` is the user-entered "I counted X" figure. The DB stores
// it in company currency; the display shows it in closing currency.
const closingDisplayValue = (item) => {
	const stored = Number(item?.closing_amount) || 0;
	if (!stored) {
		// Empty / 0 in DB → empty string in input so the cashier sees a
		// blank "Edit" placeholder rather than a literal "0".
		return item?.closing_amount === 0 ? 0 : "";
	}
	return stored * safeRate.value;
};

// Reverse: parse the cashier's typed value (in closing currency) back to
// company currency and store on the row.
const onClosingInput = (item, rawValue) => {
	if (!item) return;
	if (rawValue === "" || rawValue === null || rawValue === undefined) {
		item.closing_amount = "";
		return;
	}
	const num = typeof rawValue === "number" ? rawValue : Number(String(rawValue).trim());
	if (!Number.isFinite(num)) {
		item.closing_amount = rawValue;
		return;
	}
	item.closing_amount = num / safeRate.value;
};

const onChangeCurrency = (value) => {
	emit("update:closing-currency", value);
};

const closingAmountRule = (v) => {
	if (v === "" || v === null || v === undefined) {
		return true;
	}

	const value = typeof v === "number" ? v : Number(String(v).trim());

	if (!Number.isFinite(value)) {
		return "Please enter a valid number";
	}

	const stringValue = String(v);
	const [integerPart, fractionalPart] = stringValue.split(".");

	if (integerPart.replace(/^-/, "").length > 20) {
		return "Number is too large";
	}

	if (fractionalPart && fractionalPart.length > 2) {
		return "Maximum of 2 decimal places";
	}

	return true;
};

const calculateDifference = (item) => {
	const closing = Number(item?.closing_amount) || 0;
	const expected = Number(item?.expected_amount) || 0;
	return expected - closing;
};

const displayDifference = (item) => {
	return calculateDifference(item) * safeRate.value;
};

const formatVariancePercent = (item) => {
	const expected = Number(item?.expected_amount) || 0;
	if (!expected) {
		const closing = Number(item?.closing_amount) || 0;
		return closing ? __("N/A") : "0%";
	}
	// Variance % is unit-less so the rate cancels out. Calculate against
	// company-currency figures directly.
	const variance = (calculateDifference(item) / expected) * 100;
	const prefix = variance > 0 ? "+" : variance < 0 ? "" : "";
	return `${prefix}${props.formatFloat(variance, 2)}%`;
};

const varianceClass = (item) => {
	const expected = Number(item?.expected_amount) || 0;
	if (!expected) {
		return "variance-neutral";
	}
	const variance = (calculateDifference(item) / expected) * 100;
	if (!variance) {
		return "variance-neutral";
	}
	return variance > 0 ? "variance-negative" : "variance-positive";
};
</script>

<style scoped>
.white-table {
	background: rgb(var(--v-theme-surface)) !important;
	border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.pos-themed-input :deep(.v-field__outline__start),
.pos-themed-input :deep(.v-field__outline__end) {
	border-color: rgba(var(--v-border-color), var(--v-border-opacity)) !important;
}

.variance-chip {
	display: inline-block;
	padding: 4px 12px;
	border-radius: 12px;
	font-size: 0.75rem;
	font-weight: 600;
	letter-spacing: 0.5px;
}

.variance-positive {
	background-color: rgba(var(--v-theme-success), 0.1);
	color: rgb(var(--v-theme-success));
}

.variance-negative {
	background-color: rgba(var(--v-theme-error), 0.1);
	color: rgb(var(--v-theme-error));
}

.variance-neutral {
	background-color: rgba(var(--v-theme-on-surface), 0.05);
	opacity: 0.7;
}

.closing-currency-picker {
	min-width: 220px;
	display: flex;
	flex-direction: column;
	gap: 4px;
}

.closing-currency-picker__select {
	min-width: 220px;
}

.closing-currency-picker__rate {
	text-align: right;
}
</style>
