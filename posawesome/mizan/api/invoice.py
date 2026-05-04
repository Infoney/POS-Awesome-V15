# Copyright (c) 2021, Youssef Restom and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.mapper import get_mapped_doc
from frappe.utils import add_days, flt

from posawesome.mizan.api.utilities import get_company_domain  # Updated import
from posawesome.mizan.api.payments import get_posawesome_credit_redeem_remark
from posawesome.mizan.doctype.delivery_charges.delivery_charges import (
    get_applicable_delivery_charges,
)
from posawesome.mizan.doctype.pos_coupon.pos_coupon import update_coupon_code_count


# ---------------------------------------------------------------------------
# Monkey-patch: prevent ERPNext's POS-return rounding-drift bug.
#
# `erpnext.controllers.taxes_and_totals.calculate_taxes_and_totals
# .set_total_amount_to_default_mop` runs inside `validate()` for any
# POS Sales Invoice that is a return. It compares two values that can
# diverge by floating-point dust on a foreign-currency return:
#
#   * `total_amount_to_pay` = `base_grand_total` rounded to 3 decimals.
#   * `total_paid_amount`   = sum of `payment.base_amount`, computed
#                             inside `calculate_paid_amount` as
#                             `amount × conversion_rate` with NO
#                             precision rounding.
#
# For a SAR-on-KWD refund of -575.5 SAR, `base_grand_total` = -47.367
# (rounded) but the unrounded sum of `base_amount` = -47.36725...
# `pending_amount = -47.367 - (-47.36725) = +0.00025` — positive. The
# original method then WIPES the cashier's payments table and replaces
# it with a single default-MOP row carrying that tiny positive amount,
# which trips `verify_payment_amount_is_negative` two function calls
# later: "Row #1 (Payment Table): Amount must be negative".
#
# The patch adds a tolerance check: if `pending_amount` is within 0.01
# of zero, treat the invoice as fully refunded and skip the rebuild.
# Real under-refunds (pending > 0.01) still fall through to the
# original behaviour.
#
# Applied at module import time. The first time Frappe loads a Sales
# Invoice or POS Invoice doc_event hook, this module imports and the
# patch takes effect for the worker's lifetime.
# ---------------------------------------------------------------------------
try:
    from erpnext.controllers import taxes_and_totals as _ttn

    _orig_set_total_amount_to_default_mop = (
        _ttn.calculate_taxes_and_totals.set_total_amount_to_default_mop
    )

    def _posa_set_total_amount_to_default_mop(self, total_amount_to_pay):
        if self.doc.get("is_return") and self.doc.get("is_pos"):
            same_currency = self.doc.party_account_currency == self.doc.currency
            # TEMP DIAG: log every entry into this method while the
            # manual-return regression is being traced. Remove once
            # confirmed fixed end-to-end.
            try:
                frappe.log_error(
                    title="POSA mop-rebuild entry",
                    message=(
                        "doc={n} same_currency={sc} total_amount_to_pay={t} "
                        "doc.currency={c} party_currency={pc} conv={cr} "
                        "payments={p}"
                    ).format(
                        n=self.doc.name,
                        sc=same_currency,
                        t=total_amount_to_pay,
                        c=self.doc.currency,
                        pc=self.doc.party_account_currency,
                        cr=self.doc.conversion_rate,
                        p=[
                            {"mop": p.mode_of_payment, "amount": flt(p.amount), "base_amount": flt(p.base_amount)}
                            for p in (self.doc.get("payments") or [])
                        ],
                    ),
                )
            except Exception:
                pass
            # Multi-currency: ALWAYS skip ERPNext's rebuild — see commit
            # 25d1bd08 for full rationale.
            if not same_currency:
                return
            # Single-currency: small-tolerance check.
            total_paid_amount = sum(
                p.amount for p in self.doc.get("payments") or []
            )
            pending_amount = total_amount_to_pay - total_paid_amount
            if abs(pending_amount) < 0.01:
                return
        return _orig_set_total_amount_to_default_mop(self, total_amount_to_pay)

    _ttn.calculate_taxes_and_totals.set_total_amount_to_default_mop = (
        _posa_set_total_amount_to_default_mop
    )
except Exception:
    # If ERPNext's API changes (method renamed / removed), the patch
    # silently no-ops and `before_validate`'s defensive sign-flip
    # remains the safety net.
    pass


def before_validate(doc, method):
    """Defensive negative-sign flip on returns. Backup safety net for the
    ERPNext POS-return rounding-drift fix above — even if that monkey-
    patch fails for some reason, this guarantees no positive payment row
    reaches `verify_payment_amount_is_negative`.

    `amount` and `base_amount` are flipped independently because they're
    in different currencies on a multi-currency invoice — mirroring one
    onto the other corrupts the saved figures.
    """
    if not getattr(doc, "is_return", 0):
        return
    # TEMP DIAG: capture state at hook entry for the manual-return
    # regression investigation. Remove once confirmed fixed.
    try:
        frappe.log_error(
            title="POSA before_validate entry",
            message=(
                "doc={n} is_return={ir} is_pos={ip} currency={c} "
                "party_currency={pc} conv={cr} grand_total={gt} "
                "base_grand_total={bgt} docstatus={ds}\npayments={p}"
            ).format(
                n=doc.name,
                ir=doc.is_return,
                ip=doc.get("is_pos"),
                c=doc.currency,
                pc=doc.get("party_account_currency"),
                cr=doc.conversion_rate,
                gt=doc.grand_total,
                bgt=doc.base_grand_total,
                ds=getattr(doc, "docstatus", "?"),
                p=[
                    {"mop": p.mode_of_payment, "amount": flt(p.amount), "base_amount": flt(p.base_amount)}
                    for p in (doc.payments or [])
                ],
            ),
        )
    except Exception:
        pass
    if not getattr(doc, "payments", None):
        return
    for payment in doc.payments:
        amount = flt(payment.get("amount"))
        if amount > 0:
            payment.amount = -amount
        base_amount = flt(payment.get("base_amount"))
        if base_amount > 0:
            payment.base_amount = -base_amount

    # Detect and undo ERPNext's client-side value-swap on multi-currency
    # returns created via the standard Sales Invoice form (back-end /
    # manual creation). Symptom captured on kpgtest invoice 03329:
    # cashier intended to refund -702.075 SAR but the form sent
    # `payment.amount = -57.785` (which is the KWD value of
    # `base_grand_total`, not the SAR value of `grand_total`). The
    # form lands a company-currency value into the invoice-currency
    # `amount` field. POS Awesome's own payment dialog avoids this
    # because it controls amount entry directly; manual SI creation
    # goes through ERPNext's standard form code which has the bug.
    #
    # Detection criteria (all required):
    #   * Multi-currency (party_account_currency != doc.currency)
    #   * conversion_rate is non-trivial (> 0 and != 1)
    #   * payment.amount magnitude matches base_grand_total within 0.01
    #   * payment.amount magnitude is far (> 1.0) from grand_total
    #
    # The tight `< 0.01` match against base_grand_total + the
    # `> 1.0` separation from grand_total together make this safe
    # against legitimate partial refunds at coincidentally-similar
    # amounts.
    #
    # Recovery values: anchor directly to ``doc.grand_total`` /
    # ``doc.base_grand_total`` instead of inverse-converting
    # ``payment.amount / conv``. The inverse path drifts because
    # ``base_grand_total`` is already rounded to invoice precision
    # before we see it. For ``grand_total = -960.25 SAR`` at
    # ``conv = 0.082306261``, the rounded ``base_grand_total = -79.035
    # KWD``; ``-79.035 / 0.082306261 = -960.2550163...``, off by
    # 0.005 SAR. Stored at field precision that lands as -960.255
    # vs. the doc's -960.25, leaving a +0.005 SAR ``outstanding_amount``
    # that breaks downstream (closing-shift sums, GL reconciliation,
    # printed receipt totals).
    #
    # Anchoring is safe because the corrector only fires when
    # ``payment.amount ≈ base_grand_total`` (i.e. the form filled the
    # full refund into a single row); doc.grand_total is then exactly
    # the refund magnitude in invoice currency.
    if (
        doc.get("is_pos")
        and doc.get("party_account_currency")
        and doc.party_account_currency != doc.currency
    ):
        conv = flt(doc.conversion_rate) or 1
        if conv > 0 and conv != 1:
            grand_total_abs = abs(flt(doc.grand_total))
            base_grand_total_abs = abs(flt(doc.base_grand_total))
            for payment in doc.payments:
                amount_abs = abs(flt(payment.amount))
                if amount_abs <= 0:
                    continue
                close_to_base = abs(amount_abs - base_grand_total_abs) < 0.01
                far_from_invoice = abs(amount_abs - grand_total_abs) > 1
                if close_to_base and far_from_invoice:
                    # Preserve the stored sign — the earlier negative-flip
                    # block already ensured payment.amount is ≤ 0 on a
                    # return, so flt(payment.amount) is negative here.
                    sign = -1 if flt(payment.amount) < 0 else 1
                    payment.amount = sign * grand_total_abs
                    payment.base_amount = sign * base_grand_total_abs


def validate(doc, method):
    # TEMP DIAG: log post-validate state. If this fires for a return,
    # validate succeeded and we can see the final payment values right
    # before save commit. If it doesn't fire, something inside
    # doc.validate() threw. Remove once confirmed fixed.
    if getattr(doc, "is_return", 0):
        try:
            frappe.log_error(
                title="POSA validate entry",
                message=(
                    "doc={n} is_pos={ip} docstatus={ds} grand_total={gt} "
                    "paid_amount={pa} base_paid_amount={bpa}\npayments={p}"
                ).format(
                    n=doc.name,
                    ip=doc.get("is_pos"),
                    ds=getattr(doc, "docstatus", "?"),
                    gt=doc.grand_total,
                    pa=getattr(doc, "paid_amount", None),
                    bpa=getattr(doc, "base_paid_amount", None),
                    p=[
                        {"mop": p.mode_of_payment, "amount": flt(p.amount), "base_amount": flt(p.base_amount)}
                        for p in (doc.payments or [])
                    ],
                ),
            )
        except Exception:
            pass

    validate_shift(doc)
    set_patient(doc)
    auto_set_delivery_charges(doc)
    calc_delivery_charges(doc)
    apply_tax_inclusive(doc)


def before_submit(doc, method):
    add_loyalty_point(doc)
    create_sales_order(doc)
    update_coupon(doc, "used")


def before_cancel(doc, method):
    update_coupon(doc, "cancelled")


def on_cancel(doc, method):
    cancel_posawesome_credit_journal_entries(doc)
    restore_posawesome_gift_card_redemptions(doc)


def cancel_posawesome_credit_journal_entries(doc):
    remark = get_posawesome_credit_redeem_remark(doc.name)
    linked_journal_entries = frappe.get_all(
        "Journal Entry",
        filters={"docstatus": 1, "user_remark": remark},
        pluck="name",
    )

    for journal_entry in linked_journal_entries:
        je_doc = frappe.get_doc("Journal Entry", journal_entry)

        if je_doc.docstatus != 1:
            continue

        has_reference = any(
            d.reference_type == doc.doctype and d.reference_name == doc.name for d in je_doc.accounts
        )

        if not has_reference:
            continue

        try:
            je_doc.cancel()
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                "POSAwesome Credit Journal Cancellation Error",
            )
            frappe.throw(
                _(
                    "Unable to cancel Journal Entry {0} linked to this invoice. Please cancel it manually and try again."
                ).format(journal_entry)
            )


def restore_posawesome_gift_card_redemptions(doc):
    try:
        from posawesome.mizan.api.gift_cards import restore_invoice_gift_card_redemptions

        restore_invoice_gift_card_redemptions(doc)
    except Exception:
        frappe.log_error(
            frappe.get_traceback(),
            "POSAwesome Gift Card Restoration Error",
        )
        frappe.throw(
            _(
                "Unable to restore gift card balances linked to this invoice. Please review the applied gift cards and try again."
            )
        )


def add_loyalty_point(invoice_doc):
    for offer in getattr(invoice_doc, "posa_offers", []):
        if offer.offer == "Loyalty Point":
            original_offer = frappe.get_doc("POS Offer", offer.offer_name)
            if original_offer.loyalty_points > 0:
                loyalty_program = frappe.get_value("Customer", invoice_doc.customer, "loyalty_program")
                if not loyalty_program:
                    loyalty_program = original_offer.loyalty_program
                doc = frappe.get_doc(
                    {
                        "doctype": "Loyalty Point Entry",
                        "loyalty_program": loyalty_program,
                        "loyalty_program_tier": original_offer.name,
                        "customer": invoice_doc.customer,
                        "invoice_type": "Sales Invoice",
                        "invoice": invoice_doc.name,
                        "loyalty_points": original_offer.loyalty_points,
                        "expiry_date": add_days(invoice_doc.posting_date, 10000),
                        "posting_date": invoice_doc.posting_date,
                        "company": invoice_doc.company,
                    }
                )
                doc.insert(ignore_permissions=True)


def create_sales_order(doc):
    if (
        getattr(doc, "posa_pos_opening_shift", None)
        and doc.pos_profile
        and doc.is_pos
        and getattr(doc, "posa_delivery_date", None)
        and not doc.update_stock
        and frappe.get_value("POS Profile", doc.pos_profile, "posa_allow_sales_order")
    ):
        sales_order_doc = make_sales_order(doc.name)
        if sales_order_doc:
            sales_order_doc.posa_notes = getattr(doc, "posa_notes", None)
            sales_order_doc.flags.ignore_permissions = True
            sales_order_doc.flags.ignore_account_permission = True
            sales_order_doc.save()
            sales_order_doc.submit()
            url = frappe.utils.get_url_to_form(sales_order_doc.doctype, sales_order_doc.name)
            msgprint = f"Sales Order Created at <a href='{url}'>{sales_order_doc.name}</a>"
            frappe.msgprint(_(msgprint), title="Sales Order Created", indicator="green", alert=True)
            i = 0
            for item in sales_order_doc.items:
                doc.items[i].sales_order = sales_order_doc.name
                doc.items[i].so_detail = item.name
                i += 1


def make_sales_order(source_name, target_doc=None, ignore_permissions=True):
    def set_missing_values(source, target):
        target.ignore_pricing_rule = 1
        target.flags.ignore_permissions = ignore_permissions
        target.run_method("set_missing_values")
        target.run_method("calculate_taxes_and_totals")

    def update_item(obj, target, source_parent):
        target.stock_qty = flt(obj.qty) * flt(obj.conversion_factor)
        target.delivery_date = getattr(obj, "posa_delivery_date", None) or getattr(
            source_parent, "posa_delivery_date", None
        )

    doclist = get_mapped_doc(
        "Sales Invoice",
        source_name,
        {
            "Sales Invoice": {
                "doctype": "Sales Order",
            },
            "Sales Invoice Item": {
                "doctype": "Sales Order Item",
                "field_map": {
                    "cost_center": "cost_center",
                    "Warehouse": "warehouse",
                    "delivery_date": "posa_delivery_date",
                    "posa_notes": "posa_notes",
                },
                "postprocess": update_item,
            },
            "Sales Taxes and Charges": {
                "doctype": "Sales Taxes and Charges",
                "add_if_empty": True,
            },
            "Sales Team": {"doctype": "Sales Team", "add_if_empty": True},
            "Payment Schedule": {"doctype": "Payment Schedule", "add_if_empty": True},
        },
        target_doc,
        set_missing_values,
        ignore_permissions=ignore_permissions,
    )

    return doclist


def update_coupon(doc, transaction_type):
    for coupon in getattr(doc, "posa_coupons", []):
        if not coupon.applied:
            continue
        update_coupon_code_count(coupon.coupon, transaction_type)


def set_patient(doc):
    domain = get_company_domain(doc.company)
    if domain != "Healthcare":
        return
    patient_list = frappe.get_all("Patient", filters={"customer": doc.customer}, page_length=1)
    if len(patient_list) > 0:
        doc.patient = patient_list[0].name


def auto_set_delivery_charges(doc):
    if not doc.pos_profile:
        return
    if not frappe.get_cached_value("POS Profile", doc.pos_profile, "posa_auto_set_delivery_charges"):
        return

    delivery_charges = get_applicable_delivery_charges(
        doc.company,
        doc.pos_profile,
        doc.customer,
        doc.shipping_address_name,
        doc.posa_delivery_charges,
        restrict=True,
    )

    if doc.posa_delivery_charges:
        if doc.posa_delivery_charges_rate:
            return
        else:
            if len(delivery_charges) > 0:
                doc.posa_delivery_charges_rate = delivery_charges[0].rate
    else:
        if len(delivery_charges) > 0:
            doc.posa_delivery_charges = delivery_charges[0].name
            doc.posa_delivery_charges_rate = delivery_charges[0].rate
        else:
            doc.posa_delivery_charges = None
            doc.posa_delivery_charges_rate = None


def calc_delivery_charges(doc):
    if not doc.pos_profile:
        return

    old_doc = None
    calculate_taxes_and_totals = False
    if not doc.is_new():
        old_doc = doc.get_doc_before_save()
        if not doc.posa_delivery_charges and not old_doc.posa_delivery_charges:
            return
    else:
        if not doc.posa_delivery_charges:
            return
    if not doc.posa_delivery_charges:
        doc.posa_delivery_charges_rate = 0

    charges_doc = None
    if doc.posa_delivery_charges:
        charges_doc = frappe.get_cached_doc("Delivery Charges", doc.posa_delivery_charges)
        doc.posa_delivery_charges_rate = charges_doc.default_rate
        charges_profile = next((i for i in charges_doc.profiles if i.pos_profile == doc.pos_profile), None)
        if charges_profile:
            doc.posa_delivery_charges_rate = charges_profile.rate
        conversion_rate = doc.conversion_rate or 1
        doc.posa_delivery_charges_rate = flt(
            doc.posa_delivery_charges_rate / conversion_rate,
            doc.precision("posa_delivery_charges_rate"),
        )

    if old_doc and old_doc.posa_delivery_charges:
        old_charges = next(
            (
                i
                for i in doc.taxes
                if i.charge_type == "Actual" and i.description == old_doc.posa_delivery_charges
            ),
            None,
        )
        if old_charges:
            doc.taxes.remove(old_charges)
            calculate_taxes_and_totals = True

    if doc.posa_delivery_charges:
        doc.append(
            "taxes",
            {
                "charge_type": "Actual",
                "description": doc.posa_delivery_charges,
                "tax_amount": doc.posa_delivery_charges_rate,
                "cost_center": charges_doc.cost_center,
                "account_head": charges_doc.shipping_account,
            },
        )
        calculate_taxes_and_totals = True

    if calculate_taxes_and_totals:
        doc.calculate_taxes_and_totals()


def apply_tax_inclusive(doc):
    """Mark taxes as inclusive based on POS Profile setting.

    Bug observed on kpgtest invoice 03334 manual return: ERPNext's
    standard "Create Return" path drops `included_in_print_rate` from
    the new return's tax rows. The original (tax-inclusive: net 726
    + tax 109 = grand 835 SAR) becomes a return with the original
    grand re-interpreted as net (835 + 15% tax = 960.25 SAR), so
    refunding the original SAR 835 hits "Total payments amount can't
    be greater than 960.25". Re-asserting `included_in_print_rate`
    here from the POS Profile setting fixes it.

    Actual-type rows (e.g. delivery charges) stay exclusive
    regardless — they're add-on amounts, not item rate components.
    """
    if not doc.pos_profile:
        return
    try:
        tax_inclusive = frappe.get_cached_value("POS Profile", doc.pos_profile, "posa_tax_inclusive")
    except Exception:
        tax_inclusive = 0

    has_changes = False
    for tax in doc.get("taxes", []):
        if tax.charge_type == "Actual":
            # Actual tax rows are add-on amounts (delivery charges,
            # round-off, etc.) and should never be included in print
            # rate. Skip the inclusive logic for these.
            if tax.included_in_print_rate:
                tax.included_in_print_rate = 0
                has_changes = True
            continue
        # Non-Actual rows (On Net Total, On Previous Row Amount, etc.)
        # honour the POS Profile's tax-inclusive setting.
        if tax_inclusive and not tax.included_in_print_rate:
            tax.included_in_print_rate = 1
            has_changes = True
        elif not tax_inclusive and tax.included_in_print_rate:
            tax.included_in_print_rate = 0
            has_changes = True
    if has_changes:
        doc.calculate_taxes_and_totals()


def validate_shift(doc):
    if doc.posa_pos_opening_shift and doc.pos_profile and doc.is_pos:
        # check if shift is open
        shift = frappe.get_cached_doc("POS Opening Shift", doc.posa_pos_opening_shift)
        if shift.status != "Open":
            frappe.throw(_("POS Shift {0} is not open").format(shift.name))
        # check if shift is for the same profile
        if shift.pos_profile != doc.pos_profile:
            frappe.throw(_("POS Opening Shift {0} is not for the same POS Profile").format(shift.name))
        # check if shift is for the same company
        if shift.company != doc.company:
            frappe.throw(_("POS Opening Shift {0} is not for the same company").format(shift.name))
