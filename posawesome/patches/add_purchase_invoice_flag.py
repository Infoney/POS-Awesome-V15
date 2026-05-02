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
    Add a POS Profile toggle for the new in-app "Purchase Invoice"
    flow. Mirrors the existing `posa_allow_purchase_receipt` /
    `posa_allow_purchase_order` toggles — the menu entry only
    surfaces in the POS shell when this flag is on, so tenants who
    don't want cashiers booking stock at the till keep the menu
    clean.

    The flow this gate controls: a one-step Purchase Invoice with
    `update_stock=1`, `set_warehouse` and `cost_center` taken from
    the active POS Profile, followed by an optional barcode-label
    print pass over the lines via QZ Tray. Used by pharmacies that
    receive a small replenishment shipment, want to update stock
    immediately, and label the new units in one operator session.
    """
    if not frappe.db.exists("DocType", "POS Profile"):
        return

    _upsert_custom_field(
        "POS Profile",
        {
            "fieldname": "posa_allow_purchase_invoice",
            "label": "Allow Purchase Invoice",
            "fieldtype": "Check",
            "default": 0,
            "description": (
                "When on, the POS left menu shows a 'Purchase Invoice' "
                "entry. Cashiers can book a Purchase Invoice with stock "
                "update; warehouse + cost_center are auto-filled from this "
                "profile. After submit the operator can print one barcode "
                "label per unit purchased via QZ Tray."
            ),
            "insert_after": "posa_allow_purchase_receipt",
        },
    )

    frappe.clear_cache(doctype="POS Profile")
