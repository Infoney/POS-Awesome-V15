import importlib.util
import json
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]


class AttrDict(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__


def _install_framework_stubs():
    frappe_module = types.ModuleType("frappe")
    frappe_utils = types.ModuleType("frappe.utils")
    frappe_utils.nowdate = lambda: "2026-03-21"

    class _FrappeDict(AttrDict):
        pass

    frappe_module._dict = _FrappeDict
    frappe_module._ = lambda text: text
    frappe_module.as_json = json.dumps
    frappe_module.whitelist = lambda *args, **kwargs: (lambda fn: fn)
    frappe_module.log_error = lambda *args, **kwargs: None
    frappe_module.get_all = lambda *args, **kwargs: []
    frappe_module.db = types.SimpleNamespace(
        get_value=lambda *args, **kwargs: None,
    )

    sys.modules["frappe"] = frappe_module
    sys.modules["frappe.utils"] = frappe_utils
    return frappe_module


def _install_dependency_stubs():
    item_fetchers_module = types.ModuleType("posawesome.posawesome.api.item_fetchers")
    item_fetchers_module.ItemDetailAggregator = object
    item_fetchers_module.get_batches = lambda *args, **kwargs: []
    sys.modules["posawesome.posawesome.api.item_fetchers"] = item_fetchers_module

    stock_module = types.ModuleType("posawesome.posawesome.api.item_processing.stock")
    stock_module.get_stock_availability = lambda *args, **kwargs: 0
    sys.modules["posawesome.posawesome.api.item_processing.stock"] = stock_module

    utils_module = types.ModuleType("posawesome.posawesome.api.utils")
    utils_module._ensure_pos_profile = lambda pos_profile: (pos_profile, pos_profile)
    utils_module.log_perf_event = lambda *args, **kwargs: None
    sys.modules["posawesome.posawesome.api.utils"] = utils_module

    erpnext_stock_module = types.ModuleType("erpnext.stock.get_item_details")
    erpnext_stock_module.get_item_details = lambda *args, **kwargs: {}
    sys.modules["erpnext.stock.get_item_details"] = erpnext_stock_module


def _install_package_stubs():
    package_paths = {
        "posawesome": REPO_ROOT / "posawesome",
        "posawesome.posawesome": REPO_ROOT / "posawesome" / "posawesome",
        "posawesome.posawesome.api": REPO_ROOT / "posawesome" / "posawesome" / "api",
        "posawesome.posawesome.api.item_processing": (
            REPO_ROOT / "posawesome" / "posawesome" / "api" / "item_processing"
        ),
    }
    for name, path in package_paths.items():
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules[name] = module


def _load_module():
    module_name = "posawesome.posawesome.api.item_processing.details"
    file_path = REPO_ROOT / "posawesome" / "posawesome" / "api" / "item_processing" / "details.py"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class TestGetItemDetailNormalization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frappe = _install_framework_stubs()
        _install_dependency_stubs()
        _install_package_stubs()
        cls.details = _load_module()

    def test_normalizes_dict_item_and_json_doc_before_attribute_access(self):
        captured = {}

        def fake_get_item_details(item, doc, overwrite_warehouse=False):
            captured["item"] = item
            captured["doc"] = doc
            return {}

        with patch.object(self.details, "get_stock_availability", return_value=0), patch.object(
            self.details, "get_batches", return_value=[]
        ), patch.object(self.details.frappe, "get_all", return_value=[]), patch.object(
            self.details.frappe.db,
            "get_value",
            side_effect=lambda doctype, name, field, as_dict=False: (
                {"max_discount": 0, "allow_negative_stock": 0, "stock_uom": "Nos"}
                if doctype == "Item" and as_dict
                else "USD"
            ),
        ), patch.dict(
            sys.modules,
            {
                "erpnext.stock.get_item_details": types.SimpleNamespace(
                    get_item_details=fake_get_item_details
                )
            },
        ):
            result = self.details.get_item_detail(
                {"item_code": "ITEM-001", "is_stock_item": 0},
                doc=json.dumps({"customer": "Test Customer"}),
                price_list="Standard Selling",
                company="Test Company",
            )

        self.assertEqual(result["item_uoms"], [{"uom": "Nos", "conversion_factor": 1.0}])
        self.assertIsInstance(captured["item"], self.frappe._dict)
        self.assertIsInstance(captured["doc"], self.frappe._dict)
        self.assertEqual(captured["item"]["item_code"], "ITEM-001")
        self.assertEqual(captured["doc"].price_list_currency, "USD")
        self.assertEqual(captured["doc"].conversion_rate, 1)

    def test_accepts_existing_frappe_dict_without_redecoding(self):
        captured = {}
        item = self.frappe._dict({"item_code": "ITEM-002", "is_stock_item": 0})

        def fake_get_item_details(item_arg, doc_arg, overwrite_warehouse=False):
            captured["item"] = item_arg
            captured["doc"] = doc_arg
            return {}

        with patch.object(self.details, "get_stock_availability", return_value=0), patch.object(
            self.details, "get_batches", return_value=[]
        ), patch.object(self.details.frappe, "get_all", return_value=[]), patch.object(
            self.details.frappe.db,
            "get_value",
            side_effect=lambda doctype, name, field, as_dict=False: (
                {"max_discount": 0, "allow_negative_stock": 0, "stock_uom": "Nos"}
                if doctype == "Item" and as_dict
                else "USD"
            ),
        ), patch.dict(
            sys.modules,
            {
                "erpnext.stock.get_item_details": types.SimpleNamespace(
                    get_item_details=fake_get_item_details
                )
            },
        ):
            self.details.get_item_detail(
                item,
                doc=self.frappe._dict({"customer": "Test Customer"}),
                company="Test Company",
            )

        self.assertIs(captured["item"], item)
        self.assertIsInstance(captured["doc"], self.frappe._dict)


class TestBatchedActualQtyClampsNegatives(unittest.TestCase):
    """Items selector must show *sellable* qty.

    For batched items, ERPNext rejects SLEs that would consume from a
    negative-qty batch. So the displayed actual_qty must reflect what's
    actually sellable — sum of POSITIVE non-expired batch qtys — not the
    naive sum which can mask negative batches behind positive ones and
    mislead the cashier into a sale that fails at submit.
    """

    @classmethod
    def setUpClass(cls):
        cls.frappe = _install_framework_stubs()
        _install_dependency_stubs()
        _install_package_stubs()
        cls.details = _load_module()

    def _run(self, batch_rows):
        captured = {}

        def fake_get_item_details(item, doc, overwrite_warehouse=False):
            captured["item"] = item
            return {}

        with patch.object(
            self.details, "get_batches", return_value=batch_rows
        ), patch.object(self.details.frappe, "get_all", return_value=[]), patch.object(
            self.details.frappe.db,
            "get_value",
            side_effect=lambda doctype, name, field, as_dict=False: (
                {"max_discount": 0, "allow_negative_stock": 0, "stock_uom": "Nos"}
                if doctype == "Item" and as_dict
                else "USD"
            ),
        ), patch.dict(
            sys.modules,
            {
                "erpnext.stock.get_item_details": types.SimpleNamespace(
                    get_item_details=fake_get_item_details
                )
            },
        ):
            return self.details.get_item_detail(
                {
                    "item_code": "ITEM-30879",
                    "is_stock_item": 1,
                    "has_batch_no": 1,
                },
                doc=self.frappe._dict({"customer": "Test"}),
                warehouse="AL-KHANSA - PPC",
                price_list="Standard Selling",
                company="Test Company",
            )

    def test_negative_batch_does_not_inflate_displayed_qty(self):
        # The original bug: cashier sees positive qty (8) and adds to cart;
        # ERPNext later rejects because batch B-NEG is at -2.
        result = self._run(
            [
                AttrDict(batch_no="B-POS", batch_qty=10, expiry_date=None),
                AttrDict(batch_no="B-NEG", batch_qty=-2, expiry_date=None),
            ]
        )
        # 10 (positive batch only), not 8 (10 + -2).
        self.assertEqual(result["actual_qty"], 10)
        # Per-batch data keeps the signed value so the picker can flag it.
        rows = {row["batch_no"]: row["batch_qty"] for row in result["batch_no_data"]}
        self.assertEqual(rows, {"B-POS": 10, "B-NEG": -2})

    def test_all_batches_negative_yields_zero_displayed_qty(self):
        # The reported scenario: every batch is at or below 0. The selector
        # must show 0 so the cashier knows it's actually out of stock.
        result = self._run(
            [
                AttrDict(batch_no="B1", batch_qty=-5, expiry_date=None),
                AttrDict(batch_no="B2", batch_qty=0, expiry_date=None),
                AttrDict(batch_no="B3", batch_qty=-1, expiry_date=None),
            ]
        )
        self.assertEqual(result["actual_qty"], 0)


if __name__ == "__main__":
    unittest.main()
