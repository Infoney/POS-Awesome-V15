# Copyright (c) 2026, Infoney and contributors
# For license information, please see license.txt
"""
Standalone barcode label print flow — no Purchase Invoice or
Receipt backing. The cashier picks items, qty per item, optionally
batch + expiry, and hits Print; the same `BarcodeLabelPrintDialog`
opens with the labels payload built here.

Reuses every helper the PI / PR label flow already uses, so a label
printed here is byte-identical to one printed off a PI or PR. The
only difference is there's no Frappe document backing it — labels
are computed on the fly from the request payload.

Companion frontend: `frontend/src/posapp/components/pos/shell/
MizanBarcodePrint.vue` builds the request; this module accepts it.
"""

import json

import frappe
from frappe import _
from frappe.utils import flt

from .purchase_invoices import (
    _fetch_item_metadata,
    _format_iso_date,
    _resolve_barcode_symbology,
    _resolve_item_barcode,
    _resolve_pharmacy_brand_name,
    _resolve_selling_price,
    _resolve_selling_price_list,
)
from .purchase_orders import _ensure_allowed, _resolve_pos_profile


def _resolve_batch_meta_for_label(batch_no):
    """
    Inline copy of `purchase_invoices._resolve_batch_meta`.

    Cross-module imports of underscore-prefixed helpers feel
    rougher than just duplicating a 12-line lookup. If this grows a
    third caller it should move to a shared `purchase_label_payload`
    module — until then, copy is fine.
    """
    if not batch_no:
        return {
            "batch_no": "",
            "batch_expiry_date": "",
            "batch_manufacturing_date": "",
        }
    if not frappe.db.exists("Batch", batch_no):
        return {
            "batch_no": batch_no,
            "batch_expiry_date": "",
            "batch_manufacturing_date": "",
        }
    row = frappe.db.get_value(
        "Batch",
        batch_no,
        ["expiry_date", "manufacturing_date"],
        as_dict=True,
    )
    return {
        "batch_no": batch_no,
        "batch_expiry_date": _format_iso_date(row.get("expiry_date")) if row else "",
        "batch_manufacturing_date": (
            _format_iso_date(row.get("manufacturing_date")) if row else ""
        ),
    }


@frappe.whitelist()
def build_labels(data):
    """
    Build a labels[] payload for the standalone Mizan Barcode Print
    page.

    Required payload fields:
      * `items[]` — `[{item_code, qty, uom?, batch_no?,
                        batch_expiry_date?}]`
      * `pos_profile` — POS Profile name OR full dict (matches
                          PI / PR endpoints).

    Returns the same shape as the PI / PR label payloads:
      `{labels: [...], brand_name, company_currency, invoice_currency}`

    so the existing `BarcodeLabelPrintDialog` consumes it without
    branching. `invoice_currency` is set to the POS Profile's
    currency since there's no invoice backing the request.
    """
    payload = json.loads(data) if isinstance(data, str) else data
    profile = _resolve_pos_profile(payload.get("pos_profile"))
    _ensure_allowed(
        profile,
        "posa_allow_mizan_barcode_print",
        _("Mizan Barcode Print"),
    )

    items = payload.get("items") or []
    if not items:
        frappe.throw(_("Add at least one item to print labels for."))

    company = (
        payload.get("company")
        or profile.get("company")
        or frappe.defaults.get_default("company")
    )
    if not company:
        frappe.throw(_("Company is required."))

    selling_price_list = _resolve_selling_price_list(profile)
    company_currency = frappe.get_cached_value(
        "Company", company, "default_currency"
    )
    # No invoice backing — fall back to POS Profile's display
    # currency for `invoice_currency` so the label currency reads
    # the same as the cashier's typical sale currency.
    invoice_currency = profile.get("currency") or company_currency
    brand_name = _resolve_pharmacy_brand_name(profile, company)

    item_codes = {row.get("item_code") for row in items if row.get("item_code")}
    if not item_codes:
        frappe.throw(_("Every line needs an item code."))
    metadata = _fetch_item_metadata(item_codes)

    batch_meta_cache: dict[str, dict] = {}

    labels = []
    for row in items:
        item_code = row.get("item_code")
        if not item_code:
            continue
        qty = max(1, int(flt(row.get("qty") or 1) + 0.999))

        meta = metadata.get(item_code) or {}
        stock_uom = row.get("stock_uom") or meta.get("stock_uom") or ""
        printed_uom = row.get("uom") or stock_uom

        barcode = _resolve_item_barcode(meta, printed_uom, stock_uom)
        selling_rate = _resolve_selling_price(
            item_code, selling_price_list, printed_uom, stock_uom
        )

        batch_no = (row.get("batch_no") or "").strip()
        if batch_no not in batch_meta_cache:
            batch_meta_cache[batch_no] = _resolve_batch_meta_for_label(batch_no)
        batch_info = batch_meta_cache[batch_no]

        # Allow the operator to override batch_expiry_date when
        # they're labelling a freshly-bought lot whose Batch hasn't
        # been created yet (e.g. ad-hoc relabelling). When the row
        # carries an explicit expiry, prefer it over the cached
        # Batch.expiry_date.
        explicit_expiry = (row.get("batch_expiry_date") or "").strip()
        if explicit_expiry:
            batch_info = dict(batch_info)
            batch_info["batch_expiry_date"] = _format_iso_date(explicit_expiry)

        labels.append(
            {
                "item_code": item_code,
                "item_name": (
                    row.get("item_name")
                    or meta.get("item_name")
                    or item_code
                ),
                "uom": printed_uom,
                "qty": qty,
                "selling_rate": flt(selling_rate),
                "barcode": barcode,
                "barcode_format": _resolve_barcode_symbology(barcode),
                "batch_no": batch_info.get("batch_no", ""),
                "batch_expiry_date": batch_info.get("batch_expiry_date", ""),
                "batch_manufacturing_date": batch_info.get(
                    "batch_manufacturing_date", ""
                ),
                "brand_name": brand_name,
                "currency": invoice_currency,
            }
        )

    return {
        "labels": labels,
        "brand_name": brand_name,
        "company_currency": company_currency,
        "invoice_currency": invoice_currency,
    }


@frappe.whitelist()
def search_items_for_labels(search_text=None, limit=20):
    """
    Light item search for the Mizan Barcode Print picker. Mirrors
    `purchase_orders.search_items` but trims fields to what the
    label picker actually needs (no UOM table — the page just lets
    the operator type qty per item, no UOM cascade required).
    """
    filters = {"disabled": 0}
    or_filters = None
    if search_text:
        like_value = f"%{search_text}%"
        or_filters = {
            "name": ["like", like_value],
            "item_name": ["like", like_value],
        }

    return frappe.get_all(
        "Item",
        filters=filters,
        or_filters=or_filters,
        fields=["name", "item_name", "stock_uom", "standard_rate"],
        limit_page_length=int(limit) if str(limit).isdigit() else 20,
        order_by="name asc",
    )
