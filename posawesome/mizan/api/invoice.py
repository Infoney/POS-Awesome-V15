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


_VALIDATE_CALL_COUNTER = {}


def _diag_payment_snapshot(doc):
    try:
        return [
            {
                "idx": p.idx,
                "mop": p.mode_of_payment,
                "amount": flt(p.amount),
                "base_amount": flt(p.base_amount),
            }
            for p in (doc.payments or [])
        ]
    except Exception:
        return []


def before_validate(doc, method):
    """Run before ERPNext's `validate()` so we can pre-empt
    `verify_payment_amount_is_negative` — the check that throws
    "Row #N (Payment Table): Amount must be negative" on returns.

    Independent flips for `amount` and `base_amount` because they're in
    different currencies on a multi-currency invoice — mirroring one
    onto the other corrupts the saved figures.
    """
    if not getattr(doc, "is_return", 0):
        return
    if not getattr(doc, "payments", None):
        return
    snapshot_before = _diag_payment_snapshot(doc)
    for payment in doc.payments:
        amount = flt(payment.get("amount"))
        if amount > 0:
            payment.amount = -amount
        base_amount = flt(payment.get("base_amount"))
        if base_amount > 0:
            payment.base_amount = -base_amount
    snapshot_after = _diag_payment_snapshot(doc)
    # TEMP DIAG: tag each call with a per-doc counter + docstatus so we
    # can tell draft re-saves apart from the final submit. Remove once
    # the foreign-currency return flow is confirmed working.
    try:
        key = doc.name or "<new>"
        _VALIDATE_CALL_COUNTER[key] = _VALIDATE_CALL_COUNTER.get(key, 0) + 1
        call_n = _VALIDATE_CALL_COUNTER[key]
        frappe.log_error(
            title="POSA before_validate #{n} {ds}".format(
                n=call_n, ds=getattr(doc, "docstatus", "?")
            ),
            message=(
                "doc={name} call#={n} docstatus={ds} is_return={ir} "
                "currency={c} conv={cr} grand_total={gt} base_grand_total={bgt}\n"
                "before={sb}\nafter={sa}\ncustom_return_reason={crr!r}"
            ).format(
                name=doc.name,
                n=call_n,
                ds=getattr(doc, "docstatus", "?"),
                ir=doc.is_return,
                c=doc.currency,
                cr=doc.conversion_rate,
                gt=doc.grand_total,
                bgt=doc.base_grand_total,
                sb=snapshot_before,
                sa=snapshot_after,
                crr=doc.get("custom_return_reason"),
            ),
        )
    except Exception:
        pass


def validate(doc, method):
    # TEMP DIAG: log post-validate state for foreign-currency return
    # investigation. If verify_payment_amount_is_negative threw inside
    # doc.validate(), this hook never runs (proving the throw happened
    # between before_validate and our hook). If it does run, we get the
    # final state right before save commit. Remove once confirmed working.
    if getattr(doc, "is_return", 0) and getattr(doc, "payments", None):
        try:
            frappe.log_error(
                title="POSA post-validate {ds}".format(ds=getattr(doc, "docstatus", "?")),
                message=(
                    "doc={name} docstatus={ds} after-validate payments={p} "
                    "paid_amount={pa} base_paid_amount={bpa}"
                ).format(
                    name=doc.name,
                    ds=getattr(doc, "docstatus", "?"),
                    p=_diag_payment_snapshot(doc),
                    pa=getattr(doc, "paid_amount", None),
                    bpa=getattr(doc, "base_paid_amount", None),
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
    """Mark taxes as inclusive based on POS Profile setting."""
    if not doc.pos_profile:
        return
    try:
        tax_inclusive = frappe.get_cached_value("POS Profile", doc.pos_profile, "posa_tax_inclusive")
    except Exception:
        tax_inclusive = 0

    has_changes = False
    for tax in doc.get("taxes", []):
        if tax.charge_type == "Actual":
            if tax.included_in_print_rate:
                tax.included_in_print_rate = 0
                has_changes = True
        continue
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
