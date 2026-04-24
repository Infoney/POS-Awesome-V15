<template>
	<!--
		Compact Command Center-style item card.

		Layout (top → bottom):
		  1. Header row: product thumbnail + title + (stock-tier)
		  2. SKU row (barcode removed per request — it only rendered "[object
		     Object]" because backend barcodes arrive as an array of rows)
		  3. Stats row: Qty total + stock uom · Batch number + batch qty · price
		  4. Thin tier-colored progress bar pinned to the bottom edge

		A 4px solid tier-colored stripe runs down the left edge. The card is
		sized to fit inside the virtual-scroller slot (see
		`useItemSelectorLayout.ts`) — every row lives on its own so no two
		cards can visually overlap.
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
		<div class="pos-cc-card__header">
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
							<v-icon size="14" color="white">mdi-image-outline</v-icon>
						</div>
					</template>
				</v-img>
				<div v-else class="pos-cc-card__fallback" :aria-label="item.item_name">
					<v-icon size="14" color="white">mdi-cube-outline</v-icon>
				</div>
			</div>
			<h4 class="pos-cc-card__name" :title="item.item_name">
				{{ item.item_name }}
			</h4>
		</div>

		<div class="pos-cc-card__ids" v-if="item.item_code">
			<span class="pos-cc-card__id-item" :title="item.item_code">
				<span class="pos-cc-card__id-label">SKU</span>
				<span class="pos-cc-card__id-value num">{{ item.item_code }}</span>
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
				<span v-if="item.stock_uom" class="pos-cc-card__stat-unit">
					{{ item.stock_uom }}
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
				<span class="pos-cc-card__stat-sep">·</span>
				<span class="pos-cc-card__stat" :title="batchChipTitle">
					<span class="pos-cc-card__stat-label">Batch:</span>
					<span class="pos-cc-card__stat-value pos-cc-card__stat-value--batch num">
						{{ batchInlineText }}
					</span>
					<span
						v-if="batchInlineQty"
						class="pos-cc-card__stat-batch-qty num"
					>
						({{ batchInlineQty }})
					</span>
				</span>
			</template>

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

// Lead batch = the first sellable batch. Used for the inline label.
const leadBatch = computed(() => sellableBatches.value[0] || null);

const batchInlineText = computed(() => {
	const item = props.item;
	if (!item || !item.has_batch_no) return "";
	const list = sellableBatches.value;
	if (!list.length) return "";
	if (list.length === 1) return list[0].batch_no;
	return `${list[0].batch_no} +${list.length - 1}`;
});

// Qty in the lead batch. Only rendered when we have a finite number — the
// "Qty:" total already covers the aggregate stock; this gives the cashier
// the per-batch qty alongside the batch identifier.
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
	flex-direction: column;
	gap: 4px;
	width: 100%;
	height: 100%;
	padding: 8px 12px 12px 14px;
	background: var(--pos-surface-raised, var(--cc-bg-card, rgba(22, 28, 39, 0.8)));
	border: 1px solid var(--pos-border-light, var(--cc-border, #252b37));
	border-radius: 10px;
	box-shadow: var(--cc-shadow-sm, 0 2px 6px rgba(0, 0, 0, 0.08));
	cursor: pointer;
	overflow: hidden;
	transition:
		border-color var(--cc-ease-base, 220ms ease-out),
		background-color var(--cc-ease-base, 220ms ease-out),
		transform var(--cc-ease-base, 220ms ease-out),
		box-shadow var(--cc-ease-base, 220ms ease-out);
}

/* Solid tier-colored stripe on the left edge (reverted from the
   pink→orange gradient — the user asked to bring back the legacy tier
   colours so low / critical / out are readable at a glance). */
.pos-cc-card::before {
	content: "";
	position: absolute;
	top: 0;
	bottom: 0;
	left: 0;
	width: 4px;
	background: var(--row-accent, #64748b);
	border-top-left-radius: inherit;
	border-bottom-left-radius: inherit;
	pointer-events: none;
}

.pos-cc-card--ok {
	--row-accent: #22c55e;
	--row-bar: linear-gradient(90deg, #22c55e, #4ade80);
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

/* ─── Header (thumb + title) ──────────────────────────────────────────── */
.pos-cc-card__header {
	display: flex;
	align-items: center;
	gap: 8px;
	min-width: 0;
}

.pos-cc-card__thumb {
	flex: 0 0 auto;
	width: 28px;
	height: 28px;
	border-radius: 6px;
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

.pos-cc-card__name {
	margin: 0;
	font-size: 0.76rem;
	font-weight: 700;
	line-height: 1.2;
	color: var(--pos-text-primary, var(--cc-text, #edf2f7));
	letter-spacing: -0.005em;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	min-width: 0;
	flex: 1 1 auto;
}

/* ─── SKU row ─────────────────────────────────────────────────────────── */
.pos-cc-card__ids {
	display: flex;
	align-items: baseline;
	gap: 10px;
	min-width: 0;
	font-size: 0.62rem;
	line-height: 1.2;
	color: var(--pos-text-secondary, var(--cc-muted, #7b899d));
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	padding-left: 36px; /* align under the title (thumb 28 + gap 8) */
}

.pos-cc-card__id-item {
	display: inline-flex;
	align-items: baseline;
	gap: 4px;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
}

.pos-cc-card__id-label {
	color: var(--cc-subtle, var(--pos-text-disabled, #4a5568));
	font-weight: 500;
	text-transform: uppercase;
	letter-spacing: 0.06em;
}

/* Reverted to muted/secondary — the pink SKU value was overpowering the
   neutral "SKU ######" treatment the user wanted restored. */
.pos-cc-card__id-value {
	color: var(--pos-text-secondary, var(--cc-muted, #7b899d));
	font-weight: 600;
	letter-spacing: 0.01em;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

/* ─── Qty / Batch / Price stat strip ─────────────────────────────────── */
.pos-cc-card__stats {
	display: flex;
	align-items: baseline;
	gap: 6px;
	flex-wrap: nowrap;
	font-size: 0.66rem;
	color: var(--pos-text-secondary, var(--cc-muted, #7b899d));
	min-width: 0;
	padding-left: 36px;
	overflow: hidden;
}

.pos-cc-card__stat {
	display: inline-flex;
	align-items: baseline;
	gap: 3px;
	min-width: 0;
	white-space: nowrap;
}

.pos-cc-card__stat--price {
	margin-left: auto;
}

.pos-cc-card__stat-label {
	color: var(--cc-muted, var(--pos-text-secondary, #7b899d));
	font-weight: 500;
	font-size: 0.62rem;
}

.pos-cc-card__stat-sep {
	color: var(--cc-subtle, var(--pos-text-disabled, #4a5568));
	font-weight: 500;
	opacity: 0.75;
	font-size: 0.62rem;
}

.pos-cc-card__stat-value {
	font-weight: 700;
	letter-spacing: -0.01em;
}

.pos-cc-card__stat-value--qty {
	color: var(--pos-text-primary, var(--cc-text, #edf2f7));
	font-size: 0.74rem;
}

.pos-cc-card__stat-value--negative {
	color: rgb(var(--v-theme-error));
}

.pos-cc-card__stat-unit {
	font-size: 0.56rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.06em;
	color: var(--cc-subtle, var(--pos-text-disabled, #4a5568));
}

/* Batch value — green, consistent with the earlier "batch chip" treatment
   the user approved ("change the batch color from red to green"). */
.pos-cc-card__stat-value--batch {
	color: var(--cc-green, #34b29d);
	font-size: 0.7rem;
}

.pos-cc-card__stat-batch-qty {
	color: var(--cc-subtle, var(--pos-text-disabled, #4a5568));
	font-weight: 600;
	font-size: 0.6rem;
}

/* Price reverted to the brand orange (pos-primary). Earlier iteration
   briefly used pink to copy the CC reference card's "~Nd left" slot, but
   the user asked to bring back the original colour treatment. */
.pos-cc-card__stat-value--price {
	color: var(--pos-primary, var(--cc-orange, #f46a25));
	font-size: 0.78rem;
}

.pos-cc-card__price-currency {
	font-size: 0.56rem;
	font-weight: 600;
	color: var(--cc-muted, var(--pos-text-secondary, #7b899d));
	letter-spacing: 0.05em;
	text-transform: uppercase;
	margin-right: 2px;
}

.pos-cc-card__price-secondary {
	font-size: 0.6rem;
	color: var(--cc-muted, var(--pos-text-secondary, #7b899d));
	text-align: right;
	font-variant-numeric: tabular-nums;
	padding-left: 36px;
}

/* ─── Bottom progress bar ─────────────────────────────────────────────── */
.pos-cc-card__track {
	display: block;
	position: absolute;
	left: 4px;
	right: 0;
	bottom: 0;
	height: 3px;
	background: rgba(148, 163, 184, 0.14);
	overflow: hidden;
	border-bottom-right-radius: 10px;
}

.pos-cc-card__track-fill {
	display: block;
	height: 100%;
	background: var(--row-bar, linear-gradient(90deg, #64748b, #94a3b8));
	border-radius: inherit;
	transition: width 0.25s ease;
}

/* ─── Compact mobile sizing ───────────────────────────────────────────── */
@media (max-width: 768px) {
	.pos-cc-card {
		padding: 6px 10px 10px 12px;
		gap: 3px;
		border-radius: 8px;
	}
	.pos-cc-card__thumb {
		width: 24px;
		height: 24px;
	}
	.pos-cc-card__name {
		font-size: 0.72rem;
	}
	.pos-cc-card__ids,
	.pos-cc-card__stats,
	.pos-cc-card__price-secondary {
		padding-left: 32px;
	}
	.pos-cc-card__ids {
		font-size: 0.58rem;
	}
	.pos-cc-card__stats {
		font-size: 0.62rem;
	}
	.pos-cc-card__stat-value--qty {
		font-size: 0.7rem;
	}
	.pos-cc-card__stat-value--price {
		font-size: 0.74rem;
	}
}
</style>
