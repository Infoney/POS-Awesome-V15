<template>
	<div
		:class="[
			'pos-row-card',
			stockTierClass,
			{ 'pos-row-card--highlighted': isItemHighlighted },
		]"
		@click="onClick"
		:draggable="true"
		@dragstart="onDragStart"
		@dragend="onDragEnd"
	>
		<div class="pos-row-card__thumb">
			<v-img
				:src="item.image || placeholderImage"
				class="pos-row-card__image"
				aspect-ratio="1"
				:alt="item.item_name"
				cover
			>
				<template #placeholder>
					<div class="pos-row-card__placeholder">
						<v-icon size="22" color="grey-lighten-2">mdi-image-outline</v-icon>
					</div>
				</template>
			</v-img>
		</div>

		<div class="pos-row-card__main">
			<div class="pos-row-card__title-row">
				<h4 class="pos-row-card__name" :title="item.item_name">
					{{ item.item_name }}
				</h4>
				<span
					v-if="item.item_code && item.item_code !== item.item_name"
					class="pos-row-card__code"
					:title="item.item_code"
				>
					{{ item.item_code }}
				</span>
			</div>

			<div class="pos-row-card__meta-row">
				<span class="pos-row-card__stock-track" :title="stockTooltip">
					<span
						class="pos-row-card__stock-fill"
						:style="{ width: stockFillPercent + '%' }"
					></span>
				</span>
				<span class="pos-row-card__stock-label">
					<v-icon size="12" class="pos-row-card__stock-icon">mdi-package-variant</v-icon>
					<span
						class="pos-row-card__stock-amount"
						:class="{ 'pos-row-card__stock-amount--negative': isNegative(item.actual_qty) }"
					>
						{{ formattedActualQty }}
					</span>
					<span class="pos-row-card__stock-uom">{{ item.stock_uom || "" }}</span>
					<ItemStockInfoMenu
						v-if="showStockInfo"
						:item="item"
						:pos-profile="posProfile"
						:format-number="formatNumber"
						:hide-qty-decimals="hideQtyDecimals"
					/>
				</span>
			</div>
		</div>

		<div class="pos-row-card__price">
			<div class="pos-row-card__price-primary">
				<span class="pos-row-card__price-currency">{{ currencySymbol(primaryCurrency) }}</span>
				<span class="pos-row-card__price-amount">
					{{ formatCurrency(primaryRate, primaryCurrency, primaryPrecision) }}
				</span>
				<ItemRateInfoMenu
					v-if="showRateInfo"
					:rate-info="rateInfo"
					:currency-symbol="currencySymbol"
					:format-currency="formatCurrency"
					:rate-precision="ratePrecision"
				/>
			</div>
			<div v-if="showSecondaryPrice" class="pos-row-card__price-secondary">
				{{ currencySymbol(secondaryCurrency) }}
				{{ formatCurrency(item.rate, secondaryCurrency, primaryPrecision) }}
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import placeholderImage from "../placeholder-image.png";
import ItemRateInfoMenu from "./ItemRateInfoMenu.vue";
import ItemStockInfoMenu from "./ItemStockInfoMenu.vue";

const props = defineProps({
	item: { type: Object, required: true },
	posProfile: { type: Object, required: true },
	context: { type: String, default: "pos" },
	selectedCurrency: { type: String, default: "" },
	hideQtyDecimals: { type: Boolean, default: false },
	showRateInfo: { type: Boolean, default: true },
	getItemRateInfo: { type: Function, required: true },
	isItemHighlighted: { type: Boolean, default: false },
	currencySymbol: { type: Function, required: true },
	formatCurrency: { type: Function, required: true },
	formatNumber: { type: Function, required: true },
	ratePrecision: { type: Function, required: true },
	isNegative: { type: Function, default: (val) => val < 0 },
});

const emit = defineEmits(["click", "dragstart", "dragend"]);

const primaryCurrency = computed(() => {
	return (
		props.item.original_currency ||
		props.item.currency ||
		props.item.price_list_currency ||
		props.posProfile.currency
	);
});

const primaryRate = computed(() => {
	if (props.context === "purchase") {
		return props.item.original_rate ?? props.item.rate ?? props.item.standard_rate ?? 0;
	}
	return props.item.original_rate ?? props.item.rate ?? 0;
});

const primaryPrecision = computed(() => props.ratePrecision(primaryRate.value));

const rateInfo = computed(() => props.getItemRateInfo(props.item));

const secondaryCurrency = computed(() => props.selectedCurrency);

const showSecondaryPrice = computed(() => {
	return (
		props.context !== "purchase" &&
		props.posProfile.posa_allow_multi_currency &&
		Boolean(props.selectedCurrency) &&
		props.selectedCurrency !== primaryCurrency.value
	);
});

const numericQty = computed(() => {
	const n = Number(props.item.actual_qty ?? 0);
	return Number.isFinite(n) ? n : 0;
});

const formattedActualQty = computed(() => {
	if (props.hideQtyDecimals) {
		return props.formatNumber(Math.round(numericQty.value), 0);
	}
	return props.formatNumber(numericQty.value, 4);
});

// Stock tier drives both the accent stripe colour and the progress-bar fill.
// Thresholds are intentionally conservative: anything at/below 5 reads as
// "almost out", 5–20 as "low", 20+ as healthy. Negative values are oversold.
const stockTier = computed(() => {
	const qty = numericQty.value;
	if (qty <= 0) return "out";
	if (qty < 5) return "critical";
	if (qty < 20) return "low";
	return "ok";
});

const stockTierClass = computed(() => `pos-row-card--${stockTier.value}`);

// Log-ish scale so a single warehouse with 2000 units doesn't flatten the
// bar for everything else in the list. 100+ units reads as ~full.
const stockFillPercent = computed(() => {
	const qty = numericQty.value;
	if (qty <= 0) return 6;
	if (qty >= 100) return 100;
	if (qty >= 20) return 70 + Math.min(30, (qty - 20) * 0.375);
	if (qty >= 5) return 35 + (qty - 5) * (35 / 15);
	return 12 + qty * (22 / 5);
});

const stockTooltip = computed(() => {
	const uom = props.item.stock_uom || "";
	return `${props.formatNumber(numericQty.value, props.hideQtyDecimals ? 0 : 4)} ${uom}`.trim();
});

const showStockInfo = computed(() => {
	const item = props.item;
	if (!item) return false;
	if (item.has_batch_no) return true;
	if (Array.isArray(item.batch_no_data) && item.batch_no_data.length > 0) return true;
	return numericQty.value <= 0;
});

const onClick = (event) => emit("click", event, props.item);
const onDragStart = (event) => emit("dragstart", event, props.item);
const onDragEnd = (event) => emit("dragend", event);
</script>

<style scoped>
.pos-row-card {
	display: flex;
	align-items: center;
	gap: 14px;
	padding: 10px 14px 10px 12px;
	background: var(--pos-surface-raised);
	border: 1px solid var(--pos-border-light);
	border-radius: 14px;
	box-shadow: 0 4px 14px var(--pos-shadow-light);
	cursor: pointer;
	width: 100%;
	height: 100%;
	min-height: 76px;
	position: relative;
	overflow: hidden;
	transition:
		border-color 0.18s ease,
		background-color 0.18s ease,
		transform 0.18s ease,
		box-shadow 0.18s ease;
}

.pos-row-card::before {
	content: "";
	position: absolute;
	inset: 0 auto 0 0;
	width: 4px;
	background: var(--row-accent, rgba(148, 163, 184, 0.35));
	opacity: 0.9;
}

.pos-row-card:hover {
	border-color: rgba(var(--v-theme-primary), 0.35);
	transform: translateY(-1px);
	box-shadow: 0 10px 22px var(--pos-shadow);
}

.pos-row-card--highlighted {
	border-color: rgb(var(--v-theme-primary));
	background: rgba(var(--v-theme-primary), 0.08);
	box-shadow:
		0 0 0 2px rgba(var(--v-theme-primary), 0.3),
		0 10px 22px rgba(var(--v-theme-primary), 0.18);
}

/* Stock-tier accent: drives the left stripe and the progress-bar colour. */
.pos-row-card--ok {
	--row-accent: #22c55e;
	--row-bar: linear-gradient(90deg, #22c55e, #4ade80);
}
.pos-row-card--low {
	--row-accent: #f59e0b;
	--row-bar: linear-gradient(90deg, #f59e0b, #fbbf24);
}
.pos-row-card--critical {
	--row-accent: #ef4444;
	--row-bar: linear-gradient(90deg, #ef4444, #f97316);
}
.pos-row-card--out {
	--row-accent: #64748b;
	--row-bar: linear-gradient(90deg, #64748b, #94a3b8);
}

.pos-row-card__thumb {
	flex: 0 0 auto;
	width: 56px;
	height: 56px;
	border-radius: 10px;
	overflow: hidden;
	background: var(--pos-surface-muted);
	border: 1px solid var(--pos-border-light);
}

.pos-row-card__image {
	width: 100%;
	height: 100%;
	object-fit: cover;
}

.pos-row-card__placeholder {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 100%;
	height: 100%;
	background: var(--pos-surface-muted);
}

.pos-row-card__main {
	flex: 1 1 auto;
	min-width: 0;
	display: flex;
	flex-direction: column;
	gap: 6px;
}

.pos-row-card__title-row {
	display: flex;
	align-items: center;
	gap: 10px;
	min-width: 0;
}

.pos-row-card__name {
	margin: 0;
	font-size: 0.96rem;
	font-weight: 700;
	line-height: 1.25;
	color: var(--pos-text-primary);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	min-width: 0;
}

.pos-row-card__code {
	font-size: 0.72rem;
	font-weight: 500;
	color: var(--pos-text-secondary);
	letter-spacing: 0.03em;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
	max-width: 40%;
}

.pos-row-card__meta-row {
	display: flex;
	align-items: center;
	gap: 10px;
	min-width: 0;
}

.pos-row-card__stock-track {
	flex: 1 1 auto;
	min-width: 40px;
	height: 4px;
	background: rgba(148, 163, 184, 0.18);
	border-radius: 999px;
	overflow: hidden;
}

.pos-row-card__stock-fill {
	display: block;
	height: 100%;
	background: var(--row-bar, linear-gradient(90deg, #64748b, #94a3b8));
	border-radius: inherit;
	transition: width 0.25s ease;
}

.pos-row-card__stock-label {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	font-size: 0.76rem;
	color: var(--pos-text-secondary);
	flex: 0 0 auto;
	white-space: nowrap;
}

.pos-row-card__stock-icon {
	opacity: 0.8;
}

.pos-row-card__stock-amount {
	font-weight: 700;
	color: var(--pos-text-primary);
}

.pos-row-card__stock-amount--negative {
	color: rgb(var(--v-theme-error));
}

.pos-row-card__stock-uom {
	font-size: 0.68rem;
	text-transform: uppercase;
	opacity: 0.8;
}

.pos-row-card__price {
	flex: 0 0 auto;
	text-align: right;
	display: flex;
	flex-direction: column;
	align-items: flex-end;
	gap: 2px;
	min-width: 92px;
}

.pos-row-card__price-primary {
	display: inline-flex;
	align-items: baseline;
	gap: 4px;
	font-weight: 700;
	color: var(--pos-primary);
	font-size: 1rem;
}

.pos-row-card__price-currency {
	font-size: 0.75rem;
	font-weight: 600;
	color: var(--pos-text-secondary);
	letter-spacing: 0.04em;
}

.pos-row-card__price-amount {
	font-size: 1.02rem;
	font-variant-numeric: tabular-nums;
}

.pos-row-card__price-secondary {
	font-size: 0.74rem;
	color: var(--pos-text-secondary);
}

@media (max-width: 768px) {
	.pos-row-card {
		gap: 10px;
		padding: 8px 12px 8px 10px;
	}
	.pos-row-card__thumb {
		width: 48px;
		height: 48px;
	}
	.pos-row-card__name {
		font-size: 0.9rem;
	}
	.pos-row-card__price-amount {
		font-size: 0.95rem;
	}
	.pos-row-card__code {
		display: none;
	}
}
</style>
