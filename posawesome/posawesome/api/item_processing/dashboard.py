"""Per-item dashboard payload for the POS product-details drawer.

Returns a single bundle the frontend can render command-center-style:
hero (image, name, sku, barcode, in/out of stock badge), aggregate stats
(revenue, sales invoices/orders, qty sold, avg price, total stock),
stock-by-warehouse breakdown, and recent invoices.

Numbers are scoped to the company of the given POS Profile so a multi-
company instance doesn't leak figures across legal entities. Returns
empty/zero payloads instead of throwing for items the cashier can't see.
"""

from __future__ import annotations

import time
from typing import Any

import frappe
from frappe.utils import cint, cstr, flt

from posawesome.posawesome.api.item_processing.stock import (
    _expand_warehouse,
    get_bulk_stock_availability,
)
from posawesome.posawesome.api.utils import _ensure_pos_profile, log_perf_event


_RECENT_INVOICE_LIMIT = 10


def _safe_get_value(doctype: str, name: str, fields):
    if not name:
        return None
    try:
        return frappe.db.get_value(doctype, name, fields, as_dict=True)
    except Exception:
        return None


def _profile_currency(profile_dict: dict[str, Any]) -> str:
    currency = cstr(profile_dict.get("currency"))
    if currency:
        return currency
    company = profile_dict.get("company")
    if company:
        return cstr(frappe.db.get_value("Company", company, "default_currency"))
    return ""


def _hero_payload(item_code: str, profile_dict: dict[str, Any]) -> dict[str, Any]:
    item = _safe_get_value(
        "Item",
        item_code,
        ["item_code", "item_name", "image", "stock_uom", "has_batch_no", "has_serial_no"],
    ) or {}

    primary_barcode = (
        frappe.db.get_value(
            "Item Barcode",
            {"parent": item_code},
            "barcode",
            order_by="idx asc",
        )
        or ""
    )

    return {
        "item_code": item.get("item_code") or item_code,
        "item_name": item.get("item_name") or item_code,
        "image": item.get("image") or "",
        "stock_uom": item.get("stock_uom") or "",
        "sku": item.get("item_code") or item_code,
        "barcode": primary_barcode,
        "has_batch_no": bool(cint(item.get("has_batch_no") or 0)),
        "has_serial_no": bool(cint(item.get("has_serial_no") or 0)),
    }


def _aggregate_sales(item_code: str, company: str) -> dict[str, Any]:
    """Submitted Sales Invoice items only — drafts and cancellations excluded."""
    if not company:
        return {
            "total_revenue": 0.0,
            "sales_invoices": 0,
            "qty_sold": 0.0,
            "avg_price": 0.0,
        }

    rows = (
        frappe.db.sql(
            """
            SELECT
                COUNT(DISTINCT sii.parent) AS invoice_count,
                COALESCE(SUM(sii.qty), 0) AS qty_sold,
                COALESCE(SUM(sii.base_net_amount), 0) AS revenue
            FROM `tabSales Invoice Item` sii
            INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
            WHERE si.docstatus = 1
              AND si.company = %(company)s
              AND sii.item_code = %(item_code)s
            """,
            {"item_code": item_code, "company": company},
            as_dict=True,
        )
        or [{}]
    )
    row = rows[0] or {}
    qty_sold = flt(row.get("qty_sold") or 0)
    revenue = flt(row.get("revenue") or 0)
    avg_price = flt(revenue / qty_sold) if qty_sold else 0.0
    return {
        "total_revenue": revenue,
        "sales_invoices": cint(row.get("invoice_count") or 0),
        "qty_sold": qty_sold,
        "avg_price": avg_price,
    }


def _sales_orders_count(item_code: str, company: str) -> int:
    if not company:
        return 0
    rows = (
        frappe.db.sql(
            """
            SELECT COUNT(DISTINCT soi.parent) AS order_count
            FROM `tabSales Order Item` soi
            INNER JOIN `tabSales Order` so ON so.name = soi.parent
            WHERE so.docstatus = 1
              AND so.company = %(company)s
              AND soi.item_code = %(item_code)s
            """,
            {"item_code": item_code, "company": company},
            as_dict=True,
        )
        or [{}]
    )
    return cint((rows[0] or {}).get("order_count") or 0)


def _stock_by_warehouse(item_code: str, profile_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-leaf-warehouse Bin qty for the item, scoped to the profile's company.

    A POS Profile typically points to a single warehouse (or warehouse group);
    showing only that scope keeps the breakdown relevant to the cashier.
    Falls back to all company warehouses when the profile doesn't set one.
    """

    profile_warehouse = profile_dict.get("warehouse")
    company = profile_dict.get("company")

    target_warehouses: list[str] = []
    if profile_warehouse:
        target_warehouses = list(_expand_warehouse(profile_warehouse))

    if not target_warehouses and company:
        target_warehouses = (
            frappe.get_all(
                "Warehouse",
                filters={"company": company, "is_group": 0, "disabled": 0},
                pluck="name",
            )
            or []
        )

    if not target_warehouses:
        return []

    rows = (
        frappe.db.sql(
            """
            SELECT warehouse, COALESCE(SUM(actual_qty), 0) AS actual_qty
            FROM `tabBin`
            WHERE item_code = %(item_code)s AND warehouse IN %(warehouses)s
            GROUP BY warehouse
            ORDER BY actual_qty DESC, warehouse ASC
            """,
            {
                "item_code": item_code,
                "warehouses": tuple(target_warehouses),
            },
            as_dict=True,
        )
        or []
    )

    if not rows:
        return []

    return [
        {
            "warehouse": row.get("warehouse"),
            "actual_qty": flt(row.get("actual_qty") or 0),
        }
        for row in rows
    ]


def _recent_invoices(item_code: str, company: str, limit: int = _RECENT_INVOICE_LIMIT) -> list[dict[str, Any]]:
    if not company:
        return []

    rows = (
        frappe.db.sql(
            """
            SELECT
                si.name,
                si.customer,
                si.customer_name,
                si.posting_date,
                si.grand_total,
                si.currency,
                si.is_return
            FROM `tabSales Invoice Item` sii
            INNER JOIN `tabSales Invoice` si ON si.name = sii.parent
            WHERE si.docstatus = 1
              AND si.company = %(company)s
              AND sii.item_code = %(item_code)s
            GROUP BY si.name
            ORDER BY si.posting_date DESC, si.creation DESC
            LIMIT %(limit)s
            """,
            {"item_code": item_code, "company": company, "limit": cint(limit)},
            as_dict=True,
        )
        or []
    )

    return [
        {
            "name": row.get("name"),
            "customer": row.get("customer"),
            "customer_name": row.get("customer_name") or row.get("customer"),
            "posting_date": cstr(row.get("posting_date")),
            "grand_total": flt(row.get("grand_total") or 0),
            "currency": row.get("currency"),
            "is_return": bool(cint(row.get("is_return") or 0)),
        }
        for row in rows
    ]


@frappe.whitelist()
def get_item_dashboard(item_code: str, pos_profile=None, recent_limit: int = _RECENT_INVOICE_LIMIT):
    """Single-call dashboard payload for the POS product-details drawer."""

    started_at = time.perf_counter()

    item_code = cstr(item_code).strip()
    if not item_code:
        frappe.throw(frappe._("item_code is required"))

    profile_dict, _ = _ensure_pos_profile(pos_profile)
    company = cstr(profile_dict.get("company"))

    hero = _hero_payload(item_code, profile_dict)
    sales_aggregate = _aggregate_sales(item_code, company)
    sales_orders = _sales_orders_count(item_code, company)
    stock_rows = _stock_by_warehouse(item_code, profile_dict)
    total_stock = sum(flt(row.get("actual_qty") or 0) for row in stock_rows)

    profile_warehouse = profile_dict.get("warehouse")
    profile_stock_lookup = (
        get_bulk_stock_availability(
            [{"item_code": item_code, "warehouse": profile_warehouse}]
        )
        if profile_warehouse
        else {}
    )
    profile_stock = flt(
        profile_stock_lookup.get((item_code, profile_warehouse, ""), 0.0)
    )

    payload = {
        "hero": hero,
        "currency": _profile_currency(profile_dict),
        "totals": {
            "total_revenue": sales_aggregate["total_revenue"],
            "sales_invoices": sales_aggregate["sales_invoices"],
            "sales_orders": sales_orders,
            "qty_sold": sales_aggregate["qty_sold"],
            "avg_price": sales_aggregate["avg_price"],
            "total_stock": total_stock,
            "profile_stock": profile_stock,
        },
        "stock_by_warehouse": stock_rows,
        "recent_invoices": _recent_invoices(item_code, company, limit=recent_limit),
    }

    log_perf_event(
        "get_item_dashboard",
        started_at,
        item_code=item_code,
        warehouses=len(stock_rows),
        invoices=len(payload["recent_invoices"]),
    )
    return payload
