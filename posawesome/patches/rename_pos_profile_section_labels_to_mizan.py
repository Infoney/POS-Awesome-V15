import frappe


# Map of `Custom Field` rows to update for the second wave of
# Awesome → Mizan brand renames on the POS Profile UI. These are
# section breaks + a checkbox label that the user explicitly
# requested in addition to the dashboard rename done by
# `rename_dashboard_labels_to_mizan` — kept in a separate patch so
# tenants that already migrated the dashboard ones don't re-run that
# work, and so the dashboard patch's blast radius stays small +
# auditable.
#
# Only display labels change. Internal fieldnames
# (`posa_pos_awesome_settings`, `pos_awesome_payments`, etc.)
# stay as-is — they're referenced by depends_on chains, saved POS
# Profile values, hooks.py whitelist entries, and the
# `posa_use_pos_awesome_payments` toggle. Renaming those is its
# own migration with a much wider blast radius.
RENAMES = {
    "POS Profile-posa_pos_awesome_settings": {
        "label": "Mizan Settings",
    },
    "POS Profile-pos_awesome_payments": {
        "label": "Mizan Payments",
    },
    "POS Profile-posa_use_pos_awesome_payments": {
        "label": "Use Mizan Payments",
    },
    "POS Profile-posa_pos_awesome_advance_settings": {
        "label": "Mizan Advance Settings",
    },
}


def execute():
    """
    Rename the remaining "POS Awesome" labels on the POS Profile
    form to the Mizan brand on existing tenants.

    Idempotent — `frappe.db.set_value` on each Custom Field is a
    cheap no-op once the labels are already correct.
    """
    touched = 0
    for custom_field_name, updates in RENAMES.items():
        if not frappe.db.exists("Custom Field", custom_field_name):
            # Field hasn't been created on this site yet — the
            # standard fixture sync will create it with the new
            # label next time it runs. Nothing to do here.
            continue

        try:
            frappe.db.set_value(
                "Custom Field",
                custom_field_name,
                updates,
                update_modified=False,
            )
            touched += 1
            print(f"Renamed Custom Field '{custom_field_name}' to Mizan.")
        except Exception as exc:  # noqa: BLE001
            print(f"Could not rename Custom Field '{custom_field_name}': {exc}")

    if touched:
        frappe.db.commit()
        frappe.clear_cache(doctype="POS Profile")
        print(f"Mizan POS Profile section rename: {touched} field(s) updated.")
