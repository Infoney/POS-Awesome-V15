import frappe

# The on-disk JSON fixtures historically used two capitalizations of the
# old module name interchangeably:
#   * "POSAwesome" — the canonical form (modules.txt, ~all DocType JSONs)
#   * "Posawesome" — a typo on `pos_awesome_print_format_rule.json`,
#     which Frappe's CI surfaced via "Module Posawesome not found" on
#     fresh install of feat/mizan-module-rename. The branch fixes the
#     JSON; this patch handles the equivalent typo if it leaked into
#     any production DB row over the years.
OLD_MODULES = ("POSAwesome", "Posawesome")
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
    existing_old = [m for m in OLD_MODULES if frappe.db.exists("Module Def", m)]
    if not existing_old:
        print(f"No old Module Defs ({OLD_MODULES}) found — already migrated or fresh install.")
        return

    # Make sure the destination Module Def exists. On a fresh install
    # Frappe creates it from `modules.txt` automatically before patches
    # run; on an existing site it may not exist yet, in which case we
    # create it here so the cascade has somewhere to land.
    if not frappe.db.exists("Module Def", NEW_MODULE):
        frappe.get_doc(
            {
                "doctype": "Module Def",
                "module_name": NEW_MODULE,
                "app_name": "posawesome",
            }
        ).insert(ignore_permissions=True)
        print(f"Created Module Def '{NEW_MODULE}'.")

    for old in existing_old:
        try:
            frappe.rename_doc(
                "Module Def",
                old,
                NEW_MODULE,
                force=True,
                merge=True,  # merge cascades onto the new row if it already exists
                ignore_permissions=True,
            )
            print(f"Renamed/merged Module Def '{old}' → '{NEW_MODULE}'.")
        except Exception as e:
            print(f"rename_doc('{old}') failed ({e}); falling back to manual cascade + delete.")
            _repoint_module_references(old)
            try:
                frappe.delete_doc("Module Def", old, force=1, ignore_permissions=True)
            except Exception as inner:
                print(f"Couldn't drop Module Def '{old}': {inner}")

    # Belt-and-braces: tables that store the module as a plain string (not
    # a Link to Module Def) won't be touched by rename_doc. Update them
    # explicitly for every old variant.
    for old in OLD_MODULES:
        _repoint_module_references(old)

    frappe.db.commit()


def _repoint_module_references(old_module: str) -> None:
    """Rewrite any DocType/Page/Workspace/Custom Field row that still
    carries `old_module` as its module string. Safe to call repeatedly."""
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
            count = frappe.db.count(doctype, filters={"module": old_module})
            if count:
                frappe.db.sql(
                    f"UPDATE `tab{doctype}` SET `module` = %s WHERE `module` = %s",
                    (NEW_MODULE, old_module),
                )
                print(f"Repointed {count} {doctype} row(s) from '{old_module}' to '{NEW_MODULE}'.")
        except Exception as e:
            # `module` may not exist on every doctype across Frappe versions
            # (e.g. Custom Script vs Client Script naming churn); ignore
            # missing-column errors quietly.
            print(f"Skipping {doctype} repoint: {e}")
