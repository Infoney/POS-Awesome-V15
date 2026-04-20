"""Add per-POS-Profile branding fields (custom name + logo).

These let each POS Profile show its own brand name and logo in the navbar
instead of the bundled "POS Awesome" wordmark/logo.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


def _upsert_custom_field(field):
    fieldname = field["fieldname"]
    custom_field_name = f"POS Profile-{fieldname}"

    if not frappe.db.exists("Custom Field", custom_field_name):
        create_custom_field("POS Profile", field)
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
    fields = [
        {
            "fieldname": "posa_section_branding",
            "label": "Branding",
            "fieldtype": "Section Break",
            "collapsible": 1,
            "insert_after": "posa_allow_print_last_invoice",
        },
        {
            "fieldname": "posa_brand_name",
            "label": "Brand Name",
            "fieldtype": "Data",
            "description": "Shown in the POS navbar instead of \"POS Awesome\". Leave blank to keep the default.",
            "insert_after": "posa_section_branding",
        },
        {
            "fieldname": "posa_column_break_branding",
            "fieldtype": "Column Break",
            "insert_after": "posa_brand_name",
        },
        {
            "fieldname": "posa_brand_logo",
            "label": "Brand Logo",
            "fieldtype": "Attach Image",
            "description": "Shown in the POS navbar instead of the default logo. Leave blank to keep the default.",
            "insert_after": "posa_column_break_branding",
        },
        {
            "fieldname": "posa_hide_brand_text",
            "label": "Hide Brand Text in Navbar",
            "fieldtype": "Check",
            "default": "0",
            "description": "Show only the logo in the POS navbar — hides the \"POS Awesome\" / Brand Name wordmark.",
            "insert_after": "posa_brand_logo",
        },
    ]

    for field in fields:
        _upsert_custom_field(field)

    frappe.clear_cache(doctype="POS Profile")
