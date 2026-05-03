"""Install / refresh the 'Mizan Receipt Print' Jinja Print Format.

Ships a 4in / 80mm thermal receipt format that's fully driven by
operator-editable POS Profile fields:

  * `custom_shop_name`     — pharmacy / shop name (Arabic primary)
  * `custom_shop_address`  — street + area
  * `custom_shop_phone`    — contact number
  * `custom_receipt_footer_primary`     — primary thanks line
  * `custom_receipt_footer_secondary`   — secondary subtitle
  * `custom_receipt_disclaimer_primary` — return policy etc
  * `custom_receipt_disclaimer_secondary` — secondary policy line

Empty fields are skipped on the printed page, so a tenant only
fills the rows they want. Cashier label is per-POS-Profile via
`posa_cashier_label` (existing field — falls back to "Cashier").

Re-runnable: `frappe.get_doc("Print Format", ...).save()` is
idempotent. Touching the patch + running migrate refreshes the
template on every site.

Target doctype: Sales Invoice (the AL-KHANSA POS flow). To enable
the same format on POS Invoice, clone it from the Print Format
list view (Duplicate, change Doc Type) — the bundled patch keeps a
single canonical copy.
"""

import frappe


PRINT_FORMAT_NAME = "Mizan Receipt Print"
PRINT_FORMAT_DOCTYPE = "Sales Invoice"


def _build_html() -> str:
    """
    Returns the Jinja template body. Triple-quoted so the markup
    survives without escaping. Anything that uses the `{{ ... }}`
    or `{% ... %}` Jinja syntax goes through verbatim.

    The template fetches `pos_profile_doc` via
    `frappe.get_cached_doc` so the operator-editable strings
    above-the-fold render WITHOUT a per-field DB hit at print time.
    """
    return r"""{# ------------------------------------------------------------------
   Mizan Receipt Print — 4in / 80mm thermal POS receipt.
   All branding copy comes from the active POS Profile so the
   template stays tenant-neutral.
   ------------------------------------------------------------------ #}

{%- set company = frappe.get_cached_doc("Company", doc.company) -%}
{%- set pos_profile_doc = frappe.get_cached_doc("POS Profile", doc.pos_profile) if doc.pos_profile else None -%}
{%- set cashier_name = frappe.db.get_value("User", doc.owner, "full_name") or doc.owner -%}

{# Configurable cashier label — falls back to "Cashier" if the POS
   Profile field is empty. Translated through Frappe's i18n. #}
{%- set profile_label = pos_profile_doc.get("posa_cashier_label") if pos_profile_doc else None -%}
{%- set cashier_label = _(profile_label) if profile_label else _("Cashier") -%}

{# Pharmacy / shop branding — operator fills these on POS Profile.
   The template falls back to Company.company_name when the shop
   name is blank so a fresh install still prints a meaningful
   header. #}
{%- set shop_name = (pos_profile_doc.get("custom_shop_name") if pos_profile_doc else "") or company.company_name -%}
{%- set shop_address = pos_profile_doc.get("custom_shop_address") if pos_profile_doc else "" -%}
{%- set shop_phone = (pos_profile_doc.get("custom_shop_phone") if pos_profile_doc else "") or company.phone_no -%}
{%- set footer_primary = pos_profile_doc.get("custom_receipt_footer_primary") if pos_profile_doc else "" -%}
{%- set footer_secondary = pos_profile_doc.get("custom_receipt_footer_secondary") if pos_profile_doc else "" -%}
{%- set disclaimer_primary = pos_profile_doc.get("custom_receipt_disclaimer_primary") if pos_profile_doc else "" -%}
{%- set disclaimer_secondary = pos_profile_doc.get("custom_receipt_disclaimer_secondary") if pos_profile_doc else "" -%}

{%- set is_return = (doc.is_return or doc.status == "Return") -%}
{%- set outstanding = (doc.outstanding_amount or 0) -%}
{%- set change_due = (doc.change_amount or 0) -%}
{%- set status_label = "RETURN" if is_return
                       else ("UNPAID" if outstanding > 0
                       else "PAID") -%}
{%- set line_count = doc.items|length -%}
{%- set total_qty = doc.items|sum(attribute="qty") -%}

<style>
  .print-format,
  .print-format table,
  .print-format tr,
  .print-format td,
  .print-format th,
  .print-format div,
  .print-format p {
    line-height: 1.25;
    margin: 0;
    padding: 0;
    vertical-align: top;
  }

  @media screen {
    .print-format {
      width: 4in;
      padding: 0.22in 0.2in;
      min-height: 8in;
    }
  }

  .print-format {
    font-family: "Helvetica Neue", Arial, "Segoe UI", "Noto Sans Arabic", sans-serif;
    font-size: 12px;
    color: #000;
    -webkit-font-smoothing: antialiased;
  }

  .num {
    font-variant-numeric: tabular-nums;
    font-feature-settings: "tnum";
    letter-spacing: -0.01em;
  }

  .brand-bar { height: 3px; background: #000; margin: 0 0 8px; }
  .pharma-logo { max-height: 0.7in; margin: 0 auto 4px; display: block; }
  .pharma-name {
    font-size: 19px;
    font-weight: 800;
    text-align: center;
    line-height: 1.1;
    letter-spacing: -0.01em;
    unicode-bidi: plaintext;
  }
  .pharma-meta {
    text-align: center;
    font-size: 10.5px;
    color: #333;
    margin-top: 4px;
    line-height: 1.45;
    unicode-bidi: plaintext;
  }

  .eyebrow {
    display: block;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: #555;
    line-height: 1;
  }

  .receipt-banner {
    text-align: center;
    margin: 10px 0 6px;
    padding: 7px 0;
    border-top: 1px solid #000;
    border-bottom: 1px solid #000;
  }
  .receipt-banner .eyebrow { margin-bottom: 3px; }
  .receipt-banner .num {
    font-size: 14px;
    font-weight: 800;
    letter-spacing: 0.02em;
  }

  .meta { width: 100%; font-size: 11px; margin-bottom: 6px; }
  .meta td { padding: 1.5px 0; }
  .meta td.label {
    color: #555;
    width: 30%;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }
  .meta td.value { font-weight: 600; }

  .rule { border: 0; border-top: 1px solid #000; margin: 6px 0; }
  .rule-dotted { border: 0; border-top: 1px dotted #999; margin: 6px 0; }

  .items { width: 100%; }
  .items thead th {
    border-bottom: 1px solid #000;
    padding: 4px 0;
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.16em;
    color: #555;
  }
  .items thead th.right { text-align: right; }

  .items tbody td {
    padding: 7px 0 6px;
    border-bottom: 1px dotted #d0d0d0;
    vertical-align: top;
  }
  .items tbody tr:last-child td { border-bottom: 0; }

  .items td.right {
    text-align: right;
    width: 32%;
    white-space: nowrap;
  }
  .items td.right .qty { font-size: 13px; font-weight: 700; line-height: 1.1; }
  .items td.right .qty small {
    font-size: 9px;
    font-weight: 600;
    color: #555;
    margin-left: 2px;
    letter-spacing: 0.04em;
  }
  .items td.right .amt { font-size: 12px; font-weight: 700; margin-top: 3px; line-height: 1.1; }

  .item-name {
    font-size: 12px;
    font-weight: 700;
    line-height: 1.25;
    unicode-bidi: plaintext;
  }
  .item-name--ar { font-weight: 500; color: #333; margin-top: 1px; }
  .item-line { font-size: 10px; color: #555; margin-top: 3px; line-height: 1.35; }
  .item-line b { font-weight: 700; color: #333; letter-spacing: 0.04em; }

  .count-strip {
    display: flex;
    justify-content: space-between;
    font-size: 10px;
    color: #555;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-weight: 700;
    margin: 8px 0 4px;
  }

  .totals { width: 100%; }
  .totals td { padding: 2.5px 0; font-size: 12px; }
  .totals td.l { text-align: right; padding-right: 8px; color: #444; }
  .totals td.v { text-align: right; width: 38%; white-space: nowrap; font-weight: 600; }
  .totals tr.grand td {
    border-top: 2px solid #000;
    border-bottom: 2px solid #000;
    padding: 7px 0;
    font-size: 15px;
    font-weight: 800;
  }
  .totals tr.grand td.l { letter-spacing: 0.08em; }
  .totals tr.paid td { padding-top: 6px; font-weight: 700; }
  .totals tr.change td { font-weight: 700; }
  .totals tr.outstanding td { font-weight: 800; }

  .status-wrap { text-align: center; margin: 12px 0 10px; }
  .status-pill {
    display: inline-block;
    padding: 5px 22px;
    background: #000;
    color: #fff;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.22em;
  }
  .status-pill--unpaid {
    background: transparent;
    color: #000;
    border: 2px solid #000;
  }

  .thanks {
    text-align: center;
    font-size: 11px;
    margin: 4px 0;
    line-height: 1.4;
    unicode-bidi: plaintext;
  }
  .thanks-primary { font-size: 13px; font-weight: 700; }
  .thanks-secondary {
    font-size: 9px;
    text-transform: uppercase;
    letter-spacing: 0.18em;
    color: #444;
  }
  .disclaimer {
    text-align: center;
    font-size: 9.5px;
    color: #555;
    margin-top: 4px;
    line-height: 1.4;
    unicode-bidi: plaintext;
  }
  .disclaimer-secondary {
    font-size: 8.5px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin-top: 2px;
  }

  .codes {
    text-align: center;
    margin-top: 10px;
    padding-top: 6px;
    border-top: 1px dotted #999;
  }
  .code-id {
    font-size: 10px;
    font-family: "Courier New", monospace;
    margin-top: 4px;
    letter-spacing: 0.04em;
  }
  .reprint {
    text-align: center;
    font-size: 8.5px;
    color: #777;
    margin-top: 8px;
    letter-spacing: 0.06em;
    font-style: italic;
  }
</style>

{# ─── Brand bar + header ────────────────────────────────────── #}
<div class="brand-bar"></div>

{% if company.company_logo %}
  <img src="{{ company.company_logo }}" class="pharma-logo" />
{% endif %}

<div class="pharma-name">{{ shop_name }}</div>

<div class="pharma-meta">
  {% if shop_address %}{{ shop_address }}<br>{% endif %}
  {% if shop_phone %}{{ shop_phone }}{% endif %}
  {% if company.tax_id %}<br><span class="eyebrow" style="display:inline; color:#555;">{{ _("Tax ID") }}</span> &nbsp;<span class="num">{{ company.tax_id }}</span>{% endif %}
</div>

{# ─── Receipt-no banner ────────────────────────────────────── #}
<div class="receipt-banner">
  <span class="eyebrow">{{ _("Receipt") }}</span>
  <div class="num">#&nbsp;{{ doc.name }}</div>
</div>

{# ─── Meta block ───────────────────────────────────────────── #}
<table class="meta">
  <tr>
    <td class="label">{{ _("Date") }}</td>
    <td class="value num">
      {{ doc.get_formatted("posting_date") }}
      &nbsp;·&nbsp;
      {{ doc.get_formatted("posting_time")[:5] }}
    </td>
  </tr>
  <tr>
    <td class="label">{{ cashier_label }}</td>
    <td class="value">{{ cashier_name }}</td>
  </tr>
  <tr>
    <td class="label">{{ _("Customer") }}</td>
    <td class="value">
      {{ doc.customer_name or doc.customer or _("Walk-in") }}
    </td>
  </tr>
  {% if doc.po_no %}
  <tr>
    <td class="label">{{ _("Ref") }}</td>
    <td class="value">{{ doc.po_no }}</td>
  </tr>
  {% endif %}
</table>

{# ─── Items ────────────────────────────────────────────────── #}
<table class="items">
  <thead>
    <tr>
      <th>{{ _("Item") }}</th>
      <th class="right">{{ _("Qty / Amount") }}</th>
    </tr>
  </thead>
  <tbody>
  {%- for item in doc.items -%}
    {%- set q = item.qty -%}
    {%- if q == q|int -%}
      {%- set qty_display = q|int -%}
    {%- else -%}
      {%- set qty_display = "%g"|format(q) -%}
    {%- endif -%}

    <tr>
      <td>
        <div class="item-name">
          {{ item.item_name or item.item_code }}
        </div>
        {% if item.custom_arabic_name %}
          <div class="item-name item-name--ar">{{ item.custom_arabic_name }}</div>
        {% endif %}

        {# Batch / expiry resolver: bundle → batches[] → batch_no #}
        {%- set bundle = item.serial_and_batch_bundle -%}
        {%- set sb_rows = [] -%}
        {%- if bundle -%}
          {%- set sb_rows = frappe.get_all(
                "Serial and Batch Entry",
                filters={"parent": bundle},
                fields=["batch_no","serial_no","qty"]) -%}
        {%- endif -%}

        {%- if sb_rows and sb_rows|length > 0 -%}
          <div class="item-line">
            {%- for b in sb_rows if b.batch_no -%}
              {%- set exp = frappe.db.get_value("Batch", b.batch_no, "expiry_date") -%}
              {%- set bq = b.qty -%}
              {%- if bq == bq|int %}{% set bqd = bq|int %}{% else %}{% set bqd = "%g"|format(bq) %}{% endif -%}
              <b>{{ _("Batch") }}</b> {{ b.batch_no }}{% if exp %} &nbsp;<span class="num">EXP {{ frappe.utils.formatdate(exp, "MM/yyyy") }}</span>{% endif %}
              {%- if b.qty %} &nbsp;<span class="num">× {{ bqd }}</span>{% endif -%}
              {%- if not loop.last %}<br>{% endif -%}
            {%- endfor -%}
          </div>
        {%- elif item.get("batches") and item.batches|length > 0 -%}
          <div class="item-line">
            {%- for b in item.batches if b.batch_no -%}
              {%- set exp = frappe.db.get_value("Batch", b.batch_no, "expiry_date") -%}
              {%- set bq = b.qty -%}
              {%- if bq == bq|int %}{% set bqd = bq|int %}{% else %}{% set bqd = "%g"|format(bq) %}{% endif -%}
              <b>{{ _("Batch") }}</b> {{ b.batch_no }}{% if exp %} &nbsp;<span class="num">EXP {{ frappe.utils.formatdate(exp, "MM/yyyy") }}</span>{% endif %}
              {%- if b.qty %} &nbsp;<span class="num">× {{ bqd }}</span>{% endif -%}
              {%- if not loop.last %}<br>{% endif -%}
            {%- endfor -%}
          </div>
        {%- elif item.batch_no -%}
          {%- set exp = frappe.db.get_value("Batch", item.batch_no, "expiry_date") -%}
          <div class="item-line">
            <b>{{ _("Batch") }}</b> {{ item.batch_no }}{% if exp %} &nbsp;<span class="num">EXP {{ frappe.utils.formatdate(exp, "MM/yyyy") }}</span>{% endif %}
            &nbsp;<span class="num">× {{ qty_display }}</span>
          </div>
        {%- endif -%}

        {%- if item.serial_no -%}
          <div class="item-line">
            <b>{{ _("SR.No") }}</b> {{ item.serial_no | replace("\n", ", ") }}
          </div>
        {%- endif -%}

        {%- if item.discount_percentage and item.discount_percentage > 0 -%}
          <div class="item-line">
            <b>{{ _("Disc") }}</b> <span class="num">{{ "%g"|format(item.discount_percentage) }}%</span>
            ({{ item.get_formatted("discount_amount") }})
          </div>
        {%- endif -%}
      </td>
      <td class="right">
        <div class="qty num">
          {{ qty_display }}{% if item.uom and item.uom != item.stock_uom %} <small>{{ item.uom }}</small>{% endif %}
        </div>
        <div class="amt num">{{ item.get_formatted("net_amount") }}</div>
      </td>
    </tr>
  {%- endfor -%}
  </tbody>
</table>

{# ─── Quick-scan count strip ───────────────────────────────── #}
{%- if line_count -%}
  {%- if total_qty == total_qty|int %}{% set total_qty_disp = total_qty|int %}{% else %}{% set total_qty_disp = "%g"|format(total_qty) %}{% endif -%}
  <div class="count-strip">
    <span>{{ line_count }} {{ _("Lines") }}</span>
    <span>{{ total_qty_disp }} {{ _("Units") }}</span>
  </div>
{%- endif -%}

{# ─── Totals ──────────────────────────────────────────────── #}
<table class="totals">
  <tr>
    <td class="l">{{ _("Subtotal") }}</td>
    <td class="v num">{{ doc.get_formatted("total") }}</td>
  </tr>

  {%- for row in doc.taxes -%}
    <tr>
      <td class="l">
        {%- if "%" in (row.description or "") -%}
          {{ row.description }}
        {%- else -%}
          {{ row.description }} @ <span class="num">{{ "%g"|format(row.rate) }}%</span>
        {%- endif -%}
      </td>
      <td class="v num">{{ row.get_formatted("tax_amount", doc) }}</td>
    </tr>
  {%- endfor -%}

  {%- if doc.discount_amount and doc.discount_amount > 0 -%}
    <tr>
      <td class="l">{{ _("Discount") }}</td>
      <td class="v num">− {{ doc.get_formatted("discount_amount") }}</td>
    </tr>
  {%- endif -%}

  <tr class="grand">
    <td class="l">{{ _("GRAND TOTAL") }}</td>
    <td class="v num">{{ doc.get_formatted("grand_total") }}</td>
  </tr>

  {%- if doc.payments -%}
    {%- for row in doc.payments -%}
      {%- if row.amount and row.amount != 0 -%}
        <tr class="paid">
          <td class="l">{{ row.mode_of_payment }}</td>
          <td class="v num">{{ row.get_formatted("amount", doc) }}</td>
        </tr>
      {%- endif -%}
    {%- endfor -%}
  {%- elif doc.paid_amount -%}
    <tr class="paid">
      <td class="l">{{ _("Paid") }}</td>
      <td class="v num">{{ doc.get_formatted("paid_amount") }}</td>
    </tr>
  {%- endif -%}

  {%- if change_due and change_due > 0 -%}
    <tr class="change">
      <td class="l">{{ _("Change") }}</td>
      <td class="v num">{{ doc.get_formatted("change_amount") }}</td>
    </tr>
  {%- endif -%}

  {%- if outstanding and outstanding > 0 -%}
    <tr class="outstanding">
      <td class="l">{{ _("Outstanding") }}</td>
      <td class="v num">{{ doc.get_formatted("outstanding_amount") }}</td>
    </tr>
  {%- endif -%}
</table>

{# ─── Status pill ─────────────────────────────────────────── #}
<div class="status-wrap">
  <span class="status-pill {% if status_label == 'UNPAID' %}status-pill--unpaid{% endif %}">
    {{ _(status_label) }}
  </span>
</div>

{# ─── Optional terms ──────────────────────────────────────── #}
{% if doc.terms %}
  <hr class="rule-dotted">
  <div class="thanks">{{ doc.terms }}</div>
{% endif %}

{# ─── Receipt footer + disclaimer (operator-editable) ─────── #}
{%- if footer_primary or footer_secondary -%}
  <hr class="rule-dotted">
  {% if footer_primary %}<div class="thanks thanks-primary">{{ footer_primary }}</div>{% endif %}
  {% if footer_secondary %}<div class="thanks thanks-secondary">{{ footer_secondary }}</div>{% endif %}
{%- endif -%}

{%- if disclaimer_primary or disclaimer_secondary -%}
  <div class="disclaimer">
    {% if disclaimer_primary %}{{ disclaimer_primary }}{% endif %}
    {% if disclaimer_secondary %}<div class="disclaimer-secondary">{{ disclaimer_secondary }}</div>{% endif %}
  </div>
{%- endif -%}

{# ─── Codes ───────────────────────────────────────────────── #}
<div class="codes">
  <table style="width:100%;">
    <tr>
      <td style="text-align: center; vertical-align: middle;">
        <barcode code="{{ doc.name }}" type="Code128" height="0.7in" width="2in" />
      </td>
      <td style="width: 1in; text-align: center; vertical-align: middle;">
        <barcode code="{{ doc.name }}" type="QR" height="0.95in" width="0.95in" />
      </td>
    </tr>
  </table>
  <div class="code-id num">{{ doc.name }}</div>
</div>

<div class="reprint">
  {{ _("PRINTED") }} ·
  <span class="num">{{ frappe.utils.format_datetime(frappe.utils.now(), "dd MMM yyyy HH:mm") }}</span>
</div>
"""


def execute():
    """
    Idempotently install / refresh the 'Mizan Receipt Print' Print
    Format. Re-running on a site that already has it just updates
    the html / metadata — no duplicate format is created.
    """
    if not frappe.db.exists("DocType", "Print Format"):
        return

    html = _build_html()

    if frappe.db.exists("Print Format", PRINT_FORMAT_NAME):
        doc = frappe.get_doc("Print Format", PRINT_FORMAT_NAME)
    else:
        doc = frappe.new_doc("Print Format")
        doc.name = PRINT_FORMAT_NAME

    doc.doc_type = PRINT_FORMAT_DOCTYPE
    doc.module = "Mizan"
    doc.print_format_type = "Jinja"
    doc.standard = "Yes"
    doc.disabled = 0
    doc.custom_format = 1
    doc.font = "Default"
    doc.font_size = 14
    doc.margin_top = 0
    doc.margin_bottom = 0
    doc.margin_left = 0
    doc.margin_right = 0
    doc.page_number = "Hide"
    doc.html = html

    doc.flags.ignore_permissions = True
    doc.save()
