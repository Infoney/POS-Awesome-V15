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

    Args:
        items (str | list[dict]): JSON string or list of dicts with
            item_code, warehouse and optional batch_no.

    Returns:
        list: List of dicts with item_code, warehouse and available_qty
            in stock UOM.
    """

    if isinstance(items, str):
        items = json.loads(items)

    result = []
    for it in items or []:
        item_code = it.get("item_code")
        warehouse = it.get("warehouse")
        batch_no = it.get("batch_no")

        if not item_code or not warehouse:
            continue

        if batch_no:
            available_qty = get_batch_qty(batch_no, warehouse) or 0
        else:
            available_qty = get_stock_availability(item_code, warehouse)

        result.append(
            {
                "item_code": item_code,
                "warehouse": warehouse,
                "available_qty": flt(available_qty),
            }
        )

    return result
