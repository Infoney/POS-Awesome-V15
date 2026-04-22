<template>
	<div
		ref="tableContainer"
		class="my-0 py-0 overflow-y-auto posa-items-table-container posa-responsive-table-container pos-themed-card"
		:style="containerStyles"
		:class="containerClasses"
		@dragover="onDragOverFromSelector($event)"
		@drop="onDropFromSelector($event)"
		@dragenter="onDragEnterFromSelector"
		@dragleave="onDragLeaveFromSelector"
	>
		<v-data-table-virtual
			:headers="finalVisibleColumns"
			:items="items"
			item-value="posa_row_id"
			class="posa-cart-table elevation-2 pos-themed-card"
			:class="tableClasses"
			:items-per-page="virtualScrollConfig.itemsPerPage"
			:item-height="virtualScrollConfig.itemHeight"
			:buffer-size="virtualScrollConfig.bufferSize"
			fixed-header
			:density="tableDensity"
			hide-default-footer
			:header-props="dynamicHeaderProps"
			:search="itemSearch"
			:custom-filter="customItemFilter"
		>
			<template #no-data>
				<div class="posa-cart-empty-state">
					<div class="posa-cart-empty-state__icon-wrap">
						<v-icon :icon="emptyStateIcon" size="42" class="posa-cart-empty-state__icon" />
					</div>
					<div class="posa-cart-empty-state__title">{{ emptyStateTitle }}</div>
					<div class="posa-cart-empty-state__subtitle">{{ emptyStateSubtitle }}</div>
				</div>
			</template>

			<template v-slot:item="{ item }">
				<CartItemRow
					:item="item"
					:visible-columns="finalVisibleColumns"
					:posProfile="pos_profile"
					:isReturnInvoice="isReturnInvoice"
					:invoiceType="invoiceType"
					:displayCurrency="displayCurrency"
					:formatFloat="memoizedFormatFloat"
					:formatCurrency="memoizedFormatCurrency"
					:currencySymbol="currencySymbol"
					:isNumber="isNumber"
					:isNegative="memoizedIsNegative"
					:hideQtyDecimals="hide_qty_decimals"
					:isRTL="isRtl"
					:is-expanded="isItemInDrawer(item)"
					@update-qty="handleQtyUpdate"
					@minus-click="handleMinusClick"
					@add-one="addOne"
					@calc-uom="calcUom"
					@update-rate="handleRateUpdate"
					@update-discount-percent="handleDiscountPercentUpdate"
					@update-discount-amount="handleDiscountAmountUpdate"
					@open-name-dialog="openNameDialog"
					@reset-item-name="resetItemName"
					@toggle-offer="toggleOffer"
					@toggle-expand="openDetailsDrawer(item)"
					@remove-item="removeItem"
					@click="handleRowClick($event, item)"
				/>
			</template>
		</v-data-table-virtual>

		<!-- Right-side product details drawer (command-center style).
		     Teleported to <body> so it overlays the entire viewport instead of
		     being clipped by the cart container's overflow:auto. -->
		<Teleport to="body">
			<v-dialog
				v-model="detailsDrawerOpen"
				:width="detailsDrawerWidth"
				:max-width="detailsDrawerWidth"
				:fullscreen="false"
				transition="dialog-right-transition"
				scrim="rgba(15, 23, 42, 0.55)"
				class="posa-details-drawer-dialog"
				@update:model-value="(open) => !open && closeDetailsDrawer()"
			>
				<v-card
					class="posa-details-drawer pos-themed-card card-accent-top"
					:height="'100dvh'"
				>
					<div class="posa-details-drawer__header">
						<div class="posa-details-drawer__title">
							<span class="icon-badge icon-badge--pink posa-details-drawer__title-badge">
								<v-icon size="18">mdi-information-outline</v-icon>
							</span>
							<div class="posa-details-drawer__heading">
								<span class="posa-details-drawer__eyebrow cc-eyebrow">{{ __("Product Details") }}</span>
								<strong v-if="drawerItem" class="posa-details-drawer__name gradient-text">
									{{ drawerItem.item_name || drawerItem.item_code }}
								</strong>
							</div>
						</div>
						<v-btn
							icon="mdi-close"
							variant="text"
							density="compact"
							class="posa-details-drawer__close"
							:aria-label="__('Close')"
							@click="closeDetailsDrawer"
						/>
					</div>
					<v-divider class="posa-details-drawer__top-divider" />
					<div class="posa-details-drawer__body">
						<ItemDetailsPanel
							v-if="drawerItem"
							:item-code="drawerItem.item_code"
							:pos-profile="pos_profile"
							:hide-qty-decimals="hide_qty_decimals"
							@dashboard-loaded="handleDashboardLoaded"
						>
							<template #after-stats>
								<details class="posa-details-drawer__edit" open>
									<summary class="posa-details-drawer__edit-summary">
										<v-icon size="14">mdi-pencil-outline</v-icon>
										<span>{{ __("Edit line item") }}</span>
									</summary>
									<div class="posa-details-drawer__edit-body">
										<ItemsTableExpandedRow
											:item="drawerItem"
											:is-expanded="true"
											render-as="div"
											:pos_profile="pos_profile"
											:invoice-type="invoiceType"
											:is-return-invoice="isReturnInvoice"
											:invoice_doc="invoice_doc"
											:hide_qty_decimals="hide_qty_decimals"
											:expanded-content-classes="expandedContentClasses"
											:format-float="memoizedFormatFloat"
											:format-currency="memoizedFormatCurrency"
											:currency-symbol="currencySymbol"
											:is-number="isNumber"
											:set-formated-currency="setFormatedCurrency"
											:calc-prices="calcPrices"
											:calc-uom="calcUom"
											:change-price-list-rate="changePriceListRate"
											:get-serial-options="getSerialOptions"
											:set-serial-no="setSerialNo"
											:set-batch-qty="setBatchQty"
											:validate-due-date="validateDueDate"
											@qty-change="handleQtyChange"
										/>
									</div>
								</details>
							</template>
						</ItemDetailsPanel>
					</div>
				</v-card>
			</v-dialog>
		</Teleport>

		<!-- Edit name dialog -->
		<v-dialog v-model="editNameDialog" max-width="400">
			<v-card>
				<v-card-title>{{ __("Item Name") }}</v-card-title>
				<v-card-text>
					<v-text-field v-model="editedName" :maxlength="140" />
				</v-card-text>
				<v-card-actions>
					<v-btn
						v-if="editNameTarget && editNameTarget.name_overridden"
						variant="text"
						@click="resetItemName(editNameTarget)"
						>{{ __("Reset") }}</v-btn
					>
					<v-spacer></v-spacer>
					<v-btn variant="text" @click="editNameDialog = false">{{ __("Cancel") }}</v-btn>
					<v-btn color="primary" variant="text" @click="saveItemName">{{ __("Save") }}</v-btn>
				</v-card-actions>
			</v-card>
		</v-dialog>
	</div>
</template>

<script setup lang="ts">
import { ref, computed, onBeforeUnmount, onMounted, watch, getCurrentInstance } from "vue";
import { useInvoiceStore } from "../../../stores/invoiceStore";
import { loadItemSelectorSettings } from "../../../utils/itemSelectorSettings";
import { logComponentRender } from "../../../utils/perf";
import CartItemRow from "./CartItemRow.vue";
import ItemsTableExpandedRow from "./ItemsTableExpandedRow.vue";
import ItemDetailsPanel from "./ItemDetailsPanel.vue";

import { useItemsTableSearch } from "../../../composables/pos/items/useItemsTableSearch";
import { useItemsTableDragDrop } from "../../../composables/pos/items/useItemsTableDragDrop";
import { useResponsive } from "../../../composables/core/useResponsive";
import {
	DATA_TABLE_EXPAND_COLUMN,
	useItemsTableResponsive,
} from "../../../composables/pos/items/useItemsTableResponsive";
import { useItemsTableMerge } from "../../../composables/pos/items/useItemsTableMerge";
import { useItemsTableNameEdit } from "../../../composables/pos/items/useItemsTableNameEdit";
import { useFormatters } from "../../../composables/core/useFormatters";
import { useRtl } from "../../../composables/core/useRtl";
import { focusCartItemField, type CartShortcutField } from "../../../utils/cartFieldFocus";
import "./items-table-styles.css";

// Global declarations for Frappe
declare const __: (_str: string, _args?: any[]) => string;

interface Props {
	headers?: any[];
	expanded?: any[];
	itemsPerPage?: number;
	itemSearch?: string;
	pos_profile?: any;
	invoiceType?: string;
	stock_settings?: any;
	displayCurrency?: string;
	formatFloat: (_value: number, _precision?: number | string) => string;
	formatCurrency: (_value: number, _precision?: number | string) => string;
	currencySymbol: (_currency?: string) => string;
	isNumber: (_value: any) => boolean;
	setFormatedQty: (_item: any, _field: string, _value: any, _force?: boolean, _event?: any) => void;
	setFormatedCurrency: (_item: any, _field: string, _value: any, _force?: boolean, _event?: any) => void;
	calcPrices: (_item: any, _value: any, _event?: any) => void;
	calcUom: (_item: any, _uom: string) => void;
	setSerialNo: (_item: any) => void;
	setBatchQty: (_item: any, _event: any) => void;
	validateDueDate: (_item: any) => void;
	removeItem: (_item: any) => void;
	subtractOne: (_item: any) => void;
	addOne: (_item: any) => void;
	isReturnInvoice?: boolean;
	toggleOffer: (_item: any) => void;
	changePriceListRate: (_item: any) => void;
	isNegative: (_value: any) => boolean;
}

const props = withDefaults(defineProps<Props>(), {
	headers: () => [],
	expanded: () => [],
	isReturnInvoice: false,
});

const emit = defineEmits<{
	"update:expanded": [val: any[]];
	"show-drop-feedback": [val: boolean];
	"item-dropped": [val: boolean];
}>();

const { proxy } = getCurrentInstance() as any;
const eventBus = proxy?.eventBus;
const invoiceStore = useInvoiceStore();
const tableContainer = ref<HTMLElement | null>(null);

// Composables
const { customItemFilter } = useItemsTableSearch();
const dragDropHandlers = useItemsTableDragDrop(emit, eventBus);
const { isRtl } = useRtl();
const { memoizedFormatFloat, memoizedFormatCurrency, clearFormatCache } = useFormatters({
	formatFloat: props.formatFloat,
	formatCurrency: props.formatCurrency,
});

const responsive = useItemsTableResponsive(
	tableContainer,
	computed(() => props.headers || []),
);
const merge = useItemsTableMerge(computed(() => invoiceStore.items));
const nameEdit = useItemsTableNameEdit();

// Computed
const items = computed(() => invoiceStore.items);
const invoice_doc = computed(() => invoiceStore.invoiceDoc || {});
const hasItemSearch = computed(() => !!props.itemSearch?.trim());
const emptyStateIcon = computed(() => (hasItemSearch.value ? "mdi-cart-search" : "mdi-cart-outline"));
const emptyStateTitle = computed(() =>
	hasItemSearch.value ? __("No matching items in cart") : __("No items in cart"),
);
const emptyStateSubtitle = computed(() =>
	hasItemSearch.value
		? __("Try a different search term or clear the cart search.")
		: __("Add items from the selector to start building this sale."),
);

const memoizedIsNegative = computed(() => {
	return (value: any) => {
		if (typeof value === "number") return value < 0;
		return props.isNegative(value);
	};
});

const {
	breakpoint,
	responsiveHeaders,
	containerStyles,
	containerClasses,
	tableClasses,
	expandedContentClasses,
	tableDensity,
	containerHeight,
} = responsive;

const dynamicHeaderProps = computed(() => ({
	class: `responsive-header container-${breakpoint.value}`,
}));

const finalVisibleColumns = computed(() => [
	...responsiveHeaders.value,
	DATA_TABLE_EXPAND_COLUMN,
]);

const virtualScrollConfig = computed(() => {
	const itemCount = items.value?.length || 0;
	const height = containerHeight.value || 600;

	return {
		itemHeight: tableDensity.value === "compact" ? 48 : tableDensity.value === "comfortable" ? 72 : 60,
		itemsPerPage: Math.max(20, Math.ceil(height / 60) + 5),
		bufferSize: itemCount > 1000 ? 20 : itemCount > 500 ? 15 : 10,
	};
});

const hide_qty_decimals = computed(() => {
	const opts = loadItemSelectorSettings();
	return !!opts?.hide_qty_decimals;
});

// Watchers
watch(() => props.displayCurrency, clearFormatCache);
watch(() => props.pos_profile, clearFormatCache, { deep: true });

// Methods
const getSerialOptions = (item: any) => {
	if (Array.isArray(item?.filtered_serial_no_data)) {
		return item.filtered_serial_no_data;
	}
	return Array.isArray(item?.serial_no_data) ? item.serial_no_data : [];
};

// Right-side details drawer state (replaces the previous inline expanded row).
const detailsDrawerOpen = ref(false);
const drawerItem = ref<any>(null);
const { windowWidth } = useResponsive();
// Open the drawer at command-center scale: ~half the viewport on desktop,
// capped at 960px so it doesn't dwarf the cart, and falling back to
// (viewport - 16) on small screens. Reactive on resize via useResponsive.
const detailsDrawerWidth = computed(() => {
	const viewport = windowWidth.value || 1280;
	const desired = Math.round(viewport * 0.36);
	const max = Math.min(viewport - 16, 580);
	return Math.max(340, Math.min(desired, max));
});

const isItemInDrawer = (item: any) =>
	detailsDrawerOpen.value && drawerItem.value?.posa_row_id === item?.posa_row_id;

const openDetailsDrawer = (item: any) => {
	if (!item) return;
	drawerItem.value = item;
	detailsDrawerOpen.value = true;
};

const closeDetailsDrawer = () => {
	detailsDrawerOpen.value = false;
	// Defer clearing so the drawer animates out cleanly with content still present.
	setTimeout(() => {
		if (!detailsDrawerOpen.value) {
			drawerItem.value = null;
		}
	}, 250);
};

watch(detailsDrawerOpen, (open) => {
	if (!open) {
		// Mirror the legacy emit so external listeners don't see stale state.
		emit("update:expanded", []);
	}
});

// Keep the drawer item reference fresh as the cart re-renders (e.g. qty edits).
watch(items, (next) => {
	if (!detailsDrawerOpen.value || !drawerItem.value) return;
	const refreshed = next.find(
		(row: any) => row.posa_row_id === drawerItem.value.posa_row_id,
	);
	if (!refreshed) {
		closeDetailsDrawer();
	} else if (refreshed !== drawerItem.value) {
		drawerItem.value = refreshed;
	}
});

/**
 * Reconcile the cart line's cached stock snapshot with the freshly fetched
 * dashboard payload. Without this, `_base_actual_qty` / `actual_batch_qty`
 * stick to whatever the items selector primed them with at add-to-cart
 * time — which is often 0 for items the cashier rebuilt the cart against
 * after a bin replenishment. The drawer then ends up showing
 * "IN STOCK 0 / Out of Stock" while "Available Batches" simultaneously
 * shows 1 unit, and the customer's invoice eventually fails at submit
 * with the "negative stock of -X" backend validator.
 */
const handleDashboardLoaded = (payload: {
	itemCode: string;
	profileWarehouse: string;
	profileStock: number;
	totalStock: number;
	stockByWarehouse: { warehouse: string; actual_qty: number }[];
	batches: {
		batch_no: string;
		warehouse: string;
		qty: number;
		expiry_date: string;
		is_expired: boolean;
	}[];
	hasBatchNo: boolean;
}) => {
	if (!payload || !payload.itemCode) return;

	// Patch every cart row that points at this item — multiple lines can
	// reference the same item_code (different batches, splits, etc.).
	const matchingRows = items.value.filter(
		(row: any) => row?.item_code === payload.itemCode,
	);
	if (!matchingRows.length) return;

	// Build a quick lookup of freshly-known batch availability so we can
	// patch each line's `batch_no_data` rows in O(1).
	const freshBatchQty = new Map<string, number>();
	(payload.batches || []).forEach((b) => {
		if (!b?.batch_no) return;
		freshBatchQty.set(String(b.batch_no), Number(b.qty || 0));
	});

	matchingRows.forEach((row: any) => {
		// Profile-warehouse stock — this drives the "In Stock" tile and the
		// `addItem` quantity gate. Use the dashboard's `profile_stock` first
		// because that's the same number ERPNext will validate against.
		const fresh = Number(payload.profileStock || 0);
		row._base_actual_qty = fresh;
		row.actual_qty = fresh;

		// Patch batch availability where we have fresh numbers; leave
		// untouched batches alone (they may be valid in another warehouse).
		if (Array.isArray(row.batch_no_data) && freshBatchQty.size) {
			row.batch_no_data = row.batch_no_data.map((batch: any) => {
				if (!batch?.batch_no) return batch;
				const freshQty = freshBatchQty.get(String(batch.batch_no));
				if (freshQty === undefined) return batch;
				return {
					...batch,
					available_qty: freshQty,
					batch_qty: freshQty,
					original_batch_qty: freshQty,
				};
			});
		}

		// Sync the currently-selected batch's display qty too.
		if (row.batch_no) {
			const selectedFresh = freshBatchQty.get(String(row.batch_no));
			if (selectedFresh !== undefined) {
				row.actual_batch_qty = selectedFresh;
			}
		}
	});
};

const handleQtyChange = (item: any, event: any) => {
	const newQty = parseFloat(event.target.value) || 0;
	if (newQty === 0) {
		props.removeItem(item);
	} else {
		props.setFormatedQty(item, "qty", null, false, event.target.value);
	}
	eventBus?.emit("recalculate_return_discount", { defer: true });
};

const handleMinusClick = (item: any) => {
	// Replacement rows should still be removed directly.
	if (item.posa_is_replace) {
		props.removeItem(item);
		return;
	}

	// magnitude-based removal: only remove if qty magnitude <= 1
	// This handles -1 for returns and 1 for normal invoices correctly
	const absQty = Math.abs(item.qty || 0);
	if (absQty <= 1) {
		props.removeItem(item);
	} else {
		// subtract_one handles the sign-aware logic (e.g. -5 -> -4 in returns)
		props.subtractOne(item);
	}
	eventBus?.emit("recalculate_return_discount", { defer: true });
};

const handleQtyUpdate = (item: any, newQty: any) => {
	props.setFormatedQty(item, "qty", null, false, newQty);
	eventBus?.emit("recalculate_return_discount", { defer: true });
};

const handleRateUpdate = (item: any, newRate: any) => {
	props.setFormatedCurrency(item, "rate", null, false, { target: { value: newRate } });
	props.calcPrices(item, newRate, { target: { id: "rate" } });
};

const handleDiscountPercentUpdate = (item: any, newDiscount: any) => {
	props.setFormatedCurrency(item, "discount_percentage", null, false, {
		target: { value: newDiscount },
	});
	props.calcPrices(item, newDiscount, { target: { id: "discount_percentage" } });
};

const handleDiscountAmountUpdate = (item: any, newDiscount: any) => {
	props.setFormatedCurrency(item, "discount_amount", null, false, {
		target: { value: newDiscount },
	});
	props.calcPrices(item, newDiscount, { target: { id: "discount_amount" } });
};

const handleRowClick = (_event: any, item: any) => {
	openDetailsDrawer(item);
};

const focusItemField = (index: number, field: CartShortcutField) => {
	return focusCartItemField(tableContainer.value, index, field);
};

// Drag and Drop delegation
const onDragOverFromSelector = (event: DragEvent) => dragDropHandlers.onDragOverFromSelector(event);
const onDragEnterFromSelector = () => dragDropHandlers.onDragEnterFromSelector();
const onDragLeaveFromSelector = (event: DragEvent) => dragDropHandlers.onDragLeaveFromSelector(event);
const onDropFromSelector = (event: DragEvent) => dragDropHandlers.onDropFromSelector(event);

// Name editing logic
const { editNameDialog, editedName, editNameTarget, openNameDialog, saveItemName, resetItemName } = nameEdit;

// Life-cycle
onMounted(() => {
	logComponentRender({ $el: tableContainer.value }, "ItemsTable", "mounted", {
		rows: items.value?.length || 0,
	});
});

onBeforeUnmount(() => {
	merge.clearMergeCache();
});

defineExpose({
	focusItemField,
	openDetailsDrawer,
	closeDetailsDrawer,
});
</script>

<style>
/* Global styles for ItemsTable and its children */
@import "./items-table-styles.css";
</style>

<style scoped>
/* Scoped styles for ItemsTable component specific logic */
.posa-items-table-container {
	position: relative;
	transition: all 0.3s ease;
}

/* Anchor the dialog to the right edge so it reads as a side drawer. */
.posa-details-drawer-dialog :deep(.v-overlay__content) {
	position: fixed;
	top: 0;
	right: 0;
	bottom: 0;
	margin: 0;
	max-height: 100dvh;
	border-radius: 0;
	transform-origin: right center;
}

.posa-details-drawer {
	background: var(--cc-bg, var(--pos-surface-muted, #0e121b)) !important;
	border-radius: 0 !important;
	border-left: 1px solid var(--cc-border, var(--pos-border, rgba(148, 163, 184, 0.2))) !important;
	box-shadow: var(--cc-shadow-lg, 0 20px 60px rgba(0, 0, 0, 0.55));
	display: flex;
	flex-direction: column;
	overflow: hidden;
}

.posa-details-drawer.card-accent-top::before {
	border-radius: 0 !important;
	opacity: 0.85;
}

.posa-details-drawer__header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 10px;
	padding: 12px 16px 10px;
	background: linear-gradient(
		180deg,
		var(--cc-bg-sec, rgba(255, 255, 255, 0.02)) 0%,
		transparent 100%
	);
}

.posa-details-drawer__title {
	display: flex;
	align-items: center;
	gap: 12px;
	min-width: 0;
}

.posa-details-drawer__title-badge {
	margin-top: 0;
	flex-shrink: 0;
	box-shadow: var(--cc-glow-pink, 0 0 18px rgba(226, 54, 112, 0.18));
}

.posa-details-drawer__heading {
	display: flex;
	flex-direction: column;
	gap: 4px;
	min-width: 0;
}

.posa-details-drawer__eyebrow {
	font-size: 0.66rem;
}

.posa-details-drawer__name {
	font-size: 1rem;
	font-weight: 700;
	line-height: 1.2;
	letter-spacing: -0.01em;
	overflow-wrap: anywhere;
}

.posa-details-drawer__close {
	color: var(--cc-muted, var(--pos-text-secondary)) !important;
}

.posa-details-drawer__close:hover {
	color: var(--cc-text, var(--pos-text-primary)) !important;
	background: var(--cc-bg-ter, rgba(255, 255, 255, 0.06)) !important;
}

.posa-details-drawer__top-divider {
	border-color: var(--cc-border, var(--pos-border)) !important;
	opacity: 1;
}

.posa-details-drawer__body {
	flex: 1 1 auto;
	overflow-y: auto;
	padding: 10px 14px 20px;
	background: var(--cc-bg, var(--pos-surface-muted));
}

.posa-details-drawer__divider {
	margin: 20px 0;
	border-color: var(--cc-border, var(--pos-border)) !important;
	opacity: 1;
}

.posa-details-drawer__edit {
	position: relative;
	border: 1px solid var(--cc-border, rgba(148, 163, 184, 0.18));
	border-radius: 12px;
	background: var(--cc-bg-sec, rgba(148, 163, 184, 0.04));
	overflow: hidden;
	transition: border-color var(--cc-ease-base, 220ms ease-out);
}

.posa-details-drawer__edit:hover {
	border-color: var(--cc-border-hover, rgba(148, 163, 184, 0.32));
}

.posa-details-drawer__edit-summary {
	display: flex;
	align-items: center;
	gap: 7px;
	padding: 8px 12px;
	font-weight: 700;
	font-size: 0.68rem;
	letter-spacing: 0.04em;
	text-transform: uppercase;
	color: var(--cc-muted, var(--pos-text-secondary));
	cursor: pointer;
	user-select: none;
	list-style: none;
}

.posa-details-drawer__edit-summary::-webkit-details-marker {
	display: none;
}

.posa-details-drawer__edit-summary::after {
	content: "";
	width: 8px;
	height: 8px;
	margin-inline-start: auto;
	border-right: 1.5px solid currentColor;
	border-bottom: 1.5px solid currentColor;
	transform: rotate(45deg);
	transition: transform 0.2s ease;
	opacity: 0.6;
}

.posa-details-drawer__edit[open] .posa-details-drawer__edit-summary::after {
	transform: rotate(-135deg);
}

.posa-details-drawer__edit-body {
	padding: 2px 10px 10px;
}
</style>
