# Copyright (c) 2026, Infoney and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class POSClosingShiftCashier(Document):
    """
    Per-cashier rollup row on a POS Closing Shift.

    Multiple cashiers can use the same POS shift sequentially via the
    in-app "Switch Cashier" flow (PIN-driven, doesn't end the shift).
    A typical AL-KHANSA shift might be cashier A → B → C → close — three
    "mini shifts" against one Opening Shift document. This child table
    keeps the per-cashier breakdown so the closing report shows who
    rang what without scanning every linked Sales Invoice.

    Populated by `pos_closing_shift.js::aggregate_cashiers` (client) and
    `_collect_cashier_breakdown` in the closing-processing helpers
    (server). Each row sums every Sales Invoice in the shift whose
    `posa_cashier` matches.
    """

    pass
