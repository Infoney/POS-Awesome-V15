"""One-shot cleanup of stale `Item Default` rows ERPNext wrote against
Items via the `set_default_income_account_for_item` writeback path.

Background
----------
ERPNext v15's ``erpnext.controllers.selling_controller.set_default_income_account_for_item``
runs inside ``SellingController.validate()`` on every Sales/POS Invoice
save. When the line-level ``income_account`` differs from the company's
``default_income_account`` (which is exactly what happens for any POS
Profile that overrides the company income account), it persists that
account back onto ``Item.item_defaults`` via ``set_item_default``.

We landed Defendicon's monkey-patch in commit ``816c21f3`` (merged on
``pos-iteration-2`` as ``63961e63``) that short-circuits the writeback
for POS docs (``is_pos=1`` and ``pos_profile`` set). New sales no
longer pollute Item Defaults — but rows ERPNext already wrote BEFORE
the patch landed are still on existing Items.

This script removes those stale rows.

Strategy
--------
1. Build the set of (income_account, company) pairs currently or
   historically configured on ANY POS Profile (including disabled,
   since pollution may have been written under a now-disabled
   profile). This is the candidate-pollution account list.
2. Pull every ``Item Default`` row whose ``income_account`` is in
   that set.
3. For each candidate row, classify:
   - **delete** — the row's ONLY non-empty data-bearing field is
     ``income_account``. The row is pure writeback pollution and is
     safe to remove entirely.
   - **clear** — the row carries other manually-set fields
     (``default_warehouse``, ``expense_account``, etc.). The
     ``income_account`` is most likely the writeback pollution; we
     null it out but leave the rest of the row intact.
   - **skip** — falls through (shouldn't happen given the filter,
     defensive).

A dry-run prints what WILL change without writing. Pass
``commit=True`` to actually apply.

Bench commands
--------------
.. code-block:: bash

   # Dry-run — read-only, prints planned changes:
   bench --site <site> execute \\
     posawesome.posawesome.maintenance.cleanup_pos_income_account_defaults.run

   # Apply (irreversible — back up first via `bench backup --with-files`):
   bench --site <site> execute \\
     posawesome.posawesome.maintenance.cleanup_pos_income_account_defaults.run \\
     --kwargs "{'commit': True}"

   # If your bench version expects JSON-style kwargs:
   bench --site <site> execute \\
     posawesome.posawesome.maintenance.cleanup_pos_income_account_defaults.run \\
     --kwargs '{"commit": true}'

Always take a backup before the commit run. The script logs every
delete + clear to the Frappe error log via ``frappe.log_error`` so the
audit trail survives even if you forget to pipe the output.
"""

from __future__ import annotations

from typing import Iterable

import frappe


# ``Item Default`` data-bearing fields besides ``income_account``. If any
# of these is non-empty on a row, the row carries something the operator
# may have set manually and we don't delete it — we just clear the
# ``income_account`` field.
#
# Pulled from the v15 ``Item Default`` doctype JSON
# (``erpnext/stock/doctype/item_default/item_default.json``). When ERPNext
# adds new fields, this list should be extended; missing fields just
# means we'll delete more rows than we should, which is the unsafe
# direction — keep this list current.
OTHER_DATA_FIELDS = (
    "default_warehouse",
    "default_price_list",
    "buying_cost_center",
    "default_supplier",
    "expense_account",
    "selling_cost_center",
    "default_discount_account",
    "default_provisional_account",
    "deferred_expense_account",
    "deferred_revenue_account",
)


def _resolve_pos_profile_account_pairs() -> set[tuple[str, str]]:
    """All ``(income_account, company)`` pairs ever configured on a POS Profile.

    Includes disabled profiles because pollution may have been written
    while a profile was active and then disabled.
    """
    rows = frappe.db.get_all(
        "POS Profile",
        fields=["name", "income_account", "company"],
        # No filter on `disabled`; we want every profile that ever existed.
    )
    pairs: set[tuple[str, str]] = set()
    for row in rows:
        income = row.get("income_account")
        company = row.get("company")
        if income and company:
            pairs.add((income, company))
    return pairs


def _row_has_other_data(row: dict) -> bool:
    return any(row.get(field) for field in OTHER_DATA_FIELDS)


def _classify(row: dict, pos_pairs: set[tuple[str, str]]) -> str:
    """Return one of: 'delete', 'clear', 'skip'."""
    income = row.get("income_account")
    company = row.get("company")
    if not income:
        return "skip"
    if (income, company) not in pos_pairs:
        return "skip"
    return "clear" if _row_has_other_data(row) else "delete"


def _format_row_summary(row: dict) -> str:
    return (
        f"  - Item Default {row['name']} "
        f"on Item {row['parent']!r} "
        f"(company={row.get('company')!r}, "
        f"income_account={row.get('income_account')!r})"
    )


def _print_sample(label: str, rows: Iterable[dict], limit: int = 25) -> None:
    rows = list(rows)
    print(f"\n{label}: {len(rows)}")
    for row in rows[:limit]:
        print(_format_row_summary(row))
    if len(rows) > limit:
        print(f"  ... and {len(rows) - limit} more")


def run(commit: bool = False) -> dict:
    """Entry point. ``commit=False`` (default) is a dry-run.

    Returns a small report dict summarising what was found and what was
    written, useful when calling from a Frappe console for assertions.
    """
    print("=" * 72)
    print("POS-Awesome cleanup: stale Item Default income-account rows")
    print("(see docstring for context — this scrubs pollution ERPNext")
    print(" wrote BEFORE the `set_default_income_account_for_item` guard")
    print(" landed in pos-iteration-2 commit 63961e63.)")
    print("=" * 72)

    pos_pairs = _resolve_pos_profile_account_pairs()
    if not pos_pairs:
        print(
            "\nNo POS Profile has an income_account + company pair set. "
            "Nothing to scrub — exiting."
        )
        return {"deleted": 0, "cleared": 0, "candidates": 0}

    print(f"\nPOS Profile (income_account, company) pairs: {len(pos_pairs)}")
    for account, company in sorted(pos_pairs):
        print(f"  - {account!r}  on company {company!r}")

    # The only `income_account` filter we apply at the SQL level is
    # "is in the set of POS Profile income accounts". Company match is
    # checked in Python below — `Item Default` rows can carry mismatched
    # (account, company) pairs in rare manual-edit scenarios, and we
    # don't want to scrub those.
    candidate_accounts = sorted({pair[0] for pair in pos_pairs})
    fields = ["name", "parent", "company", "income_account"] + list(OTHER_DATA_FIELDS)
    rows = frappe.db.get_all(
        "Item Default",
        fields=fields,
        filters={"income_account": ("in", candidate_accounts)},
        limit_page_length=0,  # no implicit page cap
    )
    print(f"\nCandidate Item Default rows (income_account in POS-Profile set): {len(rows)}")

    deletes: list[dict] = []
    clears: list[dict] = []
    skips: list[dict] = []
    for row in rows:
        action = _classify(row, pos_pairs)
        if action == "delete":
            deletes.append(row)
        elif action == "clear":
            clears.append(row)
        else:
            skips.append(row)

    _print_sample("Will DELETE entire row (pollution-only)", deletes)
    _print_sample("Will CLEAR income_account only (row has other defaults)", clears)
    _print_sample("Will SKIP (mismatched company or no income_account)", skips)

    if not commit:
        print(
            "\n[dry-run] No changes written. Re-run with kwargs "
            "`{'commit': True}` (or JSON `{\"commit\": true}`) to apply."
        )
        return {
            "deleted": 0,
            "cleared": 0,
            "candidates": len(rows),
            "would_delete": len(deletes),
            "would_clear": len(clears),
            "skipped": len(skips),
            "dry_run": True,
        }

    print("\n[commit] Applying changes — this is irreversible.")
    deleted = 0
    cleared = 0
    audit_lines: list[str] = []

    for row in deletes:
        frappe.db.delete("Item Default", {"name": row["name"]})
        deleted += 1
        audit_lines.append(f"DELETED {row['name']} from Item {row['parent']!r}")

    for row in clears:
        frappe.db.set_value(
            "Item Default",
            row["name"],
            "income_account",
            None,
            update_modified=False,
        )
        cleared += 1
        audit_lines.append(
            f"CLEARED income_account on {row['name']} "
            f"(Item {row['parent']!r}, was {row.get('income_account')!r})"
        )

    frappe.db.commit()

    if audit_lines:
        # Frappe truncates `frappe.log_error` to 140 chars on title and
        # ~140KB on body. Chunk the audit log so a big run still all
        # ends up searchable in the error log.
        chunk = []
        chunk_size = 0
        chunks: list[list[str]] = []
        for line in audit_lines:
            if chunk_size + len(line) > 100_000:
                chunks.append(chunk)
                chunk = []
                chunk_size = 0
            chunk.append(line)
            chunk_size += len(line) + 1
        if chunk:
            chunks.append(chunk)
        for index, lines in enumerate(chunks, start=1):
            frappe.log_error(
                title=(
                    f"cleanup_pos_income_account_defaults "
                    f"({index}/{len(chunks)})"
                ),
                message="\n".join(lines),
            )

    print(f"\nDone. Deleted {deleted} rows, cleared {cleared} rows.")
    print(
        "Audit trail logged to Error Log "
        "(/app/error-log?error_type=cleanup_pos_income_account_defaults)."
    )
    return {
        "deleted": deleted,
        "cleared": cleared,
        "candidates": len(rows),
        "skipped": len(skips),
        "dry_run": False,
    }
