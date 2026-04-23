/**
 * Build printable HTML for the Closing Shift dialog and ship it to a new
 * window for the browser to print. Two layouts:
 *   - `printReceiptClosingShift` — 80mm thermal receipt printer
 *   - `printA4ClosingShift`     — full A4 page with every section
 *
 * Both pull from the same in-memory closing data so the user doesn't
 * have to hit the network again — the dialog has already loaded
 * everything it needs.
 */

declare const frappe: any;

import { getCashierLabel } from "../shared/useCashierLabel";

type AnyDict = Record<string, any>;

interface InsightCard {
	key?: string;
	label: string;
	value: string;
	caption?: string;
}

interface ReconciliationRow {
	mode_of_payment?: string;
	opening_amount?: number;
	closing_amount?: number;
	expected_amount?: number;
	difference?: number;
	variance_percent?: number;
}

interface CurrencyRow {
	currency?: string;
	total?: number;
	company_currency_total?: number;
	invoice_count?: number;
}

interface MultiCurrencyRow extends CurrencyRow {
	invoice_total?: number;
	overpayment_total?: number;
}

interface PaymentByModeRow extends CurrencyRow {
	mode_of_payment?: string;
}

export interface PrintClosingShiftPayload {
	shiftName: string;
	companyName: string;
	posProfileName: string;
	cashierName: string;
	periodStart: string;
	periodEnd: string;
	companyCurrency: string;
	companyCurrencySymbol: string;
	primaryInsights: InsightCard[];
	secondaryInsights: InsightCard[];
	multiCurrencyTotals: MultiCurrencyRow[];
	paymentsByMode: PaymentByModeRow[];
	reconciliation: ReconciliationRow[];
	creditInvoicesByCurrency: CurrencyRow[];
	returnsByCurrency: CurrencyRow[];
	cashMovementCompanyTotal: number;
	/**
	 * Whether the shift had already been submitted (closed) when the
	 * user triggered the print. Drives the status banner: an OPEN-shift
	 * print warns that the figures may still change, while a CLOSED-shift
	 * print confirms the document is final.
	 */
	shiftClosed?: boolean;
	formatCurrencyWithSymbol: (_value: number, _currency: string) => string;
	formatCurrency: (_value: number, _precision?: number) => string;
	formatFloat: (_value: number, _precision?: number) => string;
}

/**
 * Build the status banner that goes at the very top of every printed
 * closing-shift report. Two variants:
 *   - OPEN SHIFT  → orange tone, warns that totals may change
 *   - CLOSED SHIFT → green tone, confirms the document is final
 *
 * The mode parameter selects styling: `receipt` keeps the banner narrow
 * and monochrome (works on 80mm thermal paper); `a4` uses a coloured
 * pill so it reads strongly on a printed page.
 */
const buildStatusBanner = (
	shiftClosed: boolean,
	mode: "receipt" | "a4",
): string => {
	const status = shiftClosed
		? tt("CLOSED SHIFT — printed after closing")
		: tt("OPEN SHIFT — printed before closing (totals may still change)");
	const stamp = `${tt("Printed")}: ${new Date().toLocaleString()}`;

	if (mode === "receipt") {
		const border = shiftClosed ? "1px solid #111" : "1px dashed #555";
		return `<div class="status-banner" style="border:${border};padding:4px 6px;margin-bottom:6px;text-align:center;font-weight:700;text-transform:uppercase;font-size:10px;letter-spacing:0.04em;">
			${escapeHtml(status)}
			<div style="font-weight:400;text-transform:none;letter-spacing:0;font-size:9px;color:#444;margin-top:2px;">${escapeHtml(stamp)}</div>
		</div>`;
	}

	const palette = shiftClosed
		? { bg: "#dcfce7", border: "#16a34a", text: "#166534" }
		: { bg: "#fef3c7", border: "#d97706", text: "#92400e" };
	return `<div class="status-banner" style="background:${palette.bg};border:1.5px solid ${palette.border};color:${palette.text};border-radius:8px;padding:8px 14px;margin-bottom:14px;display:flex;justify-content:space-between;align-items:center;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;font-size:11px;">
		<span>${escapeHtml(status)}</span>
		<span style="font-weight:500;text-transform:none;letter-spacing:0;font-size:10px;color:${palette.text};">${escapeHtml(stamp)}</span>
	</div>`;
};

const escapeHtml = (value: unknown): string => {
	if (value === null || value === undefined) return "";
	return String(value)
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&#39;");
};

const tt = (text: string): string => {
	const translator =
		typeof window !== "undefined"
			? (window as any).__ || (window as any).frappe?._
			: undefined;
	try {
		return translator ? translator(text) : text;
	} catch {
		return text;
	}
};

const openPrintWindow = (html: string, title: string) => {
	if (typeof window === "undefined") return;

	const win = window.open("", "_blank", "width=900,height=1000");
	if (!win) {
		// Fallback toast — popup blocker probably tripped.
		try {
			frappe?.show_alert?.(
				{
					message: tt(
						"Allow pop-ups so the closing shift can be printed.",
					),
					indicator: "orange",
				},
				6,
			);
		} catch {
			console.warn("[POSA] Print window blocked");
		}
		return;
	}

	win.document.open();
	win.document.write(
		`<!DOCTYPE html><html><head><meta charset="utf-8"><title>${escapeHtml(
			title,
		)}</title></head><body>${html}</body></html>`,
	);
	win.document.close();

	// Give the new window a tick to lay things out before printing.
	const trigger = () => {
		try {
			win.focus();
			win.print();
		} catch (error) {
			console.error("[POSA] print failed", error);
		}
	};
	if (win.document.readyState === "complete") {
		setTimeout(trigger, 150);
	} else {
		win.addEventListener("load", () => setTimeout(trigger, 150));
	}
};

const formatRow = (
	label: string,
	value: string,
	options: { bold?: boolean; muted?: boolean } = {},
): string => {
	const labelClass = options.muted ? "muted" : "";
	const valueClass = `value${options.bold ? " bold" : ""}`;
	return `<div class="kv-row"><span class="${labelClass}">${escapeHtml(
		label,
	)}</span><span class="${valueClass}">${escapeHtml(value)}</span></div>`;
};

const buildReconciliationRows = (
	rows: ReconciliationRow[],
	formatCurrency: (_value: number, _precision?: number) => string,
): string => {
	if (!Array.isArray(rows) || !rows.length) return "";
	return rows
		.map((row) => {
			const variance =
				row.variance_percent !== undefined &&
				row.variance_percent !== null
					? `${formatCurrency(row.variance_percent || 0, 2)}%`
					: "—";
			return `<tr>
				<td>${escapeHtml(row.mode_of_payment || "")}</td>
				<td class="num">${escapeHtml(formatCurrency(row.opening_amount || 0))}</td>
				<td class="num">${escapeHtml(formatCurrency(row.closing_amount || 0))}</td>
				<td class="num">${escapeHtml(formatCurrency(row.expected_amount || 0))}</td>
				<td class="num">${escapeHtml(formatCurrency(row.difference || 0))}</td>
				<td class="num">${escapeHtml(variance)}</td>
			</tr>`;
		})
		.join("");
};

/* ─────────────────────────── 80mm Receipt ─────────────────────────── */

export function printReceiptClosingShift(payload: PrintClosingShiftPayload) {
	const {
		shiftName,
		posProfileName,
		cashierName,
		periodStart,
		periodEnd,
		companyCurrency,
		primaryInsights,
		secondaryInsights,
		paymentsByMode,
		reconciliation,
		formatCurrency,
		formatCurrencyWithSymbol,
		shiftClosed = false,
	} = payload;
	const statusBanner = buildStatusBanner(Boolean(shiftClosed), "receipt");

	const insightRows = [...primaryInsights, ...secondaryInsights]
		.map((card) => formatRow(card.label, card.value))
		.join("");

	const paymentRows = (paymentsByMode || [])
		.map((row) =>
			formatRow(
				`${row.mode_of_payment || "—"}${row.currency ? ` (${row.currency})` : ""}`,
				formatCurrencyWithSymbol(
					Number(row.total || 0),
					row.currency || companyCurrency,
				),
			),
		)
		.join("");

	const reconcileRows = (reconciliation || [])
		.map((row) => {
			const opening = formatCurrency(row.opening_amount || 0);
			const closing = formatCurrency(row.closing_amount || 0);
			const expected = formatCurrency(row.expected_amount || 0);
			const difference = formatCurrency(row.difference || 0);
			return `<div class="reconcile-block">
				<div class="reconcile-mode">${escapeHtml(row.mode_of_payment || "—")}</div>
				${formatRow(tt("Opening"), opening, { muted: true })}
				${formatRow(tt("Closing"), closing)}
				${formatRow(tt("Expected"), expected, { muted: true })}
				${formatRow(tt("Difference"), difference, { bold: true })}
			</div>`;
		})
		.join("");

	const html = `
		<style>
			@page { size: 80mm auto; margin: 0; }
			html, body { margin: 0; padding: 0; background: #fff; color: #111; }
			body {
				font-family: 'Courier New', 'Roboto Mono', monospace;
				font-size: 11px;
				line-height: 1.35;
				width: 76mm;
				padding: 6px 4px 12px;
			}
			.center { text-align: center; }
			.bold { font-weight: 700; }
			.muted { color: #555; }
			h1 {
				font-size: 14px;
				margin: 0 0 4px;
				text-transform: uppercase;
				letter-spacing: 0.04em;
			}
			h2 {
				font-size: 12px;
				margin: 10px 0 4px;
				text-transform: uppercase;
				border-bottom: 1px dashed #888;
				padding-bottom: 2px;
				letter-spacing: 0.04em;
			}
			.divider { border-top: 1px dashed #888; margin: 6px 0; }
			.kv-row {
				display: flex;
				justify-content: space-between;
				gap: 6px;
				padding: 1px 0;
			}
			.kv-row .value { text-align: right; }
			.kv-row .value.bold { font-weight: 700; }
			.reconcile-block {
				border: 1px dashed #aaa;
				padding: 4px 6px;
				margin-bottom: 6px;
			}
			.reconcile-mode {
				font-weight: 700;
				margin-bottom: 2px;
				text-transform: uppercase;
			}
			.footer {
				margin-top: 10px;
				font-size: 10px;
				text-align: center;
				color: #555;
			}
		</style>

		${statusBanner}

		<div class="center">
			<h1>${escapeHtml(tt("Shift Closing"))}</h1>
			<div class="bold">${escapeHtml(posProfileName)}</div>
		</div>

		<div class="divider"></div>

		${formatRow(tt("Shift"), shiftName)}
		${formatRow(getCashierLabel(), cashierName)}
		${formatRow(tt("Opened"), periodStart, { muted: true })}
		${formatRow(tt("Closed"), periodEnd)}

		<h2>${escapeHtml(tt("Summary"))}</h2>
		${insightRows || `<div class="muted">${escapeHtml(tt("No data"))}</div>`}

		${
			paymentRows
				? `<h2>${escapeHtml(tt("Payments by Mode"))}</h2>${paymentRows}`
				: ""
		}

		${
			reconcileRows
				? `<h2>${escapeHtml(tt("Payment Reconciliation"))}</h2>${reconcileRows}`
				: ""
		}

		<div class="footer">
			${escapeHtml(tt("Printed"))}: ${escapeHtml(new Date().toLocaleString())}
		</div>
	`;

	openPrintWindow(html, `Shift Closing — ${shiftName}`);
}

/* ─────────────────────────── A4 Detailed ──────────────────────────── */

export function printA4ClosingShift(payload: PrintClosingShiftPayload) {
	const {
		shiftName,
		posProfileName,
		cashierName,
		periodStart,
		periodEnd,
		companyCurrency,
		companyCurrencySymbol,
		primaryInsights,
		secondaryInsights,
		multiCurrencyTotals,
		paymentsByMode,
		reconciliation,
		creditInvoicesByCurrency,
		returnsByCurrency,
		cashMovementCompanyTotal,
		formatCurrency,
		formatCurrencyWithSymbol,
		shiftClosed = false,
	} = payload;
	const statusBanner = buildStatusBanner(Boolean(shiftClosed), "a4");

	const renderInsightCards = (cards: InsightCard[]) =>
		cards
			.map(
				(card) => `
			<div class="card">
				<div class="card__label">${escapeHtml(card.label)}</div>
				<div class="card__value">${escapeHtml(card.value)}</div>
				${
					card.caption
						? `<div class="card__caption">${escapeHtml(card.caption)}</div>`
						: ""
				}
			</div>
		`,
			)
			.join("");

	const renderCurrencyTable = (
		title: string,
		rows: MultiCurrencyRow[],
		options: { showInvoiceCount?: boolean } = {},
	) => {
		if (!Array.isArray(rows) || !rows.length) return "";
		const headerCount = options.showInvoiceCount
			? `<th class="num">${escapeHtml(tt("Invoices"))}</th>`
			: "";
		const body = rows
			.map((row) => {
				const isCompany = (row.currency || "") === companyCurrency;
				const total = formatCurrencyWithSymbol(
					Number(row.total || 0),
					row.currency || companyCurrency,
				);
				const companyTotal = formatCurrencyWithSymbol(
					Number(row.company_currency_total || 0),
					companyCurrency,
				);
				const invoiceCol = options.showInvoiceCount
					? `<td class="num">${escapeHtml(String(row.invoice_count || 0))}</td>`
					: "";
				return `<tr>
					<td>${escapeHtml(row.currency || "—")}</td>
					<td class="num">${escapeHtml(total)}</td>
					<td class="num">${escapeHtml(isCompany ? "—" : companyTotal)}</td>
					${invoiceCol}
				</tr>`;
			})
			.join("");
		return `
			<section class="block">
				<h3>${escapeHtml(title)}</h3>
				<table class="data-table">
					<thead>
						<tr>
							<th>${escapeHtml(tt("Currency"))}</th>
							<th class="num">${escapeHtml(tt("Total"))}</th>
							<th class="num">${escapeHtml(`${tt("In")} ${companyCurrency}`)}</th>
							${headerCount}
						</tr>
					</thead>
					<tbody>${body}</tbody>
				</table>
			</section>
		`;
	};

	const renderPaymentsTable = (rows: PaymentByModeRow[]) => {
		if (!Array.isArray(rows) || !rows.length) return "";
		const body = rows
			.map(
				(row) => `<tr>
					<td>${escapeHtml(row.mode_of_payment || "—")}</td>
					<td>${escapeHtml(row.currency || companyCurrency)}</td>
					<td class="num">${escapeHtml(
						formatCurrencyWithSymbol(
							Number(row.total || 0),
							row.currency || companyCurrency,
						),
					)}</td>
					<td class="num">${escapeHtml(
						formatCurrencyWithSymbol(
							Number(row.company_currency_total || 0),
							companyCurrency,
						),
					)}</td>
				</tr>`,
			)
			.join("");
		return `
			<section class="block">
				<h3>${escapeHtml(tt("Payments by Mode"))}</h3>
				<table class="data-table">
					<thead>
						<tr>
							<th>${escapeHtml(tt("Mode of Payment"))}</th>
							<th>${escapeHtml(tt("Currency"))}</th>
							<th class="num">${escapeHtml(tt("Total"))}</th>
							<th class="num">${escapeHtml(`${tt("In")} ${companyCurrency}`)}</th>
						</tr>
					</thead>
					<tbody>${body}</tbody>
				</table>
			</section>
		`;
	};

	const reconcileBody = buildReconciliationRows(reconciliation, formatCurrency);

	const html = `
		<style>
			@page { size: A4; margin: 12mm 14mm; }
			html, body { margin: 0; padding: 0; background: #fff; color: #1f2937; }
			body {
				font-family: 'Helvetica Neue', Arial, sans-serif;
				font-size: 12px;
				line-height: 1.45;
			}
			h1, h2, h3 { margin: 0; }
			h1 {
				font-size: 22px;
				font-weight: 800;
				letter-spacing: 0.02em;
				color: #111827;
			}
			h2 {
				font-size: 14px;
				color: #6b7280;
				font-weight: 600;
				text-transform: uppercase;
				letter-spacing: 0.04em;
				margin-bottom: 4px;
			}
			h3 {
				font-size: 13px;
				font-weight: 700;
				text-transform: uppercase;
				letter-spacing: 0.04em;
				margin: 0 0 8px;
				color: #374151;
				border-left: 4px solid #e23670;
				padding-left: 10px;
			}
			.header {
				display: flex;
				justify-content: space-between;
				align-items: flex-start;
				border-bottom: 2px solid #111827;
				padding-bottom: 12px;
				margin-bottom: 16px;
			}
			.header__meta {
				text-align: right;
				font-size: 11px;
				color: #4b5563;
				line-height: 1.5;
			}
			.header__meta strong { color: #111827; }
			.shift-meta {
				display: grid;
				grid-template-columns: repeat(2, 1fr);
				gap: 6px 24px;
				margin-bottom: 18px;
				padding: 10px 14px;
				background: #f9fafb;
				border-radius: 8px;
				border: 1px solid #e5e7eb;
				font-size: 12px;
			}
			.shift-meta .label {
				color: #6b7280;
				font-weight: 500;
				margin-right: 6px;
			}
			.shift-meta .value { font-weight: 600; color: #111827; }
			.block { margin-bottom: 18px; page-break-inside: avoid; }
			.cards-grid {
				display: grid;
				grid-template-columns: repeat(4, 1fr);
				gap: 8px;
			}
			.card {
				border: 1px solid #e5e7eb;
				border-radius: 8px;
				padding: 10px 12px;
				background: #f9fafb;
			}
			.card__label {
				font-size: 10px;
				text-transform: uppercase;
				color: #6b7280;
				letter-spacing: 0.03em;
				margin-bottom: 4px;
			}
			.card__value {
				font-size: 14px;
				font-weight: 700;
				color: #111827;
			}
			.card__caption {
				font-size: 10px;
				color: #6b7280;
				margin-top: 2px;
			}
			.data-table {
				width: 100%;
				border-collapse: collapse;
				font-size: 11px;
			}
			.data-table th, .data-table td {
				border: 1px solid #e5e7eb;
				padding: 6px 8px;
				text-align: left;
				vertical-align: top;
			}
			.data-table th {
				background: #f3f4f6;
				font-weight: 700;
				color: #374151;
				text-transform: uppercase;
				font-size: 10px;
				letter-spacing: 0.03em;
			}
			.data-table .num { text-align: right; font-variant-numeric: tabular-nums; }
			tfoot td {
				font-weight: 700;
				background: #f9fafb;
			}
			.footer {
				margin-top: 24px;
				padding-top: 10px;
				border-top: 1px solid #e5e7eb;
				font-size: 10px;
				color: #6b7280;
				display: flex;
				justify-content: space-between;
			}
		</style>

		${statusBanner}

		<div class="header">
			<div>
				<h2>${escapeHtml(tt("Shift Closing Report"))}</h2>
				<h1>${escapeHtml(posProfileName)}</h1>
			</div>
			<div class="header__meta">
				<div><strong>${escapeHtml(tt("Shift"))}:</strong> ${escapeHtml(shiftName)}</div>
				<div><strong>${escapeHtml(tt("Currency"))}:</strong> ${escapeHtml(
		`${companyCurrencySymbol} (${companyCurrency})`,
	)}</div>
				<div>${escapeHtml(tt("Generated"))}: ${escapeHtml(new Date().toLocaleString())}</div>
			</div>
		</div>

		<div class="shift-meta">
			<div><span class="label">${escapeHtml(getCashierLabel())}:</span><span class="value">${escapeHtml(cashierName)}</span></div>
			<div><span class="label">${escapeHtml(tt("Cash Movements"))}:</span><span class="value">${escapeHtml(
		formatCurrencyWithSymbol(cashMovementCompanyTotal || 0, companyCurrency),
	)}</span></div>
			<div><span class="label">${escapeHtml(tt("Period Start"))}:</span><span class="value">${escapeHtml(periodStart)}</span></div>
			<div><span class="label">${escapeHtml(tt("Period End"))}:</span><span class="value">${escapeHtml(periodEnd)}</span></div>
		</div>

		<section class="block">
			<h3>${escapeHtml(tt("Sales Overview"))}</h3>
			<div class="cards-grid">
				${renderInsightCards(primaryInsights)}
			</div>
		</section>

		<section class="block">
			<h3>${escapeHtml(tt("Cash & Returns"))}</h3>
			<div class="cards-grid">
				${renderInsightCards(secondaryInsights)}
			</div>
		</section>

		${renderCurrencyTable(tt("Multi-Currency Totals"), multiCurrencyTotals)}
		${renderPaymentsTable(paymentsByMode)}
		${renderCurrencyTable(tt("Credit Invoices Outstanding"), creditInvoicesByCurrency, { showInvoiceCount: true })}
		${renderCurrencyTable(tt("Returns by Currency"), returnsByCurrency, { showInvoiceCount: true })}

		${
			reconcileBody
				? `<section class="block">
				<h3>${escapeHtml(tt("Payment Reconciliation"))}</h3>
				<table class="data-table">
					<thead>
						<tr>
							<th>${escapeHtml(tt("Mode of Payment"))}</th>
							<th class="num">${escapeHtml(tt("Opening"))}</th>
							<th class="num">${escapeHtml(tt("Closing"))}</th>
							<th class="num">${escapeHtml(tt("Expected"))}</th>
							<th class="num">${escapeHtml(tt("Difference"))}</th>
							<th class="num">${escapeHtml(tt("Variance %"))}</th>
						</tr>
					</thead>
					<tbody>${reconcileBody}</tbody>
				</table>
			</section>`
				: ""
		}

		<div class="footer">
			<div>${escapeHtml(tt("Printed by"))}: ${escapeHtml(cashierName)}</div>
			<div>${escapeHtml(tt("Generated"))}: ${escapeHtml(new Date().toLocaleString())}</div>
		</div>
	`;

	openPrintWindow(html, `Shift Closing — ${shiftName}`);
}
