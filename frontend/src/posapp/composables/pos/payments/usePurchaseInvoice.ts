/*
 * State + helpers for the in-app one-step Purchase Invoice flow.
 *
 * Mirrors `usePurchaseReceipt.ts` 1:1 (batch / expiry / serial state,
 * item-meta lookup, validate) with two intentional differences:
 *
 *   - Submit hits `posawesome.mizan.api.purchase_invoices.
 *     create_purchase_invoice`, which builds a Purchase Invoice with
 *     `update_stock = 1` (single document for stock + payable) instead
 *     of a Purchase Receipt.
 *   - The server response carries a `labels[]` payload — one entry
 *     per unit purchased — that the page hands to
 *     `BarcodeLabelPrintDialog` for the post-submit print pass.
 *
 * Everything else (batch resolution, serial parsing, supplier price-
 * list resolution, UOM cascades, qty / rate / discount editors) is
 * lifted from the PR composable so the UX is identical between the
 * two screens. Cashiers who already use PR for stock-only intake can
 * switch to PI for stock-with-payable intake without re-learning the
 * form.
 */

import { ref, computed, type Ref } from "vue";
import { useItemsStore } from "../../../stores/itemsStore";
import { formatUtils } from "../../../format";

declare const frappe: any;
declare const __: (_str: string, _args?: any[]) => string;

export interface PurchaseInvoiceBatchOption {
	name: string;
	batch_id: string;
	expiry_date: string | null;
	supplier: string | null;
	is_expired: boolean;
}

export interface PurchaseInvoiceLine {
	line_id: string;
	item_code: string;
	item_name: string;
	stock_uom: string;
	item_group?: string;
	item_uoms: any[];
	uom: string;
	conversion_factor: number;
	qty: number;
	rate: number;
	discount_percentage: number;
	stock_uom_rate: number;
	standard_rate: number;
	has_batch_no: boolean;
	has_serial_no: boolean;
	batch_no: string;
	batch_is_new: boolean;
	batch_expiry_date: string | null;
	batch_options: PurchaseInvoiceBatchOption[];
	batch_options_loaded: boolean;
	batch_options_loading: boolean;
	serial_no: string;
	_isEditingQty?: boolean;
	_editingQtyValue?: string;
	_isEditingRate?: boolean;
	_editingRateValue?: string;
	_isEditingDiscount?: boolean;
	_editingDiscountValue?: string;
	_isEditingUom?: boolean;
}

export function usePurchaseInvoice(options: {
	posProfile: Ref<any>;
	formatFloat?: (_val: any, _prec?: number) => number;
}) {
	const { posProfile } = options;
	const itemsStore = useItemsStore();

	const invoiceItems = ref<PurchaseInvoiceLine[]>([]);
	const supplier = ref<string | null>(null);
	const warehouse = ref<string | null>(null);
	const costCenter = ref<string | null>(null);
	const postingDate = ref<string | null>(null);
	const billNo = ref<string | null>(null);
	const supplierCurrency = ref<string | null>(null);
	const supplierPriceList = ref<string | null>(null);
	const priceListCurrency = ref<string | null>(null);
	const updatePriceList = ref(false);
	const submitLoading = ref(false);
	const errorMessage = ref("");

	const totalAmount = computed(() =>
		invoiceItems.value.reduce((sum, row) => {
			const lineTotal =
				row.qty *
				row.rate *
				(1 - (Number(row.discount_percentage) || 0) / 100);
			return sum + lineTotal;
		}, 0),
	);

	const totalQty = computed(() =>
		invoiceItems.value.reduce(
			(sum, row) => sum + (Number(row.qty) || 0),
			0,
		),
	);

	const generateLineId = () =>
		`pi_${Date.now()}_${Math.floor(Math.random() * 10000)}`;

	const fetchSupplierInfo = async (supplierName: string | null) => {
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

	const fetchItemMeta = async (itemCode: string) => {
		try {
			const { message } = await frappe.call({
				method: "posawesome.mizan.api.purchase_receipts.get_item_meta",
				args: { item_code: itemCode },
			});
			return message || null;
		} catch (e) {
			console.warn("Failed to fetch item meta", e);
			return null;
		}
	};

	const loadBatchOptions = async (
		row: PurchaseInvoiceLine,
		{ force = false } = {},
	): Promise<PurchaseInvoiceBatchOption[]> => {
		if (!row.has_batch_no) return [];
		if (row.batch_options_loaded && !force) return row.batch_options;
		row.batch_options_loading = true;
		try {
			const { message } = await frappe.call({
				method:
					"posawesome.mizan.api.purchase_receipts.get_existing_batches",
				args: { item_code: row.item_code },
			});
			row.batch_options = Array.isArray(message)
				? (message as PurchaseInvoiceBatchOption[])
				: [];
			row.batch_options_loaded = true;
		} catch (e) {
			console.warn("Failed to load batches", e);
			row.batch_options = [];
		} finally {
			row.batch_options_loading = false;
		}
		return row.batch_options;
	};

	const onAddItem = async (item: any) => {
		if (!item) return;

		const meta = await fetchItemMeta(item.item_code);
		if (meta) {
			if (!item.item_uoms || !item.item_uoms.length) {
				item.item_uoms = meta.item_uoms;
			}
			item.has_batch_no = meta.has_batch_no;
			item.has_serial_no = meta.has_serial_no;
			item.purchase_uom = meta.purchase_uom;
			item.stock_uom = meta.stock_uom || item.stock_uom;
		}

		// For batched items: one row per batch entry (so the user can
		// land 5 boxes of batch A and 3 of batch B as two lines on the
		// same Panadol). For non-batched: stack qty on the existing row.
		const existing = !meta?.has_batch_no
			? invoiceItems.value.find(
					(row) => row.item_code === item.item_code,
				)
			: undefined;

		if (existing) {
			existing.qty += 1;
			return;
		}

		let rate = item.rate || item.standard_rate || meta?.standard_rate || 0;
		const uom = item.purchase_uom || item.stock_uom;
		let conversion_factor = 1;
		if (uom !== item.stock_uom && item.item_uoms) {
			const uomData = item.item_uoms.find((u: any) => u.uom === uom);
			if (uomData) conversion_factor = uomData.conversion_factor || 1;
		}

		const activePriceList =
			supplierPriceList.value || itemsStore.activePriceList;
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

		const newRow: PurchaseInvoiceLine = {
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
			discount_percentage: 0,
			stock_uom_rate: rate,
			standard_rate: item.standard_rate || meta?.standard_rate || 0,
			has_batch_no: !!meta?.has_batch_no,
			has_serial_no: !!meta?.has_serial_no,
			batch_no: "",
			batch_is_new: false,
			batch_expiry_date: null,
			batch_options: [],
			batch_options_loaded: false,
			batch_options_loading: false,
			serial_no: "",
		};

		invoiceItems.value.unshift(newRow);

		if (newRow.has_batch_no) {
			void loadBatchOptions(newRow);
		}
	};

	const updateItemUom = async (row: PurchaseInvoiceLine, value: string) => {
		if (!row || !value) return;
		row.uom = value;
		const matched = (row.item_uoms || []).find(
			(uom: any) => uom.uom === value,
		);
		row.conversion_factor = matched?.conversion_factor || 1;

		let priceFound = false;
		try {
			const priceList = supplierPriceList.value || itemsStore.activePriceList;
			if (priceList) {
				const { message } = await frappe.call({
					method: "posawesome.mizan.api.items.get_price_for_uom",
					args: {
						item_code: row.item_code,
						price_list: priceList,
						uom: value,
					},
				});
				if (message !== undefined && message !== null && message > 0) {
					row.rate = message;
					priceFound = true;
				}
			}
		} catch (e) {
			console.error("Failed to update rate for UOM", e);
		}

		if (!priceFound) {
			const baseRate = row.stock_uom_rate || row.standard_rate || 0;
			row.rate = baseRate * row.conversion_factor;
		}
	};

	const updateItemQty = (row: PurchaseInvoiceLine, value: any) => {
		const val = parseFloat(value);
		row.qty = isNaN(val) ? 0 : val;
	};

	const updateItemRate = (row: PurchaseInvoiceLine, value: any) => {
		const val = parseFloat(value);
		row.rate = isNaN(val) ? 0 : val;
	};

	const updateItemDiscount = (row: PurchaseInvoiceLine, value: any) => {
		const val = parseFloat(value);
		const safe = isNaN(val) ? 0 : Math.max(0, Math.min(100, val));
		row.discount_percentage = safe;
	};

	const setBatch = (
		row: PurchaseInvoiceLine,
		value:
			| string
			| null
			| undefined
			| {
					value?: string;
					title?: string;
					batch_id?: string;
					name?: string;
					raw?: any;
			  },
	) => {
		// Vuetify v-combobox can emit a raw string (free text) OR an
		// object (item picked from dropdown). Coerce both shapes to a
		// clean string before normalizing.
		let raw: unknown = value;
		if (raw && typeof raw === "object") {
			const obj = raw as Record<string, any>;
			raw =
				obj.value ??
				obj.batch_id ??
				obj.name ??
				obj.title ??
				obj.raw?.batch_id ??
				obj.raw?.name ??
				"";
		}
		const batchId = String(raw ?? "").trim();
		row.batch_no = batchId;
		const match = row.batch_options.find(
			(opt) => opt.batch_id === batchId || opt.name === batchId,
		);
		if (match) {
			row.batch_is_new = false;
			row.batch_expiry_date = match.expiry_date || null;
		} else {
			row.batch_is_new = !!batchId;
			if (!batchId) {
				row.batch_expiry_date = null;
			}
		}
	};

	const removeItem = (row: PurchaseInvoiceLine) => {
		invoiceItems.value = invoiceItems.value.filter(
			(line) => line.line_id !== row.line_id,
		);
	};

	const resetForm = () => {
		supplier.value = null;
		supplierPriceList.value = null;
		priceListCurrency.value = null;
		invoiceItems.value = [];
		errorMessage.value = "";
		submitLoading.value = false;
		updatePriceList.value = false;
		billNo.value = null;
		warehouse.value =
			posProfile.value?.posa_purchase_warehouse ||
			posProfile.value?.warehouse ||
			null;
		costCenter.value =
			posProfile.value?.cost_center ||
			posProfile.value?.posa_cost_center ||
			null;
		postingDate.value = formatUtils.toArabicNumerals(
			frappe.datetime.nowdate(),
		);
	};

	const validate = (): string | null => {
		if (!supplier.value) return __("Supplier is required.");
		if (!warehouse.value) return __("Warehouse is required.");
		if (!invoiceItems.value.length)
			return __("Add at least one item before submitting.");

		for (const row of invoiceItems.value) {
			if (!row.qty || row.qty <= 0) {
				return __("Quantity must be greater than zero for {0}.", [
					row.item_name,
				]);
			}
			if (row.rate < 0) {
				return __("Rate cannot be negative for {0}.", [row.item_name]);
			}
			if (row.has_batch_no) {
				if (!row.batch_no) {
					return __("Pick or enter a batch for {0}.", [row.item_name]);
				}
				if (row.batch_is_new && !row.batch_expiry_date) {
					return __(
						"New batch {0} for {1} needs an expiry date.",
						[row.batch_no, row.item_name],
					);
				}
			}
			if (row.has_serial_no && !row.serial_no.trim()) {
				return __("Enter serial numbers for {0}.", [row.item_name]);
			}
		}

		return null;
	};

	const submitInvoice = async () => {
		const validation = validate();
		if (validation) {
			errorMessage.value = validation;
			throw new Error(validation);
		}
		errorMessage.value = "";
		submitLoading.value = true;
		try {
			const payload = {
				pos_profile: posProfile.value?.name || posProfile.value,
				supplier: supplier.value,
				company: posProfile.value?.company,
				warehouse: warehouse.value,
				cost_center: costCenter.value || undefined,
				posting_date: postingDate.value,
				bill_no: billNo.value || undefined,
				buying_price_list: supplierPriceList.value || undefined,
				update_price_list: updatePriceList.value ? 1 : 0,
				items: invoiceItems.value.map((row) => ({
					item_code: row.item_code,
					item_name: row.item_name,
					qty: row.qty,
					uom: row.uom,
					stock_uom: row.stock_uom,
					conversion_factor: row.conversion_factor,
					rate: row.rate,
					discount_percentage: row.discount_percentage,
					warehouse: warehouse.value,
					batch_no: row.has_batch_no ? row.batch_no : undefined,
					batch_expiry_date: row.has_batch_no
						? row.batch_expiry_date
						: undefined,
					serial_no: row.has_serial_no ? row.serial_no : undefined,
				})),
			};

			const { message } = await frappe.call({
				method:
					"posawesome.mizan.api.purchase_invoices.create_purchase_invoice",
				args: { data: JSON.stringify(payload) },
			});
			return message;
		} finally {
			submitLoading.value = false;
		}
	};

	return {
		invoiceItems,
		supplier,
		warehouse,
		costCenter,
		postingDate,
		billNo,
		supplierCurrency,
		supplierPriceList,
		priceListCurrency,
		updatePriceList,
		totalAmount,
		totalQty,
		submitLoading,
		errorMessage,
		onAddItem,
		fetchSupplierInfo,
		loadBatchOptions,
		setBatch,
		updateItemUom,
		updateItemQty,
		updateItemRate,
		updateItemDiscount,
		removeItem,
		resetForm,
		submitInvoice,
		generateLineId,
	};
}
