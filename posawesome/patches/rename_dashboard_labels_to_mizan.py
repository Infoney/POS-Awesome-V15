import frappe


# Map of `Custom Field` rows to update for the Awesome → Mizan
# dashboard rename. Keys are the Custom Field primary keys; values
# are the field updates to apply. Only Frappe-fixture-driven labels
# / descriptions land here — the actual fieldnames stay
# (posa_*_awesome_*) so we don't break any code or saved values that
# reference them.
RENAMES = {
    # POS Profile section + checkbox
    "POS Profile-posa_section_awesome_dashboard": {
        "label": "Mizan Dashboard",
    },
    "POS Profile-posa_enable_awesome_dashboard": {
        "label": "Enable Mizan Dashboard",
    },
    # POS Settings (global) section + checkbox + description
    "POS Settings-posa_section_dashboard": {
        "label": "Mizan Dashboard",
    },
    "POS Settings-posa_enable_awesome_dashboard_global": {
        "label": "Enable Mizan Dashboard",
        "description": "Enable Mizan dashboard globally.",
    },
}


def execute():
    """
    Rename the "Awesome Dashboard" labels in the POS Profile + POS
    Settings UIs to "Mizan Dashboard" on existing tenants.

    The original `add_dashboard_settings`, `add_dashboard_global_settings`,
    and `reorganize_pos_profile_sections` patches that created these
    Custom Field rows already updated their own source files to the
    new "Mizan Dashboard" copy, BUT Frappe's patch runner only
    executes a patch entry once per site — so existing tenants
    (AL-KHANSA, mizan-test, etc.) keep showing the old labels until
    something explicitly rewrites them.

    This patch runs `frappe.db.set_value` on each Custom Field name,
    so it's idempotent and cheap — re-running it is a no-op.
    """
    touched = 0
    for custom_field_name, updates in RENAMES.items():
        if not frappe.db.exists("Custom Field", custom_field_name):
            # Field hasn't been created on this site yet — the
            # original add_* patch will create it with the new copy
            # next time it runs (we already updated those source
            # files). Nothing to do here.
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
        # Bust the metadata cache for the doctypes whose UIs we just
        # touched so the renamed labels show up without a manual
        # refresh.
        frappe.clear_cache(doctype="POS Profile")
        frappe.clear_cache(doctype="POS Settings")
        print(f"Mizan dashboard label rename: {touched} field(s) updated.")
