"""Tests for the bulk stock availability path.

Run directly: ``python posawesome/posawesome/api/item_processing/test_stock_bulk.py``.
Mirrors the framework-stub style used by ``test_offline_sync_stock.py`` so the
suite stays runnable without a live Frappe bench.
"""

import importlib.util
import pathlib
import sys
import types
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]


class AttrDict(dict):
    __getattr__ = dict.get


def _install_stubs(sql_results):
    frappe_module = types.ModuleType("frappe")

    class _Q:
        @staticmethod
        def from_(*args, **kwargs):
            raise RuntimeError("Bin path not exercised by these tests")

    frappe_module.qb = _Q
    frappe_module.query_builder = types.SimpleNamespace(DocType=lambda name: object())
    frappe_module.query_builder.functions = types.SimpleNamespace(
        Sum=lambda *args, **kwargs: object()
    )
    frappe_module.utils = types.SimpleNamespace(
        cstr=lambda value: "" if value is None else str(value),
        flt=lambda value, *args: float(value or 0),
        json=__import__("json"),
    )
    frappe_module._dict = AttrDict
    frappe_module.whitelist = lambda *args, **kwargs: (lambda fn: fn)
    frappe_module.db = types.SimpleNamespace(
        get_value=lambda doctype, name, field: 0,
        get_descendants=lambda doctype, warehouse: [],
        sql=lambda query, params=None, as_dict=False: (
            sql_results.pop(0) if sql_results else []
        ),
    )
    frappe_module.get_all = lambda doctype, **kwargs: []
    sys.modules["frappe"] = frappe_module
    sys.modules["frappe.query_builder"] = frappe_module.query_builder
    sys.modules["frappe.query_builder.functions"] = frappe_module.query_builder.functions
    sys.modules["frappe.utils"] = frappe_module.utils

    erpnext_modules = {
        "erpnext": types.ModuleType("erpnext"),
        "erpnext.stock": types.ModuleType("erpnext.stock"),
        "erpnext.stock.doctype": types.ModuleType("erpnext.stock.doctype"),
        "erpnext.stock.doctype.batch": types.ModuleType("erpnext.stock.doctype.batch"),
        "erpnext.stock.doctype.batch.batch": types.ModuleType(
            "erpnext.stock.doctype.batch.batch"
        ),
    }
    erpnext_modules["erpnext.stock.doctype.batch.batch"].get_batch_qty = (
        lambda batch_no, warehouse: 0
    )
    sys.modules.update(erpnext_modules)


def _load_module():
    file_path = REPO_ROOT / "posawesome" / "posawesome" / "api" / "item_processing" / "stock.py"
    spec = importlib.util.spec_from_file_location("posa_stock_under_test", file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestBulkBatchPath(unittest.TestCase):
    def setUp(self):
        self.sql_results = []
        _install_stubs(self.sql_results)
        self.mod = _load_module()

    def test_empty_input_returns_empty_dict(self):
        self.assertEqual(self.mod.get_bulk_stock_availability([]), {})

    def test_batched_items_use_single_bulk_query_pair(self):
        # First call returns Serial-and-Batch-Bundle aggregated rows; second
        # call returns the legacy SLE fallback.
        self.sql_results.extend(
            [
                [
                    AttrDict(item_code="ITEM-A", batch_no="B1", qty=7),
                    AttrDict(item_code="ITEM-A", batch_no="B2", qty=3),
                ],
                [],
            ]
        )

        result = self.mod.get_bulk_stock_availability(
            [
                {"item_code": "ITEM-A", "warehouse": "WH-1", "batch_no": "B1"},
                {"item_code": "ITEM-A", "warehouse": "WH-1", "batch_no": "B2"},
                {"item_code": "ITEM-A", "warehouse": "WH-1", "batch_no": "B3"},
            ]
        )

        self.assertEqual(
            result,
            {
                ("ITEM-A", "WH-1", "B1"): 7.0,
                ("ITEM-A", "WH-1", "B2"): 3.0,
                # Batch present in request but missing from DB defaults to 0.
                ("ITEM-A", "WH-1", "B3"): 0.0,
            },
        )

    def test_legacy_sle_quantities_are_added_to_bundle_quantities(self):
        self.sql_results.extend(
            [
                # Bundle path
                [AttrDict(item_code="ITEM-X", batch_no="BX", qty=4)],
                # Legacy path
                [AttrDict(item_code="ITEM-X", batch_no="BX", qty=2)],
            ]
        )

        result = self.mod.get_bulk_stock_availability(
            [{"item_code": "ITEM-X", "warehouse": "WH-1", "batch_no": "BX"}]
        )

        self.assertEqual(result, {("ITEM-X", "WH-1", "BX"): 6.0})

    def test_rows_with_missing_item_or_warehouse_are_skipped(self):
        result = self.mod.get_bulk_stock_availability(
            [
                {"item_code": None, "warehouse": "WH-1"},
                {"item_code": "X", "warehouse": None},
                {"item_code": "Y", "warehouse": ""},
            ]
        )
        self.assertEqual(result, {})

    def test_chunked_helper_splits_at_size_boundary(self):
        chunks = list(self.mod._chunked(range(1200), size=500))
        self.assertEqual([len(c) for c in chunks], [500, 500, 200])


if __name__ == "__main__":
    unittest.main()
