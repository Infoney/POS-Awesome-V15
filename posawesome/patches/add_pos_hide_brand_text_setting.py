"""Add the per-POS-Profile "hide brand text" toggle.

Existing servers already have `posa_brand_name`/`posa_brand_logo` from
`add_pos_branding_settings`. This separate patch adds the new wordmark
opt-out so operators who set a logo can drop the textual title.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


FIELD = {
    "fieldname": "posa_hide_brand_text",
    "label": "Hide Brand Text in Navbar",
    "fieldtype": "Check",
    "default": "0",
    "description": "Show only the logo in the POS navbar — hides the \"POS Awesome\" / Brand Name wordmark.",
    "insert_after": "posa_brand_logo",
}


def execute():
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
