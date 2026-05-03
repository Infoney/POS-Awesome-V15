"""Unit tests for the Item-Default cleanup classifier.

These cover the pure-Python decision logic
(``_classify`` / ``_row_has_other_data`` / ``_resolve_pos_profile_account_pairs``)
that drives ``run()``. The full ``run()`` integration relies on
``frappe.db`` + ``frappe.log_error`` and is exercised by hand via the
``bench execute`` dry-run on a real bench (see the module docstring).
"""

from __future__ import annotations

import sys
import types
import unittest


def _stub_frappe() -> None:
    """Inject a lightweight ``frappe`` module so the cleanup module imports cleanly.

    The classifier helpers we test don't call frappe; ``run()`` does. The
    stub satisfies ``import frappe`` at module load.
    """

    if "frappe" in sys.modules:
        return
    stub = types.ModuleType("frappe")
    stub.db = types.SimpleNamespace(
        get_all=lambda *args, **kwargs: [],
        delete=lambda *args, **kwargs: None,
        set_value=lambda *args, **kwargs: None,
        commit=lambda: None,
    )
    stub.log_error = lambda **kwargs: None
    sys.modules["frappe"] = stub


_stub_frappe()

from posawesome.posawesome.maintenance import (  # noqa: E402  -- stub installed above
    cleanup_pos_income_account_defaults as cleanup,
)


POS_PAIRS = {
    ("4306 - KHANSA PH - SALES - PPC", "KHANSA PH"),
    ("4306 - KHANSA PH - SALES - PPC", "KHANSA OTHER CO"),
    ("4310 - DEMO - SALES - DC", "DEMO COMPANY"),
}


def _row(**kwargs):
    """Default Item Default row: only `name`, `parent`, `company`, `income_account`."""
    base = {
        "name": "ID-001",
        "parent": "ITEM-001",
        "company": "KHANSA PH",
        "income_account": None,
        # Other data-bearing fields default to None.
    }
    for field in cleanup.OTHER_DATA_FIELDS:
        base[field] = None
    base.update(kwargs)
    return base


class ClassifierTests(unittest.TestCase):
    def test_pure_pollution_row_is_marked_delete(self):
        row = _row(income_account="4306 - KHANSA PH - SALES - PPC")
        self.assertEqual(cleanup._classify(row, POS_PAIRS), "delete")

    def test_row_with_default_warehouse_is_marked_clear(self):
        row = _row(
            income_account="4306 - KHANSA PH - SALES - PPC",
            default_warehouse="Stores - KP",
        )
        self.assertEqual(cleanup._classify(row, POS_PAIRS), "clear")

    def test_row_with_expense_account_is_marked_clear(self):
        row = _row(
            income_account="4306 - KHANSA PH - SALES - PPC",
            expense_account="5101 - COGS - KP",
        )
        self.assertEqual(cleanup._classify(row, POS_PAIRS), "clear")

    def test_mismatched_company_is_skipped_even_if_account_matches(self):
        # account is in POS pairs but paired with a different company
        row = _row(
            income_account="4306 - KHANSA PH - SALES - PPC",
            company="UNRELATED COMPANY",
        )
        self.assertEqual(cleanup._classify(row, POS_PAIRS), "skip")

    def test_account_not_on_any_pos_profile_is_skipped(self):
        row = _row(income_account="9999 - SOMETHING ELSE - KP")
        self.assertEqual(cleanup._classify(row, POS_PAIRS), "skip")

    def test_empty_income_account_is_skipped(self):
        row = _row(income_account=None)
        self.assertEqual(cleanup._classify(row, POS_PAIRS), "skip")

        row_blank = _row(income_account="")
        self.assertEqual(cleanup._classify(row_blank, POS_PAIRS), "skip")


class RowHasOtherDataTests(unittest.TestCase):
    def test_empty_row_has_no_other_data(self):
        self.assertFalse(cleanup._row_has_other_data(_row()))

    def test_each_data_field_independently_flags_other_data(self):
        for field in cleanup.OTHER_DATA_FIELDS:
            row = _row(**{field: "anything"})
            self.assertTrue(
                cleanup._row_has_other_data(row),
                msg=f"{field} should count as other data",
            )

    def test_only_income_account_does_not_count_as_other_data(self):
        row = _row(income_account="4306 - KHANSA PH - SALES - PPC")
        self.assertFalse(cleanup._row_has_other_data(row))


class FormatRowSummaryTests(unittest.TestCase):
    def test_summary_includes_key_fields(self):
        row = _row(income_account="4306 - KHANSA PH - SALES - PPC")
        summary = cleanup._format_row_summary(row)
        self.assertIn("ID-001", summary)
        self.assertIn("ITEM-001", summary)
        self.assertIn("KHANSA PH", summary)
        self.assertIn("4306 - KHANSA PH - SALES - PPC", summary)


if __name__ == "__main__":
    unittest.main()
