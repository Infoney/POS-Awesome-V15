import frappe
from frappe.utils import flt


def _backfill_invoice_cashier(doctype: str) -> int:
    """
    Copy `owner` into `posa_cashier` for every invoice of `doctype`
    where the cashier field is empty. Skips Administrator/Guest so
    a shift created during install doesn't end up flagged as a real
    cashier sale.

    Returns the number of rows updated.
    """
    if not frappe.db.exists("DocType", doctype):
        return 0
    try:
        meta = frappe.get_meta(doctype)
    except Exception:
        return 0
    if not meta.has_field("posa_cashier"):
        return 0

    rows = frappe.get_all(
        doctype,
        filters={
            "docstatus": ["!=", 2],
        },
        or_filters=[
            {"posa_cashier": ""},
            {"posa_cashier": ["is", "not set"]},
        ],
        fields=["name", "owner"],
        limit_page_length=0,
    )
    updated = 0
    for row in rows:
        owner = row.get("owner") or ""
        if not owner or owner in ("Administrator", "Guest"):
            continue
        if not frappe.db.exists("User", owner):
            continue
        # Use db.set_value so the timestamp / modified-by markers don't
        # change — the patch is a backfill, not a real edit.
        frappe.db.set_value(
            doctype,
            row["name"],
            "posa_cashier",
            owner,
            update_modified=False,
        )
        updated += 1
    return updated


def _backfill_pos_transactions_cashier() -> int:
    """
    For every Sales Invoice Reference row (the `pos_transactions`
    child of POS Closing Shift) with empty `cashier`, look up the
    linked invoice's `posa_cashier` (just backfilled above) or
    `owner` and copy it into the row.

    Returns the number of rows updated.
    """
    rows = frappe.db.sql(
        """
        select name, parent, sales_invoice, pos_invoice
        from `tabSales Invoice Reference`
        where ifnull(cashier, '') = ''
        """,
        as_dict=True,
    )
    if not rows:
        return 0

    # Collect invoice names per doctype so we can batch the lookups.
    by_doctype = {"Sales Invoice": set(), "POS Invoice": set()}
    for row in rows:
        if row.get("sales_invoice"):
            by_doctype["Sales Invoice"].add(row["sales_invoice"])
        elif row.get("pos_invoice"):
            by_doctype["POS Invoice"].add(row["pos_invoice"])

    cashier_by_invoice = {}
    for doctype, names in by_doctype.items():
        if not names or not frappe.db.exists("DocType", doctype):
            continue
        fields = ["name", "owner"]
        try:
            meta = frappe.get_meta(doctype)
            if meta.has_field("posa_cashier"):
                fields.append("posa_cashier")
        except Exception:
            pass
        for entry in frappe.get_all(
            doctype,
            filters={"name": ["in", list(names)]},
            fields=fields,
        ):
            cashier = entry.get("posa_cashier") or entry.get("owner") or ""
            if cashier and cashier not in ("Administrator", "Guest"):
                cashier_by_invoice[(doctype, entry["name"])] = cashier

    updated = 0
    for row in rows:
        if row.get("sales_invoice"):
            key = ("Sales Invoice", row["sales_invoice"])
        elif row.get("pos_invoice"):
            key = ("POS Invoice", row["pos_invoice"])
        else:
            continue
        cashier = cashier_by_invoice.get(key)
        if not cashier:
            continue
        frappe.db.set_value(
            "Sales Invoice Reference",
            row["name"],
            "cashier",
            cashier,
            update_modified=False,
        )
        updated += 1
    return updated


def _rebuild_closing_shift_cashier_rollup() -> int:
    """
    Re-aggregate the `cashiers` child table on every existing POS
    Closing Shift from the (now-backfilled) `pos_transactions` rows.
    Replaces the table contents wholesale so a re-run of the patch is
    idempotent.

    Returns the number of shifts touched.
    """
    if not frappe.db.exists("DocType", "POS Closing Shift Cashier"):
        return 0
    try:
        meta = frappe.get_meta("POS Closing Shift")
        if not meta.has_field("cashiers"):
            return 0
    except Exception:
        return 0

    shifts = frappe.get_all("POS Closing Shift", pluck="name", limit_page_length=0)
    if not shifts:
        return 0

    has_user_sales_person = False
    try:
        has_user_sales_person = frappe.db.has_column("User", "posa_sales_person")
    except Exception:
        pass

    updated = 0
    for shift_name in shifts:
        transactions = frappe.get_all(
            "Sales Invoice Reference",
            filters={"parent": shift_name},
            fields=["cashier", "grand_total", "sales_invoice", "pos_invoice"],
        )
        if not transactions:
            # Wipe any stale cashiers rows on a shift that has no
            # transactions left.
            frappe.db.sql(
                "delete from `tabPOS Closing Shift Cashier` where parent = %s",
                shift_name,
            )
            continue

        buckets = {}
        invoice_keys = []
        for row in transactions:
            cashier = (row.get("cashier") or "").strip()
            if not cashier:
                continue
            bucket = buckets.setdefault(
                cashier,
                {
                    "cashier": cashier,
                    "invoice_count": 0,
                    "grand_total": 0.0,
                    "net_total": 0.0,
                },
            )
            bucket["invoice_count"] += 1
            bucket["grand_total"] += flt(row.get("grand_total") or 0)
            if row.get("sales_invoice"):
                invoice_keys.append(("Sales Invoice", row["sales_invoice"], cashier))
            elif row.get("pos_invoice"):
                invoice_keys.append(("POS Invoice", row["pos_invoice"], cashier))

        # Pull base_net_total per invoice for the net column.
        net_lookup = {}
        per_doctype = {}
        for doctype, name, _ in invoice_keys:
            per_doctype.setdefault(doctype, set()).add(name)
        for doctype, names in per_doctype.items():
            if not frappe.db.exists("DocType", doctype):
                continue
            for entry in frappe.get_all(
                doctype,
                filters={"name": ["in", list(names)]},
                fields=["name", "base_net_total"],
            ):
                net_lookup[(doctype, entry["name"])] = flt(
                    entry.get("base_net_total") or 0
                )
        for doctype, name, cashier in invoice_keys:
            if cashier in buckets:
                buckets[cashier]["net_total"] += net_lookup.get((doctype, name), 0)

        # Optional sales_person hydration.
        sales_person_by_user = {}
        if has_user_sales_person and buckets:
            for entry in frappe.get_all(
                "User",
                filters={"name": ["in", list(buckets.keys())]},
                fields=["name", "posa_sales_person"],
            ):
                sales_person_by_user[entry["name"]] = entry.get("posa_sales_person") or ""

        # Wipe + re-insert. Cheaper than a diff for a typical shift's
        # ~1-5 cashier rows, and idempotent.
        frappe.db.sql(
            "delete from `tabPOS Closing Shift Cashier` where parent = %s",
            shift_name,
        )
        idx = 0
        for bucket in sorted(
            buckets.values(),
            key=lambda b: (b.get("cashier") or "").lower(),
        ):
            idx += 1
            child = frappe.get_doc(
                {
                    "doctype": "POS Closing Shift Cashier",
                    "parent": shift_name,
                    "parenttype": "POS Closing Shift",
                    "parentfield": "cashiers",
                    "idx": idx,
                    "cashier": bucket["cashier"],
                    "invoice_count": bucket["invoice_count"],
                    "grand_total": flt(bucket["grand_total"]),
                    "net_total": flt(bucket["net_total"]),
                    "sales_person": sales_person_by_user.get(bucket["cashier"], ""),
                }
            )
            child.flags.ignore_permissions = True
            child.flags.ignore_validate = True
            child.db_insert()

        updated += 1

    return updated


def execute():
    """
    Backfill the cashier-tracking fields rolled out in
    `add_cashier_tracking_fields.py` for shifts that were closed
    BEFORE the JS / server-side resolver landed.

    Three passes, in order:
      1. `posa_cashier` on Sales Invoice / POS Invoice — copy `owner`
         when the field is empty.
      2. `cashier` on the Sales Invoice Reference (`pos_transactions`)
         child of every Closing Shift — read from the linked invoice
         (using the just-backfilled `posa_cashier` first, falling back
         to `owner`).
      3. `cashiers` rollup table on POS Closing Shift — wholesale
         rebuild from the (now-populated) `pos_transactions` rows so
         existing shifts gain a per-cashier breakdown without needing
         to be re-saved by hand.

    Idempotent: re-running on a backfilled site is a no-op for #1 and
    #2 (rows already have values), and #3 wipes-and-rewrites so it
    converges on the same output every run.
    """
    # Defensive reload: `bench migrate` on some setups (especially
    # when patches.txt is processed before the doctype-sync step) can
    # leave the new Mizan-owned doctype changes (added `cashier`
    # field on `Sales Invoice Reference`, new `POS Closing Shift
    # Cashier` doctype + the `cashiers` table on the parent) un-
    # registered when this patch runs. Forcing a reload here makes
    # the patch self-sufficient — `frappe.db.set_value` and `db_insert`
    # below need the SQL columns to exist.
    try:
        frappe.reload_doc("mizan", "doctype", "sales_invoice_reference")
    except Exception:
        pass
    try:
        frappe.reload_doc("mizan", "doctype", "pos_closing_shift_cashier")
    except Exception:
        pass
    try:
        frappe.reload_doc("mizan", "doctype", "pos_closing_shift")
    except Exception:
        pass

    invoices_updated = 0
    invoices_updated += _backfill_invoice_cashier("Sales Invoice")
    invoices_updated += _backfill_invoice_cashier("POS Invoice")

    if invoices_updated:
        frappe.clear_cache(doctype="Sales Invoice")
        if frappe.db.exists("DocType", "POS Invoice"):
            frappe.clear_cache(doctype="POS Invoice")

    transactions_updated = _backfill_pos_transactions_cashier()
    shifts_rebuilt = _rebuild_closing_shift_cashier_rollup()

    frappe.db.commit()

    print(
        "[backfill_cashier_tracking] "
        f"invoices={invoices_updated} "
        f"transactions={transactions_updated} "
        f"shifts={shifts_rebuilt}"
    )
