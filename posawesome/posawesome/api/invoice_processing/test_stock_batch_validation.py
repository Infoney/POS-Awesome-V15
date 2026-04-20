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

    def as_dict(self):
        return dict(self)


def _install_stubs(
    *,
    batch_rows,
    bin_qty=0.0,
    allow_negative_global=0,
    item_has_batch_no=1,
    item_allow_negative=0,
    posa_block_sale=1,
    auto_pick_batch=None,
):
    frappe_module = types.ModuleType("frappe")
    frappe_module._ = lambda text: text
    frappe_module.whitelist = lambda *args, **kwargs: (lambda fn: fn)
    frappe_module.as_json = __import__("json").dumps
    frappe_module.logger = lambda: types.SimpleNamespace(debug=lambda *a, **k: None)

    class _ValidationError(Exception):
        pass

    frappe_module.ValidationError = _ValidationError

    def _throw(message, exc=_ValidationError):
        raise exc(message)

    frappe_module.throw = _throw
    frappe_module.get_cached_value = lambda doctype, name, field: (
        item_allow_negative if field == "allow_negative_stock" else 0
    )

    def _get_value(doctype, name, field=None):
        if field == "has_batch_no":
            return item_has_batch_no
        if field == "posa_block_sale_beyond_available_qty":
            return posa_block_sale
        return 0

    frappe_module.db = types.SimpleNamespace(
        get_value=_get_value,
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
    erpnext_modules["erpnext.stock.doctype.batch.batch"].get_batch_no = (
        lambda item_code, warehouse, qty, throw=False, serial_no=None: auto_pick_batch
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


class TestItemLevelAllowNegativeBatchInteraction(unittest.TestCase):
    """Per-item allow_negative_stock must NOT bypass batch-level checks.

    ERPNext enforces per-batch positivity even when the Item is marked
    ``allow_negative_stock=1``; only ``Stock Settings.allow_negative_stock``
    (the global flag) relaxes the batch validator. We must mirror that or
    cashiers see ERPNext's cryptic stock-ledger error instead of ours.
    """

    def test_per_item_allow_negative_still_blocks_negative_batch(self):
        _install_stubs(
            batch_rows=[
                AttrDict(batch_no="2114011", batch_qty=-1.0, expiry_date=None),
            ],
            bin_qty=-1.0,
            item_allow_negative=1,  # Item.allow_negative_stock = 1
            posa_block_sale=1,
        )
        module = _load_module()

        errors = module._collect_stock_errors(
            [_make_item(batch_no="2114011", qty=1, stock_qty=1)],
        )

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["batch_no"], "2114011")

    def test_per_item_allow_negative_still_skips_plain_items(self):
        # Sanity check: the item-level override still works for non-batched
        # items (Bin-level overdraft is fine when the item allows it).
        _install_stubs(
            batch_rows=[],
            bin_qty=-5.0,
            item_has_batch_no=0,  # plain item
            item_allow_negative=1,
        )
        module = _load_module()

        errors = module._collect_stock_errors(
            [
                _make_item(
                    has_batch_no=0,
                    batch_no=None,
                    allow_negative_stock=1,
                    qty=1,
                    stock_qty=1,
                ),
            ],
        )

        self.assertEqual(errors, [])


class TestValidateStockOnInvoice(unittest.TestCase):
    """Batch-specific errors must always block, even when posa_block_sale=0.

    ERPNext's stock ledger always rejects negative-batch movements (when
    global allow_negative_stock is off), regardless of the POS Profile's
    posa_block_sale_beyond_available_qty preference. Our pre-flight must
    mirror that so the cashier sees our cleaner message first.
    """

    def _make_invoice(self, items, doctype="POS Invoice", pos_profile="POS-TEST"):
        rows = [AttrDict(it) for it in items]
        invoice = types.SimpleNamespace(
            items=rows,
            packed_items=[],
            pos_profile=pos_profile,
            doctype=doctype,
            update_stock=1,
        )
        invoice.is_return = 0
        return invoice

    def test_batch_negative_blocks_even_when_posa_block_sale_is_off(self):
        _install_stubs(
            batch_rows=[
                AttrDict(batch_no="2114011", batch_qty=-1.0, expiry_date=None),
            ],
            bin_qty=-1.0,
            posa_block_sale=0,  # cashier preference: don't block beyond qty
        )
        module = _load_module()

        invoice = self._make_invoice(
            [
                {
                    "item_code": "ITEM-30879",
                    "warehouse": "AL-KHANSA - PPC",
                    "qty": 1,
                    "stock_qty": 1,
                    "is_stock_item": 1,
                    "has_batch_no": 1,
                    "allow_negative_stock": 0,
                    "batch_no": "2114011",
                },
            ]
        )

        with self.assertRaises(Exception) as ctx:
            module._validate_stock_on_invoice(invoice)
        # The thrown payload is the JSON-encoded errors list.
        self.assertIn("2114011", str(ctx.exception))

    def test_no_errors_means_no_throw(self):
        # Sanity check that a clean invoice doesn't trigger the force-block
        # branch. Bin total covers the request, no batch involvement.
        _install_stubs(
            batch_rows=[],
            bin_qty=20.0,
            item_has_batch_no=0,
            posa_block_sale=1,
        )
        module = _load_module()

        invoice = self._make_invoice(
            [
                {
                    "item_code": "ITEM-PLAIN",
                    "warehouse": "AL-KHANSA - PPC",
                    "qty": 5,
                    "stock_qty": 5,
                    "is_stock_item": 1,
                    "has_batch_no": 0,
                    "allow_negative_stock": 0,
                    "batch_no": None,
                },
            ]
        )

        # Stock available (20) > requested (5) → no throw.
        module._validate_stock_on_invoice(invoice)


class TestAutoSetItemBatches(unittest.TestCase):
    """The draft-load → submit fix: auto-allocate batch_no on the server.

    Drafts saved before a batch could be selected (or where the cart's batch
    cache went stale on reload) used to reach ERPNext's stock ledger with no
    batch_no, tripping "Serial No / Batch No are mandatory for Item X".
    """

    def _make_invoice(self, items, is_return=False):
        items_list = []
        for it in items:
            row = AttrDict(it)
            # Mimic Frappe's ``Document`` attribute access for the fields we touch.
            row.use_serial_batch_fields = row.get("use_serial_batch_fields") or 0
            items_list.append(row)
        # Use SimpleNamespace so .items doesn't collide with dict.items().
        return types.SimpleNamespace(items=items_list, is_return=int(is_return))

    def test_assigns_picked_batch_when_item_missing_one(self):
        _install_stubs(
            batch_rows=[],  # not relevant for this code path
            auto_pick_batch="303490",
        )
        module = _load_module()

        invoice = self._make_invoice(
            [
                {
                    "item_code": "ITEM-25205",
                    "warehouse": "AL-KHANSA - PPC",
                    "qty": 1,
                    "stock_qty": 1,
                    "batch_no": None,
                    "serial_no": None,
                },
            ]
        )

        module._auto_set_item_batches(invoice)

        self.assertEqual(invoice.items[0].batch_no, "303490")
        self.assertEqual(invoice.items[0].use_serial_batch_fields, 1)

    def test_keeps_existing_batch_untouched(self):
        _install_stubs(batch_rows=[], auto_pick_batch="ANOTHER-BATCH")
        module = _load_module()

        invoice = self._make_invoice(
            [
                {
                    "item_code": "ITEM-25205",
                    "warehouse": "AL-KHANSA - PPC",
                    "qty": 1,
                    "stock_qty": 1,
                    "batch_no": "PRESET",
                    "serial_no": None,
                },
            ]
        )

        module._auto_set_item_batches(invoice)

        # An operator-set batch must win — never silently overwrite.
        self.assertEqual(invoice.items[0].batch_no, "PRESET")

    def test_does_not_assign_when_no_batch_can_be_picked(self):
        _install_stubs(batch_rows=[], auto_pick_batch=None)
        module = _load_module()

        invoice = self._make_invoice(
            [
                {
                    "item_code": "ITEM-25205",
                    "warehouse": "AL-KHANSA - PPC",
                    "qty": 1,
                    "stock_qty": 1,
                    "batch_no": None,
                    "serial_no": None,
                },
            ]
        )

        module._auto_set_item_batches(invoice)

        # Falls through to the stock validator (which now flags it clearly).
        self.assertIsNone(invoice.items[0].batch_no)

    def test_skips_returns(self):
        _install_stubs(batch_rows=[], auto_pick_batch="WOULD-PICK")
        module = _load_module()

        invoice = self._make_invoice(
            [
                {
                    "item_code": "ITEM-25205",
                    "warehouse": "AL-KHANSA - PPC",
                    "qty": -1,
                    "stock_qty": -1,
                    "batch_no": None,
                    "serial_no": None,
                },
            ],
            is_return=True,
        )

        module._auto_set_item_batches(invoice)

        # Returns go through _auto_set_return_batches with proper expiry rules.
        self.assertIsNone(invoice.items[0].batch_no)

    def test_skips_non_batched_items(self):
        _install_stubs(
            batch_rows=[],
            auto_pick_batch="WOULD-PICK",
            item_has_batch_no=0,
        )
        module = _load_module()

        invoice = self._make_invoice(
            [
                {
                    "item_code": "ITEM-PLAIN",
                    "warehouse": "AL-KHANSA - PPC",
                    "qty": 1,
                    "stock_qty": 1,
                    "batch_no": None,
                    "serial_no": None,
                },
            ]
        )

        module._auto_set_item_batches(invoice)

        self.assertIsNone(invoice.items[0].batch_no)


if __name__ == "__main__":
    unittest.main()
