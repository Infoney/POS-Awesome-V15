import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def _upsert_custom_field(doctype: str, field: dict) -> None:
    fieldname = field["fieldname"]
    custom_field_name = f"{doctype}-{fieldname}"
    if not frappe.db.exists("Custom Field", custom_field_name):
        create_custom_field(doctype, field)
        return
    updates = {k: v for k, v in field.items() if k != "insert_after"}
    if updates:
        frappe.db.set_value(
            "Custom Field",
            custom_field_name,
            updates,
            update_modified=False,
        )
    insert_after = field.get("insert_after")
    if insert_after:
        frappe.db.set_value(
            "Custom Field",
            custom_field_name,
            "insert_after",
            insert_after,
            update_modified=False,
        )


def execute():
    """
    Add cashier-tracking custom fields to Sales Invoice, POS Invoice,
    and User so the POS app's "Switch Cashier" flow leaves an audit
    trail per Sales Invoice and lets the closing report break sales
    down per cashier.

    Why this matters: the existing `posa_pos_opening_shift` field
    already links every invoice to its parent POS Opening Shift, but
    NOT to the cashier who rang the sale. Multiple cashiers can rotate
    on the same shift via the PIN-based Switch Cashier dialog, so the
    Opening Shift's `user` field (= whoever opened the shift) isn't a
    reliable cashier-of-record for downstream invoices.

    Fields added:
      * Sales Invoice.posa_cashier — Link to User. Set on creation
        from the POS app's `currentCashier.user` (employeeStore).
      * POS Invoice.posa_cashier   — same, for tenants whose POS
        Profile has create_pos_invoice_instead_of_sales_invoice on.
      * User.posa_sales_person     — optional Link to Sales Person.
        When set, the closing-shift aggregator copies it onto each
        per-cashier row so commission reports can roll up by Sales
        Person without a second join.

    Idempotent — `_upsert_custom_field` updates existing rows in
    place. Adding the patch again on a site that already has the
    fields is a no-op.
    """
    sales_invoice_field = {
        "fieldname": "posa_cashier",
        "label": "Cashier",
        "fieldtype": "Link",
        "options": "User",
        "read_only": 1,
        "no_copy": 1,
        "in_standard_filter": 1,
        "description": (
            "Cashier who rang this invoice on the POS terminal. "
            "Captured from the POS app's currentCashier (set via the "
            "Switch Cashier PIN dialog) at submit time. May differ "
            "from `owner` when a supervisor is logged in but a "
            "different cashier is currently active on the terminal."
        ),
        "insert_after": "posa_pos_opening_shift",
    }

    if frappe.db.exists("DocType", "Sales Invoice"):
        _upsert_custom_field("Sales Invoice", sales_invoice_field)

    if frappe.db.exists("DocType", "POS Invoice"):
        _upsert_custom_field("POS Invoice", sales_invoice_field)

    user_field = {
        "fieldname": "posa_sales_person",
        "label": "POS Sales Person",
        "fieldtype": "Link",
        "options": "Sales Person",
        "description": (
            "Optional Sales Person link for this user. When set, the "
            "POS Closing Shift's per-cashier rollup copies this onto "
            "the corresponding row so commission reports can group by "
            "Sales Person."
        ),
        "insert_after": "posa_is_pos_supervisor",
    }
    if frappe.db.exists("DocType", "User"):
        _upsert_custom_field("User", user_field)

    frappe.clear_cache(doctype="Sales Invoice")
    if frappe.db.exists("DocType", "POS Invoice"):
        frappe.clear_cache(doctype="POS Invoice")
    frappe.clear_cache(doctype="User")
