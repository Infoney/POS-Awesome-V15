/**
 * Cart-level stock availability bridge to the `stockCoordinator` singleton.
 *
 * This composable does not store stock data itself — it delegates to
 * `stockCoordinator`, the application-wide singleton that merges availability
 * from IndexedDB, reservations from other open carts, and realtime server updates.
 *
 * **`primeInvoiceStockState(source?)`**
 * Called once when an invoice loads. Seeds the coordinator from the current cart
 * items (both `items` and `packed_items`) so that availability is immediately
 * computed without waiting for a coordinator event.
 *
 * **`emitCartQuantities()`**
 * Builds a `Record<itemCode, stockQty>` from all cart lines and calls
 * `stockCoordinator.updateReservations` to register the cart's demand. The
 * coordinator returns the item codes whose availability changed; these are
 * forwarded to `applyStockStateToInvoiceItems` so only affected items are updated.
 * Emits `cart_quantities_updated` on the event bus for other consumers.
 *
 * **`applyStockStateToInvoiceItems(codes?)`**
 * Pushes coordinator availability data into the cart item objects. When `codes`
 * is provided only items whose `item_code` is in the set are touched; passing
 * `null` updates every item. Calls `forceUpdate()` after writing if the caller
 * provides one (needed for Vue reactivity when items are mutated in place).
 *
 * **`handleStockCoordinatorUpdate(event)`**
 * Event handler for coordinator broadcast events. Receives `{ codes: string[] }`
 * and forwards only those codes to `applyStockStateToInvoiceItems`.
 */
import stockCoordinator from "../../../utils/stockCoordinator";

export function useInvoiceStock(
	items: any,
	packed_items: any,
	eventBus: any,
	forceUpdate: (() => void) | null,
) {
	const applyStockStateToInvoiceItems = (codes: unknown = null) => {
		const collections: any[][] = [];
		if (Array.isArray(items.value)) {
			collections.push(items.value);
		}
		if (Array.isArray(packed_items.value)) {
			collections.push(packed_items.value);
		}
		if (!collections.length) {
			return;
		}
		const codesSet = (() => {
			if (codes === null) {
				return null;
			}
			const iterableCandidate = codes as any;
			const iterable = Array.isArray(codes)
				? codes
				: codes instanceof Set ||
					  (codes &&
							typeof iterableCandidate[Symbol.iterator] ===
								"function")
					? Array.from(iterableCandidate)
					: [codes];
			return new Set(
				iterable
					.map((code) =>
						code !== undefined && code !== null
							? String(code).trim()
							: "",
					)
					.filter(Boolean),
			);
		})();

		collections.forEach((collection) => {
			stockCoordinator.applyAvailabilityToCollection(
				collection,
				codesSet,
				{
					updateBaseAvailable: false,
				},
			);
		});

		if (forceUpdate) forceUpdate();
	};

	const emitCartQuantities = () => {
		const totals: Record<string, number> = {};
		// `batchTotals` mirrors `totals` but split by chosen batch:
		// `{ item_code: { batch_no: stockQty } }`. Drives the per-batch
		// chip deduction in the items selector so the cashier sees
		// batches go down as they pick them — previously only the
		// headline qty deducted, the batch chips stayed at their
		// original snapshot regardless of cart state.
		const batchTotals: Record<string, Record<string, number>> = {};
		const seenItemCodes = new Set<string>();
		const normalizeNumber = (value: unknown) => {
			const num = Number(value);
			return Number.isFinite(num) ? num : null;
		};
		const accumulate = (line: any) => {
			if (!line || !line.item_code) {
				return;
			}

			const code = String(line.item_code).trim();
			if (!code) {
				return;
			}

			let stockQty = normalizeNumber(line.stock_qty);
			if (stockQty === null) {
				const qty = normalizeNumber(line.qty);
				if (qty !== null) {
					const conversion = normalizeNumber(line.conversion_factor);
					const factor =
						conversion !== null && conversion !== 0
							? conversion
							: 1;
					stockQty = qty * factor;
				}
			}

			if (stockQty === null) {
				return;
			}

			const positiveQty = Math.max(0, stockQty);
			if (!positiveQty) {
				return;
			}

			totals[code] = (totals[code] || 0) + positiveQty;
			seenItemCodes.add(code);

			const batchNo = line.batch_no
				? String(line.batch_no).trim()
				: "";
			if (batchNo) {
				if (!batchTotals[code]) {
					batchTotals[code] = {};
				}
				batchTotals[code][batchNo] =
					(batchTotals[code][batchNo] || 0) + positiveQty;
			}
		};

		(Array.isArray(items.value) ? items.value : []).forEach(accumulate);
		(Array.isArray(packed_items.value) ? packed_items.value : []).forEach(
			accumulate,
		);

		const impacted = stockCoordinator.updateReservations(totals, {
			source: "invoice",
		});

		// Push an empty batch map for any item that's in the cart but
		// has no batch chosen — clears stale per-batch reservations
		// when a row's batch is removed/changed.
		seenItemCodes.forEach((code) => {
			if (!batchTotals[code]) {
				batchTotals[code] = {};
			}
		});
		const batchImpacted = stockCoordinator.updateBatchReservations(batchTotals, {
			source: "invoice",
		});

		const allImpacted = Array.from(new Set([...impacted, ...batchImpacted]));
		if (allImpacted.length) {
			applyStockStateToInvoiceItems(allImpacted);
		}

		if (eventBus) {
			eventBus.emit("cart_quantities_updated", totals);
		}
	};

	const primeInvoiceStockState = (source = "invoice") => {
		const baseItems: any[] = [];
		if (Array.isArray(items.value)) {
			baseItems.push(...items.value);
		}
		if (Array.isArray(packed_items.value)) {
			baseItems.push(...packed_items.value);
		}
		if (!baseItems.length) {
			return;
		}

		// `ifMissing: true` so the invoice-side prime can only seed
		// codes the items selector hasn't already cached. Stops a
		// loaded draft (whose lines carry a stale `actual_qty`
		// snapshot from when the draft was saved) from clobbering
		// the live server qty in stockCoordinator and inflating the
		// left-panel display.
		stockCoordinator.primeFromItems(baseItems, {
			silent: true,
			source,
			ifMissing: true,
		});
		const codes = baseItems
			.map((item) =>
				item && item.item_code !== undefined
					? String(item.item_code).trim()
					: null,
			)
			.filter(Boolean);
		applyStockStateToInvoiceItems(codes);
	};

	const handleStockCoordinatorUpdate = (event: any = {}) => {
		const codes = Array.isArray(event.codes) ? event.codes : [];
		if (!codes.length) {
			return;
		}
		applyStockStateToInvoiceItems(codes);
	};

	return {
		emitCartQuantities,
		applyStockStateToInvoiceItems,
		primeInvoiceStockState,
		handleStockCoordinatorUpdate,
	};
}
