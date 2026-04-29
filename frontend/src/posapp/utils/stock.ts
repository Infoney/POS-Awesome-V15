/**
 * Utility functions for stock-related logic and message formatting.
 */

declare const __: any;

/**
 * Parses a value into a boolean based on standard Frappe/POS settings.
 * @param value The value to parse (string, number, or boolean)
 * @returns boolean
 */
export function parseBooleanSetting(value: any): boolean {
    if (value === undefined || value === null) {
        return false;
    }

    if (typeof value === "string") {
        const normalized = value.trim().toLowerCase();
        return ["1", "true", "yes", "on"].includes(normalized);
    }

    if (typeof value === "number") {
        return value === 1;
    }

    return Boolean(value);
}

/**
 * Formats a stock shortage error message.
 * @param itemName The name of the item
 * @param availableQty The quantity currently available
 * @param requestedQty The quantity requested by the user
 * @returns Formatted translated string
 */
export function formatStockShortageError(itemName: string | null, availableQty: number, requestedQty: number): string {
    const label = itemName || __("this item");
    const available = availableQty ?? 0;
    const requested = requestedQty ?? 0;

    return __("{0} has only {1} in stock. You requested {2}. Adjust quantity or restock.", [
        label,
        available,
        requested,
    ]);
}

/**
 * Formats a negative stock warning message.
 * @param itemName The name of the item
 * @param availableQty The quantity currently available
 * @param requestedQty The quantity that would be added/removed
 * @returns Formatted translated string
 */
export function formatNegativeStockWarning(itemName: string | null, availableQty: number, requestedQty: number): string {
    const label = itemName || __("this item");
    const available = availableQty ?? 0;
    const requested = requestedQty ?? 0;

    return __("Stock update: {0} has {1} available. Adding {2} will bring the stock below zero.", [
        label,
        available,
        requested,
    ]);
}

export type ParsedNegativeStockShortage = {
    item_code: string;
    batch_no: string;
    warehouse: string;
    /** On-hand BEFORE this invoice tried to consume — `requested - |negative|`, floored at 0. */
    available: number;
    /** Stock-qty the failing line tried to consume. */
    requested: number;
    /** Negative balance reported by the server (positive number). */
    negative_qty: number;
};

/**
 * Parses an ERPNext "Batch No X has negative stock of [quantity] -N in warehouse Y"
 * error string into a structured shortage row. Returns `null` when the
 * message doesn't match either of the two known formats:
 *
 *   1. "Batch No <strong>X</strong> of an Item <strong>Y</strong>
 *       has negative stock of <strong>-1.0</strong> in the warehouse Z"
 *   2. "Batch No <strong>X</strong> of an Item <strong>Y</strong>
 *       has negative stock of quantity <strong>-1.0</strong>
 *       in the warehouse Z"
 *
 * The v15+ Serial and Batch Bundle validator uses format (2)
 * (frappe/erpnext#41908, #41909) — the "quantity" word between "of"
 * and the number is what tripped up an earlier strict regex and let
 * background-submit failures slip past the StockConflictDialog router.
 */
export function parseNegativeStockMessage(rawMessage: string): ParsedNegativeStockShortage | null {
    if (!rawMessage) return null;
    const stripped = String(rawMessage)
        .replace(/<[^>]+>/g, "")
        .replace(/\s+/g, " ")
        .trim();
    const re =
        /Batch\s+No\s+([^\s]+)\s+of\s+an?\s+Item\s+([^\s]+)\s+has\s+negative\s+stock\s+of\s+(?:quantity\s+)?(-?[0-9]+(?:\.[0-9]+)?)\s+in\s+(?:the\s+)?warehouse\s+(.+?)(?:\.|$)/i;
    const match = stripped.match(re);
    if (!match) return null;
    const batch_no = String(match[1] ?? "");
    const item_code = String(match[2] ?? "");
    const negative_qty = Math.abs(parseFloat(String(match[3] ?? "0")) || 0);
    const warehouse = String(match[4] ?? "").trim();
    if (!batch_no || !item_code || !warehouse) return null;

    return {
        item_code,
        batch_no,
        warehouse,
        // Caller decorates with the actual requested qty from the cart line;
        // when nothing better is known, fall back to the negative balance
        // (server's negative ≡ requested - available, so requested ≥ negative).
        requested: negative_qty,
        available: 0,
        negative_qty,
    };
}
