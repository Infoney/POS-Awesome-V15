// Copyright (c) 2020, Youssef Restom and contributors
// For license information, please see license.txt

frappe.ui.form.on("POS Closing Shift", {
	onload: function (frm) {
		frm.set_query("pos_profile", function (doc) {
			return {
				filters: { user: doc.user },
			};
		});

		frm.set_query("user", function (doc) {
			return {
				query: "posawesome.mizan.doctype.pos_closing_shift.pos_closing_shift.get_cashiers",
				filters: { parent: doc.pos_profile },
			};
		});

		frm.set_query("pos_opening_shift", function (doc) {
			return { filters: { status: "Open", docstatus: 1 } };
		});

		if (frm.doc.docstatus === 0) frm.set_value("period_end_date", frappe.datetime.now_datetime());
		if (frm.doc.docstatus === 1) set_html_data(frm);
	},

	refresh: function (frm) {
		// Mirror the POS dialog's "Print A4" action on the Desk form so an
		// admin / auditor opening a closing shift in ERPNext can print the
		// same A4 summary the cashier sees in the POS app — without having
		// to load the POS bundle. Slim port: status banner, header, shift
		// meta, sales-overview cards, multi-currency totals (computed from
		// the in-memory `pos_transactions` child table), and the
		// reconciliation table. Sections that need extra server queries
		// (cash-movement aggregates, payments-by-mode joins,
		// credit/returns by currency) are intentionally left out of this
		// Desk-side variant — the dialog inside the POS app is still the
		// canonical "every section" view.
		frm.add_custom_button(__("Print A4 (Mizan)"), () => mizan_print_a4_closing_shift(frm));
	},

	pos_opening_shift(frm) {
		if (frm.doc.pos_opening_shift && frm.doc.user) {
			reset_values(frm);
			frappe.run_serially([
				() => frm.trigger("set_opening_amounts"),
				() => frm.trigger("get_pos_invoices"),
				() => frm.trigger("get_pos_payments"),
			]);
		}
	},

	set_opening_amounts(frm) {
		return frappe.db
			.get_doc("POS Opening Shift", frm.doc.pos_opening_shift)
			.then(({ balance_details }) => {
				balance_details.forEach((detail) => {
					frm.add_child("payment_reconciliation", {
						mode_of_payment: detail.mode_of_payment,
						opening_amount: detail.amount || 0,
						expected_amount: detail.amount || 0,
					});
				});
			});
	},

	get_pos_invoices(frm) {
		frappe.call({
			method: "posawesome.mizan.doctype.pos_closing_shift.pos_closing_shift.get_pos_invoices",
			args: {
				pos_opening_shift: frm.doc.pos_opening_shift,
			},
			callback: async (r) => {
				const pos_docs = r.message;
				await set_form_data(pos_docs, frm);
				refresh_fields(frm);
				set_html_data(frm);
			},
		});
	},

	get_pos_payments(frm) {
		frappe.call({
			method: "posawesome.mizan.doctype.pos_closing_shift.pos_closing_shift.get_payments_entries",
			args: {
				pos_opening_shift: frm.doc.pos_opening_shift,
			},
			callback: (r) => {
				let pos_payments = r.message;
				set_form_payments_data(pos_payments, frm);
				refresh_fields(frm);
				set_html_data(frm);
			},
		});
	},
});

frappe.ui.form.on("POS Closing Shift Detail", {
	closing_amount: (frm, cdt, cdn) => {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "difference", flt(row.expected_amount - row.closing_amount));
	},
});

async function set_form_data(data, frm) {
	if (!Array.isArray(data)) {
		return;
	}

	for (const d of data) {
		add_to_pos_transaction(d, frm);
		const conversion_rate = get_conversion_rate(d);
		frm.doc.grand_total += get_base_value(d, "grand_total", "base_grand_total", conversion_rate);
		frm.doc.net_total += get_base_value(d, "net_total", "base_net_total", conversion_rate);
		frm.doc.total_quantity += flt(d.total_qty);
		await add_to_payments(d, frm, conversion_rate);
		add_to_taxes(d, frm, conversion_rate);
	}
}

function set_form_payments_data(data, frm) {
	data.forEach((d) => {
		add_to_pos_payments(d, frm);
		add_pos_payment_to_payments(d, frm);
	});
}

function add_to_pos_transaction(d, frm) {
	const conversion_rate = get_conversion_rate(d);
	const child = {
		posting_date: d.posting_date,
		grand_total: get_base_value(d, "grand_total", "base_grand_total", conversion_rate),
		transaction_currency: d.currency,
		transaction_amount: flt(d.grand_total),
		customer: d.customer,
	};
	if (d.doctype === "POS Invoice") {
		child.pos_invoice = d.name;
	} else {
		child.sales_invoice = d.name;
	}
	frm.add_child("pos_transactions", child);
}

function add_to_pos_payments(d, frm) {
	frm.add_child("pos_payments", {
		payment_entry: d.name,
		posting_date: d.posting_date,
		paid_amount: d.paid_amount,
		customer: d.party,
		mode_of_payment: d.mode_of_payment,
	});
}

async function add_to_payments(d, frm, conversion_rate) {
	const payments = Array.isArray(d.payments) ? d.payments : [];
	const cash_mode_of_payment = await get_cash_mode_of_payment(frm);

	payments.forEach((p) => {
		const payment = frm.doc.payment_reconciliation.find(
			(pay) => pay.mode_of_payment === p.mode_of_payment,
		);
		if (payment) {
			let amount = get_base_value(p, "amount", "base_amount", conversion_rate);

			if (payment.mode_of_payment === cash_mode_of_payment) {
				amount -= get_base_value(d, "change_amount", "base_change_amount", conversion_rate);
			}
			payment.expected_amount += flt(amount);
		} else {
			frm.add_child("payment_reconciliation", {
				mode_of_payment: p.mode_of_payment,
				opening_amount: 0,
				expected_amount: get_base_value(p, "amount", "base_amount", conversion_rate),
			});
		}
	});
}

function add_pos_payment_to_payments(p, frm) {
	const payment = frm.doc.payment_reconciliation.find((pay) => pay.mode_of_payment === p.mode_of_payment);
	if (payment) {
		let amount = Math.abs(get_base_value(p, "paid_amount", "base_paid_amount"));
		const multiplier = p.payment_type === "Pay" ? -1 : 1;
		payment.expected_amount += flt(multiplier * amount);
	} else {
		frm.add_child("payment_reconciliation", {
			mode_of_payment: p.mode_of_payment,
			opening_amount: 0,
			expected_amount:
				Math.abs(get_base_value(p, "paid_amount", "base_paid_amount")) *
				(p.payment_type === "Pay" ? -1 : 1),
		});
	}
}

function add_to_taxes(d, frm, conversion_rate) {
	d.taxes.forEach((t) => {
		const tax = frm.doc.taxes.find((tx) => tx.account_head === t.account_head && tx.rate === t.rate);
		if (tax) {
			tax.amount += flt(get_base_value(t, "tax_amount", "base_tax_amount", conversion_rate));
		} else {
			frm.add_child("taxes", {
				account_head: t.account_head,
				rate: t.rate,
				amount: get_base_value(t, "tax_amount", "base_tax_amount", conversion_rate),
			});
		}
	});
}

function reset_values(frm) {
	frm.set_value("pos_transactions", []);
	frm.set_value("payment_reconciliation", []);
	frm.set_value("pos_payments", []);
	frm.set_value("taxes", []);
	frm.set_value("grand_total", 0);
	frm.set_value("net_total", 0);
	frm.set_value("total_quantity", 0);
}

function refresh_fields(frm) {
	frm.refresh_field("pos_transactions");
	frm.refresh_field("payment_reconciliation");
	frm.refresh_field("pos_payments");
	frm.refresh_field("taxes");
	frm.refresh_field("grand_total");
	frm.refresh_field("net_total");
	frm.refresh_field("total_quantity");
}

function set_html_data(frm) {
	frappe.call({
		method: "get_payment_reconciliation_details",
		doc: frm.doc,
		callback: (r) => {
			frm.get_field("payment_reconciliation_details").$wrapper.html(r.message);
		},
	});
}

const get_value = async (doctype, name, field) => {
	if (!doctype || !name || !field) {
		return undefined;
	}

	try {
		const { message } = await frappe.db.get_value(doctype, name, field);
		return message ? message[field] : undefined;
	} catch (error) {
		console.error("Failed to fetch value:", error);
		return undefined;
	}
};

const get_cash_mode_of_payment = async (frm) => {
	const profile = frm.doc.pos_profile;

	if (!frm.__cashModeCache || frm.__cashModeCache.profile !== profile) {
		const value = await get_value("POS Profile", profile, "posa_cash_mode_of_payment");
		frm.__cashModeCache = {
			profile,
			value: value || "Cash",
		};
	}

	return frm.__cashModeCache.value;
};

const get_conversion_rate = (doc) =>
	doc.conversion_rate || doc.exchange_rate || doc.target_exchange_rate || doc.plc_conversion_rate || 1;

const get_base_value = (doc, field, base_field, conversion_rate) => {
	const base_fieldname = base_field || `base_${field}`;
	const base_value = doc[base_fieldname];
	if (base_value !== undefined && base_value !== null && base_value !== "") {
		return flt(base_value);
	}

	const value = doc[field];
	if (value === undefined || value === null || value === "") {
		return 0;
	}

	if (!conversion_rate) {
		conversion_rate =
			doc.conversion_rate ||
			doc.exchange_rate ||
			doc.target_exchange_rate ||
			doc.plc_conversion_rate ||
			1;
	}

	return flt(value) * flt(conversion_rate || 1);
};

// ─────────────────────────────────────────────────────────────────────────
// Mizan A4 print (slim port of frontend/src/posapp/composables/pos/closing/
// usePrintClosingShift.ts → printA4ClosingShift). Inlined here so the
// Frappe Desk form doesn't need to load the POS Vue bundle.
//
// Sections covered: status banner (open vs closed), header, shift meta,
// sales-overview cards, multi-currency totals, payment reconciliation.
// Sections deliberately NOT covered (require additional queries / joins):
// cash-and-returns secondary cards, payments-by-mode aggregates, credit
// invoices outstanding, returns by currency. The POS dialog remains the
// canonical "every section" view; this Desk variant is for quick
// admin / auditor printing without opening the POS app.
// ─────────────────────────────────────────────────────────────────────────

function mizan_print_a4_closing_shift(frm) {
	try {
		const doc = frm.doc || {};
		const html = mizan_build_closing_shift_a4_html(doc);
		const win = window.open("", "_blank", "width=900,height=1000");
		if (!win) {
			frappe.show_alert({
				message: __("Allow pop-ups so the closing shift can be printed."),
				indicator: "orange",
			});
			return;
		}
		win.document.open();
		win.document.write(
			`<!DOCTYPE html><html><head><meta charset="utf-8"><title>${mizan_escape_html(
				`Shift Closing — ${doc.name || ""}`,
			)}</title></head><body>${html}</body></html>`,
		);
		win.document.close();
		const trigger = () => {
			try {
				win.focus();
				win.print();
			} catch (err) {
				console.error("[Mizan] print failed", err);
			}
		};
		if (win.document.readyState === "complete") {
			setTimeout(trigger, 150);
		} else {
			win.addEventListener("load", () => setTimeout(trigger, 150));
		}
	} catch (err) {
		console.error("[Mizan] failed to build A4 print", err);
		frappe.msgprint({
			title: __("Print failed"),
			message: __("Could not build the A4 print: {0}", [err.message || err]),
			indicator: "red",
		});
	}
}

function mizan_escape_html(value) {
	if (value === null || value === undefined) return "";
	return String(value)
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&#39;");
}

function mizan_format_currency(value, currency, precision) {
	const num = flt(value || 0);
	if (typeof currency === "string" && currency.length) {
		try {
			return format_currency(num, currency, precision);
		} catch (err) {
			// fall through to plain numeric format
		}
	}
	return format_number(num, null, precision === undefined ? 3 : precision);
}

function mizan_aggregate_pos_transactions(doc) {
	// Build the multi-currency totals from the in-memory `pos_transactions`
	// child table. Each row carries `transaction_currency` (invoice currency)
	// and `transaction_amount` (invoice-currency rounded total) plus
	// `grand_total` (already converted to company currency by
	// `set_form_data` / `add_to_pos_transaction` in this same file).
	const rows = Array.isArray(doc.pos_transactions) ? doc.pos_transactions : [];
	const buckets = {};
	rows.forEach((row) => {
		const currency = (row.transaction_currency || "").trim() || "—";
		if (!buckets[currency]) {
			buckets[currency] = {
				currency,
				total: 0,
				company_currency_total: 0,
				invoice_count: 0,
			};
		}
		buckets[currency].total += flt(row.transaction_amount || 0);
		buckets[currency].company_currency_total += flt(row.grand_total || 0);
		buckets[currency].invoice_count += 1;
	});
	return Object.values(buckets).sort((a, b) =>
		a.currency.localeCompare(b.currency),
	);
}

function mizan_build_status_banner(shiftClosed) {
	const status = shiftClosed
		? __("CLOSED SHIFT — printed after closing")
		: __("OPEN SHIFT — printed before closing (totals may still change)");
	const stamp = `${__("Printed")}: ${new Date().toLocaleString()}`;
	const palette = shiftClosed
		? { bg: "#dcfce7", border: "#16a34a", text: "#166534" }
		: { bg: "#fef3c7", border: "#d97706", text: "#92400e" };
	return `<div style="background:${palette.bg};border:1.5px solid ${palette.border};color:${palette.text};border-radius:8px;padding:8px 14px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;font-size:11px;">
		<span>${mizan_escape_html(status)}</span>
		<span style="font-weight:500;text-transform:none;letter-spacing:0;font-size:10px;color:${palette.text};">${mizan_escape_html(stamp)}</span>
	</div>`;
}

function mizan_build_card(label, value, caption) {
	return `<div class="card">
		<div class="card__label">${mizan_escape_html(label)}</div>
		<div class="card__value">${mizan_escape_html(value)}</div>
		${caption ? `<div class="card__caption">${mizan_escape_html(caption)}</div>` : ""}
	</div>`;
}

function mizan_build_currency_table(title, rows, companyCurrency) {
	if (!rows.length) return "";
	const body = rows
		.map((row) => {
			const isCompany = (row.currency || "") === companyCurrency;
			const total = mizan_format_currency(row.total, row.currency || companyCurrency);
			const companyTotal = mizan_format_currency(
				row.company_currency_total,
				companyCurrency,
			);
			return `<tr>
				<td>${mizan_escape_html(row.currency || "—")}</td>
				<td class="num">${mizan_escape_html(total)}</td>
				<td class="num">${mizan_escape_html(isCompany ? "—" : companyTotal)}</td>
				<td class="num">${mizan_escape_html(String(row.invoice_count || 0))}</td>
			</tr>`;
		})
		.join("");
	return `
		<section class="block">
			<h3>${mizan_escape_html(title)}</h3>
			<table class="data-table">
				<thead>
					<tr>
						<th>${mizan_escape_html(__("Currency"))}</th>
						<th class="num">${mizan_escape_html(__("Total"))}</th>
						<th class="num">${mizan_escape_html(`${__("In")} ${companyCurrency}`)}</th>
						<th class="num">${mizan_escape_html(__("Invoices"))}</th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
		</section>
	`;
}

function mizan_build_reconciliation_table(rows) {
	if (!rows.length) return "";
	const body = rows
		.map((row) => {
			const expected = flt(row.expected_amount || 0);
			const closing = flt(row.closing_amount || 0);
			const difference = flt(row.difference || expected - closing);
			const variance = expected ? (difference / expected) * 100 : null;
			const varianceLabel =
				variance !== null && Number.isFinite(variance)
					? `${format_number(variance, null, 2)}%`
					: "—";
			return `<tr>
				<td>${mizan_escape_html(row.mode_of_payment || "")}</td>
				<td class="num">${mizan_escape_html(format_number(row.opening_amount || 0, null, 3))}</td>
				<td class="num">${mizan_escape_html(format_number(closing, null, 3))}</td>
				<td class="num">${mizan_escape_html(format_number(expected, null, 3))}</td>
				<td class="num">${mizan_escape_html(format_number(difference, null, 3))}</td>
				<td class="num">${mizan_escape_html(varianceLabel)}</td>
			</tr>`;
		})
		.join("");
	return `
		<section class="block">
			<h3>${mizan_escape_html(__("Payment Reconciliation"))}</h3>
			<table class="data-table">
				<thead>
					<tr>
						<th>${mizan_escape_html(__("Mode of Payment"))}</th>
						<th class="num">${mizan_escape_html(__("Opening"))}</th>
						<th class="num">${mizan_escape_html(__("Closing"))}</th>
						<th class="num">${mizan_escape_html(__("Expected"))}</th>
						<th class="num">${mizan_escape_html(__("Difference"))}</th>
						<th class="num">${mizan_escape_html(__("Variance %"))}</th>
					</tr>
				</thead>
				<tbody>${body}</tbody>
			</table>
		</section>
	`;
}

function mizan_build_closing_shift_a4_html(doc) {
	const shiftClosed = doc.docstatus === 1 || doc.docstatus === "1";
	const statusBanner = mizan_build_status_banner(shiftClosed);

	const companyCurrency =
		doc.company_currency ||
		(doc.company &&
			frappe.get_doc &&
			(frappe.get_doc("Company", doc.company) || {}).default_currency) ||
		frappe.defaults.get_default("currency") ||
		"";

	const cashierName = doc.user || (frappe.session && frappe.session.user) || "";
	const periodStart = doc.period_start_date || "";
	const periodEnd = doc.period_end_date || "";

	const grandTotal = flt(doc.grand_total || 0);
	const netTotal = flt(doc.net_total || 0);
	const totalQuantity = flt(doc.total_quantity || 0);
	const invoiceCount = Array.isArray(doc.pos_transactions) ? doc.pos_transactions.length : 0;
	const avgTicket = invoiceCount ? netTotal / invoiceCount : 0;

	const fmtCompany = (value) => mizan_format_currency(value, companyCurrency);

	const cards = [
		mizan_build_card(
			__("Total Invoices"),
			format_number(invoiceCount, null, 0),
			`${__("Sales processed")}: ${format_number(invoiceCount, null, 0)}`,
		),
		mizan_build_card(
			__("Net Sales"),
			fmtCompany(netTotal),
			`${__("After returns")}: ${fmtCompany(netTotal)}`,
		),
		mizan_build_card(
			__("Gross Sales"),
			fmtCompany(grandTotal),
			`${__("Before returns")}: ${fmtCompany(grandTotal)}`,
		),
		mizan_build_card(
			__("Average Ticket"),
			fmtCompany(avgTicket),
			`${__("Across")} ${format_number(invoiceCount, null, 0)} ${__("sales")}`,
		),
	].join("");

	const multiCurrencyRows = mizan_aggregate_pos_transactions(doc);
	const multiCurrencyTable =
		multiCurrencyRows.length > 1
			? mizan_build_currency_table(__("Multi-Currency Totals"), multiCurrencyRows, companyCurrency)
			: "";

	const reconciliationRows = Array.isArray(doc.payment_reconciliation)
		? doc.payment_reconciliation
		: [];
	const reconciliationTable = mizan_build_reconciliation_table(reconciliationRows);

	const totalQtyDisplay = format_number(totalQuantity, null, 0);

	return `
		<style>
			@page { size: A4; margin: 12mm 14mm; }
			html, body { margin: 0; padding: 0; background: #fff; color: #1f2937; }
			body { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 12px; line-height: 1.45; }
			h1, h2, h3 { margin: 0; }
			h1 { font-size: 22px; font-weight: 800; letter-spacing: 0.02em; color: #111827; }
			h2 { font-size: 14px; color: #6b7280; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 4px; }
			h3 { font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; margin: 0 0 8px; color: #374151; border-left: 4px solid #e23670; padding-left: 10px; }
			.header { display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px solid #111827; padding-bottom: 12px; margin-bottom: 16px; }
			.header__meta { text-align: right; font-size: 11px; color: #4b5563; line-height: 1.5; }
			.header__meta strong { color: #111827; }
			.shift-meta { display: grid; grid-template-columns: repeat(2, 1fr); gap: 6px 24px; margin-bottom: 18px; padding: 10px 14px; background: #f9fafb; border-radius: 8px; border: 1px solid #e5e7eb; font-size: 12px; }
			.shift-meta .label { color: #6b7280; font-weight: 500; margin-right: 6px; }
			.shift-meta .value { font-weight: 600; color: #111827; }
			.block { margin-bottom: 18px; page-break-inside: avoid; }
			.cards-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
			.card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 10px 12px; background: #f9fafb; }
			.card__label { font-size: 10px; text-transform: uppercase; color: #6b7280; letter-spacing: 0.03em; margin-bottom: 4px; }
			.card__value { font-size: 14px; font-weight: 700; color: #111827; }
			.card__caption { font-size: 10px; color: #6b7280; margin-top: 2px; }
			.data-table { width: 100%; border-collapse: collapse; font-size: 11px; }
			.data-table th, .data-table td { border: 1px solid #e5e7eb; padding: 6px 8px; text-align: left; vertical-align: top; }
			.data-table th { background: #f3f4f6; font-weight: 700; color: #374151; text-transform: uppercase; font-size: 10px; letter-spacing: 0.03em; }
			.data-table .num { text-align: right; font-variant-numeric: tabular-nums; }
			.footer { margin-top: 24px; padding-top: 10px; border-top: 1px solid #e5e7eb; font-size: 10px; color: #6b7280; display: flex; justify-content: space-between; }
		</style>

		${statusBanner}

		<div class="header">
			<div>
				<h2>${mizan_escape_html(__("Shift Closing Report"))}</h2>
				<h1>${mizan_escape_html(doc.pos_profile || "")}</h1>
			</div>
			<div class="header__meta">
				<div><strong>${mizan_escape_html(__("Shift"))}:</strong> ${mizan_escape_html(doc.name || "")}</div>
				<div><strong>${mizan_escape_html(__("Currency"))}:</strong> ${mizan_escape_html(companyCurrency)}</div>
				<div>${mizan_escape_html(__("Generated"))}: ${mizan_escape_html(new Date().toLocaleString())}</div>
			</div>
		</div>

		<div class="shift-meta">
			<div><span class="label">${mizan_escape_html(__("Cashier"))}:</span><span class="value">${mizan_escape_html(cashierName)}</span></div>
			<div><span class="label">${mizan_escape_html(__("Total Quantity"))}:</span><span class="value">${mizan_escape_html(totalQtyDisplay)}</span></div>
			<div><span class="label">${mizan_escape_html(__("Period Start"))}:</span><span class="value">${mizan_escape_html(periodStart)}</span></div>
			<div><span class="label">${mizan_escape_html(__("Period End"))}:</span><span class="value">${mizan_escape_html(periodEnd)}</span></div>
		</div>

		<section class="block">
			<h3>${mizan_escape_html(__("Sales Overview"))}</h3>
			<div class="cards-grid">${cards}</div>
		</section>

		${multiCurrencyTable}
		${reconciliationTable}

		<div class="footer">
			<div>${mizan_escape_html(__("Printed by"))}: ${mizan_escape_html(cashierName)}</div>
			<div>${mizan_escape_html(__("Generated"))}: ${mizan_escape_html(new Date().toLocaleString())}</div>
		</div>
	`;
}
