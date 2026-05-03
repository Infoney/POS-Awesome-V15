import { computed, unref } from "vue";

type SummaryFormatters = {
	formatCurrencyWithSymbol: (_value: number, _currency: string) => string;
	formatCount: (_value: number) => string;
	formatCurrency: (_value: number, _precision?: number) => string;
	currencySymbol: (_currency: string) => string;
	__: (_text: string, _args?: any[]) => string;
};

export function useClosingSummary(
	overview: any,
	posProfile: any,
	dialogData: any,
	formatters: SummaryFormatters,
) {
	const {
		formatCurrencyWithSymbol,
		formatCount,
		formatCurrency,
		currencySymbol,
		__,
	} = formatters;

	const overviewCompanyCurrency = computed(() => {
		const ov = unref(overview);
		const prof = unref(posProfile);
		const data = unref(dialogData);
		return ov?.company_currency || prof?.currency || data?.currency || "";
	});

	const companyCurrencySymbol = computed(() => {
		const currency = overviewCompanyCurrency.value;
		const symbol = currencySymbol(currency);
		return symbol || currency || "";
	});

	const multiCurrencyTotals = computed(() => {
		const ov = unref(overview);
		return Array.isArray(ov?.multi_currency_totals)
			? ov.multi_currency_totals
			: [];
	});

	const paymentsByMode = computed(() => {
		const ov = unref(overview);
		return Array.isArray(ov?.payments_by_mode) ? ov.payments_by_mode : [];
	});

	const creditInvoices = computed(() => {
		const ov = unref(overview);
		return (
			ov?.credit_invoices || {
				count: 0,
				company_currency_total: 0,
				by_currency: [],
			}
		);
	});

	const creditInvoicesByCurrency = computed(() => {
		return Array.isArray(creditInvoices.value.by_currency)
			? creditInvoices.value.by_currency
			: [];
	});

	const returnsSummary = computed(() => {
		const ov = unref(overview);
		return (
			ov?.returns || {
				count: 0,
				company_currency_total: 0,
				by_currency: [],
			}
		);
	});

	const returnsByCurrency = computed(() => {
		return Array.isArray(returnsSummary.value.by_currency)
			? returnsSummary.value.by_currency
			: [];
	});

	const changeReturnedSummary = computed(() => {
		const ov = unref(overview);
		return (
			ov?.change_returned || {
				company_currency_total: 0,
				by_currency: [],
				invoice_change: { company_currency_total: 0, by_currency: [] },
				overpayment_change: {
					company_currency_total: 0,
					by_currency: [],
				},
			}
		);
	});

	const invoiceChangeReturnedSummary = computed(() => {
		return (
			changeReturnedSummary.value?.invoice_change || {
				company_currency_total: 0,
				by_currency: [],
			}
		);
	});

	const changeReturnedByCurrency = computed(() => {
		return Array.isArray(changeReturnedSummary.value.by_currency)
			? changeReturnedSummary.value.by_currency
			: [];
	});

	const invoiceChangeReturnedByCurrency = computed(() => {
		return Array.isArray(invoiceChangeReturnedSummary.value.by_currency)
			? invoiceChangeReturnedSummary.value.by_currency
			: [];
	});

	const overpaymentChangeReturnedSummary = computed(() => {
		return (
			changeReturnedSummary.value?.overpayment_change || {
				company_currency_total: 0,
				by_currency: [],
			}
		);
	});

	const overpaymentChangeReturnedByCurrency = computed(() => {
		return Array.isArray(overpaymentChangeReturnedSummary.value.by_currency)
			? overpaymentChangeReturnedSummary.value.by_currency
			: [];
	});

	const overpaymentChangeByCurrencyMap = computed(() => {
		const map = new Map<
			string,
			{ total: number; company_currency_total: number }
		>();
		(overpaymentChangeReturnedByCurrency.value || []).forEach(
			(item: any) => {
				const currency =
					item.currency || overviewCompanyCurrency.value || "";
				map.set(currency, {
					total: item.total || 0,
					company_currency_total: item.company_currency_total || 0,
				});
			},
		);
		return map;
	});

	const changeReturnedRows = computed(() => {
		const buildCurrencyMap = (items: any[]) => {
			const map = new Map<string, any>();
			(items || []).forEach((item: any) => {
				const currency =
					item.currency || overviewCompanyCurrency.value || "";
				const existing = map.get(currency) || {
					currency,
					total: 0,
					company_currency_total: 0,
					exchange_rates: new Set<number>(),
				};

				existing.total += item.total || 0;
				existing.company_currency_total +=
					item.company_currency_total || 0;
				(item.exchange_rates || []).forEach((rate: number) =>
					existing.exchange_rates.add(rate),
				);
				map.set(currency, existing);
			});
			return map;
		};

		const invoiceMap = buildCurrencyMap(
			invoiceChangeReturnedByCurrency.value,
		);
		const overpaymentMap = buildCurrencyMap(
			overpaymentChangeReturnedByCurrency.value,
		);
		const totalMap = buildCurrencyMap(changeReturnedByCurrency.value);

		const currencies = new Set([
			...invoiceMap.keys(),
			...overpaymentMap.keys(),
			...totalMap.keys(),
		]);

		const rows = Array.from(currencies).map((currency) => {
			const invoiceEntry = invoiceMap.get(currency);
			const overpaymentEntry = overpaymentMap.get(currency);
			const totalEntry = totalMap.get(currency);

			const invoiceTotal = invoiceEntry?.total || 0;
			const invoiceCompanyTotal =
				invoiceEntry?.company_currency_total || 0;
			const invoiceExchangeRates = new Set(
				invoiceEntry?.exchange_rates || [],
			);

			const overpaymentTotal = overpaymentEntry?.total || 0;
			const overpaymentCompanyTotal =
				overpaymentEntry?.company_currency_total || 0;

			const exchangeRates = new Set([
				...invoiceExchangeRates,
				...(overpaymentEntry?.exchange_rates || []),
				...(totalEntry?.exchange_rates || []),
			]);

			const total = totalEntry
				? totalEntry.total || 0
				: invoiceTotal + overpaymentTotal;
			const companyTotal = totalEntry
				? totalEntry.company_currency_total || 0
				: invoiceCompanyTotal + overpaymentCompanyTotal;

			return {
				currency,
				invoice_total: invoiceTotal,
				invoice_company_currency_total: invoiceCompanyTotal,
				overpayment_total: overpaymentTotal,
				overpayment_company_currency_total: overpaymentCompanyTotal,
				total,
				company_currency_total: companyTotal,
				exchange_rates: Array.from(exchangeRates).sort((a, b) => a - b),
			};
		});

		return rows.sort((a: any, b: any) =>
			(a.currency || "").localeCompare(b.currency || ""),
		);
	});

	const cashExpectedSummary = computed(() => {
		const ov = unref(overview);
		return (
			ov?.cash_expected || {
				mode_of_payment: "",
				company_currency_total: 0,
				by_currency: [],
			}
		);
	});

	const cashMovementSummary = computed(() => {
		const ov = unref(overview);
		return (
			ov?.cash_movements || {
				count: 0,
				company_currency_total: 0,
				by_currency: [],
				by_type: [],
			}
		);
	});

	const cashExpectedByCurrency = computed(() => {
		return Array.isArray(cashExpectedSummary.value.by_currency)
			? cashExpectedSummary.value.by_currency
			: [];
	});

	const salesSummary = computed(() => {
		const ov = unref(overview);
		return (
			ov?.sales_summary || {
				gross_company_currency_total: 0,
				net_company_currency_total: 0,
				average_invoice_value: 0,
				sale_invoices_count: 0,
			}
		);
	});

	// When every shift invoice was billed in a single non-company currency
	// (e.g. SAR transactions on a KWD company), the "Net Sales / Gross Sales /
	// Avg Ticket" insight cards should lead with the invoice-currency figure
	// (`total` / `net_total`) and surface the company-currency equivalent
	// (`base_total` / `base_net_total`) in the caption — that's what the
	// cashier counted at the till. The backend's sales_summary aggregates only
	// company currency, so we derive the invoice-currency totals from
	// `multi_currency_totals`. If multiple invoice currencies are present we
	// can't pick one, so we keep the company-currency-only display.
	const dominantInvoiceCurrency = computed(() => {
		const rows = multiCurrencyTotals.value;
		if (!Array.isArray(rows) || rows.length !== 1) return null;
		const row = rows[0];
		const currency = row?.currency;
		if (!currency || currency === overviewCompanyCurrency.value) return null;
		return row;
	});

	const primaryInsights = computed(() => {
		const companyCurrency = overviewCompanyCurrency.value;
		const dominantRow: any = dominantInvoiceCurrency.value;
		const netCompany = salesSummary.value.net_company_currency_total || 0;
		const grossCompany = salesSummary.value.gross_company_currency_total || 0;
		const avgCompany = salesSummary.value.average_invoice_value || 0;
		const saleCount = salesSummary.value.sale_invoices_count || 0;

		const formatCompany = (value: number) =>
			formatCurrencyWithSymbol(value, companyCurrency);

		let netSalesValue = formatCompany(netCompany);
		let grossSalesValue = formatCompany(grossCompany);
		let avgInvoiceValue = formatCompany(avgCompany);

		// Card captions spell out the formula so the cashier / store
		// manager doesn't have to guess what "Net" and "Gross" mean
		// here:
		//   * Gross Sales = sum of every invoice's grand_total (what
		//     customers actually paid, including tax)
		//   * Net Sales   = Gross − Returns (refunds reduce net but NOT
		//     gross — gross is "money that came in", net is "money we
		//     keep before tax")
		// Tax is surfaced as its own card / table elsewhere; we
		// deliberately don't fold it into either "gross" or "net" so
		// the breakdown stays explicit.
		const netCaptionPrefix = __("Gross − returns");
		const grossCaptionPrefix = __("Sum of grand totals");
		const avgCaptionPrefix = __("Across");

		let netCaption = `${netCaptionPrefix}: ${formatCompany(netCompany)}`;
		let grossCaption = `${grossCaptionPrefix}`;
		let avgCaption = `${avgCaptionPrefix}: ${formatCount(saleCount)} ${__("sales")}`;

		if (dominantRow) {
			// When all shift invoices share one foreign currency, derive the
			// net/gross totals in that invoice currency from the per-currency
			// row (`total` is the invoice-currency rounded total). Returns
			// reduce net but not gross, so net_total ≈ company_currency_total *
			// (invoice_total / company_currency_total) — keep the ratio so the
			// card reflects what the cashier saw on the printed invoice.
			const invoiceTotal = Number(dominantRow.total) || 0;
			const invoiceCompanyTotal = Number(dominantRow.company_currency_total) || 0;
			const ratio =
				invoiceCompanyTotal && Number.isFinite(invoiceCompanyTotal)
					? invoiceTotal / invoiceCompanyTotal
					: 0;
			const dominantCurrency = dominantRow.currency;

			const grossInvoice = invoiceTotal;
			const netInvoice = ratio ? netCompany * ratio : grossInvoice;
			const avgInvoiceInvoiceCurrency = saleCount ? grossInvoice / saleCount : 0;

			netSalesValue = formatCurrencyWithSymbol(netInvoice, dominantCurrency);
			grossSalesValue = formatCurrencyWithSymbol(grossInvoice, dominantCurrency);
			avgInvoiceValue = formatCurrencyWithSymbol(
				avgInvoiceInvoiceCurrency,
				dominantCurrency,
			);

			netCaption = `${netCaptionPrefix} • ${formatCompany(netCompany)}`;
			grossCaption = `${grossCaptionPrefix} • ${formatCompany(grossCompany)}`;
			avgCaption = `${avgCaptionPrefix} ${formatCount(saleCount)} ${__("sales")} • ${formatCompany(avgCompany)}`;
		}

		return [
			{
				key: "total-invoices",
				label: __("Total Invoices"),
				value: formatCount(unref(overview)?.total_invoices || 0),
				caption: `${__("Sales processed")}: ${formatCount(saleCount)}`,
				icon: "mdi-receipt-text-multiple",
				color: "accent-primary",
			},
			{
				key: "net-sales",
				label: __("Net Sales"),
				value: netSalesValue,
				caption: netCaption,
				icon: "mdi-cash-multiple",
				color: "accent-success",
			},
			{
				key: "gross-sales",
				label: __("Gross Sales"),
				value: grossSalesValue,
				caption: grossCaption,
				icon: "mdi-chart-bar",
				color: "accent-secondary",
			},
			{
				key: "average-ticket",
				label: __("Average Ticket"),
				value: avgInvoiceValue,
				caption: avgCaption,
				icon: "mdi-chart-donut",
				color: "accent-info",
			},
		];
	});

	const secondaryInsights = computed(() => {
		const creditValue = formatCurrencyWithSymbol(
			creditInvoices.value.company_currency_total,
			overviewCompanyCurrency.value,
		);
		const returnsValue = formatCurrencyWithSymbol(
			returnsSummary.value.company_currency_total,
			overviewCompanyCurrency.value,
		);
		const changeValue = formatCurrencyWithSymbol(
			changeReturnedSummary.value.company_currency_total,
			overviewCompanyCurrency.value,
		);
		const cashMovementValue = formatCurrencyWithSymbol(
			cashMovementSummary.value.company_currency_total,
			overviewCompanyCurrency.value,
		);
		const cashValue = formatCurrencyWithSymbol(
			cashExpectedSummary.value.company_currency_total,
			overviewCompanyCurrency.value,
		);

		return [
			{
				key: "credit-sales",
				label: __("Credit Outstanding"),
				value: creditValue,
				caption: `${__("Open invoices")}: ${formatCount(creditInvoices.value.count || 0)}`,
				icon: "mdi-account-cash-outline",
				color: "accent-warning",
			},
			{
				key: "returns",
				label: __("Returns"),
				value: returnsValue,
				caption: `${__("Return count")}: ${formatCount(returnsSummary.value.count || 0)}`,
				icon: "mdi-undo-variant",
				color: "accent-secondary",
			},
			{
				key: "change-returned",
				label: __("Change Returned"),
				value: changeValue,
				caption: `${__("Cash back to customers")}`,
				icon: "mdi-cash-refund",
				color: "accent-info",
			},
			{
				key: "cash-movements",
				label: __("Cash Movements"),
				value: cashMovementValue,
				caption: `${__("Submitted entries")}: ${formatCount(cashMovementSummary.value.count || 0)}`,
				icon: "mdi-cash-sync",
				color: "accent-warning",
			},
			{
				key: "cash-expected",
				label: __("Expected Cash"),
				value: cashValue,
				caption:
					cashExpectedSummary.value.mode_of_payment && cashMovementSummary.value.company_currency_total
						? `${__("Mode")}: ${cashExpectedSummary.value.mode_of_payment} | ${__("Cash movement deduction applied")}`
						: cashExpectedSummary.value.mode_of_payment
							? `${__("Mode")}: ${cashExpectedSummary.value.mode_of_payment}`
							: __("No cash mode configured"),
				icon: "mdi-safe",
				color: "accent-success",
			},
		];
	});

	const shouldShowCompanyEquivalent = (row: any, currency: string) => {
		const resolvedCurrency = currency || row?.currency || "";
		if (!resolvedCurrency) {
			return false;
		}

		if (resolvedCurrency !== overviewCompanyCurrency.value) {
			return true;
		}

		const companyTotal = Number(row?.company_currency_total);
		if (!Number.isFinite(companyTotal)) {
			return false;
		}

		const amount = Number(row?.total);
		if (
			Number.isFinite(amount) &&
			Math.abs(amount - companyTotal) < 0.005
		) {
			return false;
		}

		return Math.abs(companyTotal) > 0.0001;
	};

	const showExchangeRates = (row: any, currency: string) => {
		const resolvedCurrency = currency || row?.currency || "";
		if (
			!resolvedCurrency ||
			resolvedCurrency === overviewCompanyCurrency.value
		) {
			return false;
		}
		return (
			Array.isArray(row?.exchange_rates) && row.exchange_rates.length > 0
		);
	};

	const formatExchangeRates = (
		rates: unknown[],
		sourceCurrency: string,
		targetCurrency: string,
	) => {
		if (!sourceCurrency || !targetCurrency) {
			return "";
		}

		const validRates = Array.isArray(rates)
			? rates
					.map((rate) => Number(rate))
					.filter((rate) => Number.isFinite(rate) && rate > 0)
			: [];

		if (!validRates.length) {
			return "";
		}

		const targetSymbol = currencySymbol(targetCurrency) || targetCurrency;
		const formattedRates = validRates.map((rate) => {
			const formattedRate = formatCurrency(rate, 4);
			return `1 ${sourceCurrency} = ${targetSymbol} ${formattedRate}`;
		});

		return `${__("Exchange Rate")}: ${formattedRates.join(" • ")}`;
	};

	const isCashMode = (modeOfPayment: string) => {
		const cashMode = cashExpectedSummary.value?.mode_of_payment || "";
		return Boolean(cashMode && modeOfPayment === cashMode);
	};

	const overpaymentDeductionForCurrency = (currency: string) => {
		const key = currency || overviewCompanyCurrency.value || "";
		const entry = overpaymentChangeByCurrencyMap.value.get(key);
		return entry?.total || 0;
	};

	// ── Taxes collected ────────────────────────────────────────────────
	// Surfaced as its own section in the dialog AND on the printed
	// closing report so the cashier / store manager / accountant can
	// see exactly how much of the day's revenue was tax owed to the
	// government (vs revenue we keep). Driven by overview.py's
	// `taxes_collected` payload (added in this commit). Populated on
	// the dialog via `salesSummary.tax_company_currency_total` (single
	// number for the headline card) plus per-account / per-currency
	// breakdowns for the detail tables.
	const taxesCollectedSummary = computed(() => {
		const ov: any = unref(overview);
		const node = ov?.taxes_collected || {};
		return {
			company_currency_total: Number(node.company_currency_total) || 0,
			by_account: Array.isArray(node.by_account) ? node.by_account : [],
			by_currency: Array.isArray(node.by_currency) ? node.by_currency : [],
		};
	});
	const taxesCollectedByAccount = computed(() => taxesCollectedSummary.value.by_account);
	const taxesCollectedByCurrency = computed(() => taxesCollectedSummary.value.by_currency);

	// ── Cashiers ───────────────────────────────────────────────────────
	// Per-cashier breakdown for the shift. Driven by `overview.cashiers`
	// (added on the server side in
	// `posawesome/mizan/doctype/pos_closing_shift/closing_processing/
	// overview.py::_resolve_cashier_breakdown_rows`). Each row carries
	// `{cashier, cashier_name, sales_person, invoice_count, grand_total,
	// net_total}`. The dialog's "Cashiers" section + the A4 print read
	// from this directly. Empty array on shifts that pre-date the
	// rollout — the section/table just doesn't render in that case.
	const cashiersBreakdown = computed(() => {
		const ov: any = unref(overview);
		return Array.isArray(ov?.cashiers) ? ov.cashiers : [];
	});

	return {
		overviewCompanyCurrency,
		companyCurrencySymbol,
		multiCurrencyTotals,
		paymentsByMode,
		creditInvoicesByCurrency,
		returnsByCurrency,
		changeReturnedRows,
		cashExpectedByCurrency,
		cashMovementSummary,
		primaryInsights,
		secondaryInsights,
		taxesCollectedSummary,
		taxesCollectedByAccount,
		taxesCollectedByCurrency,
		cashiersBreakdown,
		shouldShowCompanyEquivalent,
		showExchangeRates,
		formatExchangeRates,
		isCashMode,
		overpaymentDeductionForCurrency,
	};
}
