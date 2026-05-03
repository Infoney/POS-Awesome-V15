"""Add the per-POS-Profile "Allow Mizan Barcode Print" toggle.

Sibling of the older `posa_allow_purchase_invoice` flag — gates the
new standalone Mizan Barcode Print menu entry. The existing
`/barcode` page (Barcode Printing) stays gated by its own legacy
permissions; this new entry surfaces the QZ-Tray-driven label
printer that PI / PR already use, but standalone (not coupled to a
Purchase document).

When on, the POS left menu shows a "Mizan Barcode Print" entry.
The cashier picks items, qty per item, optional batch + expiry,
hits Print, and the same `BarcodeLabelPrintDialog` opens with the
labels payload.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


FIELD = {
    "fieldname": "posa_allow_mizan_barcode_print",
    "label": "Allow Mizan Barcode Print",
    "fieldtype": "Check",
    "default": "0",
    "description": (
        "When on, the POS left menu shows a 'Mizan Barcode Print' "
        "entry. Cashiers can print barcode labels for ad-hoc item "
        "lists (item + qty + optional batch / expiry) via QZ Tray, "
        "without needing a Purchase Invoice or Receipt to back it."
    ),
    "insert_after": "posa_allow_purchase_invoice",
}


def execute():
    if not frappe.db.exists("DocType", "POS Profile"):
        return

    custom_field_name = f"POS Profile-{FIELD['fieldname']}"
    if not frappe.db.exists("Custom Field", custom_field_name):
        create_custom_field("POS Profile", FIELD)
    else:
        updates = {k: v for k, v in FIELD.items() if k != "insert_after"}
        if updates:
            frappe.db.set_value(
                "Custom Field",
                custom_field_name,
                updates,
                update_modified=False,
            )
        frappe.db.set_value(
            "Custom Field",
            custom_field_name,
            "insert_after",
            FIELD["insert_after"],
            update_modified=False,
        )

    frappe.clear_cache(doctype="POS Profile")
