/*
 * State + helpers for the in-app one-step Purchase Invoice flow.
 *
 * Mirrors `usePurchaseOrder.ts` but trims everything tied to the
 * three-doctype flow (PO → PR → PI): no `receiveNow`, no
 * `createInvoice`, no schedule_date. The matching server endpoint
 * (`posawesome.mizan.api.purchase_invoices.create_purchase_invoice`)
 * always submits a Purchase Invoice with `update_stock = 1`, so the
 * cashier sees one button — "Submit & Print Labels" — that does both
 * "land stock in the warehouse" and "produce labels for every unit".
 *
 * Warehouse + cost center are NOT operator-editable fields here. They
 * come from the active POS Profile and are stamped on the server side;
 * the cashier doesn't see them on screen at all.
 */

import { ref, computed, type Ref } from "vue";
import { useItemsStore } from "../../../stores/itemsStore";

declare const frappe: any;

export interface PurchaseInvoiceLine {
	line_id: string;
	item_code: string;
	item_name: string;
	stock_uom: string;
	item_group: string;
	item_uoms: any[];
	uom: string;
	conversion_factor: number;
	qty: number;
	rate: number;
	stock_uom_rate: number;
	standard_rate: number;
	_isEditingQty?: boolean;
	_editingQtyValue?: string;
	_isEditingRate?: boolean;
	_editingRateValue?: string;
	_isEditingUom?: boolean;
}

export function usePurchaseInvoice(options: { posProfile: Ref<any> }) {
	const { posProfile } = options;
	const itemsStore = useItemsStore();

	const purchaseItems = ref<PurchaseInvoiceLine[]>([]);
	const supplier = ref<string | null>(null);
	const supplierCurrency = ref<string | null>(null);
	const supplierPriceList = ref<string | null>(null);
	const priceListCurrency = ref<string | null>(null);
	const billNo = ref<string | null>(null);
	const submitLoading = ref(false);
	const errorMessage = ref("");

	const totalAmount = computed(() => {
		return purchaseItems.value.reduce(
			(sum, item) => sum + item.qty * item.rate,
			0,
		);
	});

	const generateLineId = () => {
		return `pi_${Date.now()}_${Math.floor(Math.random() * 10000)}`;
	};

	const fetchSupplierInfo = async (supplierName: string) => {
		if (!supplierName) {
			supplierPriceList.value = null;
			priceListCurrency.value = null;
			return null;
		}
		try {
			const { message } = await frappe.call({
				method: "posawesome.mizan.api.purchase_orders.get_supplier_info",
				args: { supplier: supplierName },
			});
			if (message) {
				supplierPriceList.value = message.buying_price_list || null;
				priceListCurrency.value = message.price_list_currency || null;
				supplierCurrency.value =
					message.default_currency || posProfile.value?.currency || null;
			}
			return message;
		} catch (e) {
			console.error("Failed to fetch supplier info", e);
			return null;
		}
	};

	const onAddItem = async (item: any) => {
		if (!item) return;

		// Hydrate UOMs if the items panel passed a stripped-down item
		// (e.g. result of a barcode scan).
		if (!item.item_uoms || !item.item_uoms.length) {
			try {
				const details = await itemsStore.getItemByCode(item.item_code);
				if (details) {
					if (details.item_uoms) item.item_uoms = details.item_uoms;
					if (details.purchase_uom)
						item.purchase_uom = details.purchase_uom;
				}
			} catch (e) {
				console.warn("Failed to fetch item details for UOMs", e);
			}
		}

		const existing = purchaseItems.value.find(
			(p) => p.item_code === item.item_code,
		);

		if (existing) {
			existing.qty += 1;
			return;
		}

		let rate = item.rate || item.standard_rate || 0;
		let uom = item.purchase_uom || item.stock_uom;
		let conversion_factor = 1;

		if (uom !== item.stock_uom && item.item_uoms) {
			const uomData = item.item_uoms.find((u: any) => u.uom === uom);
			if (uomData) {
				conversion_factor = uomData.conversion_factor;
			}
		}

		// Try fetching the buying-list rate so the cashier doesn't
		// have to type the supplier's price for every line. Falls back
		// to standard_rate if the price list lookup misses.
		const activePriceList = supplierPriceList.value || itemsStore.activePriceList;
		if (activePriceList) {
			try {
				const { message } = await frappe.call({
					method: "posawesome.mizan.api.items.get_price_for_uom",
					args: {
						item_code: item.item_code,
						price_list: activePriceList,
						uom,
					},
				});
				if (message !== undefined && message !== null && message > 0) {
					rate = message;
				}
			} catch (e) {
				console.warn("Failed to fetch buying price for item", e);
			}
		}

		const newLine: PurchaseInvoiceLine = {
			line_id: generateLineId(),
			item_code: item.item_code,
			item_name: item.item_name,
			stock_uom: item.stock_uom,
			item_group: item.item_group,
			item_uoms: item.item_uoms || [
				{ uom: item.stock_uom, conversion_factor: 1 },
			],
			uom,
			conversion_factor,
			qty: 1,
			rate,
			stock_uom_rate: rate,
			standard_rate: item.standard_rate || 0,
		};

		purchaseItems.value.unshift(newLine);

		if (newLine.uom !== newLine.stock_uom) {
			updateItemUom(newLine, newLine.uom);
		}
	};

	const updateItemUom = async (item: PurchaseInvoiceLine, value: string) => {
		if (!item || !value) return;

		item.uom = value;
		const matched = (item.item_uoms || []).find(
			(uom: any) => uom.uom === value,
		);
		item.conversion_factor = matched ? matched.conversion_factor : 1;

		let priceFound = false;
		try {
			const priceList = supplierPriceList.value || itemsStore.activePriceList;
			if (priceList) {
				const { message } = await frappe.call({
					method: "posawesome.mizan.api.items.get_price_for_uom",
					args: {
						item_code: item.item_code,
						price_list: priceList,
						uom: value,
					},
				});
				if (message !== undefined && message !== null && message > 0) {
					item.rate = message;
					priceFound = true;
				}
			}
		} catch (e) {
			console.error("Failed to update rate for UOM", e);
		}

		if (!priceFound) {
			const baseRate = item.stock_uom_rate || item.standard_rate || 0;
			item.rate = baseRate * item.conversion_factor;
		}
	};

	const updateItemQty = (item: PurchaseInvoiceLine, value: any) => {
		const val = Number.parseFloat(value);
		item.qty = Number.isNaN(val) ? 0 : val;
	};

	const updateItemRate = (item: PurchaseInvoiceLine, value: any) => {
		const val = Number.parseFloat(value);
		item.rate = Number.isNaN(val) ? 0 : val;
	};

	const removeItem = (item: PurchaseInvoiceLine) => {
		purchaseItems.value = purchaseItems.value.filter(
			(row) => row.line_id !== item.line_id,
		);
	};

	const resetForm = () => {
		supplier.value = null;
		supplierPriceList.value = null;
		priceListCurrency.value = null;
		purchaseItems.value = [];
		errorMessage.value = "";
		submitLoading.value = false;
		billNo.value = null;
	};

	return {
		purchaseItems,
		supplier,
		supplierCurrency,
		supplierPriceList,
		priceListCurrency,
		billNo,
		totalAmount,
		submitLoading,
		errorMessage,
		onAddItem,
		fetchSupplierInfo,
		updateItemUom,
		updateItemQty,
		updateItemRate,
		removeItem,
		resetForm,
		generateLineId,
	};
}
