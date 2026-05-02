# Copyright (c) 2026, Infoney and contributors
# For license information, please see license.txt
"""
One-step Purchase Invoice flow for the in-app POS shell.

Pharmacies replenishing the till from a small shipment don't want
the three-doctype dance (Purchase Order → Purchase Receipt →
Purchase Invoice) — they want to type the items + quantities they
just received, hit submit, see stock land in the warehouse, and
print barcode labels for every unit.

The standard ERPNext lever for "one document, all three effects"
is `Purchase Invoice` with `update_stock = 1`. Submitting that
single document creates Stock Ledger entries directly (same as a
Purchase Receipt would) AND books the payable, so the cashier
walks away with one document name to keep.

Warehouse + cost center are NOT operator inputs here — they come
from the active POS Profile. The profile is the cashier's
authority for "where to receive into" and "which cost center to
hit", so re-asking at the till adds friction with no upside.

Companion frontend: `frontend/src/posapp/components/pos/purchase/
PurchaseInvoice.vue` builds the payload; this module accepts it.
The response includes a `labels` array — one row per unit
purchased, with the metadata the label-print dialog needs (item
name, cost rate, standard selling price, barcode, brand name) so
the client can render labels without a second round-trip per
item.
"""

import json

import frappe
from frappe import _
from frappe.utils import cint, flt, nowdate

from .purchase_orders import (
    _ensure_allowed,
    _resolve_pos_profile,
    _resolve_supplier,
    _resolve_supplier_buying_price_list,
)
from .utils import get_default_warehouse


def _resolve_pharmacy_brand_name(profile, company):
    """
    Pick the most user-meaningful "brand name" to print at the foot
    of every barcode label. Fallback chain mirrors the navbar's
    `customBrandName` resolver:

        1. POS Profile.posa_brand_name (operator-set custom label —
           often already in Arabic on AL-KHANSA tenants).
        2. Company.company_name (fallback to legal name, may be
           latin).

    Returning empty string is fine — the label dialog hides the
    footer line when blank.
    """
    candidate = (profile or {}).get("posa_brand_name")
    if candidate:
        candidate = str(candidate).strip()
        if candidate:
            return candidate
    if company:
        company_name = frappe.db.get_value("Company", company, "company_name")
        if company_name:
            return str(company_name).strip()
    return ""


def _resolve_selling_price_list(profile):
    candidate = (profile or {}).get("selling_price_list")
    if candidate:
        return candidate
    return frappe.db.get_single_value("Selling Settings", "selling_price_list")


def _fetch_item_metadata(item_codes):
    """
    Batch-fetch the per-item display metadata the label print dialog
    needs (item_name, stock_uom, standard_rate, default barcode).
    Returns a dict keyed by item_code so the per-line loop can hydrate
    cheaply.
    """
    if not item_codes:
        return {}

    rows = frappe.get_all(
        "Item",
        filters={"name": ["in", list(item_codes)]},
        fields=["name", "item_name", "stock_uom", "standard_rate"],
    )
    by_code = {row["name"]: row for row in rows}

    barcode_rows = frappe.get_all(
        "Item Barcode",
        filters={"parent": ["in", list(item_codes)]},
        fields=["parent", "barcode", "uom", "posa_uom"],
    )
    barcodes_by_code = {}
    for row in barcode_rows:
        barcodes_by_code.setdefault(row["parent"], []).append(row)
    for code, meta in by_code.items():
        meta["barcodes"] = barcodes_by_code.get(code, [])
    return by_code


def _resolve_item_barcode(meta, uom, stock_uom):
    """
    Pick the barcode to print for this line. Prefer a barcode whose
    `posa_uom` (or stock-table `uom`) matches the line's UOM — many
    pharmacies have separate barcodes for "1 box of 24" vs "single
    blister" and printing the wrong one causes scan-checkout
    mismatches at sale time. Fall back to any barcode if none match.
    """
    if not meta:
        return ""
    rows = meta.get("barcodes") or []
    for row in rows:
        row_uom = row.get("posa_uom") or row.get("uom")
        if row_uom and uom and row_uom == uom:
            return row.get("barcode") or ""
    if uom and uom != stock_uom:
        for row in rows:
            row_uom = row.get("posa_uom") or row.get("uom")
            if row_uom and row_uom == stock_uom:
                return row.get("barcode") or ""
    if rows:
        return rows[0].get("barcode") or ""
    return ""


def _resolve_selling_price(item_code, price_list, uom, stock_uom):
    """
    Look up the per-item selling rate the customer would actually pay
    so the label can show "Cost vs Sell" side-by-side. Prefer the
    price-list rate at the printed UOM, then at stock UOM, then fall
    back to `Item.standard_rate`. Empty/0 is fine — the dialog skips
    the line if both rates are zero.
    """
    if not item_code:
        return 0
    if price_list:
        for candidate_uom in (uom, stock_uom):
            if not candidate_uom:
                continue
            row = frappe.db.get_value(
                "Item Price",
                {
                    "item_code": item_code,
                    "price_list": price_list,
                    "uom": candidate_uom,
                    "selling": 1,
                },
                "price_list_rate",
            )
            if row:
                return flt(row)
        # No UOM-scoped price — pick any selling price for this item.
        row = frappe.db.get_value(
            "Item Price",
            {
                "item_code": item_code,
                "price_list": price_list,
                "selling": 1,
            },
            "price_list_rate",
        )
        if row:
            return flt(row)
    standard_rate = frappe.db.get_value("Item", item_code, "standard_rate")
    return flt(standard_rate or 0)


def _build_label_payload(invoice_doc, profile):
    """
    Expand each Purchase Invoice line into one entry per unit
    purchased — three boxes of Panadol come back as three separate
    `labels` entries, so the print dialog doesn't have to re-multiply
    by qty client-side. Each entry carries the four printable fields
    (item name, cost rate, selling price, barcode) plus the brand
    name footer.

    Quantity is rounded to nearest int because labels are physical
    objects: a fractional qty (e.g. 1.5 kg of weighed goods) gets
    rounded UP to 2 labels so every receivable unit has a label.
    For pharmacies the qty is integer in 99% of cases so this is a
    no-op; the rare scale-weighed line just leans toward over-print
    rather than under-print.
    """
    item_codes = {
        row.item_code for row in (invoice_doc.items or []) if row.item_code
    }
    metadata = _fetch_item_metadata(item_codes)
    selling_price_list = _resolve_selling_price_list(profile)
    company_currency = frappe.get_cached_value(
        "Company", invoice_doc.company, "default_currency"
    )
    brand_name = _resolve_pharmacy_brand_name(profile, invoice_doc.company)

    labels = []
    for row in invoice_doc.items or []:
        meta = metadata.get(row.item_code) or {}
        stock_uom = row.stock_uom or meta.get("stock_uom") or ""
        printed_uom = row.uom or stock_uom

        barcode = _resolve_item_barcode(meta, printed_uom, stock_uom)
        selling_rate = _resolve_selling_price(
            row.item_code, selling_price_list, printed_uom, stock_uom
        )

        # Round qty up so partial units never lose a label. Pharmacy
        # use case is integer 99% of the time, so this is normally
        # a no-op.
        qty_to_print = max(1, int(flt(row.qty) + 0.999))

        labels.append(
            {
                "item_code": row.item_code,
                "item_name": row.item_name or meta.get("item_name") or row.item_code,
                "uom": printed_uom,
                "qty": qty_to_print,
                "cost_rate": flt(row.rate),
                "selling_rate": flt(selling_rate),
                "barcode": barcode,
                "brand_name": brand_name,
                "currency": invoice_doc.currency or company_currency,
            }
        )

    return {
        "labels": labels,
        "brand_name": brand_name,
        "company_currency": company_currency,
        "invoice_currency": invoice_doc.currency or company_currency,
    }


@frappe.whitelist()
def create_purchase_invoice(data):
    """
    Submit a one-step Purchase Invoice with `update_stock=1`.

    Required payload fields:
      * `supplier` — Supplier name (will resolve case-insensitively).
      * `items[]` — `[{item_code, qty, rate, uom?, conversion_factor?}]`.
      * `pos_profile` — full POS Profile dict (from the client store),
         falls back to `get_active_pos_profile()` when missing.

    Optional payload fields:
      * `posting_date` — defaults to today.
      * `due_date`     — defaults to posting_date.
      * `bill_no` / `bill_date` — supplier's invoice reference.
      * `payments[]` — for cash-paid receipts. NOT yet wired through —
         user can still record a Payment Entry against the PI from
         desk if they need a paid-on-the-spot trail.

    Warehouse + cost_center are read from the POS Profile and stamped
    on every line and on the parent. The cashier never sees these
    fields; they're tied to where the till physically lives.
    """
    payload = json.loads(data) if isinstance(data, str) else data
    profile = _resolve_pos_profile(payload.get("pos_profile"))
    _ensure_allowed(profile, "posa_allow_purchase_invoice", _("Purchase invoices"))

    supplier_input = payload.get("supplier")
    if not supplier_input:
        frappe.throw(_("Supplier is required."))

    supplier = _resolve_supplier(supplier_input)
    if not supplier:
        frappe.throw(_("Supplier {0} was not found.").format(supplier_input))

    company = (
        payload.get("company")
        or profile.get("company")
        or frappe.defaults.get_default("company")
    )
    if not company:
        frappe.throw(_("Company is required."))

    warehouse = (
        profile.get("warehouse")
        or payload.get("warehouse")
        or get_default_warehouse(company)
    )
    if not warehouse:
        frappe.throw(
            _(
                "POS Profile {0} has no warehouse set. Set a warehouse "
                "on the profile before submitting purchase invoices "
                "from the till."
            ).format(profile.get("name") or "")
        )

    cost_center = profile.get("cost_center") or payload.get("cost_center")

    items = payload.get("items") or []
    if not items:
        frappe.throw(_("Purchase invoice requires at least one item."))

    posting_date = payload.get("posting_date") or nowdate()
    due_date = payload.get("due_date") or posting_date

    supplier_doc = frappe.get_doc("Supplier", supplier)
    supplier_currency = supplier_doc.default_currency or frappe.get_value(
        "Company", company, "default_currency"
    )
    buying_price_list = (
        payload.get("buying_price_list")
        or _resolve_supplier_buying_price_list(supplier)
    )

    invoice_doc = frappe.get_doc(
        {
            "doctype": "Purchase Invoice",
            "supplier": supplier,
            "company": company,
            "posting_date": posting_date,
            "due_date": due_date,
            "currency": supplier_currency,
            "buying_price_list": buying_price_list,
            "update_stock": 1,
            "set_warehouse": warehouse,
            "bill_no": payload.get("bill_no"),
            "bill_date": payload.get("bill_date") or posting_date,
        }
    )
    if cost_center:
        invoice_doc.cost_center = cost_center

    for row in items:
        item_code = row.get("item_code")
        if not item_code:
            continue

        qty = flt(row.get("qty"))
        if qty <= 0:
            continue

        stock_uom = row.get("stock_uom") or frappe.db.get_value(
            "Item", item_code, "stock_uom"
        )
        uom = row.get("uom") or stock_uom
        conversion_factor = flt(row.get("conversion_factor") or 1) or 1
        rate = flt(row.get("rate"))

        line = {
            "item_code": item_code,
            "item_name": row.get("item_name"),
            "qty": qty,
            "uom": uom,
            "stock_uom": stock_uom,
            "conversion_factor": conversion_factor,
            "rate": rate,
            "warehouse": row.get("warehouse") or warehouse,
        }
        if cost_center:
            line["cost_center"] = cost_center
        invoice_doc.append("items", line)

    if not invoice_doc.items:
        frappe.throw(_("Purchase invoice requires at least one item with quantity."))

    invoice_doc.flags.ignore_permissions = True
    frappe.flags.ignore_account_permission = True
    invoice_doc.insert()

    # Persist a draft copy first — if the submit fails (e.g. account
    # permissions, negative-stock guard), the operator still has the
    # invoice to investigate from desk.
    frappe.db.commit()

    if cint(payload.get("submit", 1)):
        try:
            invoice_doc.submit()
        except Exception as err:
            frappe.db.rollback()
            frappe.log_error(
                frappe.get_traceback(), "POS Awesome Purchase Invoice Submit Failed"
            )
            frappe.throw(
                _(
                    "Purchase Invoice {0} was saved as Draft. Submit "
                    "failed: {1}"
                ).format(invoice_doc.name, str(err))
            )

    label_payload = _build_label_payload(invoice_doc, profile)

    return {
        "purchase_invoice": invoice_doc.name,
        "warehouse": warehouse,
        "cost_center": cost_center,
        "grand_total": flt(invoice_doc.grand_total),
        "currency": invoice_doc.currency,
        **label_payload,
    }
