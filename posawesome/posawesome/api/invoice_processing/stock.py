import json

import frappe
from frappe.utils import cint, flt, cstr, getdate, nowdate
from frappe import _
from erpnext.stock.doctype.batch.batch import get_batch_qty, get_batch_no
from posawesome.posawesome.api.items import get_bulk_stock_availability, get_stock_availability
from posawesome.posawesome.api.item_fetchers import get_batches
from posawesome.posawesome.api.invoice_processing.utils import _sanitize_item_name

def _is_stock_item(item):
    """Return True when the provided row represents a stock item."""

    if item is None:
        return False

    flag = item.get("is_stock_item")
    if flag is not None:
        return bool(cint(flag))

    item_code = item.get("item_code")
    if not item_code:
        return False

    return bool(cint(frappe.get_cached_value("Item", item_code, "is_stock_item") or 0))


def _allow_negative_stock(item, global_allow_negative=None):
    """Return True if negative stock is allowed globally or for the item."""

    # Global setting overrides everything
    if global_allow_negative is None:
        global_allow_negative = cint(
            frappe.db.get_single_value("Stock Settings", "allow_negative_stock") or 0
        )

    if global_allow_negative:
        return True

    flag = item.get("allow_negative_stock")
    if flag is None and item.get("item_code"):
        flag = frappe.get_cached_value("Item", item.get("item_code"), "allow_negative_stock")

    return bool(cint(flag or 0))


def _get_available_stock(item):
    """Return available stock qty for an item row."""
    warehouse = item.get("warehouse")
    batch_no = item.get("batch_no")
    item_code = item.get("item_code")
    if not item_code or not warehouse:
        return 0
    if batch_no:
        return get_batch_qty(batch_no, warehouse) or 0
    return get_stock_availability(item_code, warehouse)


def _has_batch_no(item):
    """Return True when the item is configured with batches."""

    flag = item.get("has_batch_no")
    if flag is not None:
        return bool(cint(flag))

    item_code = item.get("item_code")
    if not item_code:
        return False

    return bool(cint(frappe.get_cached_value("Item", item_code, "has_batch_no") or 0))


def _today():
    return getdate(nowdate())


def _max_available_batch_qty(item_code, warehouse):
    """Return the largest non-expired batch qty available in the warehouse.

    A safe lower bound for "is it possible to fulfil ``requested`` from a
    single batch right now?". Bundle splitting may stretch this further, but
    if even the largest batch can't cover the request the cashier will hit
    ERPNext's per-batch validator at submit time.
    """

    batch_rows = get_batches(warehouse, (item_code,)) or []
    if not batch_rows:
        return 0.0

    today = _today()
    best = 0.0
    for row in batch_rows:
        expiry = row.get("expiry_date")
        if expiry and getdate(expiry) < today:
            continue
        qty = flt(row.get("batch_qty") or 0)
        if qty > best:
            best = qty
    return best


def _collect_stock_errors(items):
    """Return list of items exceeding available stock."""
    errors = []
    items_to_check = []

    global_allow_negative = cint(frappe.db.get_single_value("Stock Settings", "allow_negative_stock") or 0)

    for d in items:
        if flt(d.get("qty")) < 0:
            continue
        if not _is_stock_item(d):
            continue
        # Global flag fully disables both our and ERPNext's checks.
        if global_allow_negative:
            continue
        # Item-level allow_negative_stock only relaxes Bin-total checks for
        # plain items. ERPNext still enforces per-batch positivity even when
        # an Item is marked allow_negative_stock=1, so for batched rows we
        # must keep validating regardless of the item-level flag.
        if not _has_batch_no(d) and _allow_negative_stock(d, global_allow_negative=0):
            continue

        # Defensive: a stale cart line or an over-eager auto-picker can attach
        # a `batch_no` to an item that isn't actually batched. Strip it BEFORE
        # the bulk Bin/SLE fetch so the row goes down the non-batched path
        # (Bin total) instead of querying SLE for a phantom batch (which
        # returns 0 and surfaces a bogus shortage).
        if d.get("batch_no") and not _has_batch_no(d):
            try:
                d["batch_no"] = ""
            except TypeError:
                # Frappe child-doc rows reject __setitem__ — use attribute set.
                d.batch_no = ""

        items_to_check.append(d)

    if not items_to_check:
        return []

    stock_map = get_bulk_stock_availability(items_to_check)

    for d in items_to_check:
        item_code = d.get("item_code")
        warehouse = d.get("warehouse")
        batch_no = cstr(d.get("batch_no"))
        requested = flt(d.get("stock_qty") or (flt(d.get("qty")) * flt(d.get("conversion_factor") or 1)))

        if batch_no:
            # Caller picked (or auto-picker assigned) a specific batch — validate
            # that batch directly. Catches the "Batch X has negative stock" case
            # before it reaches ERPNext's stock ledger.
            available = stock_map.get((item_code, warehouse, batch_no), 0.0)
            if requested > available:
                errors.append(
                    {
                        "item_code": item_code,
                        "warehouse": warehouse,
                        "batch_no": batch_no,
                        "requested_qty": requested,
                        "available_qty": available,
                    }
                )
            continue

        # No batch picked yet — for batched items, ERPNext will allocate one at
        # submit. Bin total can mask a situation where every individual batch
        # has 0 or negative qty, so cross-check that at least one non-expired
        # batch can fulfil the request.
        if _has_batch_no(d) and item_code and warehouse:
            best_batch_qty = _max_available_batch_qty(item_code, warehouse)
            if requested > best_batch_qty:
                errors.append(
                    {
                        "item_code": item_code,
                        "warehouse": warehouse,
                        "requested_qty": requested,
                        "available_qty": best_batch_qty,
                        "reason": "no_batch_with_enough_qty",
                    }
                )
            continue

        # Plain (non-batched) stock item — Bin total is the right signal.
        available = stock_map.get((item_code, warehouse, ""), 0.0)
        if requested > available:
            errors.append(
                {
                    "item_code": item_code,
                    "warehouse": warehouse,
                    "requested_qty": requested,
                    "available_qty": available,
                }
            )
    return errors


def _should_block(pos_profile):
    allow_negative = cint(frappe.db.get_single_value("Stock Settings", "allow_negative_stock") or 0)
    if allow_negative:
        return False

    block_sale = 1
    if pos_profile:
        block_sale = cint(
            frappe.db.get_value("POS Profile", pos_profile, "posa_block_sale_beyond_available_qty") or 1
        )

    return bool(block_sale)


def _is_batch_specific_error(error):
    """A flagged row that ERPNext's per-batch validator would also reject."""
    if not isinstance(error, dict):
        return False
    if error.get("batch_no"):
        return True
    return error.get("reason") == "no_batch_with_enough_qty"


@frappe.whitelist()
def check_invoice_availability(items, pos_profile=None):
    """Dry-run stock-availability check for an outgoing POS invoice payload.

    Single source of truth for "can this cart be submitted right now?".
    Runs the **exact** same `_collect_stock_errors` pipeline that
    `_validate_stock_on_invoice` runs at submit time, then applies the same
    `_should_block` policy — but returns a structured response instead of
    throwing. The frontend calls this once, just before submit; if it comes
    back `ok: true` we proceed, otherwise we hand the offending lines to
    StockConflictDialog so the cashier can fix things without waiting on
    ERPNext's cryptic stock-ledger error.

    Why this exists: caching stock balances client-side is a losing race
    against concurrent terminals. Asking the server right before submit,
    using the same code path the server will use to actually validate, is
    the only way to guarantee preflight ↔ submit parity.

    Args:
        items: JSON string or list of dicts. Required per row:
            `item_code`, `warehouse`, and either `qty` (with optional
            `conversion_factor`) or pre-computed `stock_qty`. Optional hint
            fields honoured if present, else looked up:
            `batch_no`, `is_stock_item`, `has_batch_no`, `allow_negative_stock`,
            `item_name`.
        pos_profile: POS Profile name. Used to honour the per-profile
            `posa_block_sale_beyond_available_qty` for plain non-batched
            overdraws. Batch-specific shortages are always returned (ERPNext's
            stock ledger rejects them at submit regardless of the profile).

    Returns:
        {
            "ok": bool,
            "lines": [
                {
                    "item_code": str,
                    "item_name": str,
                    "warehouse": str,
                    "batch_no": str,        # "" for non-batched rows
                    "requested_qty": float,
                    "available_qty": float,
                    "reason": str,          # see below
                },
                ...
            ],
        }

    `reason` values:
        "insufficient_batch_stock"  — specific batch picked, not enough qty
        "no_batch_with_enough_qty"  — batched item, no single batch can fulfil
        "insufficient_stock"        — non-batched item, Bin total too low
    """
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except (TypeError, ValueError):
            return {"ok": True, "lines": []}
    if not isinstance(items, list) or not items:
        return {"ok": True, "lines": []}

    # Normalise rows so `_collect_stock_errors` has what it needs without
    # forcing the caller to compute `stock_qty`.
    normalized = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        if not raw.get("item_code") or not raw.get("warehouse"):
            continue
        row = dict(raw)
        if not row.get("conversion_factor"):
            row["conversion_factor"] = 1
        if not row.get("stock_qty"):
            row["stock_qty"] = flt(row.get("qty")) * flt(row["conversion_factor"])
        if row.get("batch_no") is None:
            row["batch_no"] = ""
        normalized.append(row)

    if not normalized:
        return {"ok": True, "lines": []}

    errors = _collect_stock_errors(normalized)
    if not errors:
        return {"ok": True, "lines": []}

    # Apply the same submit-time policy: batch errors always block (ERPNext's
    # SLE running-balance validator will reject them anyway), plain Bin
    # overdraws only block if the POS profile says so.
    block_overdraw = _should_block(pos_profile)
    filtered = [
        err for err in errors
        if _is_batch_specific_error(err) or block_overdraw
    ]
    if not filtered:
        return {"ok": True, "lines": []}

    # Decorate with item names so the dialog can show friendly labels.
    item_codes = {err.get("item_code") for err in filtered if err.get("item_code")}
    name_lookup = {
        code: (frappe.get_cached_value("Item", code, "item_name") or code)
        for code in item_codes
    }
    # Prefer the caller-supplied item_name when present (offline drafts may
    # have a customised name override).
    for raw in normalized:
        code = raw.get("item_code")
        if code and raw.get("item_name") and code not in name_lookup:
            name_lookup[code] = raw["item_name"]

    lines = []
    for err in filtered:
        code = err.get("item_code")
        batch_no = err.get("batch_no") or ""
        if err.get("reason") == "no_batch_with_enough_qty":
            reason = "no_batch_with_enough_qty"
        elif batch_no:
            reason = "insufficient_batch_stock"
        else:
            reason = "insufficient_stock"
        lines.append({
            "item_code": code,
            "item_name": name_lookup.get(code, code),
            "warehouse": err.get("warehouse"),
            "batch_no": batch_no,
            "requested_qty": flt(err.get("requested_qty")),
            "available_qty": flt(err.get("available_qty")),
            "reason": reason,
        })

    return {"ok": False, "lines": lines}


@frappe.whitelist()
def validate_draft_invoice_stock(invoice_name, doctype="Sales Invoice", pos_profile=None):
    """Re-check stock availability for an existing draft invoice.

    Drafts do **not** post Stock Ledger entries — they're just saved cart
    state. Between the moment a cashier saves a draft and the moment they
    reopen it, another terminal (or a different drawer here) may have sold
    the very items this draft expects to claim. The cashier shouldn't have
    to discover that at the payment screen; this endpoint surfaces the
    delta the moment the draft is loaded so they can adjust quantities,
    swap batches, or cancel the load with full information.

    Why a separate endpoint (vs. piggybacking on ``get_draft_invoice_doc``):
        * The frontend needs the doc itself even when stock is fine — keeping
          the heavy doc fetch separate from the validation call lets the UI
          render the cart immediately and surface warnings as they arrive.
        * Other callers (Invoice Management, audit screens) can fetch the
          doc without paying for a stock check they don't need.

    The pipeline is the **exact same** ``_collect_stock_errors`` /
    ``_should_block`` chain that ``check_invoice_availability`` and
    ``_validate_stock_on_invoice`` run, so a "warning" here is a faithful
    preview of what the cashier would hit at submit time.

    Args:
        invoice_name: name of the draft invoice (Sales Invoice or POS Invoice).
        doctype: parent doctype. Defaults to ``"Sales Invoice"``; pass
            ``"POS Invoice"`` for terminals configured to skip the Sales
            Invoice intermediary.
        pos_profile: optional POS Profile name. Used to honour the per-profile
            ``posa_block_sale_beyond_available_qty`` flag — same policy as
            ``check_invoice_availability``. Falls back to the draft's own
            ``pos_profile`` when omitted.

    Returns:
        Same shape as ``check_invoice_availability``::

            {
                "ok": bool,
                "lines": [
                    {
                        "item_code": str,
                        "item_name": str,
                        "warehouse": str,
                        "batch_no": str,
                        "requested_qty": float,
                        "available_qty": float,
                        "reason": str,
                    },
                    ...
                ],
                "invoice_name": str,
                "invoice_doctype": str,
            }
    """
    if not invoice_name:
        return {"ok": True, "lines": [], "invoice_name": None, "invoice_doctype": doctype}

    if doctype not in ("Sales Invoice", "POS Invoice"):
        # Defensive: caller can only validate the doctypes our draft flow
        # actually uses. Anything else is treated as a noop rather than
        # raising — the worst case here is a silent skip, never a false
        # positive that blocks the cashier.
        return {"ok": True, "lines": [], "invoice_name": invoice_name, "invoice_doctype": doctype}

    if not frappe.db.exists(doctype, invoice_name):
        return {"ok": True, "lines": [], "invoice_name": invoice_name, "invoice_doctype": doctype}

    try:
        doc = frappe.get_cached_doc(doctype, invoice_name)
    except Exception:
        # If the cached fetch fails (rare; usually permissions), fall back
        # to a non-cached read which will raise a clean PermissionError the
        # frontend can show. We deliberately do NOT swallow that — the
        # cashier needs to know the draft can't be opened at all.
        doc = frappe.get_doc(doctype, invoice_name)

    # Sales Invoices that don't update stock won't post SLEs at submit, so
    # there's nothing to validate. Mirrors the early-out in
    # ``_validate_stock_on_invoice``.
    if doctype == "Sales Invoice" and not cint(getattr(doc, "update_stock", 0)):
        return {"ok": True, "lines": [], "invoice_name": invoice_name, "invoice_doctype": doctype}

    items_to_check = [d.as_dict() for d in (doc.items or []) if d.get("is_stock_item")]
    if hasattr(doc, "packed_items"):
        items_to_check.extend([d.as_dict() for d in (doc.packed_items or [])])

    if not items_to_check:
        return {"ok": True, "lines": [], "invoice_name": invoice_name, "invoice_doctype": doctype}

    # Reuse the same conversion-factor / stock_qty fallback logic that
    # ``check_invoice_availability`` applies, so single-batch and bundled
    # rows behave identically across "load draft" and "submit" entry points.
    for row in items_to_check:
        if not row.get("conversion_factor"):
            row["conversion_factor"] = 1
        if not row.get("stock_qty"):
            row["stock_qty"] = flt(row.get("qty")) * flt(row["conversion_factor"])
        if row.get("batch_no") is None:
            row["batch_no"] = ""

    errors = _collect_stock_errors(items_to_check)
    if not errors:
        return {"ok": True, "lines": [], "invoice_name": invoice_name, "invoice_doctype": doctype}

    # Apply the same submit-time policy: batch shortages always surface
    # (ERPNext's SLE running-balance validator will reject them at submit
    # regardless of the profile flag), plain Bin overdraws only surface if
    # the POS profile blocks them.
    effective_profile = pos_profile or getattr(doc, "pos_profile", None)
    block_overdraw = _should_block(effective_profile)
    filtered = [
        err for err in errors
        if _is_batch_specific_error(err) or block_overdraw
    ]
    if not filtered:
        return {"ok": True, "lines": [], "invoice_name": invoice_name, "invoice_doctype": doctype}

    item_codes = {err.get("item_code") for err in filtered if err.get("item_code")}
    name_lookup = {
        code: (frappe.get_cached_value("Item", code, "item_name") or code)
        for code in item_codes
    }
    # Prefer per-row overrides on the draft itself — cashiers sometimes
    # rename rows (e.g. "Cough Syrup (Patient: Ahmed)") and we want the
    # warning toast to match what they saw in the cart.
    for row in items_to_check:
        code = row.get("item_code")
        if code and row.get("item_name") and code not in name_lookup:
            name_lookup[code] = row["item_name"]

    lines = []
    for err in filtered:
        code = err.get("item_code")
        batch_no = err.get("batch_no") or ""
        if err.get("reason") == "no_batch_with_enough_qty":
            reason = "no_batch_with_enough_qty"
        elif batch_no:
            reason = "insufficient_batch_stock"
        else:
            reason = "insufficient_stock"
        lines.append({
            "item_code": code,
            "item_name": name_lookup.get(code, code),
            "warehouse": err.get("warehouse"),
            "batch_no": batch_no,
            "requested_qty": flt(err.get("requested_qty")),
            "available_qty": flt(err.get("available_qty")),
            "reason": reason,
        })

    return {
        "ok": False,
        "lines": lines,
        "invoice_name": invoice_name,
        "invoice_doctype": doctype,
    }


def _validate_stock_on_invoice(invoice_doc):
    if invoice_doc.doctype == "Sales Invoice" and not cint(getattr(invoice_doc, "update_stock", 0)):
        frappe.logger().debug("Skipping stock validation for Sales Invoice without stock update")
        return
    items_to_check = [d.as_dict() for d in invoice_doc.items if d.get("is_stock_item")]
    if hasattr(invoice_doc, "packed_items"):
        items_to_check.extend([d.as_dict() for d in invoice_doc.packed_items])
    errors = _collect_stock_errors(items_to_check)
    if not errors:
        return

    # ERPNext's stock ledger always rejects negative-batch movements when
    # Stock Settings.allow_negative_stock is off, regardless of the POS
    # Profile's posa_block_sale_beyond_available_qty preference. Force-block
    # any error that's batch-specific so the cashier sees our cleaner
    # message before ERPNext throws a cryptic stock-ledger error. Plain
    # (non-batched) overdrafts still respect the per-profile preference.
    if any(_is_batch_specific_error(error) for error in errors) or _should_block(invoice_doc.pos_profile):
        frappe.throw(frappe.as_json({"errors": errors}), frappe.ValidationError)


def _auto_set_item_batches(invoice_doc):
    """Auto-allocate ``batch_no`` for outgoing invoice rows that lack one.

    Mirrors :func:`set_batch_nos_for_bundels` but operates on
    ``invoice_doc.items`` so the regular line items are also covered. This
    closes a gap where draft invoices saved before a batch was selected
    (or invoices loaded from a draft whose ``batch_no_data`` cache was
    stale) would reach ERPNext's stock ledger missing the batch and trip
    the "Serial No / Batch No are mandatory" validator at submit.

    Returns are intentionally skipped — :func:`_auto_set_return_batches`
    handles those with the proper expiry / free-batch semantics.
    """

    if invoice_doc.is_return:
        return

    for d in invoice_doc.items:
        item_code = d.get("item_code")
        warehouse = d.get("warehouse")
        if not item_code or not warehouse:
            continue
        if d.get("batch_no"):
            continue
        if not cint(frappe.db.get_value("Item", item_code, "has_batch_no") or 0):
            continue

        qty = flt(d.get("stock_qty") or d.get("transfer_qty") or d.get("qty") or 0)
        if qty <= 0:
            continue

        try:
            picked = get_batch_no(item_code, warehouse, qty, throw=False, serial_no=d.get("serial_no"))
        except Exception:
            picked = None

        if picked:
            d.use_serial_batch_fields = 1
            d.batch_no = picked


def _auto_set_return_batches(invoice_doc):
    """Assign batch numbers for return invoices without a source invoice.

    When the POS Profile allows returns without an original invoice and an
    item requires a batch number, this function allocates the first
    available batch in FIFO order. If no batches exist in the selected
    warehouse, an informative error is raised instead of the generic
    validation error.
    """

    if not invoice_doc.is_return or invoice_doc.get("return_against"):
        return

    profile = invoice_doc.get("pos_profile")
    allow_without_invoice = profile and frappe.db.get_value(
        "POS Profile", profile, "posa_allow_return_without_invoice"
    )
    if not cint(allow_without_invoice):
        return

    allow_free = cint(frappe.db.get_value("POS Profile", profile, "posa_allow_free_batch_return") or 0)
    today = getdate(nowdate())

    items_to_process = []
    all_batch_nos = set()

    for d in invoice_doc.items:
        if not d.get("item_code") or not d.get("warehouse"):
            continue

        has_batch = frappe.db.get_value("Item", d.item_code, "has_batch_no")
        if has_batch and not d.get("batch_no"):
            d.use_serial_batch_fields = 1
            # get_batch_qty returns batches sorted by default (usually FIFO/Expiration)
            batch_list = get_batch_qty(item_code=d.item_code, warehouse=d.warehouse) or []
            if batch_list:
                items_to_process.append((d, batch_list))
                for b in batch_list:
                    if b.get("batch_no"):
                        all_batch_nos.add(b.get("batch_no"))
            elif not allow_free:
                frappe.throw(_("No batches available in {0} for {1}.").format(d.warehouse, d.item_code))

    if not all_batch_nos:
        return

    # Fetch expiry dates for all collected batches in one query
    batch_details = frappe.get_all(
        "Batch",
        filters={"name": ["in", list(all_batch_nos)]},
        fields=["name", "expiry_date"],
    )

    valid_batches = {
        b.name
        for b in batch_details
        if not b.expiry_date or getdate(b.expiry_date) >= today
    }

    # Assign batches
    for item, batch_list in items_to_process:
        assigned = False
        for b in batch_list:
            if b.get("batch_no") in valid_batches:
                item.batch_no = b.get("batch_no")
                assigned = True
                break
        if not assigned and not allow_free:
            frappe.throw(_("No valid batches available in {0} for {1}.").format(item.warehouse, item.item_code))


def _apply_item_name_overrides(invoice_doc, overrides=None):
    """Apply custom item names to invoice items."""
    overrides = overrides or {}
    for item in invoice_doc.items:
        source = overrides.get(item.idx) or {}
        provided = source.get("item_name") if isinstance(source, dict) else None
        default_name = frappe.get_cached_value("Item", item.item_code, "item_name")
        clean = _sanitize_item_name(provided or item.item_name)
        if clean and clean != default_name:
            item.item_name = clean
            item.name_overridden = 1
        else:
            item.item_name = default_name
            item.name_overridden = 0


def _merge_duplicate_taxes(invoice_doc):
    """Remove duplicate tax rows with same account and rate.

    If duplicates are found, keep the first occurrence and recalculate totals.
    """
    seen = set()
    unique = []
    for tax in invoice_doc.get("taxes", []):
        key = (tax.account_head, flt(tax.rate), cstr(tax.charge_type))
        if key in seen:
            continue
        seen.add(key)
        unique.append(tax)
    if len(unique) != len(invoice_doc.get("taxes", [])):
        invoice_doc.set("taxes", unique)
        invoice_doc.calculate_taxes_and_totals()


def _deduplicate_free_items(invoice_doc):
    """Merge duplicate free lines created by overlapping pricing rules."""

    items = invoice_doc.get("items", [])
    if not items:
        return

    unique = []
    seen = {}

    def _normalise_qty(row):
        qty = flt(row.get("qty"))
        if not qty:
            return 0
        return qty

    def _normalise_stock_qty(row):
        stock_qty = flt(row.get("stock_qty"))
        if stock_qty:
            return stock_qty
        qty = flt(row.get("qty"))
        if not qty:
            return 0
        conversion_factor = flt(row.get("conversion_factor") or 1) or 1
        return qty * conversion_factor

    for item in items:
        if cint(item.get("is_free_item")):
            key = (
                cstr(item.get("source_rule") or item.get("pricing_rule") or item.get("pricing_rules") or ""),
                cstr(item.get("item_code") or ""),
                cstr(item.get("warehouse") or ""),
                cstr(item.get("uom") or ""),
            )

            existing = seen.get(key)
            if existing:
                existing.qty = _normalise_qty(existing) + _normalise_qty(item)
                existing.stock_qty = _normalise_stock_qty(existing) + _normalise_stock_qty(item)
                # Ensure monetary fields remain zeroed for freebies
                for field in (
                    "rate",
                    "base_rate",
                    "amount",
                    "base_amount",
                    "net_rate",
                    "net_amount",
                    "base_net_rate",
                    "base_net_amount",
                    "discount_amount",
                    "base_discount_amount",
                ):
                    if field in existing and flt(existing.get(field)):
                        existing.set(field, 0)
                continue

            seen[key] = item
            unique.append(item)
            continue

        unique.append(item)

    if len(unique) != len(items):
        invoice_doc.set("items", unique)


def _strip_client_freebies_from_payload(payload):
    """Remove auto-applied POS freebies from inbound payloads before saving."""

    if not payload or not isinstance(payload, dict):
        return

    items = payload.get("items")
    if not isinstance(items, list):
        return

    cleaned = []
    modified = False

    for row in items:
        if not isinstance(row, dict):
            cleaned.append(row)
            continue

        auto_marker = row.get("auto_free_source")
        is_free = cint(row.get("is_free_item"))
        has_name = bool(row.get("name"))

        if auto_marker:
            modified = True
            continue

        cleaned.append(row)

    if modified:
        payload["items"] = cleaned
