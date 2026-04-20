"""Tests for the per-item dashboard payload (command-center drawer)."""

import importlib.util
import pathlib
import sys
import types
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]


class AttrDict(dict):
    __getattr__ = dict.get

    def as_dict(self):
        return dict(self)


def _install_stubs(
    *,
    profile=None,
    item_meta=None,
    barcode="",
    sales_aggregate=None,
    sales_orders=0,
    bin_rows=None,
    company_warehouses=None,
    recent_invoices=None,
    bulk_stock=None,
    company_currency="KWD",
):
    profile = profile or {
        "name": "POS-TEST",
        "company": "Test Co",
        "warehouse": "Main - TC",
        "currency": "KWD",
    }
    item_meta = item_meta or {
        "item_code": "ITEM-A",
        "item_name": "Test Item",
        "image": "/files/test.png",
        "stock_uom": "Nos",
        "has_batch_no": 0,
        "has_serial_no": 0,
    }
    sales_aggregate = sales_aggregate or {
        "invoice_count": 0,
        "qty_sold": 0,
        "revenue": 0,
    }
    bin_rows = bin_rows or []
    company_warehouses = company_warehouses or []
    recent_invoices = recent_invoices or []
    bulk_stock = bulk_stock or {}

    frappe_module = types.ModuleType("frappe")
    frappe_module._ = lambda text: text

    class _ValidationError(Exception):
        pass

    frappe_module.ValidationError = _ValidationError

    def _throw(message, exc=_ValidationError):
        raise exc(message)

    frappe_module.throw = _throw
    frappe_module.whitelist = lambda *args, **kwargs: (lambda fn: fn)
    frappe_module.session = types.SimpleNamespace(user="test@example.com")

    def _db_get_value(doctype, name, fields=None, **kwargs):
        if doctype == "Item" and isinstance(fields, list):
            return {key: item_meta.get(key) for key in fields}
        if doctype == "Item Barcode":
            return barcode
        if doctype == "Company" and fields == "default_currency":
            return company_currency
        return None

    def _sql(query, params=None, as_dict=False):
        params = params or {}
        item_code = params.get("item_code")
        company = params.get("company")
        if "tabSales Invoice Item" in query and "INNER JOIN" in query and "tabSales Invoice" in query and "GROUP BY si.name" in query:
            return list(recent_invoices)
        if "tabSales Invoice Item" in query and "tabSales Invoice" in query:
            return [sales_aggregate]
        if "tabSales Order Item" in query:
            return [{"order_count": sales_orders}]
        if "tabBin" in query:
            return list(bin_rows)
        return []

    def _get_all(doctype, **kwargs):
        if doctype == "Warehouse" and kwargs.get("pluck") == "name":
            return list(company_warehouses)
        return []

    frappe_module.db = types.SimpleNamespace(
        get_value=_db_get_value,
        sql=_sql,
    )
    frappe_module.get_all = _get_all
    sys.modules["frappe"] = frappe_module

    frappe_utils = types.ModuleType("frappe.utils")
    frappe_utils.cint = lambda v: int(v or 0)
    frappe_utils.cstr = lambda v: "" if v is None else str(v)
    frappe_utils.flt = lambda v, *args: float(v or 0)
    sys.modules["frappe.utils"] = frappe_utils

    stock_module = types.ModuleType("posawesome.posawesome.api.item_processing.stock")
    stock_module._expand_warehouse = lambda w: [w] if w else []
    stock_module.get_bulk_stock_availability = lambda items: dict(bulk_stock)
    sys.modules["posawesome.posawesome.api.item_processing.stock"] = stock_module

    utils_module = types.ModuleType("posawesome.posawesome.api.utils")
    utils_module._ensure_pos_profile = lambda p: (profile, p)
    utils_module.log_perf_event = lambda *args, **kwargs: None
    sys.modules["posawesome.posawesome.api.utils"] = utils_module


def _load_module():
    file_path = (
        REPO_ROOT
        / "posawesome"
        / "posawesome"
        / "api"
        / "item_processing"
        / "dashboard.py"
    )
    spec = importlib.util.spec_from_file_location("posa_item_dashboard_under_test", file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestItemDashboard(unittest.TestCase):
    def test_returns_full_payload_with_aggregate_stats(self):
        _install_stubs(
            sales_aggregate={"invoice_count": 42, "qty_sold": 44, "revenue": 815},
            sales_orders=3,
            bin_rows=[
                {"warehouse": "DSV - TC", "actual_qty": 99},
                {"warehouse": "Main - TC", "actual_qty": 81},
            ],
            recent_invoices=[
                {
                    "name": "ACC-SINV-2026-03482",
                    "customer": "C1",
                    "customer_name": "Customer One",
                    "posting_date": "2026-04-20",
                    "grand_total": 19,
                    "currency": "KWD",
                    "is_return": 0,
                },
            ],
            bulk_stock={("ITEM-A", "Main - TC", ""): 50.0},
        )
        module = _load_module()

        payload = module.get_item_dashboard("ITEM-A", pos_profile="POS-TEST")

        self.assertEqual(payload["hero"]["item_code"], "ITEM-A")
        self.assertEqual(payload["currency"], "KWD")
        self.assertEqual(payload["totals"]["total_revenue"], 815.0)
        self.assertEqual(payload["totals"]["sales_invoices"], 42)
        self.assertEqual(payload["totals"]["sales_orders"], 3)
        self.assertEqual(payload["totals"]["qty_sold"], 44.0)
        # avg_price = revenue / qty_sold
        self.assertAlmostEqual(payload["totals"]["avg_price"], 815 / 44)
        self.assertEqual(payload["totals"]["total_stock"], 180.0)
        self.assertEqual(payload["totals"]["profile_stock"], 50.0)
        self.assertEqual(len(payload["stock_by_warehouse"]), 2)
        self.assertEqual(payload["stock_by_warehouse"][0]["actual_qty"], 99)
        self.assertEqual(len(payload["recent_invoices"]), 1)

    def test_zero_sales_returns_zero_avg_price(self):
        _install_stubs(
            sales_aggregate={"invoice_count": 0, "qty_sold": 0, "revenue": 0},
        )
        module = _load_module()

        payload = module.get_item_dashboard("ITEM-A", pos_profile="POS-TEST")

        self.assertEqual(payload["totals"]["avg_price"], 0.0)
        self.assertEqual(payload["totals"]["sales_invoices"], 0)
        self.assertEqual(payload["totals"]["total_stock"], 0.0)
        self.assertEqual(payload["recent_invoices"], [])

    def test_falls_back_to_company_warehouses_when_profile_has_none(self):
        _install_stubs(
            profile={
                "name": "POS-NOWH",
                "company": "Test Co",
                "warehouse": None,
                "currency": "KWD",
            },
            company_warehouses=["WH1", "WH2"],
            bin_rows=[{"warehouse": "WH1", "actual_qty": 10}],
        )
        module = _load_module()

        payload = module.get_item_dashboard("ITEM-A", pos_profile="POS-NOWH")

        self.assertEqual(len(payload["stock_by_warehouse"]), 1)
        self.assertEqual(payload["stock_by_warehouse"][0]["warehouse"], "WH1")
        # No profile warehouse → profile_stock falls back to 0.
        self.assertEqual(payload["totals"]["profile_stock"], 0.0)

    def test_blank_item_code_throws(self):
        _install_stubs()
        module = _load_module()

        with self.assertRaises(Exception):
            module.get_item_dashboard("", pos_profile="POS-TEST")


if __name__ == "__main__":
    unittest.main()
