# -*- coding: utf-8 -*-
# Copyright (c) 2020, Youssef Restom and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import json
import frappe
from frappe.utils import cint, nowdate
from frappe import _
from .utilities import get_version


@frappe.whitelist()
def get_opening_dialog_data():
    data = {}

    # Get only POS Profiles where current user is defined in POS Profile User table
    pos_profiles_data = frappe.db.sql(
        """
        SELECT DISTINCT p.name, p.company, p.currency 
        FROM `tabPOS Profile` p
        INNER JOIN `tabPOS Profile User` u ON u.parent = p.name
        WHERE p.disabled = 0 AND u.user = %s
        ORDER BY p.name
    """,
        frappe.session.user,
        as_dict=1,
    )

    data["pos_profiles_data"] = pos_profiles_data

    # Derive companies from accessible POS Profiles
    company_names = []
    for profile in pos_profiles_data:
        if profile.company and profile.company not in company_names:
            company_names.append(profile.company)
    data["companies"] = [{"name": c} for c in company_names]

    pos_profiles_list = []
    for i in data["pos_profiles_data"]:
        pos_profiles_list.append(i.name)

    payment_method_table = "POS Payment Method" if get_version() == 13 else "Sales Invoice Payment"
    data["payments_method"] = frappe.get_list(
        payment_method_table,
        filters={"parent": ["in", pos_profiles_list]},
        fields=["*"],
        limit_page_length=0,
        order_by="parent",
        ignore_permissions=True,
    )
    # set currency from pos profile
    for mode in data["payments_method"]:
        mode["currency"] = frappe.get_cached_value("POS Profile", mode["parent"], "currency")

    return data


@frappe.whitelist()
def create_opening_voucher(pos_profile, company, balance_details):
    balance_details = json.loads(balance_details)

    # Resolve the foreign / company currency split for each opening row.
    #
    # Before this fix the child rows only stored `amount` and the field was
    # marked `options: "company:company_currency"`, so an opening balance
    # entered in a foreign currency (e.g. POS Profile in SAR while the
    # company is in KWD) was rendered as if it were in the company currency
    # — "500 SAR" was saved and shown as "KWD 500.000". The closing shift
    # then compared that foreign-amount-as-company against the per-payment
    # base totals (which are in actual company currency) and the variance
    # was meaningless.
    #
    # We now persist three things per row:
    #   - `currency`         : the row's own currency (POS Profile currency,
    #                          falling back to the payment-method default
    #                          and finally the company currency).
    #   - `conversion_rate`  : foreign-to-company (1.0 when the currencies
    #                          match, otherwise erpnext.get_exchange_rate
    #                          on today's posting date).
    #   - `base_amount`      : the opening amount expressed in company
    #                          currency, ready to be consumed by the
    #                          closing-shift reconciliation.
    company_currency = frappe.get_cached_value("Company", company, "default_currency") or ""
    profile_currency = (
        frappe.get_cached_value("POS Profile", pos_profile, "currency") or company_currency
    )
    today = frappe.utils.getdate()

    def _resolve_rate(source_currency: str) -> float:
        if not source_currency or source_currency == company_currency:
            return 1.0
        try:
            from erpnext.setup.utils import get_exchange_rate

            rate = get_exchange_rate(source_currency, company_currency, today)
        except Exception:
            rate = None
        try:
            rate = float(rate or 0)
        except (TypeError, ValueError):
            rate = 0.0
        # Fall back to 1.0 only when the user genuinely hasn't configured
        # an exchange rate — otherwise we'd silently inflate the company
        # equivalent. The opening-shift screen surfaces the rate in the
        # form so cashiers can spot the missing config.
        return rate or 1.0

    rate_cache: dict[str, float] = {}
    normalised_details = []
    for row in balance_details or []:
        currency = (row.get("currency") or profile_currency or company_currency or "").strip()
        amount = float(row.get("amount") or 0)
        if currency not in rate_cache:
            rate_cache[currency] = _resolve_rate(currency)
        conversion_rate = rate_cache[currency]
        base_amount = round(amount * conversion_rate, 6) if amount else 0.0
        normalised_details.append(
            {
                "mode_of_payment": row.get("mode_of_payment"),
                "currency": currency or company_currency,
                "amount": amount,
                "conversion_rate": conversion_rate,
                "base_amount": base_amount,
            }
        )

    new_pos_opening = frappe.get_doc(
        {
            "doctype": "POS Opening Shift",
            "period_start_date": frappe.utils.get_datetime(),
            "posting_date": today,
            "user": frappe.session.user,
            "pos_profile": pos_profile,
            "company": company,
            "docstatus": 1,
        }
    )
    new_pos_opening.set("balance_details", normalised_details)
    new_pos_opening.insert(ignore_permissions=True)

    data = {}
    data["pos_opening_shift"] = new_pos_opening.as_dict()
    update_opening_shift_data(data, new_pos_opening.pos_profile)
    return data


@frappe.whitelist()
def check_opening_shift(user):
    open_vouchers = frappe.db.get_all(
        "POS Opening Shift",
        filters={
            "user": user,
            "pos_closing_shift": ["is", "not set"],
            "docstatus": 1,
            "status": "Open",
        },
        fields=["name", "pos_profile"],
        order_by="period_start_date desc",
    )
    data = ""
    if len(open_vouchers) > 0:
        data = {}
        data["pos_opening_shift"] = frappe.get_doc("POS Opening Shift", open_vouchers[0]["name"])
        update_opening_shift_data(data, open_vouchers[0]["pos_profile"])
    return data


def update_opening_shift_data(data, pos_profile):
    data["pos_profile"] = frappe.get_doc("POS Profile", pos_profile)
    if data["pos_profile"].get("posa_language"):
        frappe.local.lang = data["pos_profile"].posa_language
    data["company"] = frappe.get_doc("Company", data["pos_profile"].company)
    allow_negative_stock = cint(frappe.db.get_single_value("Stock Settings", "allow_negative_stock") or 0)
    data["stock_settings"] = {}
    data["stock_settings"].update({"allow_negative_stock": bool(allow_negative_stock)})
