import frappe
from frappe.utils import flt, json
from collections import defaultdict
from frappe import _
from posawesome.mizan.doctype.pos_closing_shift.closing_processing.utils import get_base_value
from posawesome.mizan.doctype.pos_closing_shift.closing_processing.data import (
    get_pos_invoices,
    get_payments_entries,
)

@frappe.whitelist()
def get_closing_shift_overview(pos_opening_shift):
    """Return invoice and payment totals for the provided POS Opening Shift."""

    if not pos_opening_shift:
        frappe.throw(_("POS Opening Shift is required to compute the overview."))

    opening_shift_doc = None
    opening_shift_name = None
    payload = pos_opening_shift

    if isinstance(payload, str):
        try:
            parsed = json.loads(payload)
        except ValueError:
            opening_shift_name = payload
        else:
            payload = parsed if isinstance(parsed, dict) else payload

    if isinstance(payload, dict):
        opening_shift_name = payload.get("name") or opening_shift_name
    elif getattr(payload, "doctype", None) == "POS Opening Shift":
        opening_shift_doc = payload
        opening_shift_name = payload.name
    elif opening_shift_name is None:
        opening_shift_name = getattr(payload, "name", None)

    if not opening_shift_doc:
        if not opening_shift_name:
            frappe.throw(_("Invalid POS Opening Shift data provided."))
        opening_shift_doc = frappe.get_doc("POS Opening Shift", opening_shift_name)

    if opening_shift_doc.doctype != "POS Opening Shift":
        frappe.throw(_("Unable to resolve POS Opening Shift."))

    pos_profile = opening_shift_doc.pos_profile
    company = opening_shift_doc.company
    company_currency = frappe.get_cached_value("Company", company, "default_currency")

    use_pos_invoice = frappe.db.get_value(
        "POS Profile",
        pos_profile,
        "create_pos_invoice_instead_of_sales_invoice",
    )
    doctype = "POS Invoice" if use_pos_invoice else "Sales Invoice"
    invoices = get_pos_invoices(opening_shift_doc.name, doctype, submit_printed=0)

    total_invoices = len(invoices)
    company_currency_total = 0
    multi_currency_totals = {}
    payments_by_mode = {}
    credit_company_currency_total = 0
    credit_invoices_count = 0
    credit_totals_by_currency = {}
    gross_company_currency_total = 0
    sale_invoices_count = 0
    returns_company_currency_total = 0
    returns_count = 0
    returns_totals_by_currency = {}
    change_company_currency_total = 0
    change_totals_by_currency = {}
    overpayment_change_company_currency_total = 0
    overpayment_change_totals_by_currency = {}
    total_change_totals_by_currency = {}
    cash_movement_count = 0
    cash_movement_company_currency_total = 0
    cash_movement_totals_by_type = {}
    cash_movement_totals_by_currency = {}
    # Tax collected during the shift, broken three ways so the dialog +
    # print can answer "how much of today's revenue was tax owed to the
    # government vs revenue we keep":
    #   * `tax_company_currency_total` — single number, sum of every
    #     invoice's `base_total_taxes_and_charges`. Used by the new
    #     "Taxes Collected" insight card.
    #   * `tax_account_breakdown` — per `account_head` (e.g. "4209 - KSA
    #     Expo Tax - KPG"), so accounting can see the per-account
    #     liability without reading the underlying invoices.
    #   * `tax_currency_breakdown` — per invoice currency, to mirror the
    #     other multi_currency_totals tables (so a SAR shift on a KWD
    #     company shows tax both in SAR and KWD).
    tax_company_currency_total = 0
    tax_account_breakdown = {}
    tax_currency_breakdown = {}
    # Cashier-of-record breakdown. Multiple cashiers can rotate on the
    # same Opening Shift via the in-app Switch Cashier flow (PIN-based,
    # doesn't end the shift). Group invoices by `posa_cashier` here so
    # the dialog + A4 print can show "who rang what" without scanning
    # every linked invoice. `posa_cashier` is the User who owned the
    # POS terminal at submit time — see `_ensure_posa_cashier` in
    # `posawesome/mizan/api/invoice_processing/creation.py`. Falls back
    # to `owner` for invoices that predate the Custom Field rollout.
    cashier_breakdown = {}

    cash_mode_of_payment = frappe.db.get_value("POS Profile", pos_profile, "posa_cash_mode_of_payment")
    if not cash_mode_of_payment:
        cash_mode_of_payment = "Cash"

    def accumulate_payment(container, mode, currency, amount, base_amount=0, conversion_rate=None):
        if not mode:
            return
        currency = currency or company_currency
        key = (mode, currency)
        if key not in container:
            container[key] = {
                "mode_of_payment": mode,
                "currency": currency,
                "total": 0,
                "company_currency_total": 0,
                "exchange_rates": set(),
            }
        container[key]["total"] += flt(amount)
        container[key]["company_currency_total"] += flt(base_amount)

        if currency != company_currency:
            rate = None
            if flt(amount):
                rate = abs(flt(base_amount)) / abs(flt(amount)) if base_amount else None
            if not rate and conversion_rate:
                rate = flt(conversion_rate)
            if rate:
                container[key]["exchange_rates"].add(rate)

    def resolve_payment_currency(payment_row, invoice_currency):
        for fieldname in (
            "currency",
            "account_currency",
            "payment_currency",
        ):
            value = payment_row.get(fieldname)
            if value:
                return value
        return invoice_currency or company_currency

    shift_invoice_names = {invoice.get("name") for invoice in invoices}
    invoice_shift_link_field_cache = {}
    invoice_membership_cache = {}
    overpayment_invoice_names = set()

    def resolve_shift_link_field(doctype_name):
        if doctype_name in invoice_shift_link_field_cache:
            return invoice_shift_link_field_cache[doctype_name]

        link_field = None
        try:
            meta = frappe.get_meta(doctype_name)
        except frappe.DoesNotExistError:
            meta = None

        if meta:
            for df in meta.get("fields", []):
                if df.fieldtype == "Link" and df.options == "POS Opening Shift":
                    link_field = df.fieldname
                    break

        invoice_shift_link_field_cache[doctype_name] = link_field
        return link_field

    def reference_belongs_to_shift(doctype_name, docname):
        key = (doctype_name, docname)
        if key in invoice_membership_cache:
            return invoice_membership_cache[key]

        if doctype_name == doctype and docname in shift_invoice_names:
            invoice_membership_cache[key] = True
            return True

        link_field = resolve_shift_link_field(doctype_name)
        if not link_field:
            invoice_membership_cache[key] = False
            return False

        value = frappe.db.get_value(doctype_name, docname, link_field)
        invoice_membership_cache[key] = bool(value and value == opening_shift_doc.name)
        return invoice_membership_cache[key]

    payment_entries = get_payments_entries(opening_shift_doc.name)

    payment_entry_names = [row.get("name") for row in payment_entries if row.get("name")]
    references_by_entry = defaultdict(list)

    if payment_entry_names:
        reference_meta = frappe.get_meta("Payment Entry Reference")
        reference_fieldnames = {df.fieldname for df in reference_meta.get("fields", [])}
        reference_fields = [
            "parent",
            "reference_doctype",
            "reference_name",
            "allocated_amount",
        ]

        if "exchange_rate" in reference_fieldnames:
            reference_fields.append("exchange_rate")
        if "allocated_amount_in_company_currency" in reference_fieldnames:
            reference_fields.append("allocated_amount_in_company_currency")
        if "base_allocated_amount" in reference_fieldnames:
            reference_fields.append("base_allocated_amount")

        reference_rows = frappe.get_all(
            "Payment Entry Reference",
            filters={"parent": ["in", payment_entry_names]},
            fields=reference_fields,
        )

        for reference in reference_rows:
            references_by_entry[reference.get("parent")].append(reference)

    for entry in payment_entries:
        if entry.get("payment_type") != "Pay":
            continue

        references = references_by_entry.get(entry.get("name")) or []

        for reference in references:
            reference_doctype = reference.get("reference_doctype")
            reference_name = reference.get("reference_name")
            belongs_to_shift = False

            if reference_doctype and reference_name:
                belongs_to_shift = reference_belongs_to_shift(
                    reference_doctype,
                    reference_name,
                )

            if belongs_to_shift and reference_doctype in {"POS Invoice", "Sales Invoice"}:
                overpayment_invoice_names.add(reference_name)

    def reference_base_amount(reference, fallback_rate=None):
        for fieldname in (
            "allocated_amount_in_company_currency",
            "base_allocated_amount",
        ):
            value = reference.get(fieldname)
            if value not in (None, ""):
                return flt(value)

        amount_value = flt(reference.get("allocated_amount") or 0)
        rate_value = reference.get("exchange_rate") or fallback_rate or 1
        return amount_value * flt(rate_value or 1)

    for invoice in invoices:
        conversion_rate = invoice.get("conversion_rate")
        base_grand_total = get_base_value(invoice, "grand_total", "base_grand_total", conversion_rate)
        company_currency_total += base_grand_total
        if base_grand_total >= 0:
            gross_company_currency_total += base_grand_total
            sale_invoices_count += 1
        else:
            returns_company_currency_total += abs(base_grand_total)
            returns_count += 1
        invoice_currency = invoice.get("currency") or company_currency
        invoice_total = invoice.get("rounded_total") or invoice.get("grand_total") or 0

        # Tally per-cashier totals. `posa_cashier` is the User-of-record
        # set when the invoice was submitted (the operator currently
        # active on the POS terminal — possibly different from `owner`
        # if a supervisor was logged in). Pre-rollout invoices where the
        # field is empty fall back to `owner` so legacy shifts still
        # render a non-empty breakdown.
        cashier_user = invoice.get("posa_cashier") or invoice.get("owner")
        if cashier_user:
            cashier_row = cashier_breakdown.setdefault(
                cashier_user,
                {
                    "cashier": cashier_user,
                    "invoice_count": 0,
                    "grand_total": 0,
                    "net_total": 0,
                    # Per-cashier invoice drill-down. The closing dialog
                    # uses this to show "who rang each invoice" so the
                    # store manager can spot anomalies (a cashier with
                    # disproportionately many returns, an oddly-large
                    # ticket on a junior cashier's mini-shift, etc.)
                    # without bouncing to ERPNext list view. Each entry
                    # carries just enough to identify the invoice on the
                    # dialog row — full doc details are one click away
                    # via the linked-invoices grid.
                    "invoices": [],
                },
            )
            cashier_row["invoice_count"] += 1
            net_base = flt(
                get_base_value(invoice, "net_total", "base_net_total", conversion_rate)
            )
            cashier_row["grand_total"] += flt(base_grand_total)
            cashier_row["net_total"] += net_base
            cashier_row["invoices"].append(
                {
                    "name": invoice.get("name"),
                    "doctype": invoice.get("doctype") or doctype,
                    "posting_date": invoice.get("posting_date"),
                    "posting_time": invoice.get("posting_time"),
                    "customer": invoice.get("customer"),
                    "customer_name": invoice.get("customer_name") or invoice.get("customer"),
                    "currency": invoice_currency,
                    "grand_total": flt(invoice.get("grand_total") or 0),
                    "base_grand_total": flt(base_grand_total),
                    "net_total": flt(invoice.get("net_total") or 0),
                    "base_net_total": net_base,
                    "is_return": bool(invoice.get("is_return"))
                    or flt(base_grand_total) < 0,
                }
            )

        # Tax collected on this invoice. The per-account / per-currency
        # breakdown comes from walking the invoice's `taxes` child
        # rows, but with a critical caveat for tax-inclusive +
        # additional-discount setups (the AL-KHANSA Jeddah Expo
        # tenants use exactly this combination):
        #
        # ERPNext stores two values per tax row:
        #   * `tax_amount` / `base_tax_amount`
        #     — the PRE-discount tax that would have applied if no
        #     additional discount were given. ERPNext keeps this for
        #     audit + recompute purposes and it can stay in the row
        #     even after the discount lands.
        #   * `tax_amount_after_discount_amount` /
        #     `base_tax_amount_after_discount_amount`
        #     — the POST-discount tax actually owed. This is what
        #     `total_taxes_and_charges` /
        #     `base_total_taxes_and_charges` aggregate to at the
        #     invoice level, and what the customer actually paid.
        #
        # Summing `base_tax_amount` across rows on a discounted
        # invoice can land at ~2× the real tax (a 50%-discount
        # invoice whose post-discount tax was KWD 17.928 then sums
        # to KWD 35.856 across its rows because both the pre- and
        # post-discount entries linger). Always prefer
        # `*_after_discount_amount`; fall back to the bare field
        # only when ERPNext didn't populate it (unusual — happens on
        # very old invoice versions or non-discount setups where the
        # two are equal anyway).
        #
        # Per-account totals + the headline `tax_company_currency_total`
        # both feed off this same row walk, so they stay consistent
        # by construction (the original drift the user reported on
        # 2026-05-01 — footer KWD 26.892 vs row KWD 53.785 — was the
        # opposite axis of this same problem).
        invoice_doctype = invoice.get("doctype") or doctype
        try:
            invoice_doc = frappe.get_cached_doc(invoice_doctype, invoice.get("name"))
        except frappe.DoesNotExistError:
            invoice_doc = None
        if invoice_doc:
            invoice_tax_currency_sum = 0
            invoice_tax_base_sum = 0
            for tax_row in invoice_doc.get("taxes") or []:
                account_head = tax_row.get("account_head")
                if not account_head:
                    continue
                rate = flt(tax_row.get("rate") or 0)
                # Always prefer the after-discount amounts; fall back
                # to the bare field only if it isn't populated (the
                # two are equal on non-discount invoices anyway).
                raw_amount = tax_row.get("tax_amount_after_discount_amount")
                if raw_amount in (None, ""):
                    raw_amount = tax_row.get("tax_amount")
                row_amount = flt(raw_amount or 0)

                raw_base = tax_row.get("base_tax_amount_after_discount_amount")
                if raw_base in (None, ""):
                    raw_base = tax_row.get("base_tax_amount")
                row_base_amount = flt(
                    raw_base or (row_amount * (flt(conversion_rate) or 1))
                )

                if not row_amount and not row_base_amount:
                    continue
                bucket_key = (account_head, rate, invoice_currency)
                tax_bucket = tax_account_breakdown.setdefault(
                    bucket_key,
                    {
                        "account_head": account_head,
                        "rate": rate,
                        "currency": invoice_currency,
                        "amount": 0,
                        "company_currency_amount": 0,
                    },
                )
                tax_bucket["amount"] += row_amount
                tax_bucket["company_currency_amount"] += row_base_amount
                invoice_tax_currency_sum += row_amount
                invoice_tax_base_sum += row_base_amount

            if invoice_tax_currency_sum or invoice_tax_base_sum:
                tax_company_currency_total += invoice_tax_base_sum
                tax_currency_entry = tax_currency_breakdown.setdefault(
                    invoice_currency,
                    {
                        "currency": invoice_currency,
                        "total": 0,
                        "company_currency_total": 0,
                    },
                )
                tax_currency_entry["total"] += invoice_tax_currency_sum
                tax_currency_entry["company_currency_total"] += invoice_tax_base_sum

        currency_entry = multi_currency_totals.setdefault(
            invoice_currency,
            {
                "currency": invoice_currency,
                "total": 0,
                "invoice_count": 0,
                "company_currency_total": 0,
                "exchange_rates": set(),
            },
        )
        currency_entry["total"] += flt(invoice_total)
        currency_entry["invoice_count"] += 1
        currency_entry["company_currency_total"] += flt(base_grand_total)

        if invoice_currency != company_currency:
            rate = flt(conversion_rate) if conversion_rate else None
            if not rate and flt(invoice_total):
                rate = abs(flt(base_grand_total)) / abs(flt(invoice_total)) if base_grand_total else None
            if rate:
                currency_entry["exchange_rates"].add(rate)

        change_amount = flt(invoice.get("change_amount") or 0)
        has_overpayment_entry = invoice.get("name") in overpayment_invoice_names

        if change_amount and not has_overpayment_entry:
            change_entry = change_totals_by_currency.setdefault(
                invoice_currency,
                {
                    "currency": invoice_currency,
                    "total": 0,
                    "company_currency_total": 0,
                    "exchange_rates": set(),
                },
            )
            change_entry["total"] += change_amount

            change_base_amount = flt(
                get_base_value(invoice, "change_amount", "base_change_amount", conversion_rate)
            )
            change_company_currency_total += change_base_amount
            change_entry["company_currency_total"] += change_base_amount

            total_change_entry = total_change_totals_by_currency.setdefault(
                invoice_currency,
                {
                    "currency": invoice_currency,
                    "total": 0,
                    "company_currency_total": 0,
                    "exchange_rates": set(),
                },
            )
            total_change_entry["total"] += change_amount
            total_change_entry["company_currency_total"] += change_base_amount

            if invoice_currency != company_currency:
                rate = None
                if change_amount:
                    rate = abs(change_base_amount) / abs(change_amount) if change_base_amount else None
                if not rate and conversion_rate:
                    rate = flt(conversion_rate)
                if rate:
                    change_entry["exchange_rates"].add(rate)
                    total_change_entry["exchange_rates"].add(rate)

        outstanding_company_currency = invoice.get("base_outstanding_amount")
        if outstanding_company_currency in (None, ""):
            outstanding_company_currency = invoice.get("outstanding_amount")
        if outstanding_company_currency in (None, ""):
            outstanding_company_currency = get_base_value(
                invoice,
                "outstanding_amount",
                "base_outstanding_amount",
                conversion_rate,
            )
        outstanding_company_currency = flt(outstanding_company_currency or 0)

        if outstanding_company_currency > 0:
            credit_invoices_count += 1
            credit_company_currency_total += outstanding_company_currency
            outstanding_invoice_currency = invoice.get("outstanding_amount")
            if outstanding_invoice_currency in (None, ""):
                base_divisor = flt(conversion_rate) or 0
                if base_divisor:
                    outstanding_invoice_currency = outstanding_company_currency / base_divisor
                else:
                    outstanding_invoice_currency = outstanding_company_currency
            outstanding_invoice_currency = flt(outstanding_invoice_currency or 0)
            credit_entry = credit_totals_by_currency.setdefault(
                invoice_currency,
                {
                    "currency": invoice_currency,
                    "total": 0,
                    "invoice_count": 0,
                    "company_currency_total": 0,
                    "exchange_rates": set(),
                },
            )
            credit_entry["total"] += flt(outstanding_invoice_currency)
            credit_entry["invoice_count"] += 1
            credit_entry["company_currency_total"] += outstanding_company_currency

            if invoice_currency != company_currency:
                rate = None
                if outstanding_invoice_currency:
                    rate = abs(outstanding_company_currency) / abs(flt(outstanding_invoice_currency))
                if not rate and conversion_rate:
                    rate = flt(conversion_rate)
                if rate:
                    credit_entry["exchange_rates"].add(rate)

        is_return = bool(invoice.get("is_return"))
        if not is_return and flt(invoice_total) < 0:
            is_return = True

        if is_return:
            returns_entry = returns_totals_by_currency.setdefault(
                invoice_currency,
                {
                    "currency": invoice_currency,
                    "total": 0,
                    "invoice_count": 0,
                    "company_currency_total": 0,
                    "exchange_rates": set(),
                },
            )
            returns_entry["total"] += abs(flt(invoice_total))
            returns_entry["invoice_count"] += 1
            returns_entry["company_currency_total"] += abs(flt(base_grand_total))

            if invoice_currency != company_currency:
                rate = flt(conversion_rate) if conversion_rate else None
                if not rate and flt(invoice_total):
                    rate = abs(flt(base_grand_total)) / abs(flt(invoice_total)) if base_grand_total else None
                if rate:
                    returns_entry["exchange_rates"].add(rate)

        for payment in invoice.get("payments", []):
            mode = payment.get("mode_of_payment")
            payment_currency = resolve_payment_currency(payment, invoice_currency)
            amount = flt(payment.get("amount") or 0)
            base_amount = get_base_value(payment, "amount", "base_amount", conversion_rate)
            accumulate_payment(
                payments_by_mode,
                mode,
                payment_currency,
                amount,
                base_amount,
                conversion_rate,
            )

    for entry in payment_entries:
        mode = entry.get("mode_of_payment")
        payment_currency = (
            entry.get("paid_to_account_currency")
            or entry.get("paid_from_account_currency")
            or company_currency
        )
        raw_amount = flt(entry.get("paid_amount") or 0)
        entry_rate = (
            entry.get("target_exchange_rate")
            or entry.get("source_exchange_rate")
            or entry.get("exchange_rate")
        )
        raw_base_amount = get_base_value(
            entry,
            "paid_amount",
            "base_paid_amount",
            entry_rate,
        )

        multiplier = -1 if entry.get("payment_type") == "Pay" else 1
        amount = multiplier * abs(raw_amount)
        base_amount = multiplier * abs(raw_base_amount)

        if entry.get("payment_type") == "Pay":
            change_row = overpayment_change_totals_by_currency.setdefault(
                payment_currency,
                {
                    "currency": payment_currency,
                    "total": 0,
                    "company_currency_total": 0,
                    "exchange_rates": set(),
                },
            )
            refund_amount = abs(raw_amount)
            refund_base_amount = abs(raw_base_amount)
            change_row["total"] += refund_amount
            change_row["company_currency_total"] += refund_base_amount
            overpayment_change_company_currency_total += refund_base_amount

            total_change_entry = total_change_totals_by_currency.setdefault(
                payment_currency,
                {
                    "currency": payment_currency,
                    "total": 0,
                    "company_currency_total": 0,
                    "exchange_rates": set(),
                },
            )
            total_change_entry["total"] += refund_amount
            total_change_entry["company_currency_total"] += refund_base_amount

            if payment_currency != company_currency:
                rate = None
                if refund_amount:
                    rate = abs(refund_base_amount) / abs(refund_amount) if refund_base_amount else None
                if not rate and entry_rate:
                    rate = flt(entry_rate)
                if rate:
                    change_row["exchange_rates"].add(rate)
                    total_change_entry["exchange_rates"].add(rate)

        references = references_by_entry.get(entry.get("name")) or []
        allocated_amount_sum = 0
        allocated_base_sum = 0

        if references:
            for reference in references:
                allocated_amount = multiplier * abs(flt(reference.get("allocated_amount") or 0))
                if not allocated_amount:
                    continue

                allocated_base = multiplier * abs(reference_base_amount(reference, entry_rate))
                allocated_amount_sum += allocated_amount
                allocated_base_sum += allocated_base

                reference_doctype = reference.get("reference_doctype")
                reference_name = reference.get("reference_name")
                belongs_to_shift = False
                if reference_doctype and reference_name:
                    belongs_to_shift = reference_belongs_to_shift(
                        reference_doctype,
                        reference_name,
                    )

                rate = reference.get("exchange_rate") or entry_rate

                accumulate_payment(
                    payments_by_mode,
                    mode,
                    payment_currency,
                    allocated_amount,
                    allocated_base,
                    rate,
                )

        residual_amount = amount - allocated_amount_sum
        residual_base = base_amount - allocated_base_sum

        unallocated_amount = entry.get("unallocated_amount")
        if unallocated_amount not in (None, ""):
            residual_amount = multiplier * abs(flt(unallocated_amount))
            residual_base = multiplier * abs(
                get_base_value(
                    entry,
                    "unallocated_amount",
                    "base_unallocated_amount",
                    entry_rate,
                )
            )

        if abs(residual_amount) > 0.0001 or abs(residual_base) > 0.0001:
            accumulate_payment(
                payments_by_mode,
                mode,
                payment_currency,
                residual_amount,
                residual_base,
                entry_rate,
            )

    cash_movements = frappe.get_all(
        "POS Cash Movement",
        filters={"pos_opening_shift": opening_shift_doc.name, "docstatus": 1},
        fields=["movement_type", "amount"],
    )
    for movement in cash_movements:
        movement_amount = abs(flt(movement.get("amount")))
        if not movement_amount:
            continue
        cash_movement_count += 1
        cash_movement_company_currency_total += movement_amount

        movement_type = movement.get("movement_type") or "Unknown"
        type_row = cash_movement_totals_by_type.setdefault(
            movement_type,
            {"movement_type": movement_type, "total": 0},
        )
        type_row["total"] += movement_amount

        currency_row = cash_movement_totals_by_currency.setdefault(
            company_currency,
            {
                "currency": company_currency,
                "total": 0,
                "company_currency_total": 0,
                "exchange_rates": set(),
            },
        )
        currency_row["total"] += movement_amount
        currency_row["company_currency_total"] += movement_amount

    if cash_mode_of_payment:
        for row in payments_by_mode.values():
            if row["mode_of_payment"] != cash_mode_of_payment:
                continue

            overpayment_change_row = overpayment_change_totals_by_currency.get(row["currency"])
            if overpayment_change_row:
                row["total"] -= flt(overpayment_change_row.get("total"))

                base_overpayment_change = overpayment_change_row.get("company_currency_total")
                if base_overpayment_change:
                    row["company_currency_total"] -= flt(base_overpayment_change)

        if cash_movement_company_currency_total:
            cash_key = (cash_mode_of_payment, company_currency)
            cash_row = payments_by_mode.setdefault(
                cash_key,
                {
                    "mode_of_payment": cash_mode_of_payment,
                    "currency": company_currency,
                    "total": 0,
                    "company_currency_total": 0,
                    "exchange_rates": set(),
                },
            )
            cash_row["total"] -= flt(cash_movement_company_currency_total)
            cash_row["company_currency_total"] -= flt(cash_movement_company_currency_total)

    cash_expected_totals = []
    cash_expected_company_currency_total = 0
    if cash_mode_of_payment:
        for row in payments_by_mode.values():
            if row["mode_of_payment"] == cash_mode_of_payment:
                cash_expected_totals.append(
                    {
                        "currency": row["currency"],
                        "total": flt(row["total"]),
                        "company_currency_total": flt(row["company_currency_total"]),
                        "exchange_rates": sorted(
                            {flt(rate) for rate in (row.get("exchange_rates") or []) if flt(rate)}
                        ),
                    },
                )
                cash_expected_company_currency_total += flt(row["company_currency_total"])

    average_invoice_value = 0
    if sale_invoices_count:
        average_invoice_value = gross_company_currency_total / sale_invoices_count

    def prepare_currency_rows(container, include_count=False):
        output = []
        for row in container.values():
            exchange_rates = row.get("exchange_rates") or []
            if isinstance(exchange_rates, set):
                exchange_rates = sorted({flt(rate) for rate in exchange_rates if flt(rate)})
            else:
                exchange_rates = [
                    flt(rate) for rate in exchange_rates if rate not in (None, "") and flt(rate)
                ]
                exchange_rates = sorted(set(exchange_rates))

            record = {
                "currency": row.get("currency"),
                "total": flt(row.get("total")),
                "company_currency_total": flt(row.get("company_currency_total")),
                "exchange_rates": exchange_rates,
            }
            if include_count:
                record["invoice_count"] = row.get("invoice_count", 0)
            output.append(record)
        return sorted(output, key=lambda r: (r.get("currency") or ""))

    def prepare_payment_rows(container):
        output = []
        for row in container.values():
            exchange_rates = row.get("exchange_rates") or []
            if isinstance(exchange_rates, set):
                exchange_rates = sorted({flt(rate) for rate in exchange_rates if flt(rate)})
            else:
                exchange_rates = [
                    flt(rate) for rate in exchange_rates if rate not in (None, "") and flt(rate)
                ]
                exchange_rates = sorted(set(exchange_rates))

            output.append(
                {
                    "mode_of_payment": row.get("mode_of_payment"),
                    "currency": row.get("currency"),
                    "total": flt(row.get("total")),
                    "company_currency_total": flt(row.get("company_currency_total")),
                    "exchange_rates": exchange_rates,
                }
            )

        output.sort(key=lambda r: (r.get("mode_of_payment") or "", r.get("currency") or ""))
        return output

    def prepare_movement_type_rows(container):
        output = []
        for row in container.values():
            output.append(
                {
                    "movement_type": row.get("movement_type"),
                    "total": flt(row.get("total")),
                }
            )
        output.sort(key=lambda r: (r.get("movement_type") or ""))
        return output

    return {
        "total_invoices": total_invoices,
        "company_currency": company_currency,
        "company_currency_total": flt(company_currency_total),
        "multi_currency_totals": prepare_currency_rows(multi_currency_totals, include_count=True),
        "payments_by_mode": prepare_payment_rows(payments_by_mode),
        "credit_invoices": {
            "count": credit_invoices_count,
            "company_currency_total": flt(credit_company_currency_total),
            "by_currency": prepare_currency_rows(credit_totals_by_currency, include_count=True),
        },
        "sales_summary": {
            # GROSS = sum of base_grand_total of POSITIVE invoices (i.e.
            # what customers paid, before subtracting returns). NET =
            # GROSS - returns (= same `company_currency_total` we use
            # for multi-currency rendering). The dialog's "Gross Sales"
            # / "Net Sales" cards read these directly.
            "gross_company_currency_total": flt(gross_company_currency_total),
            "net_company_currency_total": flt(company_currency_total),
            "tax_company_currency_total": flt(tax_company_currency_total),
            "average_invoice_value": flt(average_invoice_value),
            "sale_invoices_count": sale_invoices_count,
        },
        "taxes_collected": {
            "company_currency_total": flt(tax_company_currency_total),
            # Per-account breakdown — useful for accounting reconciliation
            # against the GL. account_head is the tax account
            # (e.g. "4209 - KSA Expo Tax - KPG"), rate is the percent
            # rate from the invoice's tax row.
            "by_account": sorted(
                [
                    {
                        "account_head": row["account_head"],
                        "rate": flt(row.get("rate") or 0),
                        "currency": row.get("currency"),
                        "amount": flt(row.get("amount") or 0),
                        "company_currency_amount": flt(
                            row.get("company_currency_amount") or 0
                        ),
                    }
                    for row in tax_account_breakdown.values()
                ],
                key=lambda r: (
                    r.get("account_head") or "",
                    r.get("currency") or "",
                ),
            ),
            "by_currency": sorted(
                [
                    {
                        "currency": row.get("currency"),
                        "total": flt(row.get("total") or 0),
                        "company_currency_total": flt(
                            row.get("company_currency_total") or 0
                        ),
                    }
                    for row in tax_currency_breakdown.values()
                ],
                key=lambda r: r.get("currency") or "",
            ),
        },
        "returns": {
            "count": returns_count,
            "company_currency_total": flt(returns_company_currency_total),
            "by_currency": prepare_currency_rows(returns_totals_by_currency, include_count=True),
        },
        "change_returned": {
            "company_currency_total": flt(
                change_company_currency_total + overpayment_change_company_currency_total
            ),
            "by_currency": prepare_currency_rows(total_change_totals_by_currency),
            "invoice_change": {
                "company_currency_total": flt(change_company_currency_total),
                "by_currency": prepare_currency_rows(change_totals_by_currency),
            },
            "overpayment_change": {
                "company_currency_total": flt(overpayment_change_company_currency_total),
                "by_currency": prepare_currency_rows(overpayment_change_totals_by_currency),
            },
        },
        "cash_expected": {
            "mode_of_payment": cash_mode_of_payment,
            "company_currency_total": flt(cash_expected_company_currency_total),
            "by_currency": sorted(
                cash_expected_totals,
                key=lambda row: (row.get("currency") or ""),
            ),
        },
        "cash_movements": {
            "count": cash_movement_count,
            "company_currency_total": flt(cash_movement_company_currency_total),
            "by_currency": prepare_currency_rows(cash_movement_totals_by_currency),
            "by_type": prepare_movement_type_rows(cash_movement_totals_by_type),
        },
        "cashiers": _resolve_cashier_breakdown_rows(cashier_breakdown),
    }


def _resolve_cashier_breakdown_rows(cashier_breakdown):
    """
    Hydrate the per-cashier rollup with `full_name` + optional
    `posa_sales_person` lookups. Done in a single batched query
    rather than per-cashier `frappe.db.get_value` calls so a 5-
    cashier shift doesn't pay 10 round-trips.
    """
    if not cashier_breakdown:
        return []
    cashier_users = list(cashier_breakdown.keys())
    user_meta = {}
    try:
        # `posa_sales_person` is added via patch — guard against tenants
        # that haven't migrated yet.
        has_sales_person = frappe.db.has_column("User", "posa_sales_person")
    except Exception:
        has_sales_person = False
    fields = ["name", "full_name"]
    if has_sales_person:
        fields.append("posa_sales_person")
    rows = frappe.get_all(
        "User",
        filters={"name": ["in", cashier_users]},
        fields=fields,
    )
    for row in rows:
        user_meta[row["name"]] = row
    output = []
    for cashier, totals in cashier_breakdown.items():
        meta = user_meta.get(cashier) or {}
        # Chronological invoice order per cashier. Cashier shifts run
        # in real time, so sorting by `(posting_date, posting_time)`
        # mirrors what the operator saw at the till — easier to spot a
        # problematic stretch ("4 returns in a row at 14:30").
        invoices = list(totals.get("invoices") or [])
        invoices.sort(
            key=lambda inv: (
                str(inv.get("posting_date") or ""),
                str(inv.get("posting_time") or ""),
                str(inv.get("name") or ""),
            )
        )
        output.append(
            {
                "cashier": cashier,
                "cashier_name": meta.get("full_name") or cashier,
                "sales_person": meta.get("posa_sales_person") or "",
                "invoice_count": int(totals.get("invoice_count") or 0),
                "grand_total": flt(totals.get("grand_total") or 0),
                "net_total": flt(totals.get("net_total") or 0),
                "invoices": invoices,
            }
        )
    output.sort(key=lambda r: (r.get("cashier_name") or "").lower())
    return output

@frappe.whitelist()
def get_payment_reconciliation_details(closing_shift_doc):
    company_currency = frappe.get_cached_value("Company", closing_shift_doc.company, "default_currency")

    sales_breakdown = defaultdict(float)
    net_breakdown = defaultdict(float)
    payment_breakdown = {}

    def update_payment_breakdown(mode_of_payment, base_amount=0, currency=None, amount=0):
        if not mode_of_payment:
            return

        row = payment_breakdown.setdefault(
            mode_of_payment,
            {"base": 0.0, "currencies": defaultdict(float)},
        )
        row["base"] += flt(base_amount)
        if currency:
            row["currencies"][currency] += flt(amount)

    cash_mode_of_payment = (
        frappe.db.get_value("POS Profile", closing_shift_doc.pos_profile, "posa_cash_mode_of_payment") or "Cash"
    )

    for row in closing_shift_doc.get("pos_transactions", []):
        invoice = row.get("sales_invoice") or row.get("pos_invoice")
        if not invoice:
            continue

        doctype = "Sales Invoice" if row.get("sales_invoice") else "POS Invoice"
        if not frappe.db.exists(doctype, invoice):
            continue

        invoice_doc = frappe.get_cached_doc(doctype, invoice)
        invoice_doc.check_permission("read")
        currency = invoice_doc.get("currency") or company_currency
        conversion_rate = (
            invoice_doc.get("conversion_rate")
            or invoice_doc.get("exchange_rate")
            or invoice_doc.get("target_exchange_rate")
            or invoice_doc.get("plc_conversion_rate")
            or 1
        )

        sales_breakdown[currency] += flt(invoice_doc.get("grand_total") or 0)
        net_breakdown[currency] += flt(invoice_doc.get("net_total") or 0)

        for payment in invoice_doc.get("payments", []):
            update_payment_breakdown(
                payment.mode_of_payment,
                get_base_value(payment, "amount", "base_amount", conversion_rate),
                currency,
                payment.amount,
            )

        change_amount = invoice_doc.get("change_amount") or 0
        if change_amount:
            update_payment_breakdown(
                cash_mode_of_payment,
                -get_base_value(
                    invoice_doc,
                    "change_amount",
                    "base_change_amount",
                    conversion_rate,
                ),
                currency,
                -change_amount,
            )

    for row in closing_shift_doc.get("pos_payments", []):
        payment_entry = row.get("payment_entry")
        if not payment_entry or not frappe.db.exists("Payment Entry", payment_entry):
            continue

        payment_doc = frappe.get_cached_doc("Payment Entry", payment_entry)
        payment_doc.check_permission("read")
        multiplier = -1 if payment_doc.get("payment_type") == "Pay" else 1
        currency = (
            payment_doc.get("paid_from_account_currency")
            or payment_doc.get("paid_to_account_currency")
            or payment_doc.get("party_account_currency")
            or payment_doc.get("currency")
            or company_currency
        )
        base_amount = multiplier * abs(flt(payment_doc.get("base_paid_amount") or 0))
        paid_amount = multiplier * abs(flt(payment_doc.get("paid_amount") or 0))
        mode_of_payment = row.get("mode_of_payment") or payment_doc.get("mode_of_payment")

        update_payment_breakdown(mode_of_payment, base_amount, currency, paid_amount)

    mode_summaries = []
    payment_breakdown_copy = payment_breakdown.copy()
    for detail in closing_shift_doc.get("payment_reconciliation", []):
        mop = detail.mode_of_payment
        breakdown = payment_breakdown_copy.pop(mop, None)
        currencies = []
        if breakdown:
            currencies = [
                frappe._dict({"currency": currency, "amount": amount})
                for currency, amount in sorted(breakdown["currencies"].items())
                if amount
            ]

        base_total = flt(detail.expected_amount) - flt(detail.opening_amount)

        mode_summaries.append(
            frappe._dict(
                {
                    "mode_of_payment": mop,
                    "base_amount": base_total,
                    "opening_amount": flt(detail.opening_amount),
                    "expected_amount": flt(detail.expected_amount),
                    "difference": flt(detail.difference),
                    "currency_breakdown": currencies,
                }
            )
        )

    for mop, breakdown in payment_breakdown_copy.items():
        mode_summaries.append(
            frappe._dict(
                {
                    "mode_of_payment": mop,
                    "base_amount": breakdown["base"],
                    "opening_amount": 0,
                    "expected_amount": breakdown["base"],
                    "difference": 0,
                    "currency_breakdown": [
                        frappe._dict({"currency": currency, "amount": amount})
                        for currency, amount in sorted(breakdown["currencies"].items())
                        if amount
                    ],
                }
            )
        )

    sales_currency_breakdown = [
        frappe._dict({"currency": currency, "amount": amount})
        for currency, amount in sorted(sales_breakdown.items())
        if amount
    ]
    net_currency_breakdown = [
        frappe._dict({"currency": currency, "amount": amount})
        for currency, amount in sorted(net_breakdown.items())
        if amount
    ]

    return frappe.render_template(
        "posawesome/mizan/doctype/pos_closing_shift/closing_shift_details.html",
        {
            "data": closing_shift_doc,
            "currency": company_currency,
            "company_currency": company_currency,
            "mode_summaries": mode_summaries,
            "sales_currency_breakdown": sales_currency_breakdown,
            "net_currency_breakdown": net_currency_breakdown,
        },
    )
