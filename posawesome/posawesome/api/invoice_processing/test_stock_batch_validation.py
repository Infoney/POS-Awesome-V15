"""Tests for the batched-item branch of ``_collect_stock_errors``.

Run directly:
``python posawesome/posawesome/api/invoice_processing/test_stock_batch_validation.py``
"""

import importlib.util
import pathlib
import sys
import types
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]


class AttrDict(dict):
    __getattr__ = dict.get


def _install_stubs(*, batch_rows, bin_qty=0.0, allow_negative_global=0):
    frappe_module = types.ModuleType("frappe")
    frappe_module._ = lambda text: text
    frappe_module.whitelist = lambda *args, **kwargs: (lambda fn: fn)
    frappe_module.get_cached_value = lambda doctype, name, field: 0
    frappe_module.db = types.SimpleNamespace(
        get_value=lambda *args, **kwargs: 0,
        get_single_value=lambda doctype, field: allow_negative_global,
    )
    sys.modules["frappe"] = frappe_module

    frappe_utils = types.ModuleType("frappe.utils")
    frappe_utils.cint = lambda v: int(v or 0)
    frappe_utils.flt = lambda v, *args: float(v or 0)
    frappe_utils.cstr = lambda v: "" if v is None else str(v)
    frappe_utils.getdate = lambda value=None: value or "2026-04-21"
    frappe_utils.nowdate = lambda: "2026-04-21"
    sys.modules["frappe.utils"] = frappe_utils

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

    items_module = types.ModuleType("posawesome.posawesome.api.items")
    items_module.get_bulk_stock_availability = lambda items: {
        (i.get("item_code"), i.get("warehouse"), str(i.get("batch_no") or "")): bin_qty
        for i in items
    }
    items_module.get_stock_availability = lambda item_code, warehouse: bin_qty
    sys.modules["posawesome.posawesome.api.items"] = items_module

    item_fetchers_module = types.ModuleType("posawesome.posawesome.api.item_fetchers")
    item_fetchers_module.get_batches = lambda warehouse, item_codes: list(batch_rows)
    sys.modules["posawesome.posawesome.api.item_fetchers"] = item_fetchers_module

    invoice_utils = types.ModuleType(
        "posawesome.posawesome.api.invoice_processing.utils"
    )
    invoice_utils._sanitize_item_name = lambda value: value
    sys.modules[
        "posawesome.posawesome.api.invoice_processing.utils"
    ] = invoice_utils


def _load_module():
    file_path = (
        REPO_ROOT
        / "posawesome"
        / "posawesome"
        / "api"
        / "invoice_processing"
        / "stock.py"
    )
    spec = importlib.util.spec_from_file_location("posa_invoice_stock_under_test", file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _make_item(**overrides):
    base = {
        "item_code": "ITEM-25205",
        "item_name": "Test Item",
        "warehouse": "AL-KHANSA - PPC",
        "qty": 1,
        "stock_qty": 1,
        "is_stock_item": 1,
        "has_batch_no": 1,
        "allow_negative_stock": 0,
    }
    base.update(overrides)
    return base


class TestBatchedItemStockValidation(unittest.TestCase):
    def test_batched_item_with_no_batch_picked_flags_when_every_batch_is_empty(self):
        """The user's reported bug: Bin total can mask that all batches are 0 or negative."""
        _install_stubs(
            batch_rows=[
                AttrDict(batch_no="303481", batch_qty=-2.0, expiry_date=None),
                AttrDict(batch_no="303482", batch_qty=0.0, expiry_date=None),
            ],
            bin_qty=5.0,  # Bin total positive — would have hidden the problem.
        )
        module = _load_module()

        errors = module._collect_stock_errors(
            [_make_item(batch_no=None, qty=1, stock_qty=1)],
        )

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["item_code"], "ITEM-25205")
        self.assertEqual(errors[0]["available_qty"], 0.0)
        self.assertEqual(errors[0]["requested_qty"], 1.0)
        self.assertEqual(errors[0]["reason"], "no_batch_with_enough_qty")

    def test_batched_item_with_explicit_negative_batch_is_flagged_directly(self):
        _install_stubs(
            batch_rows=[
                AttrDict(batch_no="303481", batch_qty=-2.0, expiry_date=None),
            ],
            bin_qty=-2.0,
        )
        module = _load_module()

        errors = module._collect_stock_errors(
            [_make_item(batch_no="303481", qty=1, stock_qty=1)],
        )

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["batch_no"], "303481")
        self.assertEqual(errors[0]["available_qty"], -2.0)

    def test_batched_item_passes_when_one_batch_can_fulfil_request(self):
        _install_stubs(
            batch_rows=[
                AttrDict(batch_no="303481", batch_qty=-2.0, expiry_date=None),
                AttrDict(batch_no="303490", batch_qty=10.0, expiry_date=None),
            ],
            bin_qty=8.0,
        )
        module = _load_module()

        errors = module._collect_stock_errors(
            [_make_item(batch_no=None, qty=3, stock_qty=3)],
        )

        self.assertEqual(errors, [])

    def test_expired_batches_are_ignored_when_picking_max(self):
        _install_stubs(
            batch_rows=[
                # Largest batch but expired → must not count.
                AttrDict(batch_no="EXP", batch_qty=99.0, expiry_date="2024-01-01"),
                AttrDict(batch_no="OK", batch_qty=2.0, expiry_date=None),
            ],
            bin_qty=101.0,
        )
        module = _load_module()

        errors = module._collect_stock_errors(
            [_make_item(batch_no=None, qty=5, stock_qty=5)],
        )

        # Only the OK batch (2 units) counts; requested 5 > 2 → flag.
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["available_qty"], 2.0)

    def test_returns_skip_validation(self):
        _install_stubs(
            batch_rows=[
                AttrDict(batch_no="303481", batch_qty=-2.0, expiry_date=None),
            ],
            bin_qty=-2.0,
        )
        module = _load_module()

        errors = module._collect_stock_errors(
            [_make_item(batch_no="303481", qty=-1, stock_qty=-1)],
        )

        self.assertEqual(errors, [])

    def test_global_allow_negative_stock_disables_validation(self):
        _install_stubs(
            batch_rows=[
                AttrDict(batch_no="303481", batch_qty=-2.0, expiry_date=None),
            ],
            bin_qty=-2.0,
            allow_negative_global=1,
        )
        module = _load_module()

        errors = module._collect_stock_errors(
            [_make_item(batch_no="303481", qty=1, stock_qty=1)],
        )

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
