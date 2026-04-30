import frappe

OLD_WORKSPACE_NAME = "POS Awesome"
NEW_WORKSPACE_NAME = "Mizan"


def execute():
    """
    Reset the workspace so Frappe's post-patch fixture sync recreates it
    under the Mizan brand AND new primary key.

    History:
      * The original workspace was named "POS Awesome" (URL slug
        `/app/pos-awesome`). An earlier rebrand pass updated only the
        display fields (title/label/header text/shortcuts) and kept
        `name = "POS Awesome"` to preserve URL bookmarks.
      * That worked for cashiers, but Frappe's module → workspace
        navigation looks up a workspace whose name matches the
        module name. After the module was renamed to "Mizan", that
        lookup couldn't find any workspace called "Mizan" and
        navigated visitors to `/app/mizan`, which 404'd as
        "Page mizan not found" on a fresh test bench install.
      * So the workspace primary key now also moves: the JSON fixture
        is `posawesome/mizan/workspace/mizan/mizan.json` with
        `"name": "Mizan"`. URL becomes `/app/mizan`.

    What this patch does on every site state:
      1. Drop the old "POS Awesome" workspace if it's still in DB.
      2. Drop any stale "Mizan" workspace whose content was written
         by an older version of this rebrand (idempotency belt).
      3. Let Frappe's standard post-patch workspace sync recreate
         "Mizan" from the JSON fixture.

    URL change is intentional and expected. Existing bookmarks at
    `/app/pos-awesome` will 404 — see docs/MIZAN_RENAME.md for the
    deploy comms checklist.
    """
    deleted_any = False
    for ws in (OLD_WORKSPACE_NAME, NEW_WORKSPACE_NAME):
        if not frappe.db.exists("Workspace", ws):
            continue
        try:
            frappe.delete_doc("Workspace", ws, force=1, ignore_permissions=True)
            print(
                f"Deleted workspace '{ws}' so the post-patch sync can recreate "
                f"it from the updated JSON fixture."
            )
            deleted_any = True
        except Exception as e:
            print(f"Failed to delete workspace '{ws}': {e}")

    if deleted_any:
        frappe.db.commit()
        frappe.clear_cache()
    else:
        print("No POS Awesome / Mizan workspace found in DB — clean install or already migrated.")
