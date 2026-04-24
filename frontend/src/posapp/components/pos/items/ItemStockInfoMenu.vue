<template>
	<v-menu
		location="bottom end"
		offset="8"
		open-on-hover
		:open-on-click="true"
		:open-on-focus="true"
		:open-delay="80"
		:close-delay="160"
		:close-on-content-click="false"
		content-class="item-stock-info-menu-content"
	>
		<template #activator="{ props: activatorProps }">
			<v-btn
				v-bind="activatorProps"
				icon
				variant="text"
				size="x-small"
				class="item-stock-info-trigger"
				:aria-label="__('Show stock breakdown')"
				@click.stop
			>
				<v-icon size="16">mdi-information-outline</v-icon>
			</v-btn>
		</template>

		<div class="item-stock-info-menu" @click.stop>
			<div class="item-stock-info-header">
				<span class="item-stock-info-header__eyebrow">{{ __("Available stock") }}</span>
				<strong
					class="item-stock-info-header__value"
					:class="{ 'is-empty': sellableQty <= 0 }"
				>
					{{ formatQty(sellableQty) }}
				</strong>
				<span v-if="warehouse" class="item-stock-info-header__meta">
					{{ warehouse }}
				</span>
			</div>

			<div v-if="hasBatches" class="item-stock-info-section">
				<div class="item-stock-info-section__title">
					{{ __("Batches") }}
					<span class="item-stock-info-section__count">{{ batches.length }}</span>
				</div>
				<div class="item-stock-info-row item-stock-info-row--header">
					<span>{{ __("Batch") }}</span>
					<span>{{ __("Qty") }}</span>
					<span>{{ __("Expires") }}</span>
				</div>
				<div
					v-for="batch in batches"
					:key="batch.batch_no"
					class="item-stock-info-row"
					:class="{
						'item-stock-info-row--empty': isEmptyBatch(batch),
						'item-stock-info-row--negative': isNegativeBatch(batch),
						'item-stock-info-row--expired': isExpiredBatch(batch),
					}"
				>
					<span class="item-stock-info-row__batch">{{ batch.batch_no }}</span>
					<span class="item-stock-info-row__qty">{{ formatQty(batch.batch_qty) }}</span>
					<span class="item-stock-info-row__expiry">
						<template v-if="isExpiredBatch(batch)">
							{{ __("Expired") }}
						</template>
						<template v-else-if="batch.expiry_date">
							{{ formatExpiry(batch.expiry_date) }}
						</template>
						<template v-else>—</template>
					</span>
				</div>
			</div>

			<div v-else-if="hasBatchSupport" class="item-stock-info-empty">
				{{ __("No batches available in this warehouse.") }}
			</div>

			<div v-if="!hasBatchSupport && rawActualQty < 0" class="item-stock-info-empty">
				{{
					__("Warehouse stock is {0} (over-sold). Replenish before billing.", [
						formatQty(rawActualQty),
					])
				}}
			</div>
		</div>
	</v-menu>
</template>

<script setup lang="ts">
import { computed } from "vue";

interface BatchRow {
	batch_no?: string;
	batch_qty?: number;
	expiry_date?: string | null;
	is_expired?: boolean;
}

interface Props {
	item: any;
	posProfile?: any;
	formatNumber: (_value: number, _precision?: number) => string;
	hideQtyDecimals?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
	posProfile: () => ({}),
	hideQtyDecimals: false,
});

const __ = (window as any).__ || ((s: string) => s);

const warehouse = computed(() => props.item?.warehouse || props.posProfile?.warehouse || "");

const rawActualQty = computed(() => Number(props.item?.actual_qty ?? 0) || 0);

const allBatches = computed<BatchRow[]>(() => {
	const raw = props.item?.batch_no_data;
	return Array.isArray(raw) ? (raw as BatchRow[]) : [];
});

const hasBatchSupport = computed(() =>
	Boolean(props.item?.has_batch_no) || allBatches.value.length > 0,
);

const batches = computed<BatchRow[]>(() => {
	// Surface every batch (positive, negative, expired) so the cashier can
	// see why a "0 available" item is actually out of stock — but sort
	// positives to the top so the picker priority is obvious.
	return [...allBatches.value].sort((a, b) => {
		const expiredDelta = Number(!!a.is_expired) - Number(!!b.is_expired);
		if (expiredDelta !== 0) return expiredDelta;
		return Number(b.batch_qty || 0) - Number(a.batch_qty || 0);
	});
});

const hasBatches = computed(() => batches.value.length > 0);

const sellableQty = computed(() => {
	if (hasBatches.value) {
		return batches.value.reduce((sum, batch) => {
			if (batch.is_expired) return sum;
			const qty = Number(batch.batch_qty ?? 0) || 0;
			return sum + Math.max(qty, 0);
		}, 0);
	}
	return Math.max(rawActualQty.value, 0);
});

const formatQty = (value: number | null | undefined) => {
	const numeric = Number(value ?? 0);
	if (!Number.isFinite(numeric)) return "0";
	const precision = props.hideQtyDecimals ? 0 : 4;
	return props.formatNumber(numeric, precision);
};

const formatExpiry = (value: string) => {
	if (!value) return "—";
	const parts = String(value).split("-");
	if (parts.length === 3) {
		return `${parts[2]}-${parts[1]}-${parts[0]}`;
	}
	return value;
};

const isEmptyBatch = (batch: BatchRow) => Number(batch.batch_qty || 0) === 0;
const isNegativeBatch = (batch: BatchRow) => Number(batch.batch_qty || 0) < 0;
const isExpiredBatch = (batch: BatchRow) => Boolean(batch.is_expired);
</script>

<style scoped>
.item-stock-info-trigger {
	min-width: 24px;
	width: 24px;
	height: 24px;
	color: rgba(var(--v-theme-on-surface), 0.62);
}

.item-stock-info-menu {
	min-width: 280px;
	max-width: min(360px, calc(100vw - 24px));
	padding: 12px 14px;
	/* Solid opaque background so the popup is readable over the items
	   table underneath — `--pos-surface-raised` was translucent and the
	   row text behind bled through (user flagged this as "hard to read"). */
	background: var(--pos-popover-bg, #1c2334);
	border: 1px solid rgba(var(--v-theme-on-surface), 0.12);
	border-radius: 12px;
	box-shadow: 0 16px 32px rgba(0, 0, 0, 0.45), 0 2px 6px rgba(0, 0, 0, 0.3);
	backdrop-filter: blur(14px) saturate(140%);
	-webkit-backdrop-filter: blur(14px) saturate(140%);
}

/* Light-theme override — a lighter opaque surface so the popup remains
   readable when the app is on the light palette. */
:global(.v-theme--light) .item-stock-info-menu,
:global(:root:not(.v-theme--dark)) .item-stock-info-menu {
	background: var(--pos-popover-bg, #ffffff);
	border-color: rgba(15, 23, 42, 0.08);
	box-shadow: 0 16px 32px rgba(15, 23, 42, 0.18), 0 2px 6px rgba(15, 23, 42, 0.08);
}

.item-stock-info-header {
	display: flex;
	flex-direction: column;
	gap: 2px;
	padding-bottom: 10px;
	border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.08);
}

.item-stock-info-header__eyebrow {
	font-size: 0.66rem;
	font-weight: 700;
	letter-spacing: 0.06em;
	text-transform: uppercase;
	color: var(--pos-text-secondary);
}

.item-stock-info-header__value {
	font-size: 1.1rem;
	font-weight: 700;
	color: var(--pos-text-primary);
	line-height: 1.1;
}

.item-stock-info-header__value.is-empty {
	color: rgb(var(--v-theme-error));
}

.item-stock-info-header__meta {
	font-size: 0.72rem;
	color: var(--pos-text-secondary);
}

.item-stock-info-section {
	margin-top: 10px;
}

.item-stock-info-section__title {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: 0.72rem;
	font-weight: 700;
	letter-spacing: 0.04em;
	text-transform: uppercase;
	color: var(--pos-text-secondary);
	margin-bottom: 6px;
}

.item-stock-info-section__count {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	min-width: 18px;
	padding: 1px 6px;
	border-radius: 999px;
	background: rgba(var(--v-theme-primary), 0.16);
	color: rgb(var(--v-theme-primary));
	font-size: 0.68rem;
	font-weight: 700;
}

.item-stock-info-row {
	display: grid;
	grid-template-columns: minmax(0, 1.2fr) minmax(0, 0.8fr) minmax(0, 1fr);
	gap: 6px;
	align-items: center;
	font-size: 0.78rem;
	color: var(--pos-text-primary);
	padding: 4px 0;
}

.item-stock-info-row--header {
	font-size: 0.66rem;
	font-weight: 700;
	letter-spacing: 0.04em;
	text-transform: uppercase;
	color: var(--pos-text-secondary);
	padding-bottom: 2px;
}

.item-stock-info-row__batch {
	font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.item-stock-info-row__qty {
	font-variant-numeric: lining-nums tabular-nums;
	font-weight: 600;
}

.item-stock-info-row--empty .item-stock-info-row__qty {
	color: var(--pos-text-secondary);
}

.item-stock-info-row--negative .item-stock-info-row__qty {
	color: rgb(var(--v-theme-error));
}

.item-stock-info-row--expired {
	opacity: 0.55;
	text-decoration: line-through;
}

.item-stock-info-empty {
	margin-top: 10px;
	padding: 8px 10px;
	border-radius: 8px;
	background: rgba(var(--v-theme-warning), 0.1);
	color: var(--pos-text-secondary);
	font-size: 0.78rem;
	line-height: 1.35;
}
</style>

<!--
  Non-scoped rules: the v-menu's overlay wrapper (`content-class`) lives
  outside this component's scoped attribute and can carry its own
  translucent background. Force it transparent so only the inner
  `.item-stock-info-menu` surface paints — keeping the popup opaque.
-->
<style>
.item-stock-info-menu-content {
	background: transparent !important;
	box-shadow: none !important;
	border: none !important;
	overflow: visible !important;
}
</style>
