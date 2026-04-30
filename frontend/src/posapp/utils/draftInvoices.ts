declare const frappe: any;

export const resolveDraftInvoiceDoctype = (
	draft: any,
	posProfile: any,
) => {
	if (draft?.doctype) {
		return draft.doctype;
	}

	return posProfile?.create_pos_invoice_instead_of_sales_invoice
		? "POS Invoice"
		: "Sales Invoice";
};

export const fetchDraftInvoices = async ({
	posOpeningShift,
	posProfile,
}: {
	posOpeningShift: any;
	posProfile: any;
}) => {
	const doctype = posProfile?.create_pos_invoice_instead_of_sales_invoice
		? "POS Invoice"
		: "Sales Invoice";

	const { message } = await frappe.call({
		method: "posawesome.mizan.api.invoices.get_draft_invoices",
		args: {
			// Send both: backend prefers pos_profile when present so the cashier
			// sees every draft on this terminal across shifts; pos_opening_shift
			// is kept as a fallback for older callers / supervisor scope.
			pos_profile: posProfile?.name,
			pos_opening_shift: posOpeningShift?.name,
			doctype,
		},
	});

	return Array.isArray(message) ? message : [];
};

export const fetchDraftInvoiceDoc = async ({
	draft,
	posProfile,
}: {
	draft: any;
	posProfile: any;
}) => {
	if (!draft?.name) {
		return null;
	}

	const { message } = await frappe.call({
		method: "posawesome.mizan.api.invoices.get_draft_invoice_doc",
		args: {
			invoice_name: draft.name,
			doctype: resolveDraftInvoiceDoctype(draft, posProfile),
		},
	});

	return message || null;
};

/**
 * Shape of a single stock-shortage line returned from the backend's
 * `validate_draft_invoice_stock` endpoint. Mirrors the row shape used by
 * `check_invoice_availability` so the same downstream rendering helpers
 * can format both.
 */
export interface DraftStockWarningLine {
	item_code: string;
	item_name: string;
	warehouse: string;
	batch_no: string;
	requested_qty: number;
	available_qty: number;
	/**
	 * "insufficient_batch_stock" — a specific batch ran dry.
	 * "no_batch_with_enough_qty" — no single batch can fulfil the request.
	 * "insufficient_stock" — non-batched item, Bin total too low.
	 */
	reason: string;
}

export interface DraftStockWarningResult {
	ok: boolean;
	lines: DraftStockWarningLine[];
	invoice_name: string | null;
	invoice_doctype: string | null;
}

/**
 * Re-run the same submit-time stock validator against an existing draft so
 * the cashier sees stock deltas the moment they reopen the draft, rather
 * than at the payment screen. Drafts do NOT post Stock Ledger entries —
 * they're just saved cart state — so between save and reload another
 * terminal may have sold the same items. This call surfaces that delta.
 *
 * Network or permission failures are intentionally swallowed and reported
 * as `{ok: true, lines: []}` so a transient outage never blocks a draft
 * from loading. The pre-submit validator will still catch real problems
 * before money changes hands.
 */
export const validateDraftInvoiceStock = async ({
	draft,
	posProfile,
}: {
	draft: any;
	posProfile: any;
}): Promise<DraftStockWarningResult> => {
	const fallback: DraftStockWarningResult = {
		ok: true,
		lines: [],
		invoice_name: draft?.name || null,
		invoice_doctype: resolveDraftInvoiceDoctype(draft, posProfile),
	};

	if (!draft?.name) {
		return fallback;
	}

	try {
		const { message } = await frappe.call({
			method:
				"posawesome.mizan.api.invoice_processing.stock.validate_draft_invoice_stock",
			args: {
				invoice_name: draft.name,
				doctype: resolveDraftInvoiceDoctype(draft, posProfile),
				pos_profile: posProfile?.name || null,
			},
		});
		if (!message || typeof message !== "object") {
			return fallback;
		}
		return {
			ok: message.ok !== false,
			lines: Array.isArray(message.lines) ? message.lines : [],
			invoice_name: message.invoice_name || draft.name,
			invoice_doctype:
				message.invoice_doctype ||
				resolveDraftInvoiceDoctype(draft, posProfile),
		};
	} catch (err) {
		// Don't let a stock-check failure stop the cashier from opening
		// their saved work — the submit-time validator is the real gate.
		console.warn(
			"[validateDraftInvoiceStock] failed; loading draft without warnings",
			err,
		);
		return fallback;
	}
};

/**
 * Convenience wrapper: fetch the draft doc and run the stock validator
 * concurrently, returning both. Use this from the "Drafts" / "Held sales"
 * dialog so the cashier gets the cart loaded immediately and sees a
 * stock warning toast in the same breath if anything has gone short
 * since the draft was saved.
 *
 * The two requests run in parallel because they're independent — the
 * cart can render even if the validator is slow, and a slow doc fetch
 * doesn't delay the warning if the validator returns first.
 */
export const fetchDraftInvoiceDocWithStockCheck = async ({
	draft,
	posProfile,
}: {
	draft: any;
	posProfile: any;
}): Promise<{
	message: any;
	stockWarnings: DraftStockWarningResult;
}> => {
	const [message, stockWarnings] = await Promise.all([
		fetchDraftInvoiceDoc({ draft, posProfile }),
		validateDraftInvoiceStock({ draft, posProfile }),
	]);

	return { message, stockWarnings };
};
