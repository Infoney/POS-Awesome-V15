"""Backfill currency / conversion_rate / base_amount on legacy POS Opening
Shift Detail rows.

Before the multi-currency opening-shift fix, the child table only carried
``mode_of_payment`` and ``amount``. The amount was rendered as if it were
the company currency regardless of the POS Profile's currency, so a 500
SAR opening on a KWD company looked like "KWD 500.000" in the form. The
schema now persists the row currency, foreign-to-company exchange rate,
and the company-currency equivalent (``base_amount``).

This patch sets sensible defaults on existing rows so they keep rendering
consistently after the schema change:

  * ``currency``        = parent POS Opening Shift's company default
                          currency (legacy rows were always treated as
                          company currency anyway).
  * ``conversion_rate`` = 1.0 (no conversion was ever applied).
  * ``base_amount``     = ``amount`` (legacy amounts were already in
                          company currency from the cashier's POV).

The patch is idempotent — rows that already have ``currency`` set are
left alone.
"""

import frappe


def execute():
    if not frappe.db.exists("DocType", "POS Opening Shift Detail"):
        return

    # Pre-`run_schema_updates` patches execute BEFORE Frappe syncs DocType
    # JSON definitions, so the new `currency` / `conversion_rate` /
    # `base_amount` columns aren't on `tabPOS Opening Shift Detail` yet at
    # this point. Reload the child + parent JSON ourselves so the schema
    # sync runs in time and the SELECT below doesn't 1054 with
    # "Unknown column 'd.currency'".
    frappe.reload_doc("posawesome", "doctype", "pos_opening_shift_detail")
    frappe.reload_doc("posawesome", "doctype", "pos_opening_shift")

    # Defensive guard: if the reload didn't add the column for any reason
    # (older Frappe builds, cached metadata, etc.), bail rather than crash
    # the migration. The next bench migrate after a clean sync will pick
    # up the rows.
    if not frappe.db.has_column("POS Opening Shift Detail", "currency"):
        return

    # Pull every legacy detail row missing the new metadata, joined to its
    # parent so we can resolve the company currency without a per-row
    # `frappe.get_cached_value` round trip.
    rows = frappe.db.sql(
        """
        SELECT
            d.name AS row_name,
            d.amount AS amount,
            COALESCE(c.default_currency, '') AS company_currency
        FROM `tabPOS Opening Shift Detail` d
        INNER JOIN `tabPOS Opening Shift` p ON p.name = d.parent
        LEFT JOIN `tabCompany` c ON c.name = p.company
        WHERE COALESCE(d.currency, '') = ''
        """,
        as_dict=True,
    )

    if not rows:
        return

    for row in rows:
        amount = float(row.get("amount") or 0)
        currency = row.get("company_currency") or ""
        frappe.db.set_value(
            "POS Opening Shift Detail",
            row.get("row_name"),
            {
                "currency": currency,
                "conversion_rate": 1.0,
                "base_amount": amount,
            },
            update_modified=False,
        )

    frappe.db.commit()
