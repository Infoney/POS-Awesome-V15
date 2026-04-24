<template>
	<!--
		POS item card, modelled on the Command Center "Top-Selling Items"
		card the user attached. Layout:

		┌───────────────────────────────────────────────────────────┐
		│ ┌────┐  Item name                              KWD 12.36 │
		│ │IMG │  SKU 30643  ·  Qty: 3  ·  Batch: VJ5737 (1)       │
		│ └────┘  ▓▓▓▓▓▓▓▓░░░░░░░░░░░░░░░░░░░░░░░░░░░░               │
		└───────────────────────────────────────────────────────────┘

		  · Big product thumbnail on the left (was 28px — now 56/60px so the
		    image reads first, as in the CC reference card).
		  · Title + price share a row (price right-aligned in bold white).
		  · SKU, Qty and Batch collapse into a single inline meta row (was
		    two separate rows).
		  · Prominent rounded progress bar sits inside the body flow, not
		    pinned to the card's bottom edge — mirrors CC's "6 sold" bar.
	-->
	<div
		:class="[
			'pos-cc-card',
			stockTierClass,
			{ 'pos-cc-card--highlighted': isItemHighlighted },
		]"
		@click="onClick"
		:draggable="true"
		@dragstart="onDragStart"
		@dragend="onDragEnd"
	>
		<div class="pos-cc-card__thumb" :class="{ 'pos-cc-card__thumb--fallback': !item.image }">
			<v-img
				v-if="item.image"
				:src="item.image"
				class="pos-cc-card__image"
				aspect-ratio="1"
				:alt="item.item_name"
				cover
			>
				<template #placeholder>
					<div class="pos-cc-card__fallback">
						<v-icon size="20" color="white">mdi-image-outline</v-icon>
					</div>
				</template>
			</v-img>
			<div v-else class="pos-cc-card__fallback" :aria-label="item.item_name">
				<v-icon size="22" color="white">mdi-cube-outline</v-icon>
			</div>
		</div>

		<div class="pos-cc-card__body">
			<div class="pos-cc-card__title-row">
				<h4 class="pos-cc-card__name" :title="item.item_name">
					{{ item.item_name }}
				</h4>
				<span class="pos-cc-card__price">
					<span class="pos-cc-card__price-currency">
						{{ currencySymbol(primaryCurrency) }}
					</span>
					<span class="pos-cc-card__price-amount num">
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

			<div class="pos-cc-card__meta">
				<span v-if="item.item_code" class="pos-cc-card__meta-item" :title="item.item_code">
					<span class="pos-cc-card__meta-label">SKU</span>
					<span class="pos-cc-card__meta-value pos-cc-card__meta-value--sku num">
						{{ item.item_code }}
					</span>
				</span>

				<span v-if="item.item_code" class="pos-cc-card__meta-sep">·</span>

				<span class="pos-cc-card__meta-item" :title="stockTooltip">
					<span class="pos-cc-card__meta-label">Qty:</span>
					<span
						class="pos-cc-card__meta-value pos-cc-card__meta-value--qty num"
						:class="{ 'pos-cc-card__meta-value--negative': isNegative(item.actual_qty) }"
					>
						{{ formattedActualQty }}
					</span>
					<ItemStockInfoMenu
						v-if="showStockInfo"
						:item="item"
						:pos-profile="posProfile"
						:format-number="formatNumber"
						:hide-qty-decimals="hideQtyDecimals"
					/>
				</span>

				<template v-if="batchInlineText">
					<span class="pos-cc-card__meta-sep">·</span>
					<span class="pos-cc-card__meta-item" :title="batchChipTitle">
						<span class="pos-cc-card__meta-label">Batch:</span>
						<span class="pos-cc-card__meta-value pos-cc-card__meta-value--batch num">
							{{ batchInlineText }}
						</span>
						<span v-if="batchInlineQty" class="pos-cc-card__meta-batch-qty num">
							({{ batchInlineQty }})
						</span>
					</span>
				</template>
			</div>

			<div class="pos-cc-card__track" :title="stockTooltip">
				<span
					class="pos-cc-card__track-fill"
					:style="{ width: stockFillPercent + '%' }"
				></span>
			</div>

			<div v-if="showSecondaryPrice" class="pos-cc-card__price-secondary">
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

const stockTier = computed(() => {
	const qty = numericQty.value;
	if (qty <= 0) return "out";
	if (qty < 5) return "critical";
	if (qty < 20) return "low";
	return "ok";
});

const stockTierClass = computed(() => `pos-cc-card--${stockTier.value}`);

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

const leadBatch = computed(() => sellableBatches.value[0] || null);

const batchInlineText = computed(() => {
	const item = props.item;
	if (!item || !item.has_batch_no) return "";
	const list = sellableBatches.value;
	if (!list.length) return "";
	if (list.length === 1) return list[0].batch_no;
	return `${list[0].batch_no} +${list.length - 1}`;
});

const batchInlineQty = computed(() => {
	const b = leadBatch.value;
	if (!b) return "";
	const raw = Number(b.batch_qty);
	if (!Number.isFinite(raw)) return "";
	if (props.hideQtyDecimals) {
		return props.formatNumber(Math.round(raw), 0);
	}
	return props.formatNumber(raw, 4);
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
/* ─── Card shell ──────────────────────────────────────────────────────── */
.pos-cc-card {
	position: relative;
	display: flex;
	align-items: stretch;
	gap: 14px;
	width: 100%;
	height: 100%;
	padding: 12px 16px 12px 14px;
	background: var(--pos-surface-raised, var(--cc-bg-card, rgba(22, 28, 39, 0.8)));
	border: 1px solid var(--pos-border-light, var(--cc-border, #252b37));
	border-radius: 12px;
	box-shadow: var(--cc-shadow-sm, 0 2px 6px rgba(0, 0, 0, 0.08));
	cursor: pointer;
	overflow: hidden;
	transition:
		border-color var(--cc-ease-base, 220ms ease-out),
		background-color var(--cc-ease-base, 220ms ease-out),
		transform var(--cc-ease-base, 220ms ease-out),
		box-shadow var(--cc-ease-base, 220ms ease-out);
}

/* Slim tier-coloured stripe on the left edge — kept as a stock-health
   glance cue; doesn't fight the prominent progress bar in the body. */
.pos-cc-card::before {
	content: "";
	position: absolute;
	top: 0;
	bottom: 0;
	left: 0;
	width: 3px;
	background: var(--row-accent, #64748b);
	pointer-events: none;
}

.pos-cc-card--ok {
	--row-accent: #22c55e;
	--row-bar: linear-gradient(90deg, var(--cc-pink, #e23670), var(--cc-orange, #f46a25));
}
.pos-cc-card--low {
	--row-accent: #f59e0b;
	--row-bar: linear-gradient(90deg, #f59e0b, #fbbf24);
}
.pos-cc-card--critical {
	--row-accent: #ef4444;
	--row-bar: linear-gradient(90deg, #ef4444, #f97316);
}
.pos-cc-card--out {
	--row-accent: #64748b;
	--row-bar: linear-gradient(90deg, #64748b, #94a3b8);
}

.pos-cc-card:hover {
	border-color: var(--cc-border-hover, rgba(var(--v-theme-primary), 0.35));
	transform: translateY(-1px);
	box-shadow: var(--cc-shadow-md, 0 10px 22px var(--pos-shadow, rgba(0, 0, 0, 0.2)));
}

.pos-cc-card--highlighted {
	border-color: rgb(var(--v-theme-primary));
	background: rgba(var(--v-theme-primary), 0.08);
	box-shadow:
		0 0 0 2px rgba(var(--v-theme-primary), 0.3),
		var(--cc-shadow-md, 0 10px 22px rgba(var(--v-theme-primary), 0.18));
}

/* ─── Product thumbnail ───────────────────────────────────────────────── */
.pos-cc-card__thumb {
	flex: 0 0 auto;
	align-self: center;
	/* Big thumb, matching the "Complete Hair Revival Set" proportions in
	   the CC reference. Was 28px before — the image now reads first. */
	width: 60px;
	height: 60px;
	border-radius: 10px;
	overflow: hidden;
	background: var(--pos-surface-muted, var(--cc-bg-ter, #1f2533));
	border: 1px solid var(--pos-border-light, var(--cc-border, #252b37));
	display: flex;
	align-items: center;
	justify-content: center;
}

.pos-cc-card__image {
	width: 100%;
	height: 100%;
	object-fit: cover;
}

.pos-cc-card__thumb--fallback {
	border: none;
}

.pos-cc-card__fallback {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 100%;
	height: 100%;
	background: linear-gradient(135deg, #ec4899 0%, #be185d 55%, #9d174d 100%);
	color: #ffffff;
	box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18);
}

/* ─── Body (title / meta / bar) ───────────────────────────────────────── */
.pos-cc-card__body {
	flex: 1 1 auto;
	min-width: 0;
	display: flex;
	flex-direction: column;
	justify-content: center;
	gap: 6px;
}

.pos-cc-card__title-row {
	display: flex;
	align-items: baseline;
	justify-content: space-between;
	gap: 12px;
	min-width: 0;
}

.pos-cc-card__name {
	margin: 0;
	font-size: 0.88rem;
	font-weight: 700;
	line-height: 1.2;
	color: var(--pos-text-primary, var(--cc-text, #edf2f7));
	letter-spacing: -0.01em;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	min-width: 0;
	flex: 1 1 auto;
}

/* Price is bold white, sized to pair with the title. Matches the CC
   reference's "KWD 279" treatment — not orange, not pink, clean white. */
.pos-cc-card__price {
	display: inline-flex;
	align-items: baseline;
	gap: 3px;
	flex: 0 0 auto;
	color: var(--pos-text-primary, var(--cc-text, #edf2f7));
	font-weight: 700;
	white-space: nowrap;
}

.pos-cc-card__price-currency {
	font-size: 0.62rem;
	font-weight: 700;
	color: var(--cc-muted, var(--pos-text-secondary, #7b899d));
	letter-spacing: 0.06em;
	text-transform: uppercase;
}

.pos-cc-card__price-amount {
	font-size: 0.88rem;
	font-weight: 800;
	letter-spacing: -0.01em;
}

/* ─── Meta row (SKU · Qty · Batch) ────────────────────────────────────── */
.pos-cc-card__meta {
	display: flex;
	align-items: baseline;
	gap: 6px;
	flex-wrap: wrap;
	font-size: 0.68rem;
	color: var(--pos-text-secondary, var(--cc-muted, #7b899d));
	min-width: 0;
}

.pos-cc-card__meta-item {
	display: inline-flex;
	align-items: baseline;
	gap: 4px;
	min-width: 0;
	white-space: nowrap;
}

.pos-cc-card__meta-label {
	color: var(--cc-muted, var(--pos-text-secondary, #7b899d));
	font-weight: 500;
}

.pos-cc-card__meta-sep {
	color: var(--cc-subtle, var(--pos-text-disabled, #4a5568));
	opacity: 0.7;
	font-weight: 500;
}

.pos-cc-card__meta-value {
	font-weight: 700;
	letter-spacing: -0.005em;
}

.pos-cc-card__meta-value--sku {
	color: var(--pos-text-secondary, var(--cc-muted, #7b899d));
	font-weight: 600;
}

.pos-cc-card__meta-value--qty {
	color: var(--pos-text-primary, var(--cc-text, #edf2f7));
}

.pos-cc-card__meta-value--negative {
	color: rgb(var(--v-theme-error));
}

.pos-cc-card__meta-value--batch {
	color: var(--cc-green, #34b29d);
}

.pos-cc-card__meta-batch-qty {
	color: var(--cc-subtle, var(--pos-text-disabled, #4a5568));
	font-weight: 600;
	font-size: 0.64rem;
}

/* ─── Progress bar (CC "Top-selling items" style) ─────────────────────── */
.pos-cc-card__track {
	position: relative;
	height: 5px;
	width: 100%;
	background: rgba(148, 163, 184, 0.14);
	border-radius: 999px;
	overflow: hidden;
}

.pos-cc-card__track-fill {
	display: block;
	height: 100%;
	background: var(--row-bar, linear-gradient(90deg, var(--cc-pink, #e23670), var(--cc-orange, #f46a25)));
	border-radius: inherit;
	transition: width 0.3s ease;
}

/* ─── Secondary price (multi-currency) ────────────────────────────────── */
.pos-cc-card__price-secondary {
	font-size: 0.62rem;
	color: var(--cc-muted, var(--pos-text-secondary, #7b899d));
	text-align: right;
	font-variant-numeric: tabular-nums;
}

/* ─── Breakpoints ─────────────────────────────────────────────────────── */
@media (max-width: 1200px) {
	.pos-cc-card {
		padding: 10px 14px 10px 13px;
		gap: 12px;
	}
	.pos-cc-card__thumb {
		width: 54px;
		height: 54px;
	}
	.pos-cc-card__name,
	.pos-cc-card__price-amount {
		font-size: 0.84rem;
	}
}

@media (max-width: 768px) {
	.pos-cc-card {
		padding: 8px 12px 8px 11px;
		gap: 10px;
		border-radius: 10px;
	}
	.pos-cc-card__thumb {
		width: 46px;
		height: 46px;
		border-radius: 8px;
	}
	.pos-cc-card__name,
	.pos-cc-card__price-amount {
		font-size: 0.8rem;
	}
	.pos-cc-card__meta {
		font-size: 0.62rem;
	}
	.pos-cc-card__track {
		height: 4px;
	}
}
</style>
