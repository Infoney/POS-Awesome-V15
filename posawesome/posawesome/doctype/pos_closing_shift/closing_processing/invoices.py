from contextlib import contextmanager

import frappe
from frappe import _, DoesNotExistError
from erpnext.accounts.doctype.pos_invoice_merge_log.pos_invoice_merge_log import (
    consolidate_pos_invoices,
)


@contextmanager
def _negative_stock_close_shift_guard():
    """Allow transient negative batch positions during close-shift writes.

    Used in two places along the close-shift flow:

    1. ``submit_printed_invoices`` — auto-submits any POS Invoice that was
       printed during the shift but never reached ``submit()`` (e.g. the
       cashier handed over goods + collected cash, the receipt printed,
       but the network blip prevented the docstatus=1 commit). At
       close-shift the close-shift dialog opens by calling
       ``make_closing_shift_from_opening``, which runs this auto-submit;
       if any batch on a printed-but-unsubmitted line has gone negative
       since the print (returns, recons, sales on a parallel terminal),
       ERPNext's per-batch validator throws and blocks the cashier from
       even *opening* the close dialog. Refusing the submit is worse than
       allowing it — the goods are already gone — so we relax the flag.

    2. ``consolidate_closing_shift_invoices`` — ERPNext's
       ``consolidate_pos_invoices`` re-aggregates the shift's POS Invoice
       movements into a Consolidated Sales Invoice and reposts the
       resulting SLEs. If between original submit and consolidation any
       batch went transiently negative, the reposting trips the same
       validator and blocks the close (e.g.
       "Batch No 42524365 of an Item 22929 has negative stock of quantity
       -1.0 in the warehouse AL-KHANSA PHARMACY - PPC"). Consolidation is
       a financial roll-up — the actual stock impact already happened at
       individual POS Invoice submit time — so suppressing the validator
       here is also safe.

    POSAwesome's own preflight (``_validate_stock_on_invoice``) still
    enforces no-negative-stock at the cashier's *initial* submit, so this
    guard only relaxes the after-the-fact close-shift rewrites — not the
    live sale path.

    Restored in ``finally`` so a thrown error inside ERPNext can't leak
    the relaxed flag to subsequent requests on the same worker.
    """

    previous = getattr(frappe.flags, "allow_negative_stock", False)
    frappe.flags.allow_negative_stock = True
    try:
        yield
    finally:
        frappe.flags.allow_negative_stock = previous


# Back-compat alias for any external import that grabbed the old name.
_negative_stock_consolidation_guard = _negative_stock_close_shift_guard

def _set_closing_entry_invoices(closing_shift_doc):
    """Set `pos_closing_entry` on linked invoices."""
    for d in closing_shift_doc.pos_transactions:
        invoice = d.get("sales_invoice") or d.get("pos_invoice")
        if not invoice:
            continue
        doctype = "Sales Invoice" if d.get("sales_invoice") else "POS Invoice"
        if frappe.db.has_column(doctype, "pos_closing_entry"):
            frappe.db.set_value(doctype, invoice, "pos_closing_entry", closing_shift_doc.name)

def _clear_closing_entry_invoices(closing_shift_doc):
    """Clear closing shift links, cancel merge logs and cancel consolidated sales invoices."""
    consolidated_sales_invoices = set()
    for d in closing_shift_doc.pos_transactions:
        pos_invoice = d.get("pos_invoice")
        sales_invoice = d.get("sales_invoice")
        if pos_invoice:
            if frappe.db.has_column("POS Invoice", "pos_closing_entry"):
                frappe.db.set_value("POS Invoice", pos_invoice, "pos_closing_entry", None)

            merge_logs = frappe.get_all(
                "POS Invoice Merge Log",
                filters={"pos_invoice": pos_invoice},
                pluck="name",
            )
            for log in merge_logs:
                log_doc = frappe.get_doc("POS Invoice Merge Log", log)
                for field in (
                    "consolidated_invoice",
                    "consolidated_credit_note",
                ):
                    si = log_doc.get(field)
                    if si:
                        consolidated_sales_invoices.add(si)
                if log_doc.docstatus == 1:
                    log_doc.cancel()
                frappe.delete_doc("POS Invoice Merge Log", log_doc.name, force=1)

            if frappe.db.has_column("POS Invoice", "consolidated_invoice"):
                frappe.db.set_value("POS Invoice", pos_invoice, "consolidated_invoice", None)

            if frappe.db.has_column("POS Invoice", "status"):
                pos_doc = frappe.get_doc("POS Invoice", pos_invoice)
                pos_doc.set_status(update=True)

        if sales_invoice:
            if frappe.db.has_column("Sales Invoice", "pos_closing_entry"):
                frappe.db.set_value("Sales Invoice", sales_invoice, "pos_closing_entry", None)
            if _is_consolidated_sales_invoice(sales_invoice):
                consolidated_sales_invoices.add(sales_invoice)

    for si in consolidated_sales_invoices:
        if frappe.db.exists("Sales Invoice", si):
            si_doc = frappe.get_doc("Sales Invoice", si)
            if si_doc.docstatus == 1:
                si_doc.cancel()

def _is_consolidated_sales_invoice(sales_invoice):
    """Return True if the Sales Invoice was generated by consolidating POS Invoices."""

    if not sales_invoice:
        return False

    if frappe.db.exists("POS Invoice Merge Log", {"consolidated_invoice": sales_invoice}):
        return True

    return bool(frappe.db.exists("POS Invoice Merge Log", {"consolidated_credit_note": sales_invoice}))

def delete_draft_invoices(pos_opening_shift, pos_profile):
    if frappe.get_value("POS Profile", pos_profile, "posa_allow_delete"):
        doctype = (
            "POS Invoice"
            if frappe.db.get_value(
                "POS Profile",
                pos_profile,
                "create_pos_invoice_instead_of_sales_invoice",
            )
            else "Sales Invoice"
        )
        data = frappe.db.sql(
            f"""
        select
            name
        from
            `tab{doctype}`
        where
            docstatus = 0 and posa_is_printed = 0 and posa_pos_opening_shift = %s
        """,
            (pos_opening_shift),
            as_dict=1,
        )

        for invoice in data:
            frappe.delete_doc(doctype, invoice.name, force=1)

def _get_cancelled_return_against(invoice_doc, doctype):
    if not invoice_doc.get("is_return"):
        return None

    return_against = invoice_doc.get("return_against")
    if not return_against:
        return None

    if frappe.db.get_value(doctype, return_against, "docstatus") == 2:
        return return_against

    return None

def submit_printed_invoices(pos_opening_shift, doctype):
    skipped_invoices = []
    invoices_list = frappe.get_all(
        doctype,
        filters={
            "posa_pos_opening_shift": pos_opening_shift,
            "docstatus": 0,
            "posa_is_printed": 1,
        },
    )
    # Wrap the whole loop in the close-shift negative-stock guard. The
    # cashier already printed the receipt and handed over goods on each
    # printed-but-unsubmitted invoice; refusing the docstatus=1 commit at
    # close-shift just leaves an inconsistent system-of-record vs.
    # reality (and worse — it blocks the cashier from even *opening* the
    # close-shift dialog, since this runs inside
    # ``make_closing_shift_from_opening``). See the guard's docstring.
    with _negative_stock_close_shift_guard():
        for invoice in invoices_list:
            invoice_doc = frappe.get_doc(doctype, invoice.name)
            cancelled_return_against = _get_cancelled_return_against(invoice_doc, doctype)
            if cancelled_return_against:
                skipped_invoices.append(
                    frappe._dict(
                        {
                            "invoice": invoice_doc.name,
                            "doctype": doctype,
                            "return_against": cancelled_return_against,
                        }
                    )
                )
                frappe.log_error(
                    title="POS Closing Shift Skipped Invalid Return Draft",
                    message=_(
                        "Skipped printed draft invoice {0} during close shift because Return Against {1} is cancelled."
                    ).format(invoice_doc.name, cancelled_return_against),
                )
                continue
            invoice_doc.submit()
    return skipped_invoices

def consolidate_closing_shift_invoices(closing_shift_doc):
    if frappe.db.get_value(
        "POS Profile",
        closing_shift_doc.pos_profile,
        "create_pos_invoice_instead_of_sales_invoice",
    ):
        pos_invoices = []
        for d in closing_shift_doc.pos_transactions:
            invoice_details = frappe._dict(
                frappe.db.get_value(
                    "POS Invoice",
                    d.pos_invoice,
                    [
                        "name as pos_invoice",
                        "customer",
                        "is_return",
                        "return_against",
                        "currency",
                    ],
                    as_dict=True,
                )
            )
            if invoice_details:
                pos_invoices.append(invoice_details)

        if pos_invoices:
            invoices_by_currency = {}
            for invoice in pos_invoices:
                invoices_by_currency.setdefault(invoice.currency, []).append(invoice)

            # Suppress ERPNext's per-batch negative-stock validator only for
            # the consolidation reposting — see _negative_stock_close_shift_guard
            # for the full rationale.
            with _negative_stock_close_shift_guard():
                for invoices in invoices_by_currency.values():
                    consolidate_pos_invoices(pos_invoices=invoices)
