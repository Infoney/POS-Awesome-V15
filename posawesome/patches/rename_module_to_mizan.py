import frappe

OLD_MODULE = "POSAwesome"
NEW_MODULE = "Mizan"


def execute():
    """
    Rename the Frappe Module Def "POSAwesome" → "Mizan" so the existing
    DocType / Page / Workspace records (whose `module` column points at the
    old name) line up with the post-rebrand JSON fixtures and the renamed
    on-disk module directory.

    Background. The codebase shipped this Frappe module under the name
    "POSAwesome" with its on-disk directory at `posawesome/posawesome/`,
    matching the convention `frappe.scrub("POSAwesome") == "posawesome"`.
    The full rebrand to Mizan moved the directory to `posawesome/mizan/`
    and updated `modules.txt`, every DocType/Page/Workspace JSON's
    `"module": "POSAwesome"` → `"module": "Mizan"`, and every
    `posawesome.posawesome.*` import / `frappe.call` method path to
    `posawesome.mizan.*`. The bench app slug `posawesome` stays the same
    so asset URLs (`/assets/posawesome/dist/...`), IndexedDB key prefixes,
    Python package imports (`posawesome.X`), and external integrations
    keep working.

    What this patch does on existing sites:

    1. Renames the Module Def DB row "POSAwesome" → "Mizan" so any
       record that still references the old module gets transparently
       updated by Frappe's `rename_doc` cascade (DocType, Custom Field,
       Custom Script, Page, Workspace, Print Format, Number Card,
       Property Setter — anything with a `module` link field).

    2. Best-effort cleanup of any DocType / Page / Workspace rows whose
       `module` column the cascade somehow missed (different Frappe
       versions handle the cascade differently; this is belt-and-braces).

    Idempotent: if the old Module Def is already gone (e.g. patch
    already ran, or fresh install), the patch quietly returns.
    """
    if not frappe.db.exists("Module Def", OLD_MODULE):
        print(f"Module Def '{OLD_MODULE}' not found — already migrated or fresh install.")
        return

    if frappe.db.exists("Module Def", NEW_MODULE):
        # New Module Def already there (possibly from `modules.txt` sync).
        # Repoint the cascade tables onto it manually, then drop the old row.
        print(
            f"Both '{OLD_MODULE}' and '{NEW_MODULE}' Module Defs exist — "
            f"merging cascades onto '{NEW_MODULE}' and dropping '{OLD_MODULE}'."
        )
        _repoint_module_references()
        frappe.delete_doc("Module Def", OLD_MODULE, force=1, ignore_permissions=True)
        frappe.db.commit()
        print(f"Dropped duplicate Module Def '{OLD_MODULE}'.")
        return

    try:
        frappe.rename_doc(
            "Module Def",
            OLD_MODULE,
            NEW_MODULE,
            force=True,
            merge=False,
            ignore_permissions=True,
        )
        frappe.db.commit()
        print(f"Renamed Module Def '{OLD_MODULE}' → '{NEW_MODULE}'.")
    except Exception as e:
        print(f"rename_doc failed ({e}); falling back to manual cascade + delete.")
        # Create the new Module Def explicitly, repoint references, then
        # drop the old one.
        if not frappe.db.exists("Module Def", NEW_MODULE):
            new_def = frappe.get_doc(
                {
                    "doctype": "Module Def",
                    "module_name": NEW_MODULE,
                    "app_name": "posawesome",
                }
            )
            new_def.insert(ignore_permissions=True)
        _repoint_module_references()
        frappe.delete_doc("Module Def", OLD_MODULE, force=1, ignore_permissions=True)
        frappe.db.commit()
        print(f"Manual fallback complete: '{OLD_MODULE}' references repointed to '{NEW_MODULE}'.")

    # Belt-and-braces: tables that store the module as a plain string (not
    # a Link to Module Def) won't be touched by rename_doc. Update them
    # explicitly. Limited to the doctypes the rebrand actually touches.
    _repoint_module_references()
    frappe.db.commit()


def _repoint_module_references() -> None:
    """Rewrite any DocType/Page/Workspace/Custom Field row that still
    carries the old module string. Safe to call repeatedly."""
    tables_with_module_field = [
        "DocType",
        "Page",
        "Report",
        "Workspace",
        "Custom Field",
        "Property Setter",
        "Number Card",
        "Print Format",
        "Custom Script",
        "Server Script",
        "Client Script",
    ]
    for doctype in tables_with_module_field:
        try:
            count = frappe.db.count(doctype, filters={"module": OLD_MODULE})
            if count:
                frappe.db.sql(
                    f"UPDATE `tab{doctype}` SET `module` = %s WHERE `module` = %s",
                    (NEW_MODULE, OLD_MODULE),
                )
                print(f"Repointed {count} {doctype} row(s) from '{OLD_MODULE}' to '{NEW_MODULE}'.")
        except Exception as e:
            # `module` may not exist on every doctype across Frappe versions
            # (e.g. Custom Script vs Client Script naming churn); ignore
            # missing-column errors quietly.
            print(f"Skipping {doctype} repoint: {e}")
