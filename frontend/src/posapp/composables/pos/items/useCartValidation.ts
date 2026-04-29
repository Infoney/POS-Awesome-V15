import { ref } from "vue";
import { useToastStore } from "../../../stores/toastStore.js";
import {
	parseBooleanSetting,
	formatStockShortageError,
} from "../../../utils/stock.js";

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
		skipServerValidation = false,
		isReturnInvoice = false,
		deferStockValidationToPayment = false,
		currentCartItems: any[] = [],
	) {
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

			if (
				item.actual_qty === 0 &&
				posProfile?.posa_display_items_in_stock &&
				!isReturnInvoice
			) {
				toastStore.show({
					title: `No stock available for ${item.item_name}`,
					color: "error",
				});
				return false;
			}

			const isStockItem = parseBooleanSetting(item?.is_stock_item);

			if (isStockItem && !isReturnInvoice) {
				const allowNegativeStock =
					!blockSaleBeyondAvailableQty &&
					(parseBooleanSetting(stockSettings?.allow_negative_stock) ||
						parseBooleanSetting(item?.allow_negative_stock));

				// Cart-aware availability: previously this check compared the
				// single click's `requestedQty` against `item.actual_qty`, so
				// a click of qty=1 on a 2-stock item ALWAYS passed even when
				// the cart already held 3 of the same item (palcotest log:
				// ADOL 125MG 10 SUPP cart hit qty 4 against 2 in-stock).
				// Sum the existing cart qty for the same item (in stock UoM
				// via `stock_qty`) so the gate fires once total + requested
				// would exceed `actual_qty`. Negative-qty lines (returns)
				// are excluded — they free stock back rather than reserving.
				let cartReservedStockQty = 0;
				if (Array.isArray(currentCartItems)) {
					for (const line of currentCartItems) {
						if (!line || line.item_code !== item.item_code) continue;
						const stockQty = Number(line.stock_qty);
						const fallbackQty = Number(line.qty);
						const conv = Number(line.conversion_factor) || 1;
						const lineStockQty = Number.isFinite(stockQty) && stockQty
							? stockQty
							: Number.isFinite(fallbackQty)
								? fallbackQty * conv
								: 0;
						if (lineStockQty > 0) {
							cartReservedStockQty += lineStockQty;
						}
					}
				}
				const requestedStockQty = (() => {
					const conv = Number(item.conversion_factor) || 1;
					const stockQty = Number(item.stock_qty);
					if (Number.isFinite(stockQty) && stockQty) return stockQty;
					return Number(requestedQty || 0) * conv;
				})();
				const totalAfterAdd = cartReservedStockQty + requestedStockQty;
				const exceedsAvailable =
					typeof item.actual_qty === "number" &&
					totalAfterAdd > item.actual_qty;
				const blockSale = !allowNegativeStock && exceedsAvailable;

				if (blockSale) {
					toastStore.show({
						title: formatStockShortageError(
							item.item_name || item.item_code,
							item.actual_qty,
							totalAfterAdd,
						),
						color: "error",
					});
					return false;
				}

				if (!skipServerValidation) {
					const stockValidationResult = await validateStockOnServer(
						item,
						requestedQty,
						posProfile,
					);

					if (!stockValidationResult.isValid) {
						toastStore.show({
							title: formatStockShortageError(
								stockValidationResult.data?.item_name ||
									item.item_name ||
									item.item_code,
								stockValidationResult.data?.available_qty ??
									item.actual_qty,
								stockValidationResult.data?.requested_qty ??
									requestedQty,
							),
							color: "error",
						});
						return false;
					}
				}
			}
			return true;
		} catch (error: any) {
			console.error("Cart validation error:", error);
			validationError.value = error.message;
			return performFallbackValidation(
				item,
				requestedQty,
				stockSettings,
				eventBus,
				blockSaleBeyondAvailableQty,
				_showNegativeStockWarning,
				isReturnInvoice,
				deferStockValidationToPayment,
				currentCartItems,
			);
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
		item: any,
		requestedQty: number,
		stockSettings: any,
		eventBus: any,
		blockSaleBeyondAvailableQty = false,
		_showNegativeStockWarning = true,
		isReturnInvoice = false,
		deferStockValidationToPayment = false,
		currentCartItems: any[] = [],
	) {
		console.warn(
			"Using fallback validation due to server validation failure",
		);

		if (deferStockValidationToPayment && !isReturnInvoice) {
			return true;
		}

		const isStockItem = parseBooleanSetting(item?.is_stock_item);

		if (isStockItem && !isReturnInvoice) {
			const allowNegativeStock =
				!blockSaleBeyondAvailableQty &&
				(parseBooleanSetting(stockSettings?.allow_negative_stock) ||
					parseBooleanSetting(item?.allow_negative_stock));

			if (item.actual_qty < 0 && !allowNegativeStock) {
				toastStore.show({
					title: formatStockShortageError(
						item.item_name || item.item_code,
						item.actual_qty,
						requestedQty,
					),
					color: "error",
				});
				return false;
			}

			// Mirror the cart-aware comparison from validateCartItem so the
			// fallback path can't silently pass a click that the primary
			// path would block. See validateCartItem for the rationale.
			let cartReservedStockQty = 0;
			if (Array.isArray(currentCartItems)) {
				for (const line of currentCartItems) {
					if (!line || line.item_code !== item.item_code) continue;
					const stockQty = Number(line.stock_qty);
					const fallbackQty = Number(line.qty);
					const conv = Number(line.conversion_factor) || 1;
					const lineStockQty = Number.isFinite(stockQty) && stockQty
						? stockQty
						: Number.isFinite(fallbackQty)
							? fallbackQty * conv
							: 0;
					if (lineStockQty > 0) {
						cartReservedStockQty += lineStockQty;
					}
				}
			}
			const requestedStockQty = (() => {
				const conv = Number(item.conversion_factor) || 1;
				const stockQty = Number(item.stock_qty);
				if (Number.isFinite(stockQty) && stockQty) return stockQty;
				return Number(requestedQty || 0) * conv;
			})();
			const totalAfterAdd = cartReservedStockQty + requestedStockQty;
			const exceedsAvailable =
				typeof item.actual_qty === "number" &&
				totalAfterAdd > item.actual_qty;
			const blockSale = !allowNegativeStock && exceedsAvailable;
			if (blockSale) {
				toastStore.show({
					title: formatStockShortageError(
						item.item_name || item.item_code,
						item.actual_qty,
						totalAfterAdd,
					),
					color: "error",
				});
				return false;
			}
		}

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
