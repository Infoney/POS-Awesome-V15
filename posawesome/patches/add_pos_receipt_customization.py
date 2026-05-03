"""Add receipt-customization fields to POS Profile.

These are the dynamic strings the bundled `Mizan Receipt Print`
print format reads — operator-editable copy that previously lived
hardcoded in the template (Arabic + English thank-you, return-
policy disclaimer). The shop-name / address / phone fields users
typically already added via the Frappe Customize Form (so the
patch only inserts them when missing — never overwrites).

All four footer fields are optional. The print format skips the
corresponding row when the field is empty, so a tenant who only
sets the primary Arabic line gets a clean receipt without the
secondary English subtitle.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field


# Receipt-section custom fields. Sit in a dedicated "Receipt Footer"
# section on the POS Profile so they're easy to discover.
FIELDS = [
    {
        "fieldname": "custom_receipt_footer_section",
        "label": "Receipt Footer",
        "fieldtype": "Section Break",
        "insert_after": "posa_brand_name",
        "collapsible": 1,
        "description": (
            "Dynamic receipt copy printed by the 'Mizan Receipt Print' "
            "format. All fields are optional — empty rows are skipped on "
            "the printed receipt."
        ),
    },
    {
        "fieldname": "custom_receipt_footer_primary",
        "label": "Receipt Footer — Primary",
        "fieldtype": "Small Text",
        "insert_after": "custom_receipt_footer_section",
        "description": (
            "Primary thank-you line printed at the foot of the "
            "receipt. Typically Arabic (e.g. 'نتمنى لكم دوام الصحة "
            "والعافية')."
        ),
    },
    {
        "fieldname": "custom_receipt_footer_secondary",
        "label": "Receipt Footer — Secondary",
        "fieldtype": "Data",
        "insert_after": "custom_receipt_footer_primary",
        "description": (
            "Secondary thank-you subtitle (typically English, e.g. "
            "'Wishing you good health'). Printed in a smaller "
            "uppercase tracker style under the primary line."
        ),
    },
    {
        "fieldname": "custom_receipt_disclaimer_primary",
        "label": "Receipt Disclaimer — Primary",
        "fieldtype": "Small Text",
        "insert_after": "custom_receipt_footer_secondary",
        "description": (
            "Primary disclaimer / policy line (typically Arabic, e.g. "
            "'اعادة الدواء غير مسموح به')."
        ),
    },
    {
        "fieldname": "custom_receipt_disclaimer_secondary",
        "label": "Receipt Disclaimer — Secondary",
        "fieldtype": "Data",
        "insert_after": "custom_receipt_disclaimer_primary",
        "description": (
            "Secondary disclaimer subtitle (typically English, e.g. "
            "'Medication returns are not accepted')."
        ),
    },
]


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
    if not frappe.db.exists("DocType", "POS Profile"):
        return

    for field in FIELDS:
        _upsert_custom_field("POS Profile", field)

    frappe.clear_cache(doctype="POS Profile")
