<template>
	<div class="item-details-panel">
		<!-- Hero -->
		<div class="item-details-hero">
			<div class="item-details-hero__media">
				<v-img
					v-if="hero.image"
					:src="hero.image"
					:alt="hero.item_name"
					cover
				/>
				<div v-else class="item-details-hero__placeholder">
					<v-icon size="40" color="grey">mdi-image-outline</v-icon>
				</div>
			</div>
			<div class="item-details-hero__copy">
				<h2 class="item-details-hero__title">{{ hero.item_name }}</h2>
				<div class="item-details-hero__chips">
					<div class="info-chip">
						<span class="info-chip__label">{{ __("SKU") }}</span>
						<span class="info-chip__value">{{ hero.sku }}</span>
					</div>
					<div v-if="hero.barcode" class="info-chip">
						<span class="info-chip__label">{{ __("Barcode") }}</span>
						<span class="info-chip__value">{{ hero.barcode }}</span>
					</div>
					<span class="status-chip" :class="stockStatusClass">
						<span class="status-chip__dot" />
						{{ stockStatusLabel }}
					</span>
				</div>
				<a
					v-if="erpUrl"
					:href="erpUrl"
					target="_blank"
					rel="noopener noreferrer"
					class="item-details-hero__erp-link"
				>
					{{ __("Open in ERPNext") }}
					<v-icon size="14">mdi-arrow-top-right</v-icon>
				</a>
			</div>
		</div>

		<v-divider />

		<!-- Loading / error states -->
		<div v-if="loading" class="item-details-state">
			<v-progress-circular indeterminate size="32" />
			<span>{{ __("Loading product details...") }}</span>
		</div>
		<div v-else-if="error" class="item-details-state item-details-state--error">
			<v-icon color="error" size="22">mdi-alert-circle-outline</v-icon>
			<span>{{ error }}</span>
		</div>

		<template v-else>
			<!-- Stat tiles -->
			<div class="stat-grid">
				<div class="stat-tile stat-tile--revenue">
					<div class="stat-tile__value">
						<span class="stat-tile__currency">{{ currencyLabel }}</span>
						<span>{{ formatNumber(totals.total_revenue, 0) }}</span>
					</div>
					<div class="stat-tile__label">{{ __("Total Revenue") }}</div>
				</div>
				<div class="stat-tile stat-tile--invoices">
					<div class="stat-tile__value">{{ formatInteger(totals.sales_invoices) }}</div>
					<div class="stat-tile__label">{{ __("Sales Invoices") }}</div>
				</div>
				<div class="stat-tile stat-tile--orders">
					<div class="stat-tile__value">{{ formatInteger(totals.sales_orders) }}</div>
					<div class="stat-tile__label">{{ __("Sales Orders") }}</div>
				</div>
				<div class="stat-tile stat-tile--qty">
					<div class="stat-tile__value">{{ formatNumber(totals.qty_sold, qtyPrecision) }}</div>
					<div class="stat-tile__label">{{ __("Qty Sold") }}</div>
				</div>
				<div class="stat-tile stat-tile--avg">
					<div class="stat-tile__value">
						<span class="stat-tile__currency">{{ currencyLabel }}</span>
						<span>{{ formatNumber(totals.avg_price, 0) }}</span>
					</div>
					<div class="stat-tile__label">{{ __("Avg Price") }}</div>
				</div>
				<div
					class="stat-tile stat-tile--stock"
					:class="{ 'stat-tile--empty': totalStock <= 0 }"
				>
					<div class="stat-tile__value">{{ formatNumber(totalStock, qtyPrecision) }}</div>
					<div class="stat-tile__label">{{ __("Total Stock") }}</div>
				</div>
			</div>

			<!-- Stock by warehouse -->
			<section class="panel-section">
				<header class="panel-section__header">
					<h3 class="panel-section__title">{{ __("Stock by Warehouse") }}</h3>
					<span class="panel-section__hint">{{ __("Current levels") }}</span>
				</header>
				<div v-if="stockByWarehouse.length" class="warehouse-list">
					<div
						v-for="(row, index) in stockByWarehouse"
						:key="row.warehouse"
						class="warehouse-row"
						:class="warehouseToneClass(index)"
					>
						<div class="warehouse-row__icon">
							<v-icon size="18">mdi-warehouse</v-icon>
						</div>
						<div class="warehouse-row__body">
							<div class="warehouse-row__name">{{ row.warehouse }}</div>
							<div class="warehouse-row__bar">
								<span
									class="warehouse-row__bar-fill"
									:style="{ width: warehouseBarWidth(row) }"
								/>
							</div>
						</div>
						<div class="warehouse-row__qty">
							<strong>{{ formatNumber(row.actual_qty, qtyPrecision) }}</strong>
							<span>{{ __("units") }}</span>
						</div>
					</div>
				</div>
				<div v-else class="panel-section__empty">{{ __("No stock data") }}</div>
			</section>

			<!-- Recent invoices -->
			<section class="panel-section">
				<header class="panel-section__header">
					<h3 class="panel-section__title">{{ __("Recent Invoices") }}</h3>
					<span v-if="recentInvoices.length" class="panel-section__hint">
						{{ __("Latest {0}", [recentInvoices.length]) }}
					</span>
				</header>
				<div v-if="recentInvoices.length" class="invoice-list">
					<a
						v-for="invoice in recentInvoices"
						:key="invoice.name"
						:href="invoiceUrl(invoice)"
						target="_blank"
						rel="noopener noreferrer"
						class="invoice-row"
					>
						<span class="invoice-row__name">{{ invoice.name }}</span>
						<span class="invoice-row__customer">{{ invoice.customer_name }}</span>
						<span
							class="invoice-row__amount"
							:class="{ 'is-return': invoice.is_return }"
						>
							{{ invoice.is_return ? "-" : "" }}{{ invoice.currency || currencyLabel }}
							{{ formatNumber(Math.abs(invoice.grand_total || 0), 0) }}
						</span>
						<span class="invoice-row__date">{{ formatDate(invoice.posting_date) }}</span>
					</a>
				</div>
				<div v-else class="panel-section__empty">
					{{ __("No invoices yet for this item.") }}
				</div>
			</section>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from "vue";

declare const frappe: any;

interface HeroPayload {
	item_code?: string;
	item_name?: string;
	image?: string;
	sku?: string;
	barcode?: string;
	stock_uom?: string;
	has_batch_no?: boolean;
}

interface Totals {
	total_revenue: number;
	sales_invoices: number;
	sales_orders: number;
	qty_sold: number;
	avg_price: number;
	total_stock: number;
	profile_stock: number;
}

interface WarehouseRow {
	warehouse: string;
	actual_qty: number;
}

interface RecentInvoice {
	name: string;
	customer: string;
	customer_name: string;
	posting_date: string;
	grand_total: number;
	currency?: string;
	is_return?: boolean;
}

interface DashboardPayload {
	hero: HeroPayload;
	currency: string;
	totals: Totals;
	stock_by_warehouse: WarehouseRow[];
	recent_invoices: RecentInvoice[];
}

interface Props {
	itemCode: string;
	posProfile?: any;
	hideQtyDecimals?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
	posProfile: () => ({}),
	hideQtyDecimals: false,
});

const __ = (window as any).__ || ((s: string, args: any[] = []) => {
	if (!Array.isArray(args) || !args.length) return s;
	return s.replace(/\{(\d+)\}/g, (_match, idx) => String(args[Number(idx)] ?? ""));
});

const loading = ref(false);
const error = ref("");
const dashboard = ref<DashboardPayload | null>(null);

const hero = computed<HeroPayload>(() => {
	if (dashboard.value?.hero) return dashboard.value.hero;
	return {
		item_code: props.itemCode,
		item_name: props.itemCode,
		image: "",
		sku: props.itemCode,
		barcode: "",
	};
});

const totals = computed<Totals>(() =>
	dashboard.value?.totals || {
		total_revenue: 0,
		sales_invoices: 0,
		sales_orders: 0,
		qty_sold: 0,
		avg_price: 0,
		total_stock: 0,
		profile_stock: 0,
	},
);

const stockByWarehouse = computed<WarehouseRow[]>(
	() => dashboard.value?.stock_by_warehouse || [],
);

const recentInvoices = computed<RecentInvoice[]>(
	() => dashboard.value?.recent_invoices || [],
);

const totalStock = computed(() => Number(totals.value.total_stock || 0));

const currencyLabel = computed(
	() =>
		dashboard.value?.currency ||
		props.posProfile?.currency ||
		"",
);

const qtyPrecision = computed(() => (props.hideQtyDecimals ? 0 : 2));

const stockStatusLabel = computed(() => {
	const profileQty = Number(totals.value.profile_stock || 0);
	if (profileQty > 0) return __("In Stock");
	if (totalStock.value > 0) return __("Available elsewhere");
	return __("Out of Stock");
});

const stockStatusClass = computed(() => {
	const profileQty = Number(totals.value.profile_stock || 0);
	if (profileQty > 0) return "status-chip--in-stock";
	if (totalStock.value > 0) return "status-chip--limited";
	return "status-chip--out-of-stock";
});

const erpUrl = computed(() => {
	const code = encodeURIComponent(hero.value.item_code || props.itemCode);
	return code ? `/app/item/${code}` : "";
});

const invoiceUrl = (invoice: RecentInvoice) =>
	`/app/sales-invoice/${encodeURIComponent(invoice.name)}`;

const maxWarehouseQty = computed(() =>
	stockByWarehouse.value.reduce(
		(max, row) => Math.max(max, Number(row.actual_qty || 0)),
		0,
	),
);

const warehouseBarWidth = (row: WarehouseRow) => {
	const qty = Math.max(Number(row.actual_qty || 0), 0);
	const max = maxWarehouseQty.value;
	if (max <= 0) return "0%";
	const ratio = Math.min(qty / max, 1);
	return `${Math.round(ratio * 100)}%`;
};

const warehouseTones = ["tone-pink", "tone-orange", "tone-teal", "tone-violet", "tone-cyan"];
const warehouseToneClass = (index: number) =>
	`warehouse-row--${warehouseTones[index % warehouseTones.length]}`;

const formatNumber = (value: number | string | undefined, decimals = 2) => {
	const num = Number(value ?? 0);
	if (!Number.isFinite(num)) return "0";
	return num.toLocaleString(undefined, {
		minimumFractionDigits: 0,
		maximumFractionDigits: decimals,
	});
};

const formatInteger = (value: number | string | undefined) =>
	formatNumber(Math.round(Number(value ?? 0)), 0);

const formatDate = (value: string) => {
	if (!value) return "";
	try {
		const d = new Date(value);
		if (Number.isNaN(d.getTime())) return value;
		return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
	} catch {
		return value;
	}
};

const fetchDashboard = async () => {
	if (!props.itemCode) return;
	loading.value = true;
	error.value = "";
	try {
		const resp = await frappe.call({
			method: "posawesome.posawesome.api.items.get_item_dashboard",
			args: {
				item_code: props.itemCode,
				pos_profile: props.posProfile?.name || props.posProfile || null,
			},
		});
		const payload = resp?.message;
		if (payload && typeof payload === "object") {
			dashboard.value = payload as DashboardPayload;
		} else {
			error.value = __("No data returned for this item.");
		}
	} catch (err: any) {
		console.error("[ItemDetailsPanel] dashboard fetch failed", err);
		error.value = err?.message || __("Could not load product details.");
	} finally {
		loading.value = false;
	}
};

watch(
	() => props.itemCode,
	(code) => {
		if (code) fetchDashboard();
	},
	{ immediate: true },
);
</script>

<style scoped>
.item-details-panel {
	display: flex;
	flex-direction: column;
	gap: 16px;
	padding-bottom: 12px;
}

.item-details-hero {
	display: flex;
	gap: 16px;
	align-items: flex-start;
}

.item-details-hero__media {
	width: 96px;
	height: 96px;
	flex-shrink: 0;
	border-radius: 14px;
	overflow: hidden;
	background: rgba(255, 255, 255, 0.06);
	display: flex;
	align-items: center;
	justify-content: center;
}

.item-details-hero__placeholder {
	width: 100%;
	height: 100%;
	display: flex;
	align-items: center;
	justify-content: center;
	background: rgba(148, 163, 184, 0.08);
}

.item-details-hero__copy {
	flex: 1;
	min-width: 0;
	display: flex;
	flex-direction: column;
	gap: 8px;
}

.item-details-hero__title {
	font-size: 1.4rem;
	font-weight: 700;
	color: var(--pos-text-primary);
	line-height: 1.2;
	margin: 0;
	overflow-wrap: anywhere;
}

.item-details-hero__chips {
	display: flex;
	flex-wrap: wrap;
	gap: 8px;
	align-items: center;
}

.info-chip {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	padding: 4px 10px;
	border-radius: 8px;
	background: rgba(148, 163, 184, 0.1);
	border: 1px solid rgba(148, 163, 184, 0.18);
	font-size: 0.78rem;
}

.info-chip__label {
	color: var(--pos-text-secondary);
	font-weight: 600;
	letter-spacing: 0.04em;
}

.info-chip__value {
	color: var(--pos-text-primary);
	font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
}

.status-chip {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	padding: 4px 10px;
	border-radius: 999px;
	font-size: 0.74rem;
	font-weight: 600;
	border: 1px solid currentColor;
}

.status-chip__dot {
	width: 6px;
	height: 6px;
	border-radius: 50%;
	background: currentColor;
}

.status-chip--in-stock {
	color: #34d399;
	background: rgba(52, 211, 153, 0.1);
}

.status-chip--limited {
	color: #fbbf24;
	background: rgba(251, 191, 36, 0.1);
}

.status-chip--out-of-stock {
	color: #f87171;
	background: rgba(248, 113, 113, 0.1);
}

.item-details-hero__erp-link {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	color: rgb(var(--v-theme-primary));
	font-size: 0.82rem;
	font-weight: 600;
	text-decoration: none;
	width: fit-content;
}

.item-details-hero__erp-link:hover {
	text-decoration: underline;
}

.item-details-state {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 16px 12px;
	color: var(--pos-text-secondary);
	font-size: 0.86rem;
}

.item-details-state--error {
	color: rgb(var(--v-theme-error));
}

.stat-grid {
	display: grid;
	grid-template-columns: repeat(3, minmax(0, 1fr));
	gap: 10px;
}

.stat-tile {
	padding: 14px 12px;
	border-radius: 12px;
	background: rgba(148, 163, 184, 0.06);
	border: 1px solid rgba(148, 163, 184, 0.12);
	display: flex;
	flex-direction: column;
	gap: 6px;
	transition: transform 0.18s ease, border-color 0.18s ease;
}

.stat-tile:hover {
	transform: translateY(-1px);
	border-color: rgba(148, 163, 184, 0.24);
}

.stat-tile__value {
	font-size: 1.5rem;
	font-weight: 700;
	line-height: 1.1;
	display: inline-flex;
	align-items: baseline;
	gap: 4px;
	overflow-wrap: anywhere;
}

.stat-tile__currency {
	font-size: 0.78rem;
	font-weight: 600;
	color: inherit;
	opacity: 0.8;
}

.stat-tile__label {
	font-size: 0.7rem;
	font-weight: 700;
	letter-spacing: 0.06em;
	text-transform: uppercase;
	color: var(--pos-text-secondary);
}

.stat-tile--revenue {
	color: #f87171;
}
.stat-tile--invoices {
	color: #fb923c;
}
.stat-tile--orders {
	color: #34d399;
}
.stat-tile--qty {
	color: #c084fc;
}
.stat-tile--avg {
	color: #60a5fa;
}
.stat-tile--stock {
	color: #34d399;
}
.stat-tile--stock.stat-tile--empty {
	color: #f87171;
}

.panel-section__header {
	display: flex;
	align-items: baseline;
	justify-content: space-between;
	gap: 10px;
	margin-bottom: 8px;
}

.panel-section__title {
	font-size: 0.95rem;
	font-weight: 700;
	color: var(--pos-text-primary);
	margin: 0;
}

.panel-section__hint {
	font-size: 0.72rem;
	color: var(--pos-text-secondary);
	letter-spacing: 0.04em;
}

.panel-section__empty {
	padding: 14px;
	border-radius: 10px;
	background: rgba(148, 163, 184, 0.05);
	color: var(--pos-text-secondary);
	font-size: 0.84rem;
	text-align: center;
}

.warehouse-list {
	display: flex;
	flex-direction: column;
	gap: 8px;
}

.warehouse-row {
	display: grid;
	grid-template-columns: 36px minmax(0, 1fr) auto;
	gap: 12px;
	align-items: center;
	padding: 10px 12px;
	border-radius: 12px;
	background: rgba(148, 163, 184, 0.05);
	border: 1px solid rgba(148, 163, 184, 0.12);
}

.warehouse-row__icon {
	display: flex;
	align-items: center;
	justify-content: center;
	width: 36px;
	height: 36px;
	border-radius: 9px;
	background: rgba(148, 163, 184, 0.08);
}

.warehouse-row__body {
	display: flex;
	flex-direction: column;
	gap: 6px;
	min-width: 0;
}

.warehouse-row__name {
	font-size: 0.86rem;
	font-weight: 600;
	color: var(--pos-text-primary);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.warehouse-row__bar {
	width: 100%;
	height: 4px;
	border-radius: 999px;
	background: rgba(148, 163, 184, 0.18);
	overflow: hidden;
}

.warehouse-row__bar-fill {
	display: block;
	height: 100%;
	border-radius: 999px;
	background: currentColor;
	transition: width 0.25s ease;
}

.warehouse-row__qty {
	display: flex;
	flex-direction: column;
	align-items: flex-end;
	font-weight: 700;
	color: inherit;
}

.warehouse-row__qty span {
	font-size: 0.7rem;
	color: var(--pos-text-secondary);
	font-weight: 500;
	letter-spacing: 0.04em;
}

.warehouse-row--tone-pink {
	color: #f472b6;
}
.warehouse-row--tone-orange {
	color: #fb923c;
}
.warehouse-row--tone-teal {
	color: #2dd4bf;
}
.warehouse-row--tone-violet {
	color: #a78bfa;
}
.warehouse-row--tone-cyan {
	color: #67e8f9;
}

.invoice-list {
	display: flex;
	flex-direction: column;
	gap: 6px;
}

.invoice-row {
	display: grid;
	grid-template-columns: minmax(0, 1.2fr) minmax(0, 1.6fr) minmax(0, 1fr) auto;
	gap: 10px;
	align-items: center;
	padding: 10px 12px;
	border-radius: 10px;
	background: rgba(148, 163, 184, 0.05);
	border: 1px solid rgba(148, 163, 184, 0.1);
	color: var(--pos-text-primary);
	text-decoration: none;
	font-size: 0.82rem;
	transition: background 0.15s ease;
}

.invoice-row:hover {
	background: rgba(148, 163, 184, 0.1);
}

.invoice-row__name {
	font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
	color: rgb(var(--v-theme-primary));
	font-weight: 600;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.invoice-row__customer {
	color: var(--pos-text-secondary);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.invoice-row__amount {
	font-weight: 700;
	text-align: end;
	white-space: nowrap;
}

.invoice-row__amount.is-return {
	color: rgb(var(--v-theme-error));
}

.invoice-row__date {
	color: var(--pos-text-secondary);
	font-size: 0.74rem;
	white-space: nowrap;
}

@media (max-width: 720px) {
	.stat-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}

	.invoice-row {
		grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
		grid-auto-rows: auto;
	}

	.invoice-row__amount,
	.invoice-row__date {
		grid-column: span 1;
	}
}
</style>
