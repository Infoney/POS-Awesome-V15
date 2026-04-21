"""Add a per-POS-Profile menu/drawer logo field.

The `posa_brand_logo` field already controls the navbar wordmark. Operators
asked for a *second* logo that appears in the side-drawer avatar (typically a
square or rounded crop of their corporate mark, versus the wide banner they
use in the navbar). This patch adds `posa_menu_logo` next to the existing
brand logo so each profile can set both independently.

Idempotent: runs `_upsert_custom_field` which creates on miss and refreshes
attributes on hit.
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
            "fieldname": "posa_menu_logo",
            "label": "Menu Logo",
            "fieldtype": "Attach Image",
            "description": (
                "Shown as the avatar at the top of the POS side drawer. "
                "Use a square or rounded crop of your corporate logo. "
                "Leave blank to reuse the Brand Logo."
            ),
            # Sit right after the existing brand logo so both live together
            # in the Branding section.
            "insert_after": "posa_brand_logo",
        },
    ]

    for field in fields:
        _upsert_custom_field(field)

    frappe.clear_cache(doctype="POS Profile")
