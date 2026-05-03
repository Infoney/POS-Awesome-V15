# Copyright (c) 2020, Youssef Restom and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from posawesome.mizan.doctype.pos_closing_shift.closing_processing.utils import get_base_value
from posawesome.mizan.doctype.pos_closing_shift.closing_processing.data import (
    get_cashiers,
    get_pos_invoices,
    get_payments_entries,
)
from posawesome.mizan.doctype.pos_closing_shift.closing_processing.overview import (
    get_closing_shift_overview,
    get_payment_reconciliation_details,
)
from posawesome.mizan.doctype.pos_closing_shift.closing_processing.creation import (
    make_closing_shift_from_opening,
    submit_closing_shift,
)
from posawesome.mizan.doctype.pos_closing_shift.closing_processing.invoices import (
    submit_printed_invoices,
    delete_draft_invoices,
    _set_closing_entry_invoices,
    _clear_closing_entry_invoices,
    consolidate_closing_shift_invoices
)

class POSClosingShift(Document):
    def validate(self):
        user = frappe.get_all(
            "POS Closing Shift",
            filters={
                "user": self.user,
                "docstatus": 1,
                "pos_opening_shift": self.pos_opening_shift,
                "name": ["!=", self.name],
            },
        )

        if user:
            frappe.throw(
                _(
                    "POS Closing Shift {} against {} between selected period".format(
                        frappe.bold("already exists"), frappe.bold(self.user)
                    )
                ),
                title=_("Invalid Period"),
            )

        if frappe.db.get_value("POS Opening Shift", self.pos_opening_shift, "status") != "Open":
            frappe.throw(
                _("Selected POS Opening Shift should be open."),
                title=_("Invalid Opening Entry"),
            )
        self.update_payment_reconciliation()
        # Belt-and-braces cashier resolution. The desk JS in
        # `pos_closing_shift.js::add_to_pos_transaction` already stamps
        # `cashier` on each row when the form is built, but stale
        # browser-cached desk JS (or tenants who skipped a `bench
        # build`) can leave the column empty. Resolving server-side at
        # validate time guarantees the column is populated regardless of
        # what JS the cashier had loaded — and the same pass also
        # rebuilds the per-cashier rollup table from authoritative
        # invoice data.
        self.populate_pos_transaction_cashiers()
        self.aggregate_cashiers_table()

    def populate_pos_transaction_cashiers(self):
        """
        Walk every `pos_transactions` row and resolve `cashier` from
        the linked Sales Invoice / POS Invoice's `posa_cashier`,
        falling back to `owner` for invoices that predate the
        Custom Field. Only fills empty rows so a hand-edited cashier
        on the desk grid is never overwritten.
        """
        rows = self.get("pos_transactions") or []
        if not rows:
            return

        invoice_lookup = {}
        for row in rows:
            if row.get("cashier"):
                continue
            doctype = "POS Invoice" if row.get("pos_invoice") else "Sales Invoice"
            invoice_name = row.get("pos_invoice") or row.get("sales_invoice")
            if not invoice_name:
                continue
            invoice_lookup.setdefault(doctype, set()).add(invoice_name)

        cached = {}
        for doctype, names in invoice_lookup.items():
            if not frappe.db.exists("DocType", doctype):
                continue
            fields = ["name", "owner"]
            try:
                meta = frappe.get_meta(doctype)
                if meta.has_field("posa_cashier"):
                    fields.append("posa_cashier")
            except Exception:
                pass
            data = frappe.get_all(
                doctype,
                filters={"name": ["in", list(names)]},
                fields=fields,
            )
            for entry in data:
                cached[(doctype, entry["name"])] = entry

        for row in rows:
            if row.get("cashier"):
                continue
            doctype = "POS Invoice" if row.get("pos_invoice") else "Sales Invoice"
            invoice_name = row.get("pos_invoice") or row.get("sales_invoice")
            if not invoice_name:
                continue
            entry = cached.get((doctype, invoice_name)) or {}
            cashier = entry.get("posa_cashier") or entry.get("owner")
            if cashier and cashier not in ("Administrator", "Guest"):
                row.cashier = cashier

    def aggregate_cashiers_table(self):
        """
        Rebuild the `cashiers` rollup child table from the (just-
        resolved) `pos_transactions` rows. Idempotent — full rebuild
        every save so a re-saved shift always reflects the current
        invoice state.

        Sales Person hydration: each User can carry an optional
        `posa_sales_person` link (added in
        `posawesome/patches/add_cashier_tracking_fields.py`). When set,
        the rollup row carries it through so commission reports can
        group by Sales Person without a User join.
        """
        if not self.meta.has_field("cashiers"):
            return

        rows = self.get("pos_transactions") or []
        buckets = {}
        for row in rows:
            cashier = row.get("cashier")
            if not cashier:
                continue
            bucket = buckets.setdefault(
                cashier,
                {
                    "cashier": cashier,
                    "invoice_count": 0,
                    "grand_total": 0.0,
                    "net_total": 0.0,
                },
            )
            bucket["invoice_count"] += 1
            bucket["grand_total"] += flt(row.get("grand_total") or 0)

        # Net total is more meaningfully sourced from the actual
        # invoice's `base_net_total`; pos_transactions only carries
        # `grand_total` (in company currency) so net is computed from a
        # batched lookup rather than estimated client-side.
        invoice_lookup = {}
        for row in rows:
            cashier = row.get("cashier")
            if not cashier or cashier not in buckets:
                continue
            doctype = "POS Invoice" if row.get("pos_invoice") else "Sales Invoice"
            invoice_name = row.get("pos_invoice") or row.get("sales_invoice")
            if invoice_name:
                invoice_lookup.setdefault(doctype, []).append((invoice_name, cashier))

        for doctype, items in invoice_lookup.items():
            if not items or not frappe.db.exists("DocType", doctype):
                continue
            names = [name for name, _ in items]
            net_rows = frappe.get_all(
                doctype,
                filters={"name": ["in", names]},
                fields=["name", "base_net_total"],
            )
            net_by_name = {r["name"]: flt(r.get("base_net_total") or 0) for r in net_rows}
            for invoice_name, cashier in items:
                if cashier in buckets:
                    buckets[cashier]["net_total"] += net_by_name.get(invoice_name, 0)

        # Optional posa_sales_person resolution.
        users = list(buckets.keys())
        sales_person_by_user = {}
        if users:
            try:
                if frappe.db.has_column("User", "posa_sales_person"):
                    user_rows = frappe.get_all(
                        "User",
                        filters={"name": ["in", users]},
                        fields=["name", "posa_sales_person"],
                    )
                    sales_person_by_user = {
                        r["name"]: r.get("posa_sales_person") or ""
                        for r in user_rows
                    }
            except Exception:
                pass

        # Replace child rows with the freshly computed rollup so a
        # re-validated shift never leaves stale rows behind.
        self.set("cashiers", [])
        for bucket in sorted(buckets.values(), key=lambda b: (b.get("cashier") or "").lower()):
            self.append(
                "cashiers",
                {
                    "cashier": bucket["cashier"],
                    "invoice_count": bucket["invoice_count"],
                    "grand_total": flt(bucket["grand_total"]),
                    "net_total": flt(bucket["net_total"]),
                    "sales_person": sales_person_by_user.get(bucket["cashier"], ""),
                },
            )

    def update_payment_reconciliation(self):
        # update the difference values in Payment Reconciliation child table
        # get default precision for site
        precision = frappe.get_cached_value("System Settings", None, "currency_precision") or 3
        for d in self.payment_reconciliation:
            d.difference = +flt(d.closing_amount, precision) - flt(d.expected_amount, precision)

    def on_submit(self):
        opening_entry = frappe.get_doc("POS Opening Shift", self.pos_opening_shift)
        opening_entry.pos_closing_shift = self.name
        opening_entry.set_status()
        self.delete_draft_invoices()
        opening_entry.save()
        # link invoices with this closing shift so ERPNext can block edits
        _set_closing_entry_invoices(self)
        consolidate_closing_shift_invoices(self)

    def on_cancel(self):
        if frappe.db.exists("POS Opening Shift", self.pos_opening_shift):
            opening_entry = frappe.get_doc("POS Opening Shift", self.pos_opening_shift)
            if opening_entry.pos_closing_shift == self.name:
                opening_entry.pos_closing_shift = ""
                opening_entry.set_status()
                opening_entry.save()
        # remove links from invoices so they can be cancelled
        _clear_closing_entry_invoices(self)

    def delete_draft_invoices(self):
        delete_draft_invoices(self.pos_opening_shift, self.pos_profile)

    @frappe.whitelist()
    def get_payment_reconciliation_details(self):
        return get_payment_reconciliation_details(self)
