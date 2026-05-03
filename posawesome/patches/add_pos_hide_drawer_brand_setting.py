"""Add the per-POS-Profile "hide drawer brand" toggle.

Sibling of `posa_hide_brand_text` (added in
`add_pos_hide_brand_text_setting`). That flag hides the wordmark in
the top navbar (NavbarAppBar). This one hides the company logo +
company name shown at the top of the slide-out left drawer
(NavbarDrawer) — useful for tenants who only want the menu items
visible without the brand header taking up the top 64px of drawer
real estate.

Two toggles instead of one because some operators want the appbar
brand hidden but the drawer brand kept (or vice versa) — the appbar
is always visible while the drawer is opt-in, so the cost / benefit
of each surface is different.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


FIELD = {
    "fieldname": "posa_hide_drawer_brand",
    "label": "Hide Brand in Left Menu",
    "fieldtype": "Check",
    "default": "0",
    "description": (
        "Hide the company logo and company name shown at the top of the "
        "POS left menu (drawer). Independent of the navbar wordmark "
        "toggle (`posa_hide_brand_text`)."
    ),
    "insert_after": "posa_hide_brand_text",
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
