# Copyright (c) 2026, POS Awesome contributors
# For license information, please see license.txt

"""POS-side Purchase Receipt (Material Receipt) flow.

Light, supplier-aware stock-in screen that lives next to the existing
Purchase Order page. Reuses helpers from `purchase_orders.py` so we keep
a single source of truth for supplier resolution, buying price list
selection, and POS-Profile permissioning.
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from .purchase_orders import (
    _ensure_allowed,
    _resolve_buying_price_list,
    _resolve_pos_profile,
    _resolve_supplier,
    _resolve_supplier_buying_price_list,
    _upsert_item_price,
)
from .utils import get_default_warehouse


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------


@frappe.whitelist()
def get_setup(pos_profile=None):
    """Return supplier-agnostic setup the Purchase Receipt page boots with.

    Currently exposes the resolved warehouse + buying price list defaults so
    the page can pre-fill its header before the user picks a supplier.
    """
    profile = _resolve_pos_profile(pos_profile)
    company = profile.get("company") or frappe.defaults.get_default("company")
    warehouse = (
        profile.get("posa_purchase_warehouse")
        or profile.get("warehouse")
        or get_default_warehouse(company)
    )
    return {
        "company": company,
        "warehouse": warehouse,
        "buying_price_list": _resolve_buying_price_list(),
    }


@frappe.whitelist()
def get_item_meta(item_code):
    """Return the batch/serial/UOM metadata the receipts page needs per item."""
    if not item_code:
        return None

    if not frappe.db.exists("Item", item_code):
        return None

    item = frappe.db.get_value(
        "Item",
        item_code,
        [
            "name",
            "item_name",
            "stock_uom",
            "purchase_uom",
            "has_batch_no",
            "has_serial_no",
            "is_stock_item",
            "create_new_batch",
            "shelf_life_in_days",
            "standard_rate",
        ],
        as_dict=True,
    )
    if not item:
        return None

    uoms = frappe.get_all(
        "UOM Conversion Detail",
        filters={"parent": item_code},
        fields=["uom", "conversion_factor"],
    )
    if item.stock_uom and not any(u.uom == item.stock_uom for u in uoms):
        uoms.append({"uom": item.stock_uom, "conversion_factor": 1})

    return {
        **item,
        "item_uoms": uoms,
    }


@frappe.whitelist()
def get_existing_batches(item_code):
    """List Batch records for `item_code` so the user can pick one quickly."""
    if not item_code:
        return []

    rows = frappe.get_all(
        "Batch",
        filters={"item": item_code, "disabled": 0},
        fields=["name", "batch_id", "expiry_date", "manufacturing_date", "supplier"],
        order_by="creation desc",
        limit_page_length=50,
    )
    today = getdate(nowdate())
    for row in rows:
        expiry = row.get("expiry_date")
        row["is_expired"] = bool(expiry and getdate(expiry) < today)
    return rows


# ---------------------------------------------------------------------------
# Submit flow
# ---------------------------------------------------------------------------


def _coerce_date(value, fallback=None):
    if not value:
        return fallback
    try:
        return getdate(value)
    except Exception:
        return fallback


def _resolve_or_create_batch(row: dict[str, Any], item_meta: dict[str, Any], supplier: str) -> str | None:
    """Return the Batch.name to attach to a PR row, creating one if needed.

    Pharmacy expectation: if the user is creating a new batch from this screen
    we require an expiry date (handled at the frontend; we still defend here).
    """
    if not item_meta or not cint(item_meta.get("has_batch_no")):
        return None

    batch_id = (row.get("batch_no") or row.get("batch_id") or "").strip()
    expiry = _coerce_date(row.get("batch_expiry_date") or row.get("expiry_date"))
    mfg = _coerce_date(row.get("batch_manufacturing_date") or row.get("manufacturing_date"))

    if not batch_id:
        frappe.throw(
            _("Item {0} requires a batch. Please pick one or create a new batch.").format(
                item_meta.get("item_name") or item_meta.get("name")
            )
        )

    existing = frappe.db.get_value(
        "Batch",
        {"item": item_meta["name"], "batch_id": batch_id},
        "name",
    )
    if existing:
        return existing

    if not expiry:
        frappe.throw(
            _("New batch {0} for {1} needs an expiry date.").format(
                batch_id, item_meta.get("item_name") or item_meta.get("name")
            )
        )

    batch_doc = frappe.get_doc(
        {
            "doctype": "Batch",
            "item": item_meta["name"],
            "batch_id": batch_id,
            "expiry_date": expiry,
            "manufacturing_date": mfg,
            "supplier": supplier,
        }
    )
    batch_doc.flags.ignore_permissions = True
    batch_doc.insert()
    return batch_doc.name


def _normalize_serial_payload(value) -> str | None:
    """Accept a list, comma list, or newline list and return the Frappe format."""
    if not value:
        return None
    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
    else:
        items = [s.strip() for s in str(value).replace(",", "\n").splitlines() if s.strip()]
    if not items:
        return None
    return "\n".join(items)


@frappe.whitelist()
def create_purchase_receipt(data):
    """Create + submit a Purchase Receipt straight from the POS shell."""
    payload = json.loads(data) if isinstance(data, str) else data
    profile = _resolve_pos_profile(payload.get("pos_profile"))
    _ensure_allowed(profile, "posa_allow_purchase_receipt", _("Receive stock"))

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
        payload.get("warehouse")
        or profile.get("posa_purchase_warehouse")
        or profile.get("warehouse")
        or get_default_warehouse(company)
    )
    if not warehouse:
        frappe.throw(_("Warehouse is required to receive stock."))

    rows = payload.get("items") or []
    if not rows:
        frappe.throw(_("Add at least one item before submitting the receipt."))

    posting_date = payload.get("posting_date") or nowdate()

    supplier_doc = frappe.get_doc("Supplier", supplier)
    supplier_currency = (
        supplier_doc.default_currency
        or frappe.get_value("Company", company, "default_currency")
    )

    buying_price_list = (
        payload.get("buying_price_list")
        or _resolve_supplier_buying_price_list(supplier)
    )
    price_list_currency = (
        frappe.get_value("Price List", buying_price_list, "currency")
        if buying_price_list
        else None
    )

    receipt = frappe.get_doc(
        {
            "doctype": "Purchase Receipt",
            "supplier": supplier,
            "company": company,
            "posting_date": posting_date,
            "currency": supplier_currency,
            "buying_price_list": buying_price_list,
            "ignore_pricing_rule": 1,
        }
    )
    if warehouse:
        receipt.set_warehouse = warehouse

    update_price_list = cint(payload.get("update_price_list"))
    rows_for_price_update: list[tuple[str, str | None, float]] = []

    for row in rows:
        item_code = row.get("item_code")
        if not item_code:
            continue

        qty = flt(row.get("qty"))
        if qty <= 0:
            continue

        item_meta = get_item_meta(item_code) or {}
        stock_uom = row.get("stock_uom") or item_meta.get("stock_uom")
        item_name = row.get("item_name") or item_meta.get("item_name") or item_code
        uom = row.get("uom") or stock_uom
        conversion_factor = flt(row.get("conversion_factor") or 1) or 1

        rate = flt(row.get("rate"))
        discount_percentage = flt(row.get("discount_percentage"))
        if discount_percentage:
            # Standard ERPNext column — Frappe will compute the net rate itself.
            pass

        batch_no = _resolve_or_create_batch(row, item_meta, supplier)
        serial_no = (
            _normalize_serial_payload(row.get("serial_no"))
            if cint(item_meta.get("has_serial_no"))
            else None
        )

        line = {
            "item_code": item_code,
            "item_name": item_name,
            "qty": qty,
            "received_qty": qty,
            "uom": uom,
            "stock_uom": stock_uom,
            "conversion_factor": conversion_factor,
            "rate": rate,
            "price_list_rate": rate,
            "discount_percentage": discount_percentage,
            "warehouse": row.get("warehouse") or warehouse,
        }
        if batch_no:
            line["batch_no"] = batch_no
        if serial_no:
            line["serial_no"] = serial_no

        receipt.append("items", line)
        rows_for_price_update.append((item_code, uom, rate))

    if not receipt.items:
        frappe.throw(_("Receipt requires at least one item with quantity."))

    receipt.flags.ignore_permissions = True
    frappe.flags.ignore_account_permission = True

    try:
        receipt.insert()
        receipt.submit()
    except Exception as err:
        frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "POS Awesome PR Submit Failed")
        frappe.throw(_("Failed to submit Purchase Receipt. Error: {0}").format(str(err)))

    if update_price_list and buying_price_list:
        for item_code, uom, rate in rows_for_price_update:
            if rate <= 0:
                continue
            try:
                _upsert_item_price(
                    item_code,
                    buying_price_list,
                    rate,
                    uom=uom,
                    buying=True,
                )
            except Exception:
                frappe.log_error(
                    frappe.get_traceback(),
                    "POS Awesome PR price-list update failed",
                )

    return {
        "purchase_receipt": receipt.name,
        "supplier": supplier,
        "buying_price_list": buying_price_list,
        "price_list_currency": price_list_currency,
        "warehouse": warehouse,
        "total": receipt.grand_total,
    }
