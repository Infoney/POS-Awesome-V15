import frappe

WORKSPACE_NAME = "POS Awesome"


def execute():
    """
    Re-applies the workspace JSON fixture (which now carries the Mizan brand)
    to existing sites. Without this patch, `bench migrate` does NOT re-import
    a Workspace fixture once the DB record exists — it only imports on first
    install — so the sidebar/header keep reading "POS Awesome" forever.

    Strategy mirrors patches/recreate_pos_awesome_workspace.py: delete the
    existing workspace doc, then Frappe's standard sync step that runs after
    patches recreates it from posawesome/workspace/pos_awesome/pos_awesome.json
    with the new "Mizan" / "Mizan App" labels.

    The workspace's primary key (`name`) intentionally stays "POS Awesome" —
    that's the URL slug source (/app/pos-awesome) and renaming it would break
    existing bookmarks. Only the *display* fields change.
    """
    if not frappe.db.exists("Workspace", WORKSPACE_NAME):
        print(f"Workspace '{WORKSPACE_NAME}' not found, nothing to rename.")
        return

    title = frappe.db.get_value("Workspace", WORKSPACE_NAME, "title")
    if title == "Mizan":
        print(f"Workspace '{WORKSPACE_NAME}' already shows as 'Mizan', skipping.")
        return

    try:
        frappe.delete_doc("Workspace", WORKSPACE_NAME, force=1, ignore_permissions=True)
        frappe.db.commit()
        print(
            f"Deleted workspace '{WORKSPACE_NAME}' so the migration step recreates "
            f"it from the updated JSON fixture (Mizan brand)."
        )
    except Exception as e:
        print(f"Failed to delete workspace '{WORKSPACE_NAME}' for Mizan rename: {e}")
        return

    frappe.clear_cache()
