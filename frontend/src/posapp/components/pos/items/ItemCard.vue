<template>
	<!--
		Command Center-aligned item card (exact match to the reference card the
		user attached). Layout:

		  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
		  ┃ Item name …                                                    ┃
		  ┃ SKU HC-0001   Barcode 4055482236030                            ┃
		  ┃ Qty: 18   ·   Batch: B-01   ·   $ 25.00                        ┃
		  ┃ ▬▬▬▬▬▬▬▬▬▬▬▬▬▬                                                  ┃  <- thin progress bar
		  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
		    ↑ left pink accent stripe (full height)

		The reference has no product thumbnail and no "forecast" pill. Per the
		user's most recent message, we drop "Sold 30d", "X/day" and "~Nd left"
		and reuse that space for the unit price. Batch gets the cyan (blue)
		position that `/day` occupied in the reference; price takes the pink
		`~1.8d left` position so the pink brand tone still anchors the end of
		the stat row.
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
		<h4 class="pos-cc-card__name" :title="item.item_name">
			{{ item.item_name }}
		</h4>

		<div class="pos-cc-card__ids">
			<span v-if="item.item_code" class="pos-cc-card__id-item" :title="item.item_code">
				<span class="pos-cc-card__id-label">SKU</span>
				<span class="pos-cc-card__id-value pos-cc-card__id-value--sku num">
					{{ item.item_code }}
				</span>
			</span>
			<span v-if="barcodeValue" class="pos-cc-card__id-item" :title="barcodeValue">
				<span class="pos-cc-card__id-label">Barcode</span>
				<span class="pos-cc-card__id-value pos-cc-card__id-value--barcode num">
					{{ barcodeValue }}
				</span>
			</span>
		</div>

		<div class="pos-cc-card__stats">
			<span class="pos-cc-card__stat" :title="stockTooltip">
				<span class="pos-cc-card__stat-label">Qty:</span>
				<span
					class="pos-cc-card__stat-value pos-cc-card__stat-value--qty num"
					:class="{ 'pos-cc-card__stat-value--negative': isNegative(item.actual_qty) }"
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

			<span v-if="batchInline" class="pos-cc-card__stat-sep">·</span>
			<span v-if="batchInline" class="pos-cc-card__stat" :title="batchChipTitle">
				<span class="pos-cc-card__stat-label">Batch:</span>
				<span class="pos-cc-card__stat-value pos-cc-card__stat-value--batch num">
					{{ batchInline }}
				</span>
			</span>

			<span class="pos-cc-card__stat-sep">·</span>

			<span class="pos-cc-card__stat pos-cc-card__stat--price">
				<span class="pos-cc-card__price-currency">
					{{ currencySymbol(primaryCurrency) }}
				</span>
				<span class="pos-cc-card__stat-value pos-cc-card__stat-value--price num">
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

		<div v-if="showSecondaryPrice" class="pos-cc-card__price-secondary">
			{{ currencySymbol(secondaryCurrency) }}
			{{ formatCurrency(item.rate, secondaryCurrency, primaryPrecision) }}
		</div>

		<span class="pos-cc-card__track" :title="stockTooltip">
			<span
				class="pos-cc-card__track-fill"
				:style="{ width: stockFillPercent + '%' }"
			></span>
		</span>
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

// Barcode surfaces the first usable value from the item. Different pipelines
// expose it differently (legacy Frappe: `item_barcode` / `barcode`, newer:
// an array of `{barcode}` rows), so we try each in turn.
const barcodeValue = computed(() => {
	const it = props.item || {};
	if (it.item_barcode) return String(it.item_barcode);
	if (it.barcode) return String(it.barcode);
	if (Array.isArray(it.item_barcodes) && it.item_barcodes.length) {
		return String(it.item_barcodes[0]?.barcode || "");
	}
	if (Array.isArray(it.barcodes) && it.barcodes.length) {
		return String(it.barcodes[0]?.barcode || "");
	}
	return "";
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

const stockTierClass = computed(() => `pos-cc-card--${stockTier.value}`);

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

// Compact inline batch label for the Qty/Batch/Price stat strip.
// - 0 batches → empty (the whole Batch segment collapses)
// - 1 batch   → the batch number
// - 2+        → first batch number + "+N" tail indicator
const batchInline = computed(() => {
	const item = props.item;
	if (!item || !item.has_batch_no) return "";
	const list = sellableBatches.value;
	if (!list.length) return "";
	if (list.length === 1) return list[0].batch_no;
	return `${list[0].batch_no} +${list.length - 1}`;
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
	flex-direction: column;
	gap: 6px;
	width: 100%;
	height: 100%;
	min-height: 96px;
	/* Extra left padding reserves space for the pink accent stripe that
	   runs full-height on the left edge (matches the reference card). */
	padding: 12px 14px 14px 16px;
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

/* Full-height pink gradient stripe on the left edge — the single dominant
   accent in the CC reference. Tier variants shift the gradient to orange
   / muted so the cashier reads stock health at a glance. */
.pos-cc-card::before {
	content: "";
	position: absolute;
	top: 0;
	bottom: 0;
	left: 0;
	width: 4px;
	background: linear-gradient(180deg, var(--cc-pink, #e23670), var(--cc-orange, #f46a25));
	border-top-left-radius: inherit;
	border-bottom-left-radius: inherit;
	pointer-events: none;
}

.pos-cc-card--ok::before {
	background: linear-gradient(180deg, var(--cc-pink, #e23670), var(--cc-orange, #f46a25));
}
.pos-cc-card--low::before {
	background: linear-gradient(180deg, var(--cc-orange, #f46a25), #fbbf24);
}
.pos-cc-card--critical::before {
	background: linear-gradient(180deg, var(--cc-pink, #e23670), var(--cc-orange, #f46a25));
}
.pos-cc-card--out::before {
	background: linear-gradient(180deg, #4a5568, #7b899d);
	opacity: 0.7;
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

/* ─── Title ──────────────────────────────────────────────────────────── */
.pos-cc-card__name {
	margin: 0;
	font-size: 0.95rem;
	font-weight: 700;
	line-height: 1.2;
	color: var(--pos-text-primary, var(--cc-text, #edf2f7));
	letter-spacing: -0.01em;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

/* ─── SKU / Barcode row ─────────────────────────────────────────────── */
.pos-cc-card__ids {
	display: flex;
	align-items: baseline;
	gap: 14px;
	min-width: 0;
	font-size: 0.72rem;
	line-height: 1.2;
	color: var(--pos-text-secondary, var(--cc-muted, #7b899d));
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.pos-cc-card__id-item {
	display: inline-flex;
	align-items: baseline;
	gap: 6px;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
}

.pos-cc-card__id-label {
	color: var(--cc-muted, var(--pos-text-secondary, #7b899d));
	font-weight: 500;
}

.pos-cc-card__id-value {
	font-weight: 700;
	letter-spacing: 0.01em;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

/* SKU value gets the pink brand colour — mirrors the reference card's
   `HC-00002045` treatment. */
.pos-cc-card__id-value--sku {
	color: var(--cc-pink, var(--pos-secondary, #e23670));
}

/* Barcode uses the text-primary colour so it reads as a neutral identifier
   next to the pink SKU. */
.pos-cc-card__id-value--barcode {
	color: var(--pos-text-primary, var(--cc-text, #edf2f7));
}

/* ─── Qty / Batch / Price stat strip ────────────────────────────────── */
.pos-cc-card__stats {
	display: flex;
	align-items: baseline;
	gap: 10px;
	flex-wrap: wrap;
	font-size: 0.78rem;
	color: var(--pos-text-secondary, var(--cc-muted, #7b899d));
	min-width: 0;
}

.pos-cc-card__stat {
	display: inline-flex;
	align-items: baseline;
	gap: 4px;
	min-width: 0;
	white-space: nowrap;
}

.pos-cc-card__stat--price {
	margin-left: auto;
}

.pos-cc-card__stat-label {
	color: var(--cc-muted, var(--pos-text-secondary, #7b899d));
	font-weight: 500;
}

.pos-cc-card__stat-sep {
	color: var(--cc-subtle, var(--pos-text-disabled, #4a5568));
	font-weight: 500;
	opacity: 0.8;
}

.pos-cc-card__stat-value {
	font-weight: 700;
	letter-spacing: -0.01em;
}

/* Qty: bold white numeric — dominant stat, matches the reference "18". */
.pos-cc-card__stat-value--qty {
	color: var(--pos-text-primary, var(--cc-text, #edf2f7));
	font-size: 0.9rem;
}

.pos-cc-card__stat-value--negative {
	color: rgb(var(--v-theme-error));
}

/* Batch occupies the cyan slot the reference used for `9.7/day`. Blue is
   the CC palette's "informational" accent — reads as a neutral metric
   rather than a warning. */
.pos-cc-card__stat-value--batch {
	color: var(--cc-blue, #60a5fa);
}

/* Price takes the pink accent slot the reference gave to `~1.8d left` so
   the warm brand tone anchors the right side of the stat strip. */
.pos-cc-card__stat-value--price {
	color: var(--cc-pink, var(--pos-secondary, #e23670));
	font-size: 0.92rem;
}

.pos-cc-card__price-currency {
	font-size: 0.62rem;
	font-weight: 600;
	color: var(--cc-muted, var(--pos-text-secondary, #7b899d));
	letter-spacing: 0.05em;
	text-transform: uppercase;
	margin-right: 2px;
}

.pos-cc-card__price-secondary {
	font-size: 0.68rem;
	color: var(--cc-muted, var(--pos-text-secondary, #7b899d));
	text-align: right;
	font-variant-numeric: tabular-nums;
}

/* ─── Bottom progress bar ───────────────────────────────────────────── */
.pos-cc-card__track {
	display: block;
	position: absolute;
	left: 0;
	right: 0;
	bottom: 0;
	height: 3px;
	background: rgba(148, 163, 184, 0.14);
	overflow: hidden;
	border-bottom-left-radius: 12px;
	border-bottom-right-radius: 12px;
}

.pos-cc-card__track-fill {
	display: block;
	height: 100%;
	border-radius: inherit;
	transition: width 0.25s ease;
}

.pos-cc-card--ok .pos-cc-card__track-fill {
	background: linear-gradient(90deg, var(--cc-pink, #e23670), var(--cc-orange, #f46a25));
}
.pos-cc-card--low .pos-cc-card__track-fill {
	background: linear-gradient(90deg, var(--cc-orange, #f46a25), #fbbf24);
}
.pos-cc-card--critical .pos-cc-card__track-fill {
	background: linear-gradient(90deg, var(--cc-pink, #e23670), var(--cc-orange, #f46a25));
}
.pos-cc-card--out .pos-cc-card__track-fill {
	background: linear-gradient(90deg, #4a5568, #7b899d);
	opacity: 0.6;
}

/* ─── Mobile sizing ───────────────────────────────────────────────── */
@media (max-width: 768px) {
	.pos-cc-card {
		padding: 10px 12px 12px 14px;
		min-height: 92px;
		gap: 5px;
	}
	.pos-cc-card__name {
		font-size: 0.88rem;
	}
	.pos-cc-card__ids {
		font-size: 0.68rem;
		gap: 10px;
	}
	.pos-cc-card__stats {
		font-size: 0.74rem;
		gap: 8px;
	}
	.pos-cc-card__stat-value--qty {
		font-size: 0.84rem;
	}
	.pos-cc-card__stat-value--price {
		font-size: 0.88rem;
	}
}
</style>
