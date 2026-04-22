import frappe
from frappe.query_builder import DocType
from frappe.query_builder.functions import Sum
from frappe.utils import cstr, flt, json
from erpnext.stock.doctype.batch.batch import get_batch_qty

# Keep IN-clauses well under MariaDB's max_allowed_packet / open_cursor limits.
_SQL_CHUNK_SIZE = 500


def _chunked(seq, size=_SQL_CHUNK_SIZE):
    seq = list(seq)
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def _expand_warehouse(warehouse):
    """Return the concrete leaf warehouses for a (possibly group) warehouse."""
    if not warehouse:
        return []
    if frappe.db.get_value("Warehouse", warehouse, "is_group"):
        return frappe.db.get_descendants("Warehouse", warehouse) or []
    return [warehouse]


def get_stock_availability(item_code, warehouse):
    """Return total available quantity for an item in the given warehouse.

    ``warehouse`` can be either a single warehouse or a warehouse group.
    In case of a group, quantities from all child warehouses are summed up
    to provide an accurate availability figure.
    """

    warehouses = _expand_warehouse(warehouse)
    if not warehouses:
        return 0.0

    bin_doctype = DocType("Bin")
    rows = (
        frappe.qb.from_(bin_doctype)
        .select(Sum(bin_doctype.actual_qty).as_("actual_qty"))
        .where(bin_doctype.item_code == item_code)
        .where(bin_doctype.warehouse.isin(warehouses))
        .run(as_dict=True)
    )

    return flt(rows[0].actual_qty) if rows else 0.0


def _fetch_batch_qty_bulk(items_by_warehouse):
    """Aggregate batch qty for many ``(item_code, batch_no)`` pairs in bulk.

    Args:
        items_by_warehouse (dict[str, set[tuple[str, str]]]):
            warehouse -> set of (item_code, batch_no) pairs.

    Returns:
        dict[tuple[str, str, str], float]: ``(warehouse, item_code, batch_no) -> qty``.
    """
    results = {}
    if not items_by_warehouse:
        return results

    for warehouse, pairs in items_by_warehouse.items():
        if not pairs:
            continue

        warehouses = _expand_warehouse(warehouse)
        if not warehouses:
            for item_code, batch_no in pairs:
                results[(warehouse, item_code, batch_no)] = 0.0
            continue

        item_codes = sorted({p[0] for p in pairs})
        batch_nos = sorted({p[1] for p in pairs})

        qty_map = {}  # (item_code, batch_no) -> qty

        # Modern path: aggregate via Serial and Batch Bundle linked to non-cancelled SLEs.
        for chunk_items in _chunked(item_codes):
            for chunk_batches in _chunked(batch_nos):
                bundle_rows = frappe.db.sql(
                    """
                    SELECT
                        sbb.item_code,
                        sbe.batch_no,
                        SUM(sbe.qty) AS qty
                    FROM `tabSerial and Batch Entry` sbe
                    INNER JOIN `tabSerial and Batch Bundle` sbb
                        ON sbb.name = sbe.parent
                    INNER JOIN `tabStock Ledger Entry` sle
                        ON sle.serial_and_batch_bundle = sbb.name
                    WHERE
                        sbb.item_code IN %(item_codes)s
                        AND sbb.warehouse IN %(warehouses)s
                        AND sbe.batch_no IN %(batch_nos)s
                        AND sle.is_cancelled = 0
                    GROUP BY sbb.item_code, sbe.batch_no
                    """,
                    {
                        "item_codes": tuple(chunk_items),
                        "warehouses": tuple(warehouses),
                        "batch_nos": tuple(chunk_batches),
                    },
                    as_dict=True,
                )
                for row in bundle_rows:
                    key = (row.item_code, row.batch_no)
                    qty_map[key] = qty_map.get(key, 0) + flt(row.qty)

                # Legacy fallback for SLEs created before Serial and Batch Bundle existed.
                legacy_rows = frappe.db.sql(
                    """
                    SELECT
                        item_code,
                        batch_no,
                        SUM(actual_qty) AS qty
                    FROM `tabStock Ledger Entry`
                    WHERE
                        serial_and_batch_bundle IS NULL
                        AND warehouse IN %(warehouses)s
                        AND item_code IN %(item_codes)s
                        AND batch_no IN %(batch_nos)s
                        AND is_cancelled = 0
                    GROUP BY item_code, batch_no
                    """,
                    {
                        "item_codes": tuple(chunk_items),
                        "warehouses": tuple(warehouses),
                        "batch_nos": tuple(chunk_batches),
                    },
                    as_dict=True,
                )
                for row in legacy_rows:
                    key = (row.item_code, row.batch_no)
                    qty_map[key] = qty_map.get(key, 0) + flt(row.qty)

        for item_code, batch_no in pairs:
            results[(warehouse, item_code, batch_no)] = flt(qty_map.get((item_code, batch_no), 0))

    return results


@frappe.whitelist()
def get_bulk_stock_availability(items):
    """
    Fetch available stock for a list of items.

    Args:
        items: List of dicts/objects with 'item_code', 'warehouse', and optional 'batch_no'.

    Returns:
        dict: key=(item_code, warehouse, batch_no), value=qty
    """
    if not items:
        return {}

    regular_items_map = {}        # warehouse -> set(item_code)
    batched_items_map = {}        # warehouse -> set((item_code, batch_no))
    results = {}

    for d in items:
        item_code = d.get("item_code")
        warehouse = d.get("warehouse")
        batch_no = cstr(d.get("batch_no"))  # normalize to "" so dict keys are stable

        if not item_code or not warehouse:
            continue

        if batch_no:
            batched_items_map.setdefault(warehouse, set()).add((item_code, batch_no))
        else:
            regular_items_map.setdefault(warehouse, set()).add(item_code)

    if batched_items_map:
        batched_qty = _fetch_batch_qty_bulk(batched_items_map)
        for (warehouse, item_code, batch_no), qty in batched_qty.items():
            results[(item_code, warehouse, batch_no)] = qty

    if not regular_items_map:
        return results

    all_warehouses = list(regular_items_map.keys())
    group_warehouses = set(
        frappe.get_all(
            "Warehouse",
            filters={"name": ["in", all_warehouses], "is_group": 1},
            pluck="name",
        )
    )

    bin_doctype = DocType("Bin")

    for warehouse, item_codes in regular_items_map.items():
        if not item_codes:
            continue

        target_warehouses = [warehouse]
        if warehouse in group_warehouses:
            target_warehouses = frappe.db.get_descendants("Warehouse", warehouse) or []

        if not target_warehouses:
            for code in item_codes:
                results[(code, warehouse, "")] = 0.0
            continue

        # Chunk to stay under MariaDB IN-clause limits when a profile spans many items.
        for chunk in _chunked(item_codes):
            rows = (
                frappe.qb.from_(bin_doctype)
                .select(bin_doctype.item_code, Sum(bin_doctype.actual_qty).as_("actual_qty"))
                .where(bin_doctype.item_code.isin(chunk))
                .where(bin_doctype.warehouse.isin(target_warehouses))
                .groupby(bin_doctype.item_code)
                .run(as_dict=True)
            )
            for r in rows:
                results[(r.item_code, warehouse, "")] = flt(r.actual_qty)

        for code in item_codes:
            results.setdefault((code, warehouse, ""), 0.0)

    return results


@frappe.whitelist()
def get_available_qty(items):
    """Return available stock quantity for given items.

    The returned shape mirrors the input (one row out per valid input row),
    and now includes ``batch_no`` so callers can match results back to
    their requests positionally OR by composite key. The batch-aware
    branch delegates to :func:`get_bulk_stock_availability` so we use the
    same group-warehouse expansion + bulk SLE/Bundle aggregation as the
    item-details dashboard. Without that, batched lines selling out of a
    group warehouse (e.g. ``AL-KHANSA PHARMACY``) would compare against
    an empty leaf-warehouse balance and falsely report 0 — which then
    causes the frontend's pre-submit guard to block valid sales.

    Args:
        items (str | list[dict]): JSON string or list of dicts with
            item_code, warehouse and optional batch_no.

    Returns:
        list: List of dicts with item_code, warehouse, batch_no and
            available_qty in stock UOM.
    """

    if isinstance(items, str):
        items = json.loads(items)

    items = list(items or [])
    valid_rows = [
        it
        for it in items
        if it and it.get("item_code") and it.get("warehouse")
    ]
    if not valid_rows:
        return []

    bulk_lookup = get_bulk_stock_availability(valid_rows)

    result = []
    for it in valid_rows:
        item_code = it.get("item_code")
        warehouse = it.get("warehouse")
        batch_no = cstr(it.get("batch_no"))  # normalize to "" so key matches

        available_qty = bulk_lookup.get((item_code, warehouse, batch_no))

        # Fall back to the per-row helpers if the bulk path didn't return
        # a row — keeps the legacy contract intact for unusual cases.
        if available_qty is None:
            if batch_no:
                available_qty = get_batch_qty(batch_no, warehouse) or 0
            else:
                available_qty = get_stock_availability(item_code, warehouse)

        result.append(
            {
                "item_code": item_code,
                "warehouse": warehouse,
                "batch_no": batch_no or None,
                "available_qty": flt(available_qty),
            }
        )

    return result


# ---------------------------------------------------------------------------
# Draft-invoice conflict detection
# ---------------------------------------------------------------------------
# When the cashier hits the cryptic
# "Batch X of Item Y has negative stock of -1.0 in warehouse Z"
# error at submit time, the actual blocker is almost always one or more
# OTHER draft invoices that already claim the same batch. The bin shows
# stock because drafts don't post SLEs, but each draft is a "promise" to
# consume that stock the moment it gets submitted — so from the cashier's
# perspective, the unit is already spoken for.
#
# These two endpoints power the StockConflictDialog: one finds the
# offending drafts, the other lets the cashier delete them inline so the
# current sale can proceed. Both are restricted to the cashier's own
# drafts plus drafts they have read/delete permission on, so cashiers
# can't snoop on other terminals' work.


def _normalize_conflict_items_arg(items):
    """Coerce a JSON string OR list of dicts into a clean tuple of dicts."""
    if isinstance(items, str):
        items = json.loads(items)
    return [it for it in (items or []) if it and it.get("item_code")]


def _collect_warehouse_filters(items):
    """Collect every warehouse mentioned in `items`, expanded to leaves.

    Returns a set of leaf warehouse names. Drafts in unrelated warehouses
    are not considered conflicts — they don't compete for the same Bin.
    """
    leaf_warehouses = set()
    for it in items:
        warehouse = it.get("warehouse")
        if not warehouse:
            continue
        for leaf in _expand_warehouse(warehouse) or [warehouse]:
            if leaf:
                leaf_warehouses.add(leaf)
    return leaf_warehouses


def _scan_drafts_for_doctype(
    parent_doctype,
    child_doctype,
    item_codes,
    batch_nos,
    leaf_warehouses,
    exclude_invoice,
):
    """Return draft invoices of the given doctype that include any of the
    requested (item_code, batch_no) pairs.

    We deliberately scope the SQL with explicit IN clauses (not ORM filters)
    so a cashier with hundreds of items in cart still produces a single
    bounded query. Permissions are enforced AFTER the scan via
    ``frappe.has_permission`` so we don't double-pay for the share-lookup
    join twice.
    """
    if not item_codes:
        return []

    parent_alias = parent_doctype.replace(" ", "")
    child_alias = child_doctype.replace(" ", "")

    where_clauses = [
        "parent.docstatus = 0",
        "child.item_code IN %(item_codes)s",
    ]
    params = {
        "item_codes": tuple(item_codes),
    }

    if batch_nos:
        where_clauses.append("(child.batch_no IS NULL OR child.batch_no IN %(batch_nos)s)")
        params["batch_nos"] = tuple(batch_nos)

    if leaf_warehouses:
        where_clauses.append("child.warehouse IN %(warehouses)s")
        params["warehouses"] = tuple(leaf_warehouses)

    if exclude_invoice:
        where_clauses.append("parent.name != %(exclude)s")
        params["exclude"] = exclude_invoice

    sql = f"""
        SELECT
            parent.name           AS name,
            parent.customer       AS customer,
            parent.customer_name  AS customer_name,
            parent.posting_date   AS posting_date,
            parent.posting_time   AS posting_time,
            parent.modified       AS modified,
            parent.owner          AS owner,
            parent.grand_total    AS grand_total,
            parent.currency       AS currency,
            child.name            AS row_name,
            child.item_code       AS item_code,
            child.item_name       AS item_name,
            child.batch_no        AS batch_no,
            child.warehouse       AS warehouse,
            child.qty             AS qty,
            child.stock_qty       AS stock_qty
        FROM `tab{parent_doctype}` AS parent
        INNER JOIN `tab{child_doctype}` AS child
            ON child.parent = parent.name
            AND child.parenttype = %(parent_doctype)s
        WHERE {' AND '.join(where_clauses)}
    """
    params["parent_doctype"] = parent_doctype

    rows = frappe.db.sql(sql, params, as_dict=True)
    if not rows:
        return []

    # Group by parent so each draft becomes one record with its matching items
    grouped = {}
    for row in rows:
        # Skip rows where the batch isn't in our conflict set unless the
        # original line had no batch (e.g. non-batched item). We had to
        # fetch with the wider OR clause above to also surface drafts that
        # have non-batched lines for the same item, which still consume
        # the bin total even though they don't claim a specific batch.
        if batch_nos and row.batch_no and row.batch_no not in batch_nos:
            continue

        invoice = grouped.setdefault(
            row.name,
            {
                "doctype": parent_doctype,
                "name": row.name,
                "customer": row.customer,
                "customer_name": row.customer_name or row.customer,
                "posting_date": str(row.posting_date or ""),
                "posting_time": str(row.posting_time or ""),
                "modified": str(row.modified or ""),
                "owner": row.owner,
                "grand_total": flt(row.grand_total),
                "currency": row.currency,
                "items": [],
                "conflict_qty": 0.0,
            },
        )
        invoice["items"].append(
            {
                "row_name": row.row_name,
                "item_code": row.item_code,
                "item_name": row.item_name or row.item_code,
                "batch_no": row.batch_no,
                "warehouse": row.warehouse,
                "qty": flt(row.qty),
                "stock_qty": flt(row.stock_qty),
            }
        )
        invoice["conflict_qty"] += flt(row.stock_qty or row.qty)

    # Permission check: drop drafts the cashier can't even read. We don't
    # need delete permission here — that's checked at delete time.
    visible = []
    for invoice in grouped.values():
        try:
            if frappe.has_permission(parent_doctype, doc=invoice["name"], ptype="read"):
                visible.append(invoice)
        except Exception:
            # If the permission check itself blows up, default to hiding
            # the row rather than leaking metadata.
            continue

    return visible


@frappe.whitelist()
def get_draft_invoices_for_items(items, exclude_invoice=None):
    """Return all draft Sales / POS Invoices that already claim any of
    the requested (item_code, batch_no) pairs.

    Args:
        items: list of {item_code, batch_no?, warehouse?} or a JSON string.
            ``batch_no`` and ``warehouse`` narrow the search; without them
            we surface every draft holding the item at all.
        exclude_invoice: optional invoice name to exclude (typically the
            current cart's draft, if it has been saved).

    Returns:
        dict: {
            "drafts": [...],          # one record per draft, see _scan_*
            "total_conflict_qty": x,  # sum of stock_qty across all drafts
            "draft_count": n,
        }
    """
    items = _normalize_conflict_items_arg(items)
    if not items:
        return {"drafts": [], "total_conflict_qty": 0.0, "draft_count": 0}

    item_codes = sorted({it.get("item_code") for it in items if it.get("item_code")})
    batch_nos = sorted({it.get("batch_no") for it in items if it.get("batch_no")})
    leaf_warehouses = _collect_warehouse_filters(items)

    drafts = []
    drafts.extend(
        _scan_drafts_for_doctype(
            "Sales Invoice",
            "Sales Invoice Item",
            item_codes,
            batch_nos,
            leaf_warehouses,
            exclude_invoice,
        )
    )
    drafts.extend(
        _scan_drafts_for_doctype(
            "POS Invoice",
            "POS Invoice Item",
            item_codes,
            batch_nos,
            leaf_warehouses,
            exclude_invoice,
        )
    )

    # Newest first — the cashier's most likely culprit is whatever they
    # were just working on.
    drafts.sort(key=lambda d: d.get("modified") or "", reverse=True)

    total_qty = sum(d.get("conflict_qty") or 0 for d in drafts)
    return {
        "drafts": drafts,
        "total_conflict_qty": flt(total_qty),
        "draft_count": len(drafts),
    }


@frappe.whitelist()
def delete_draft_invoices(invoices):
    """Delete a batch of Sales / POS Invoice drafts.

    Each invoice is processed independently — one failure does not abort
    the batch — and the result lists exactly what succeeded vs. what
    didn't, so the UI can report inline.

    Args:
        invoices: list of {doctype, name} or JSON string.

    Returns:
        {
            "deleted": [{doctype, name}],
            "failed":  [{doctype, name, error}],
        }
    """
    if isinstance(invoices, str):
        invoices = json.loads(invoices)

    deleted = []
    failed = []

    for entry in invoices or []:
        doctype = entry.get("doctype")
        name = entry.get("name")

        if not doctype or not name:
            failed.append(
                {
                    "doctype": doctype,
                    "name": name,
                    "error": "Missing doctype or name",
                }
            )
            continue

        if doctype not in ("Sales Invoice", "POS Invoice"):
            failed.append(
                {
                    "doctype": doctype,
                    "name": name,
                    "error": f"Unsupported doctype: {doctype}",
                }
            )
            continue

        try:
            doc = frappe.get_doc(doctype, name)
            if doc.docstatus != 0:
                failed.append(
                    {
                        "doctype": doctype,
                        "name": name,
                        "error": "Only draft invoices can be deleted from POS",
                    }
                )
                continue

            # Explicit permission check — `frappe.delete_doc` will also
            # check, but we want a friendly error rather than a generic
            # PermissionError trace in the UI.
            if not frappe.has_permission(doctype, doc=doc, ptype="delete"):
                failed.append(
                    {
                        "doctype": doctype,
                        "name": name,
                        "error": "You don't have permission to delete this invoice",
                    }
                )
                continue

            frappe.delete_doc(doctype, name, ignore_permissions=False, delete_permanently=True)
            deleted.append({"doctype": doctype, "name": name})
        except Exception as exc:  # noqa: BLE001 — surface anything sane to the UI
            failed.append(
                {
                    "doctype": doctype,
                    "name": name,
                    "error": str(exc),
                }
            )

    if deleted:
        frappe.db.commit()

    return {"deleted": deleted, "failed": failed}
