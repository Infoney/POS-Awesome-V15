import { ref } from "vue";
import { useToastStore } from "../../../stores/toastStore.js";
import { getDisplayStockQty } from "../../../utils/stock";

declare const __: (_text: string, _args?: any[]) => string;
declare const frappe: any;

export function useCartValidation() {
	const isValidating = ref(false);
	const validationError = ref<string | null>(null);
	const toastStore = useToastStore();

	async function validateCartItem(
		item: any,
		requestedQty = 1,
		posProfile: any,
		stockSettings: any,
		eventBus: any,
		blockSaleBeyondAvailableQty = false,
		_showNegativeStockWarning = true,
		_skipServerValidation = false,
		isReturnInvoice = false,
		deferStockValidationToPayment = false,
		_currentCartItems: any[] = [],
	) {
		// New architecture (2026-04-29):
		//
		// The client is a best-effort cache; the server is the only source
		// of truth for stock and batch availability at submit time. Earlier
		// revisions tried to enforce per-item / per-batch stock gates in
		// the cashier's browser using `item.actual_qty` and a cart-aware
		// running total, but that path repeatedly mis-reported because the
		// reference values drift (warehouse-scoped dashboard refresh
		// rewriting `actual_qty`, `batch_no_data` baselines getting
		// re-stamped on every detail fetch, items store hydrated from the
		// offline cache during boot, etc.). When the client number is
		// wrong the gate either blocks legitimate sales (the screenshot
		// where cart 2 + requested 1 = 3 vs actual 3 was rejected as
		// "only 1 in stock") or passes oversells without warning.
		//
		// What we do here now:
		//   - Variant template → block (the cashier needs to pick a child).
		//   - Order / Quotation flows → pass (stock is enforced when the
		//     order is converted to an invoice).
		//   - Hard "out of stock" sanity gate (actual_qty === 0 AND the
		//     profile is configured to display only in-stock items) →
		//     block. This is the only stock check that doesn't depend on
		//     cart math; it just refuses to even try when the bin is
		//     empty.
		//   - Everything else → pass through to addItem. ERPNext validates
		//     batch / bin shortages on submit and the existing
		//     StockConflictDialog flow (see usePaymentSubmission
		//     `emitStockConflictDialog`) presents the structured error so
		//     the cashier can adjust the cart and retry.
		isValidating.value = true;
		validationError.value = null;

		try {
			if (!item || !item.item_code) {
				throw new Error("Invalid item data");
			}

			if (item.has_variants) {
				toastStore.show({
					title: __(
						"This is an item template. Please choose a variant.",
					),
					color: "warning",
				});
				return false;
			}

			// Allow adding lines in Order/Quotation; enforce stock at Invoice payment/submit stage.
			if (deferStockValidationToPayment && !isReturnInvoice) {
				return true;
			}

			// Block "literally out of stock" using the SAME computation
			// the items panel uses to draw the headline qty
			// (`getDisplayStockQty`) — otherwise the card honestly shows
			// "Qty: 3" (sum of non-expired batches with positive
			// `batch_qty`) while this gate fires "No stock available"
			// because it gated on `actual_qty` (Bin running total) and
			// the two server fields drift. AL-KHANSA report:
			// ACNECINAMIDE batch 350 had batch_qty=3 but Bin=0 →
			// click was rejected even though stock was sellable.
			if (
				getDisplayStockQty(item) <= 0 &&
				posProfile?.posa_display_items_in_stock &&
				!isReturnInvoice
			) {
				toastStore.show({
					title: `No stock available for ${item.item_name}`,
					color: "error",
				});
				return false;
			}

			// Quiet the unused-arg lint noise; these stay in the signature
			// for backward compatibility with callers that haven't yet been
			// updated to drop them.
			void blockSaleBeyondAvailableQty;
			void stockSettings;
			void requestedQty;
			return true;
		} catch (error: any) {
			console.error("Cart validation error:", error);
			validationError.value = error.message;
			// On unexpected client-side errors, fail open — let the request
			// reach the server, which is authoritative.
			return true;
		} finally {
			isValidating.value = false;
		}
	}

	async function validateStockOnServer(
		item: any,
		requestedQty: number,
		posProfile: any,
	) {
		try {
			const testItem = {
				item_code: item.item_code,
				item_name: item.item_name,
				warehouse: posProfile?.warehouse || item.warehouse,
				qty: Math.abs(requestedQty),
				stock_qty: Math.abs(requestedQty),
				actual_qty: item.actual_qty,
				uom: item.stock_uom || item.uom || "Nos",
			};

			const response = await frappe.call({
				method: "posawesome.posawesome.api.invoices.validate_cart_items",
				args: {
					items: JSON.stringify([testItem]),
					pos_profile: posProfile?.name,
				},
			});

			if (response.message && response.message.length > 0) {
				const stockIssue = response.message[0];
				return {
					isValid: false,
					message: `${stockIssue.item_code}: Insufficient stock. Available: ${stockIssue.available_qty}, Requested: ${stockIssue.requested_qty}`,
					data: stockIssue,
				};
			}

			return {
				isValid: true,
				message: "Stock validation passed",
				data: null,
			};
		} catch (error) {
			console.error("Server stock validation failed:", error);
			throw new Error("Unable to validate stock on server");
		}
	}

	function performFallbackValidation(
		_item: any,
		_requestedQty: number,
		_stockSettings: any,
		_eventBus: any,
		_blockSaleBeyondAvailableQty = false,
		_showNegativeStockWarning = true,
		_isReturnInvoice = false,
		_deferStockValidationToPayment = false,
		_currentCartItems: any[] = [],
	) {
		// Kept for backward compatibility with external callers; the
		// primary validateCartItem now fails open on its own (the
		// architecture is "client = best-effort cache, server = source of
		// truth at submit"), so this fallback is also a pass-through.
		return true;
	}

	async function validateCartItems(
		items: any[],
		posProfile: any,
		stockSettings: any,
		eventBus: any,
		blockSaleBeyondAvailableQty = false,
		showNegativeStockWarning = true,
		isReturnInvoice = false,
		deferStockValidationToPayment = false,
		currentCartItems: any[] = [],
	) {
		const validItems: any[] = [];
		const invalidItems: any[] = [];

		for (const item of items) {
			const isValid = await validateCartItem(
				item.item || item,
				item.qty || 1,
				posProfile,
				stockSettings,
				eventBus,
				blockSaleBeyondAvailableQty,
				showNegativeStockWarning,
				false,
				isReturnInvoice,
				deferStockValidationToPayment,
				currentCartItems,
			);

			if (isValid) {
				validItems.push(item);
			} else {
				invalidItems.push(item);
			}
		}

		return {
			valid: validItems,
			invalid: invalidItems,
			hasErrors: invalidItems.length > 0,
		};
	}

	return {
		isValidating,
		validationError,
		validateCartItem,
		validateCartItems,
		validateStockOnServer,
		performFallbackValidation,
	};
}
