type CurrencyItem = {
	plc_conversion_rate?: number;
	original_rate?: number;
	original_currency?: string;
	rate?: number;
	currency?: string;
	base_rate?: number;
	base_price_list_rate?: number;
	price_list_rate?: number;
	[key: string]: unknown;
};

type CurrencyContext = {
	pos_profile: { currency: string };
	// Company's default_currency (e.g. "KWD"). MUST come from the Company
	// doc — NOT from `pos_profile.currency`. On profiles that intentionally
	// run in a foreign currency (SAR profile on a KWD-base company), those
	// two values diverge, and assuming `pos_profile.currency` is "the
	// company currency" caused base_rate to be stamped with the foreign
	// price-list amount, which the cart then divided by conversion_rate
	// again (449 SAR / 0.0823 = 5,455 SAR per row).
	company_currency?: string;
	price_list_currency?: string;
	selected_currency?: string;
	exchange_rate?: number;
	conversion_rate?: number;
	currency_precision?: number;
	flt?: (_value: unknown, _precision?: number) => number;
};

const _resolveCompanyCurrency = (context: CurrencyContext): string =>
	context.company_currency || context.pos_profile.currency;

export function useItemCurrency() {
	/**
	 * Calculates the rate from Price List Currency to Company Currency.
	 * @param {Object} item
	 * @param {Object} context - Needs: pos_profile, company_currency,
	 *                           price_list_currency, exchange_rate, conversion_rate
	 * @returns {number}
	 */
	const getPlcToCompanyRate = (
		item: CurrencyItem,
		context: CurrencyContext,
	): number => {
		const companyCurrency = _resolveCompanyCurrency(context);
		const priceListCurrency =
			context.price_list_currency || companyCurrency;
		// Benchmark note: favor item-level plc_conversion_rate to avoid recomputing PLC->CC.
		return (
			item.plc_conversion_rate ??
			(priceListCurrency === companyCurrency
				? 1
				: (context.exchange_rate || 1) * (context.conversion_rate || 1))
		);
	};

	/**
	 * Applies currency conversion to a single item.
	 * Updates item.rate, item.currency, item.base_rate, item.base_price_list_rate
	 * @param {Object} item
	 * @param {Object} context - Needs: pos_profile, company_currency,
	 *                           price_list_currency, selected_currency,
	 *                           exchange_rate, currency_precision, flt
	 */
	const applyCurrencyConversionToItem = (
		item: CurrencyItem | null | undefined,
		context: CurrencyContext,
	) => {
		if (!item) return;
		const companyCurrency = _resolveCompanyCurrency(context);

		if (!item.original_rate) {
			item.original_rate = item.rate;
			item.original_currency =
				item.currency || context.price_list_currency || companyCurrency;
		}

		// original_rate is in price list currency
		const price_list_rate = item.original_rate || 0;

		// Determine base rate using available conversion info (Price List -> Company)
		const plc_to_cc_rate = getPlcToCompanyRate(item, context);
		const base_rate = price_list_rate * plc_to_cc_rate;

		item.base_rate = base_rate;
		item.base_price_list_rate = base_rate;

		// Determine selected rate using exchange rate (Price List -> Selected)
		// item.original_currency is the Price List Currency
		const priceListCurrency = context.price_list_currency || companyCurrency;
		const selectedCurrency = context.selected_currency || companyCurrency;

		// Benchmark note: when PLC === SC, keep the displayed rate in PLC to avoid CC bleed-through.
		const converted_rate =
			selectedCurrency === priceListCurrency
				? price_list_rate
				: item.original_currency === selectedCurrency
					? price_list_rate
					: price_list_rate * (context.exchange_rate || 1);

		// context.flt is expected to be available or passed
		const flt = context.flt || ((v: unknown) => Number(v));

		item.rate = flt(converted_rate, context.currency_precision);
		item.currency = selectedCurrency;
		item.price_list_rate = item.rate;
	};

	/**
	 * Batch applies conversion to a list of items.
	 * @param {Array} items
	 * @param {Object} context
	 */
	const applyCurrencyConversionToItems = (
		items: CurrencyItem[],
		context: CurrencyContext,
	) => {
		if (!items || !items.length) return;
		items.forEach((it) => applyCurrencyConversionToItem(it, context));
	};

	return {
		getPlcToCompanyRate,
		applyCurrencyConversionToItem,
		applyCurrencyConversionToItems,
	};
}
