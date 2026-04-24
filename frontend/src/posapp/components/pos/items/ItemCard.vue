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
		<div class="pos-row-card__thumb" :class="{ 'pos-row-card__thumb--fallback': !item.image }">
			<v-img
				v-if="item.image"
				:src="item.image"
				class="pos-row-card__image"
				aspect-ratio="1"
				:alt="item.item_name"
				cover
			>
				<template #placeholder>
					<div class="pos-row-card__fallback">
						<v-icon size="20" color="white">mdi-currency-usd</v-icon>
					</div>
				</template>
			</v-img>
			<div v-else class="pos-row-card__fallback" :aria-label="item.item_name">
				<v-icon size="20" color="white">mdi-currency-usd</v-icon>
			</div>
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

			<!-- Batch info pill, only when the item is batched and has data
			     to show. Uses the Command Center cc-chip pattern (rounded
			     pill, tinted background) so it sits visually above the
			     meta row without competing with the stock bar. -->
			<div v-if="batchChipText" class="pos-row-card__batch-row">
				<span
					class="pos-row-card__batch-chip"
					:title="batchChipTitle"
				>
					<v-icon size="11" class="pos-row-card__batch-icon">mdi-tag-outline</v-icon>
					<span class="pos-row-card__batch-text">{{ batchChipText }}</span>
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
				<!-- Price sits inline with NOS — was a separate right-aligned
				     column before, but the cashier wants the qty + price as
				     one visual unit so they can scan a row in one glance. -->
				<span class="pos-row-card__price-inline">
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
				</span>
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

// Batch chip data — only shown when the item is batched and we actually
// have batch rows to label. Empty / non-batched items render no chip
// (the meta row collapses cleanly).
const sellableBatches = computed(() => {
	const raw = props.item?.batch_no_data;
	if (!Array.isArray(raw)) return [];
	return raw.filter((b) => {
		if (!b || !b.batch_no) return false;
		if (b.is_expired) return false;
		const qty = Number(b.batch_qty ?? 0);
		return Number.isFinite(qty) && qty > 0;
	});
});

const batchChipText = computed(() => {
	const item = props.item;
	if (!item) return "";
	if (!item.has_batch_no) return "";
	const list = sellableBatches.value;
	if (!list.length) return "";
	if (list.length === 1) {
		return `Batch ${list[0].batch_no}`;
	}
	// Spell out batch numbers when there's enough room (the row has the
	// width). Cap at 4 names so really long batch lists don't push the
	// NOS / price off the row — the rest are surfaced via the title
	// tooltip + the existing ItemStockInfoMenu dropdown.
	const names = list.map((b) => b.batch_no);
	if (names.length <= 4) {
		return `Batches: ${names.join(", ")}`;
	}
	return `Batches: ${names.slice(0, 4).join(", ")} +${names.length - 4}`;
});

const batchChipTitle = computed(() => {
	const list = sellableBatches.value;
	if (!list.length) return "";
	return list
		.slice(0, 6)
		.map((b) => `${b.batch_no} (${b.batch_qty || 0})`)
		.concat(list.length > 6 ? [`+${list.length - 6} more`] : [])
		.join(", ");
});

const onClick = (event) => emit("click", event, props.item);
const onDragStart = (event) => emit("dragstart", event, props.item);
const onDragEnd = (event) => emit("dragend", event);
</script>

<style scoped>
.pos-row-card {
	display: flex;
	align-items: center;
	gap: 12px;
	/* Extra vertical padding so the title has breathing room from the top
	   border and the content column reads as centred against the product
	   image. Horizontal padding stays moderate to preserve the stock-bar
	   width. */
	padding: 14px 16px 14px 14px;
	background: var(--pos-surface-raised);
	border: 1px solid var(--pos-border-light);
	border-radius: 12px;
	box-shadow: 0 3px 10px var(--pos-shadow-light);
	cursor: pointer;
	width: 100%;
	height: 100%;
	min-height: 72px;
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
	/* Slightly larger thumb (was 44px) so it matches the taller content
	   column and anchors the left edge of the card visually. */
	width: 48px;
	height: 48px;
	border-radius: 8px;
	overflow: hidden;
	background: var(--pos-surface-muted);
	border: 1px solid var(--pos-border-light);
}

.pos-row-card__image {
	width: 100%;
	height: 100%;
	object-fit: cover;
}

.pos-row-card__thumb--fallback {
	border: none;
}

.pos-row-card__fallback {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 100%;
	height: 100%;
	background: linear-gradient(135deg, #ec4899 0%, #be185d 55%, #9d174d 100%);
	color: #ffffff;
	box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18);
}

.pos-row-card__main {
	flex: 1 1 auto;
	min-width: 0;
	display: flex;
	flex-direction: column;
	/* Center the title / batch / meta rows inside the card so the block
	   reads as balanced against the product image. */
	justify-content: center;
	/* Slightly more air between rows — 3px pushed them into one dense
	   block; 6px lets each row breathe. */
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
	/* Reduced from 0.82rem/700 — the old size dominated the card and
	   pushed the price/qty visually back. 0.74rem with a 600 weight
	   reads as a confident label without shouting. */
	font-size: 0.74rem;
	font-weight: 600;
	line-height: 1.3;
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

/* Inline price now lives inside the meta row beside the NOS chip. */
.pos-row-card__price-inline {
	display: inline-flex;
	align-items: baseline;
	gap: 4px;
	flex: 0 0 auto;
	font-weight: 700;
	color: var(--pos-primary);
	white-space: nowrap;
	margin-left: 2px;
}

.pos-row-card__price-currency {
	font-size: 0.62rem;
	font-weight: 600;
	color: var(--pos-text-secondary);
	letter-spacing: 0.04em;
}

.pos-row-card__price-amount {
	/* Trimmed from 0.95rem — the price was reading bigger than the item
	   name after the name was reduced. 0.82rem keeps the orange accent
	   prominent without dominating. */
	font-size: 0.82rem;
	font-variant-numeric: tabular-nums;
}

.pos-row-card__price-secondary {
	font-size: 0.7rem;
	color: var(--pos-text-secondary);
	text-align: right;
}

/* Batch chip — Command Center pill: rounded edge box, tinted with the
   pink brand color so the cashier can spot batched items at a glance
   without the chip pulling focus from the stock progress bar. */
.pos-row-card__batch-row {
	display: flex;
	align-items: center;
	min-width: 0;
}

.pos-row-card__batch-chip {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	max-width: 100%;
	padding: 2px 8px;
	border-radius: 999px;
	/* CC green palette — green reads as "available batch info" and stops
	   competing visually with the red/pink "warning" badges elsewhere
	   in the dialog (e.g. shortage cards). */
	background: rgba(52, 178, 157, 0.14);
	color: var(--cc-green, #34b29d);
	border: 1px solid rgba(52, 178, 157, 0.3);
	font-size: 0.65rem;
	font-weight: 600;
	letter-spacing: 0.02em;
	line-height: 1.2;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.pos-row-card__batch-icon {
	opacity: 0.85;
}

.pos-row-card__batch-text {
	overflow: hidden;
	text-overflow: ellipsis;
}

@media (max-width: 768px) {
	.pos-row-card {
		gap: 10px;
		padding: 12px 12px 12px 10px;
		min-height: 68px;
	}
	.pos-row-card__thumb {
		width: 44px;
		height: 44px;
	}
	.pos-row-card__name {
		/* Slightly larger on touch devices so the tap target reads
		   clearly, but still well below the old 0.88rem. */
		font-size: 0.78rem;
	}
	.pos-row-card__price-amount {
		font-size: 0.84rem;
	}
	.pos-row-card__code {
		display: none;
	}
}
</style>
