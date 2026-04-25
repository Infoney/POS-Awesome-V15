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

				<template v-if="batchEntries.length">
					<span class="pos-cc-card__meta-sep">·</span>
					<span class="pos-cc-card__meta-item pos-cc-card__meta-item--batches" :title="batchChipTitle">
						<span class="pos-cc-card__meta-label">Batch:</span>
						<template v-for="(batch, idx) in batchEntries" :key="batch.batch_no">
							<span
								v-if="idx > 0"
								class="pos-cc-card__meta-batch-sep"
								aria-hidden="true"
								>,</span
							>
							<span class="pos-cc-card__meta-batch">
								<span class="pos-cc-card__meta-value pos-cc-card__meta-value--batch num">
									{{ batch.batch_no }}
								</span>
								<span v-if="batch.qtyLabel" class="pos-cc-card__meta-batch-qty num">
									({{ batch.qtyLabel }})
								</span>
							</span>
						</template>
						<span
							v-if="batchOverflowCount > 0"
							class="pos-cc-card__meta-batch-more num"
							:title="batchChipTitle"
						>
							+{{ batchOverflowCount }}
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

// Headline qty in the card.
//
// For batched items we prefer the **sum of non-expired, non-negative
// batches** over the bin-level `actual_qty`. The two sources can drift
// server-side (Bin running total vs Batch.batch_qty) — e.g. item 10105
// shows -3 in the Bin column but the Batch table reports a single
// non-expired batch with qty 3. The number that actually matters at
// sale time is per-batch (each invoice line picks one and ERPNext
// validates that batch on submit), so the bin total is misleading.
// Showing the sum of batches matches the tooltip's "Available stock"
// figure and aligns the table A.QTY with what cashiers can actually
// sell. Falls back to `actual_qty` for non-batched items.
const numericQty = computed(() => {
	const item = props.item;
	const batches = Array.isArray(item?.batch_no_data) ? item.batch_no_data : [];
	if (batches.length) {
		let sum = 0;
		batches.forEach((batch) => {
			if (!batch || batch.is_expired) return;
			const qty = Number(batch.batch_qty ?? 0);
			if (Number.isFinite(qty) && qty > 0) {
				sum += qty;
			}
		});
		return sum;
	}
	const n = Number(item?.actual_qty ?? 0);
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

// Progress bar width. Floored at 8% so the bar is always visible — a
// qty of 1 or an edge case still renders a readable sliver rather than
// "no bar at all" (the user called this out on the 37-qty card).
const stockFillPercent = computed(() => {
	const qty = numericQty.value;
	let pct;
	if (qty <= 0) pct = 8;
	else if (qty >= 100) pct = 100;
	else if (qty >= 20) pct = 70 + Math.min(30, (qty - 20) * 0.375);
	else if (qty >= 5) pct = 35 + (qty - 5) * (35 / 15);
	else pct = 12 + qty * (22 / 5);
	return Math.max(8, Math.min(100, pct));
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

// Show up to this many batches inline on the card. Anything beyond
// shows as "+N" and the full list lives in the tooltip. Two batches
// read comfortably even on the 180 px narrow breakpoint; three starts
// crowding the SKU/Qty row so we cap there.
const MAX_INLINE_BATCHES = 3;

const formatBatchQty = (raw) => {
	const num = Number(raw);
	if (!Number.isFinite(num)) return "";
	if (props.hideQtyDecimals) {
		return props.formatNumber(Math.round(num), 0);
	}
	return props.formatNumber(num, 4);
};

// Each entry is { batch_no, qtyLabel } already formatted for display.
// Sorted by sellableBatches (the existing filter keeps only non-expired
// rows with qty > 0). The user's request: show all batches with their
// qty, not just "VJ5737 +1 (1)".
const batchEntries = computed(() => {
	const list = sellableBatches.value;
	if (!list.length) return [];
	return list.slice(0, MAX_INLINE_BATCHES).map((b) => ({
		batch_no: b.batch_no,
		qtyLabel: formatBatchQty(b.batch_qty),
	}));
});

const batchOverflowCount = computed(() => {
	const total = sellableBatches.value.length;
	return total > MAX_INLINE_BATCHES ? total - MAX_INLINE_BATCHES : 0;
});

const batchChipTitle = computed(() => {
	const list = sellableBatches.value;
	if (!list.length) return "";
	return list
		.map((b) => `${b.batch_no} (${formatBatchQty(b.batch_qty) || 0})`)
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
	align-items: center; /* was stretch — kept body from over-clipping the bar */
	gap: 14px;
	width: 100%;
	height: 100%;
	padding: 12px 16px 12px 16px;
	/* Lifted surface — solid gradient so the card sits visibly above the
	   panel (panel is --cc-bg ≈ #0e121b; card top is ~#1c2334 so the
	   delta is clearly readable, matching the "Veriality"-style visual
	   separation the user asked for). */
	background: linear-gradient(180deg, #1c2334 0%, #161d2c 100%);
	border: 1px solid rgba(255, 255, 255, 0.04);
	border-radius: 12px;
	box-shadow:
		0 1px 0 rgba(255, 255, 255, 0.02) inset,
		0 2px 8px rgba(0, 0, 0, 0.35);
	cursor: pointer;
	overflow: hidden;
	transition:
		border-color var(--cc-ease-base, 220ms ease-out),
		background-color var(--cc-ease-base, 220ms ease-out),
		transform var(--cc-ease-base, 220ms ease-out),
		box-shadow var(--cc-ease-base, 220ms ease-out);
}

/* Light theme: flip the lifted surface to a soft off-white so the card
   pops from the light panel the same way it does on dark. */
:deep([data-theme="light"]) .pos-cc-card,
:deep(.v-theme--light) .pos-cc-card,
[data-theme="light"] .pos-cc-card,
.v-theme--light .pos-cc-card {
	background: linear-gradient(180deg, #ffffff 0%, #f4f7fb 100%);
	border-color: rgba(15, 23, 42, 0.08);
	box-shadow:
		0 1px 0 rgba(255, 255, 255, 1) inset,
		0 2px 6px rgba(15, 23, 42, 0.08);
}

/* Tier-coloured left stripe. Widened from 3 → 5 px so the rounded top/
   bottom-left corners (clipped by the card's overflow + border-radius)
   actually read as rounded. Shares its gradient with the progress bar
   via the paired tier-start / tier-end custom props so the stripe and
   bar always carry the same tier colour. */
.pos-cc-card::before {
	content: "";
	position: absolute;
	top: 0;
	bottom: 0;
	left: 0;
	width: 5px;
	background: linear-gradient(
		180deg,
		var(--tier-start, #64748b),
		var(--tier-end, #94a3b8)
	);
	pointer-events: none;
}

/* Tier palette — user requested: green=good, orange=mid, red=low.
   The same (start, end) pair feeds the left stripe (vertical) and the
   body progress bar (horizontal) so they read as one unit. */
.pos-cc-card--ok {
	--tier-start: #16a34a;
	--tier-end: #22c55e;
}
.pos-cc-card--low {
	--tier-start: #ea580c;
	--tier-end: #f97316;
}
.pos-cc-card--critical {
	--tier-start: #dc2626;
	--tier-end: #ef4444;
}
.pos-cc-card--out {
	--tier-start: #475569;
	--tier-end: #64748b;
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
	/* Muted slate gradient — the previous bright pink thumbnail screen
	   was fatiguing across a long items list. Dark slate is neutral and
	   eye-relaxing while still giving the icon enough contrast. */
	background: linear-gradient(135deg, #3b4763 0%, #2a3550 55%, #1e2740 100%);
	color: rgba(255, 255, 255, 0.78);
	box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

/* ─── Body (title / meta / bar) ───────────────────────────────────────── */
.pos-cc-card__body {
	flex: 1 1 auto;
	min-width: 0;
	display: flex;
	flex-direction: column;
	justify-content: center;
	gap: 5px;
}

/* The info-menu triggers inside the meta row default to Vuetify's
   x-small button size, which is ~24–28 px tall and was inflating the
   meta row enough to push the progress bar out of the card's visible
   area on items that carry a batch. Constrain them to the baseline of
   the surrounding text so the row height is governed by the label. */
.pos-cc-card :deep(.item-stock-info-trigger),
.pos-cc-card :deep(.item-rate-info-trigger) {
	width: 18px !important;
	height: 18px !important;
	min-width: 18px !important;
	min-height: 18px !important;
	padding: 0 !important;
	margin: 0 0 0 2px !important;
}

.pos-cc-card :deep(.item-stock-info-trigger .v-icon),
.pos-cc-card :deep(.item-rate-info-trigger .v-icon) {
	font-size: 14px !important;
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

/* Multiple batches flow inline, each as "CODE (qty)" separated by a
   thin comma. Wrap allowed so a 3-batch row can stretch onto a second
   line rather than clipping the last entry. */
.pos-cc-card__meta-item--batches {
	flex-wrap: wrap;
	row-gap: 2px;
}

.pos-cc-card__meta-batch {
	display: inline-flex;
	align-items: baseline;
	gap: 3px;
}

.pos-cc-card__meta-batch-sep {
	color: var(--cc-subtle, var(--pos-text-disabled, #4a5568));
	opacity: 0.7;
	margin: 0 1px 0 -1px;
}

.pos-cc-card__meta-batch-more {
	color: var(--cc-orange, #f46a25);
	font-weight: 700;
	font-size: 0.62rem;
	padding: 1px 6px;
	border-radius: 999px;
	background: rgba(244, 106, 37, 0.12);
	border: 1px solid rgba(244, 106, 37, 0.25);
	margin-left: 2px;
}

/* ─── Progress bar (CC "Top-selling items" style) ─────────────────────── */
.pos-cc-card__track {
	position: relative;
	height: 6px;
	width: 100%;
	background: rgba(148, 163, 184, 0.16);
	border-radius: 999px;
	overflow: hidden;
}

.pos-cc-card__track-fill {
	display: block;
	height: 100%;
	/* Shares the tier-start/end pair with the left stripe so the two
	   always match (green / orange / red / grey). Minimum width of 4%
	   is enforced at the computed level so the bar is always visible,
	   even for 1-qty items. */
	background: linear-gradient(
		90deg,
		var(--tier-start, #64748b),
		var(--tier-end, #94a3b8)
	);
	border-radius: inherit;
	transition: width 0.3s ease;
	box-shadow: 0 0 10px rgba(var(--cc-pink-rgb, 226, 54, 112), 0.05);
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
