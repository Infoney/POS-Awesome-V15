import importlib.util
import pathlib
import sys
import types
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


class AttrDict(dict):
	__getattr__ = dict.get

	def as_dict(self):
		return dict(self)


def _install_stubs():
	frappe_module = types.ModuleType("frappe")
	frappe_module._ = lambda text: text
	frappe_module.throw = lambda message: (_ for _ in ()).throw(Exception(message))
	frappe_module.whitelist = lambda *args, **kwargs: (lambda fn: fn)
	frappe_module.get_cached_doc = lambda doctype, name: AttrDict(
		{
			"name": name,
			"warehouse": "Stores - TC",
			"modified": "2026-04-09T10:01:00",
		}
	)

	# Test scenarios mutate these via setUp.
	frappe_module._fake_bin_rows = []
	frappe_module._fake_sle_rows = []

	def fake_get_all(doctype, **kwargs):
		if doctype == "Bin":
			return list(frappe_module._fake_bin_rows)
		if doctype == "Stock Ledger Entry":
			return list(frappe_module._fake_sle_rows)
		return []

	frappe_module.get_all = fake_get_all
	frappe_module.db = types.SimpleNamespace(
		get_value=lambda doctype, name, field: 0,
		get_descendants=lambda doctype, warehouse: [],
	)
	sys.modules["frappe"] = frappe_module

	api_utils_module = types.ModuleType("posawesome.mizan.api.utils")
	api_utils_module.get_active_pos_profile = lambda user=None: {
		"name": "POS-TEST",
		"warehouse": "Stores - TC",
		"modified": "2026-04-09T10:01:00",
	}
	sys.modules["posawesome.mizan.api.utils"] = api_utils_module

	stock_module = types.ModuleType("posawesome.mizan.api.item_processing.stock")
	stock_module.get_bulk_stock_availability = lambda rows: {
		(row["item_code"], row["warehouse"], ""): index + 5
		for index, row in enumerate(rows)
	}
	sys.modules["posawesome.mizan.api.item_processing.stock"] = stock_module


def _load_module():
	module_name = "test_offline_sync_stock_target"
	file_path = (
		REPO_ROOT
		/ "posawesome"
		/ "posawesome"
		/ "api"
		/ "offline_sync"
		/ "stock.py"
	)
	spec = importlib.util.spec_from_file_location(module_name, file_path)
	module = importlib.util.module_from_spec(spec)
	sys.modules[module_name] = module
	spec.loader.exec_module(module)
	return module


_BIN_ROWS = [
	{"item_code": "ITEM-001", "modified": "2026-04-09T10:02:00"},
	{"item_code": "ITEM-002", "modified": "2026-04-09T10:03:00"},
	{"item_code": "ITEM-003", "modified": "2026-04-09T10:04:00"},
]


class TestOfflineSyncStock(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		_install_stubs()
		cls.module = _load_module()

	def setUp(self):
		import frappe as _frappe
		_frappe._fake_bin_rows = list(_BIN_ROWS)
		_frappe._fake_sle_rows = []

	def test_sync_stock_returns_scoped_actual_qty_changes(self):
		response = self.module.sync_stock(
			pos_profile="POS-TEST",
			watermark="2026-04-09T09:59:00",
			limit=5,
		)

		self.assertEqual(
			[item["key"] for item in response["changes"]],
			["stock::ITEM-001", "stock::ITEM-002", "stock::ITEM-003"],
		)
		self.assertEqual(response["changes"][0]["data"]["actual_qty"], 5)
		self.assertEqual(response["changes"][1]["data"]["warehouse"], "Stores - TC")
		self.assertEqual(response["deleted"], [])
		self.assertEqual(response["next_watermark"], "2026-04-09T10:04:00")

	def test_sync_stock_supports_initial_pagination_without_watermark(self):
		response = self.module.sync_stock(
			pos_profile="POS-TEST",
			watermark=None,
			limit=2,
		)

		self.assertEqual(
			[item["key"] for item in response["changes"]],
			["stock::ITEM-001", "stock::ITEM-002"],
		)
		self.assertTrue(response["has_more"])
		self.assertEqual(response["next_watermark"], "2026-04-09T10:03:00")

	def test_sync_stock_picks_up_sle_changes_when_bin_lags(self):
		"""Repost-lag scenario: SLE recorded a change but Bin hasn't been refreshed yet.

		The sync must still surface the affected items so clients are not stuck on
		stale qty until an unrelated Bin write happens.
		"""
		import frappe as _frappe
		_frappe._fake_bin_rows = []
		_frappe._fake_sle_rows = [
			{"item_code": "ITEM-007", "modified": "2026-04-09T10:10:00"},
		]

		response = self.module.sync_stock(
			pos_profile="POS-TEST",
			watermark="2026-04-09T09:59:00",
			limit=5,
		)

		self.assertEqual(
			[item["key"] for item in response["changes"]],
			["stock::ITEM-007"],
		)
		self.assertEqual(response["next_watermark"], "2026-04-09T10:10:00")

	def test_sync_stock_dedupes_overlap_between_bin_and_sle(self):
		"""Bin row wins on duplicates so we don't emit two changes for the same item."""
		import frappe as _frappe
		_frappe._fake_bin_rows = [
			{"item_code": "ITEM-009", "modified": "2026-04-09T10:20:00"},
		]
		_frappe._fake_sle_rows = [
			{"item_code": "ITEM-009", "modified": "2026-04-09T10:25:00"},
			{"item_code": "ITEM-010", "modified": "2026-04-09T10:26:00"},
		]

		response = self.module.sync_stock(
			pos_profile="POS-TEST",
			watermark="2026-04-09T09:59:00",
			limit=5,
		)

		self.assertEqual(
			[item["key"] for item in response["changes"]],
			["stock::ITEM-009", "stock::ITEM-010"],
		)
		# Watermark advances to the newest signal across both sources so the next
		# poll never re-pulls already-synced rows.
		self.assertEqual(response["next_watermark"], "2026-04-09T10:26:00")

	def test_sync_stock_full_resync_when_schema_version_mismatches(self):
		response = self.module.sync_stock(
			pos_profile="POS-TEST",
			watermark="2026-04-09T09:59:00",
			limit=5,
			schema_version="1999-01-01",
		)

		self.assertTrue(response.get("full_resync_required"))


if __name__ == "__main__":
	unittest.main()
