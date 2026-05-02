<template>
	<div class="overview-section">
		<div class="table-header mb-4">
			<h4 class="text-h6 text-grey-darken-2 mb-1">
				{{ __("Shift Overview") }}
			</h4>
			<p class="text-body-2 text-grey">
				{{ __("Review shift totals before submitting the closing entry") }}
			</p>
		</div>

		<div class="overview-wrapper" v-if="loading">
			<v-progress-circular color="primary" indeterminate size="32"></v-progress-circular>
		</div>

		<div v-else class="overview-wrapper">
			<div class="insight-grid">
				<v-row dense>
					<v-col
						v-for="card in primaryInsights"
						:key="card.key"
						cols="12"
						sm="6"
						md="3"
						class="d-flex"
					>
						<div class="insight-card">
							<div class="insight-icon" :class="card.color">
								<v-icon size="22">{{ card.icon }}</v-icon>
							</div>
							<div class="insight-body">
								<div class="insight-label">{{ card.label }}</div>
								<div class="insight-value">{{ card.value }}</div>
								<div class="insight-caption">{{ card.caption }}</div>
							</div>
						</div>
					</v-col>
				</v-row>
				<v-row dense class="mt-2" v-if="secondaryInsights.length">
					<v-col
						v-for="card in secondaryInsights"
						:key="card.key"
						cols="12"
						sm="6"
						md="3"
						class="d-flex"
					>
						<div class="insight-card compact">
							<div class="insight-icon" :class="card.color">
								<v-icon size="20">{{ card.icon }}</v-icon>
							</div>
							<div class="insight-body">
								<div class="insight-label">{{ card.label }}</div>
								<div class="insight-value">{{ card.value }}</div>
								<div class="insight-caption">{{ card.caption }}</div>
							</div>
						</div>
					</v-col>
				</v-row>
			</div>

			<div v-if="multiCurrencyTotals.length" class="table-section mt-6">
				<div class="table-header mb-2">
					<h5 class="text-subtitle-1 text-grey-darken-2 mb-1">
						{{ __("Totals by Invoice Currency") }}
					</h5>
					<p class="text-body-2 text-grey">
						{{ __("Shows the distribution of invoices per currency") }}
					</p>
				</div>

				<div class="overview-table-wrapper">
					<table class="overview-table">
						<thead>
							<tr>
								<th>{{ __("Currency") }}</th>
								<th class="text-end">
									{{ __("Total") }}
								</th>
								<th class="text-end">
									{{ __("Invoices") }}
								</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="row in multiCurrencyTotals" :key="row.currency">
								<td>{{ row.currency }}</td>
								<td class="text-end">
									<div class="amount-with-base">
										<div class="amount-primary">
											<span class="overview-amount">
												{{
													formatCurrencyWithSymbol(
														row.total || 0,
														row.currency || overviewCompanyCurrency,
													)
												}}
											</span>
											<span
												v-if="shouldShowCompanyEquivalent(row, row.currency)"
												class="company-equivalent"
											>
												({{
													formatCurrencyWithSymbol(
														row.company_currency_total || 0,
														overviewCompanyCurrency,
													)
												}})
											</span>
										</div>
										<div
											v-if="showExchangeRates(row, row.currency)"
											class="exchange-note"
										>
											{{
												formatExchangeRates(
													row.exchange_rates,
													row.currency || overviewCompanyCurrency,
													overviewCompanyCurrency,
												)
											}}
										</div>
									</div>
								</td>
								<td class="text-end">{{ row.invoice_count || 0 }}</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>

			<v-row
				v-if="creditInvoicesByCurrency.length || returnsByCurrency.length"
				dense
				class="mt-4"
			>
				<v-col v-if="creditInvoicesByCurrency.length" cols="12" md="6">
					<div class="table-section">
						<div class="table-header mb-2">
							<h5 class="text-subtitle-1 text-grey-darken-2 mb-1">
								{{ __("Outstanding Credit by Currency") }}
							</h5>
							<p class="text-body-2 text-grey">
								{{ __("Credit sales remaining to be collected") }}
							</p>
						</div>
						<div class="overview-table-wrapper">
							<table class="overview-table">
								<thead>
									<tr>
										<th>{{ __("Currency") }}</th>
										<th class="text-end">
											{{ __("Outstanding") }}
										</th>
										<th class="text-end">
											{{ __("Invoices") }}
										</th>
									</tr>
								</thead>
								<tbody>
									<tr
										v-for="row in creditInvoicesByCurrency"
										:key="`credit-${row.currency}`"
									>
										<td>{{ row.currency }}</td>
										<td class="text-end">
											<div class="amount-with-base">
												<div class="amount-primary">
													<span class="overview-amount">
														{{
															formatCurrencyWithSymbol(
																row.total || 0,
																row.currency || overviewCompanyCurrency,
															)
														}}
													</span>
													<span
														v-if="shouldShowCompanyEquivalent(row, row.currency)"
														class="company-equivalent"
													>
														({{
															formatCurrencyWithSymbol(
																row.company_currency_total || 0,
																overviewCompanyCurrency,
															)
														}})
													</span>
												</div>
												<div
													v-if="showExchangeRates(row, row.currency)"
													class="exchange-note"
												>
													{{
														formatExchangeRates(
															row.exchange_rates,
															row.currency || overviewCompanyCurrency,
															overviewCompanyCurrency,
														)
													}}
												</div>
											</div>
										</td>
										<td class="text-end">
											{{ row.invoice_count || 0 }}
										</td>
									</tr>
								</tbody>
							</table>
						</div>
					</div>
				</v-col>
				<v-col v-if="returnsByCurrency.length" cols="12" md="6">
					<div class="table-section">
						<div class="table-header mb-2">
							<h5 class="text-subtitle-1 text-grey-darken-2 mb-1">
								{{ __("Returns by Currency") }}
							</h5>
							<p class="text-body-2 text-grey">
								{{ __("Processed returns impacting the shift totals") }}
							</p>
						</div>
						<div class="overview-table-wrapper">
							<table class="overview-table">
								<thead>
									<tr>
										<th>{{ __("Currency") }}</th>
										<th class="text-end">
											{{ __("Returns") }}
										</th>
										<th class="text-end">
											{{ __("Count") }}
										</th>
									</tr>
								</thead>
								<tbody>
									<tr v-for="row in returnsByCurrency" :key="`return-${row.currency}`">
										<td>{{ row.currency }}</td>
										<td class="text-end">
											<div class="amount-with-base">
												<div class="amount-primary">
													<span class="overview-amount">
														{{
															formatCurrencyWithSymbol(
																row.total || 0,
																row.currency || overviewCompanyCurrency,
															)
														}}
													</span>
													<span
														v-if="shouldShowCompanyEquivalent(row, row.currency)"
														class="company-equivalent"
													>
														({{
															formatCurrencyWithSymbol(
																row.company_currency_total || 0,
																overviewCompanyCurrency,
															)
														}})
													</span>
												</div>
												<div
													v-if="showExchangeRates(row, row.currency)"
													class="exchange-note"
												>
													{{
														formatExchangeRates(
															row.exchange_rates,
															row.currency || overviewCompanyCurrency,
															overviewCompanyCurrency,
														)
													}}
												</div>
											</div>
										</td>
										<td class="text-end">
											{{ row.invoice_count || 0 }}
										</td>
									</tr>
								</tbody>
							</table>
						</div>
					</div>
				</v-col>
			</v-row>

			<v-row
				v-if="
					changeReturnedRows.length ||
					cashExpectedByCurrency.length ||
					cashMovementSummary?.count
				"
				dense
				class="mt-4"
			>
				<v-col cols="12" md="6">
					<div v-if="changeReturnedRows.length" class="table-section">
						<div class="table-header mb-2">
							<h5 class="text-subtitle-1 text-grey-darken-2 mb-1">
								{{ __("Change Returned") }}
							</h5>
							<p class="text-body-2 text-grey">
								{{ __("Track how much cash was handed back to customers") }}
							</p>
						</div>
						<div class="overview-table-wrapper">
							<table class="overview-table">
								<thead>
									<tr>
										<th>{{ __("Currency") }}</th>
										<th class="text-end">
											{{ __("Invoice Change") }}
										</th>
										<th class="text-end">
											{{ __("Overpayment Change") }}
										</th>
										<th class="text-end">
											{{ __("Total Change") }}
										</th>
									</tr>
								</thead>
								<tbody>
									<tr
										v-for="row in changeReturnedRows"
										:key="`change-returned-${row.currency}`"
									>
										<td>{{ row.currency }}</td>
										<td class="text-end">
											<div class="amount-with-base">
												<div class="amount-primary">
													<span class="overview-amount">
														{{
															formatCurrencyWithSymbol(
																row.invoice_total,
																row.currency || overviewCompanyCurrency,
															)
														}}
													</span>
													<span
														v-if="
															shouldShowCompanyEquivalent(
																{
																	currency: row.currency,
																	total: row.invoice_total,
																	company_currency_total:
																		row.invoice_company_currency_total,
																},
																row.currency,
															)
														"
														class="company-equivalent"
													>
														({{
															formatCurrencyWithSymbol(
																row.invoice_company_currency_total,
																overviewCompanyCurrency,
															)
														}})
													</span>
												</div>
												<div
													v-if="showExchangeRates(row, row.currency)"
													class="exchange-note"
												>
													{{
														formatExchangeRates(
															row.exchange_rates,
															row.currency || overviewCompanyCurrency,
															overviewCompanyCurrency,
														)
													}}
												</div>
											</div>
										</td>
										<td class="text-end">
											<div class="amount-with-base">
												<div class="amount-primary">
													<span class="overview-amount">
														{{
															formatCurrencyWithSymbol(
																row.overpayment_total,
																row.currency || overviewCompanyCurrency,
															)
														}}
													</span>
													<span
														v-if="
															shouldShowCompanyEquivalent(
																{
																	currency: row.currency,
																	total: row.overpayment_total,
																	company_currency_total:
																		row.overpayment_company_currency_total,
																},
																row.currency,
															)
														"
														class="company-equivalent"
													>
														({{
															formatCurrencyWithSymbol(
																row.overpayment_company_currency_total,
																overviewCompanyCurrency,
															)
														}})
													</span>
												</div>
												<div
													v-if="showExchangeRates(row, row.currency)"
													class="exchange-note"
												>
													{{
														formatExchangeRates(
															row.exchange_rates,
															row.currency || overviewCompanyCurrency,
															overviewCompanyCurrency,
														)
													}}
												</div>
											</div>
										</td>
										<td class="text-end">
											<div class="amount-with-base">
												<div class="amount-primary">
													<span class="overview-amount">
														{{
															formatCurrencyWithSymbol(
																row.total,
																row.currency || overviewCompanyCurrency,
															)
														}}
													</span>
													<span
														v-if="
															shouldShowCompanyEquivalent(
																row.company_currency_total,
																row.currency,
															)
														"
														class="company-equivalent"
													>
														({{
															formatCurrencyWithSymbol(
																row.company_currency_total,
																overviewCompanyCurrency,
															)
														}})
													</span>
												</div>
												<div
													v-if="showExchangeRates(row, row.currency)"
													class="exchange-note"
												>
													{{
														formatExchangeRates(
															row.exchange_rates,
															row.currency || overviewCompanyCurrency,
															overviewCompanyCurrency,
														)
													}}
												</div>
											</div>
										</td>
									</tr>
								</tbody>
							</table>
						</div>
					</div>
					<!-- End: Change Returned -->
					<div
						v-if="cashExpectedByCurrency.length"
						:class="['table-section', { 'mt-4': changeReturnedRows.length }]"
					>
						<div class="table-header mb-2">
							<h5 class="text-subtitle-1 text-grey-darken-2 mb-1">
								{{ __("Cash Drawer Snapshot") }}
							</h5>
							<p class="text-body-2 text-grey">
								{{ __("Expected cash on hand grouped by currency") }}
							</p>
						</div>
						<div class="overview-table-wrapper">
							<table class="overview-table">
								<thead>
									<tr>
										<th>{{ __("Currency") }}</th>
										<th class="text-end">
											{{ __("Expected Cash") }}
										</th>
									</tr>
								</thead>
								<tbody>
									<tr v-for="row in cashExpectedByCurrency" :key="`cash-${row.currency}`">
										<td>{{ row.currency }}</td>
										<td class="text-end">
											<div class="amount-with-base">
												<div class="amount-primary">
													<span class="overview-amount">
														{{
															formatCurrencyWithSymbol(
																row.total || 0,
																row.currency || overviewCompanyCurrency,
															)
														}}
													</span>
													<span
														v-if="shouldShowCompanyEquivalent(row, row.currency)"
														class="company-equivalent"
													>
														({{
															formatCurrencyWithSymbol(
																row.company_currency_total || 0,
																overviewCompanyCurrency,
															)
														}})
													</span>
												</div>
												<div
													v-if="
														isCashMode(row.mode_of_payment) &&
														overpaymentDeductionForCurrency(row.currency)
													"
													class="exchange-note"
												>
													{{
														__("Overpayment change deducted: {0}", [
															formatCurrencyWithSymbol(
																overpaymentDeductionForCurrency(row.currency),
																row.currency || overviewCompanyCurrency,
															),
														])
													}}
												</div>
												<div
													v-if="showExchangeRates(row, row.currency)"
													class="exchange-note"
												>
													{{
														formatExchangeRates(
															row.exchange_rates,
															row.currency || overviewCompanyCurrency,
															overviewCompanyCurrency,
														)
													}}
												</div>
											</div>
										</td>
									</tr>
								</tbody>
							</table>
						</div>
					</div>
					<div
						v-if="cashMovementSummary?.count"
						:class="[
							'table-section',
							{ 'mt-4': changeReturnedRows.length || cashExpectedByCurrency.length },
						]"
					>
						<div class="table-header mb-2">
							<h5 class="text-subtitle-1 text-grey-darken-2 mb-1">
								{{ __("Submitted Cash Movements") }}
							</h5>
							<p class="text-body-2 text-grey">
								{{ __("Expenses and deposits posted during this shift") }}
							</p>
						</div>
						<div class="overview-table-wrapper">
							<table class="overview-table">
								<thead>
									<tr>
										<th>{{ __("Movement Type") }}</th>
										<th class="text-end">{{ __("Amount") }}</th>
									</tr>
								</thead>
								<tbody>
									<tr
										v-for="row in cashMovementSummary.by_type || []"
										:key="`cash-movement-${row.movement_type}`"
									>
										<td>{{ row.movement_type }}</td>
										<td class="text-end">
											{{ formatCurrencyWithSymbol(row.total || 0, overviewCompanyCurrency) }}
										</td>
									</tr>
									<tr>
										<td><strong>{{ __("Total") }}</strong></td>
										<td class="text-end">
											<strong>
												{{
													formatCurrencyWithSymbol(
														cashMovementSummary.company_currency_total || 0,
														overviewCompanyCurrency,
													)
												}}
											</strong>
										</td>
									</tr>
								</tbody>
							</table>
						</div>
					</div>
				</v-col>
			</v-row>

			<!--
				Cashiers — per-cashier breakdown of who rang what on this
				shift, with a drill-down into the actual invoices each
				cashier rang. Multiple cashiers can rotate via the in-app
				Switch Cashier flow without ending the shift, so this is
				the only place the closing report shows the per-mini-shift
				split. The store manager opens any cashier panel to spot
				anomalies (a stretch of returns, an oddly-large ticket on
				a junior cashier's mini-shift, etc.) without bouncing to
				ERPNext list view.

				Hides on shifts that pre-date the cashier-tracking
				rollout (empty array).
			-->
			<div
				v-if="cashiersBreakdown && cashiersBreakdown.length"
				class="table-section mt-4"
			>
				<div class="table-header mb-2">
					<h5 class="text-subtitle-1 text-grey-darken-2 mb-1">
						{{ __("Invoices by Cashier") }}
					</h5>
					<p class="text-body-2 text-grey">
						{{
							__(
								"Click a cashier to see every invoice they rang. Use this to review per-cashier performance and spot errors before submitting the closing entry.",
							)
						}}
					</p>
				</div>

				<v-expansion-panels
					multiple
					variant="accordion"
					class="cashier-panels"
				>
					<v-expansion-panel
						v-for="row in cashiersBreakdown"
						:key="row.cashier"
						:value="row.cashier"
					>
						<v-expansion-panel-title class="cashier-panel-title">
							<div class="cashier-panel-summary">
								<div class="cashier-panel-summary__main">
									<v-icon size="18" class="me-2">
										mdi-account-circle-outline
									</v-icon>
									<div class="cashier-panel-summary__name-block">
										<div class="cashier-panel-summary__name">
											{{ row.cashier_name || row.cashier }}
										</div>
										<div
											v-if="row.sales_person"
											class="cashier-panel-summary__sales-person"
										>
											{{ __("Sales Person") }}:
											{{ row.sales_person }}
										</div>
									</div>
								</div>
								<div class="cashier-panel-summary__stats">
									<span class="cashier-panel-summary__count">
										{{ row.invoice_count || 0 }}
										{{ __("invoices") }}
									</span>
									<span class="cashier-panel-summary__total">
										{{
											formatCurrencyWithSymbol(
												row.grand_total || 0,
												overviewCompanyCurrency,
											)
										}}
									</span>
								</div>
							</div>
						</v-expansion-panel-title>
						<v-expansion-panel-text class="cashier-panel-text">
							<div class="overview-table-wrapper">
								<table class="overview-table cashier-invoice-table">
									<thead>
										<tr>
											<th>{{ __("Invoice") }}</th>
											<th>{{ __("Time") }}</th>
											<th>{{ __("Customer") }}</th>
											<th class="text-end">
												{{ __("Total") }}
											</th>
										</tr>
									</thead>
									<tbody>
										<tr
											v-for="invoice in row.invoices || []"
											:key="invoice.name"
											:class="{ 'is-return': invoice.is_return }"
										>
											<td class="invoice-name-cell">
												<span class="invoice-name">
													{{ invoice.name }}
												</span>
												<span
													v-if="invoice.is_return"
													class="invoice-return-tag"
												>
													{{ __("Return") }}
												</span>
											</td>
											<td class="invoice-time">
												{{
													formatInvoiceTime(
														invoice.posting_time,
													) || "—"
												}}
											</td>
											<td>
												{{
													invoice.customer_name ||
													invoice.customer ||
													"—"
												}}
											</td>
											<td class="text-end">
												<span class="overview-amount">
													{{
														formatCurrencyWithSymbol(
															invoice.grand_total || 0,
															invoice.currency ||
																overviewCompanyCurrency,
														)
													}}
												</span>
												<div
													v-if="
														invoice.currency &&
														invoice.currency !==
															overviewCompanyCurrency
													"
													class="company-equivalent"
												>
													({{
														formatCurrencyWithSymbol(
															invoice.base_grand_total ||
																0,
															overviewCompanyCurrency,
														)
													}})
												</div>
											</td>
										</tr>
										<tr
											v-if="!row.invoices || !row.invoices.length"
										>
											<td colspan="4" class="text-center text-grey">
												{{ __("No invoices for this cashier.") }}
											</td>
										</tr>
									</tbody>
									<tfoot>
										<tr class="cashier-subtotal-row">
											<td colspan="3">
												<strong>
													{{ __("Subtotal") }}
												</strong>
											</td>
											<td class="text-end">
												<strong>
													{{
														formatCurrencyWithSymbol(
															row.grand_total || 0,
															overviewCompanyCurrency,
														)
													}}
												</strong>
											</td>
										</tr>
									</tfoot>
								</table>
							</div>
						</v-expansion-panel-text>
					</v-expansion-panel>
				</v-expansion-panels>

				<div class="cashier-grand-total-row mt-2">
					<div class="cashier-grand-total-row__label">
						<v-icon size="18" class="me-2">mdi-sigma</v-icon>
						{{ __("Grand Total — All Cashiers") }}
						<span class="cashier-grand-total-row__count">
							·
							{{
								cashiersBreakdown.reduce(
									(sum, r) => sum + (r.invoice_count || 0),
									0,
								)
							}}
							{{ __("invoices") }}
						</span>
					</div>
					<div class="cashier-grand-total-row__value">
						{{
							formatCurrencyWithSymbol(
								cashiersBreakdown.reduce(
									(sum, r) => sum + (r.grand_total || 0),
									0,
								),
								overviewCompanyCurrency,
							)
						}}
					</div>
				</div>
			</div>

			<div v-if="paymentsByMode.length" class="table-section mt-4">
				<div class="table-header mb-2">
					<h5 class="text-subtitle-1 text-grey-darken-2 mb-1">
						{{ __("Payments by Mode of Payment") }}
					</h5>
					<p class="text-body-2 text-grey">
						{{ __("Grouped totals for each payment method and currency") }}
					</p>
				</div>

				<div class="overview-table-wrapper">
					<table class="overview-table">
						<thead>
							<tr>
								<th>{{ __("Mode of Payment") }}</th>
								<th>{{ __("Currency") }}</th>
								<th class="text-end">
									{{ __("Amount") }}
								</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="row in paymentsByMode" :key="`${row.mode_of_payment}-${row.currency}`">
								<td>{{ row.mode_of_payment }}</td>
								<td>{{ row.currency }}</td>
								<td class="text-end">
									<div class="amount-with-base">
										<div class="amount-primary">
											<span class="overview-amount">
												{{
													formatCurrencyWithSymbol(
														row.total || 0,
														row.currency || overviewCompanyCurrency,
													)
												}}
											</span>
											<span
												v-if="shouldShowCompanyEquivalent(row, row.currency)"
												class="company-equivalent"
											>
												({{
													formatCurrencyWithSymbol(
														row.company_currency_total || 0,
														overviewCompanyCurrency,
													)
												}})
											</span>
										</div>
										<div
											v-if="showExchangeRates(row, row.currency)"
											class="exchange-note"
										>
											{{
												formatExchangeRates(
													row.exchange_rates,
													row.currency || overviewCompanyCurrency,
													overviewCompanyCurrency,
												)
											}}
										</div>
									</div>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>

			<!--
				Taxes Collected — split out as its own section so the
				cashier / store manager / accountant can see the day's
				tax liability at a glance, broken down per tax account
				(useful for ZATCA reconciliation in KSA-shifts) AND per
				invoice currency. Hides itself when no tax was collected.
			-->
			<div
				v-if="taxesCollectedSummary && taxesCollectedSummary.company_currency_total"
				class="table-section mt-4"
			>
				<div class="table-header mb-2">
					<h5 class="text-subtitle-1 text-grey-darken-2 mb-1">
						{{ __("Taxes Collected") }}
					</h5>
					<p class="text-body-2 text-grey">
						{{ __("Tax owed to the government — separate from net sales (revenue you keep)") }}
					</p>
				</div>

				<div class="overview-table-wrapper" v-if="taxesCollectedByAccount && taxesCollectedByAccount.length">
					<table class="overview-table">
						<thead>
							<tr>
								<th>{{ __("Tax Account") }}</th>
								<th class="text-end">{{ __("Rate") }}</th>
								<th>{{ __("Currency") }}</th>
								<th class="text-end">{{ __("Amount") }}</th>
							</tr>
						</thead>
						<tbody>
							<tr
								v-for="row in taxesCollectedByAccount"
								:key="`tax-account-${row.account_head}-${row.currency}-${row.rate}`"
							>
								<td>{{ row.account_head }}</td>
								<td class="text-end">{{ row.rate }}%</td>
								<td>{{ row.currency || overviewCompanyCurrency }}</td>
								<td class="text-end">
									<div class="amount-with-base">
										<div class="amount-primary">
											<span class="overview-amount">
												{{
													formatCurrencyWithSymbol(
														row.amount || 0,
														row.currency || overviewCompanyCurrency,
													)
												}}
											</span>
											<span
												v-if="shouldShowCompanyEquivalent({ company_currency_total: row.company_currency_amount }, row.currency)"
												class="company-equivalent"
											>
												({{
													formatCurrencyWithSymbol(
														row.company_currency_amount || 0,
														overviewCompanyCurrency,
													)
												}})
											</span>
										</div>
									</div>
								</td>
							</tr>
							<tr>
								<td colspan="3"><strong>{{ __("Total Tax Collected") }}</strong></td>
								<td class="text-end">
									<strong>
										{{
											formatCurrencyWithSymbol(
												taxesCollectedSummary.company_currency_total || 0,
												overviewCompanyCurrency,
											)
										}}
									</strong>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
defineProps({
	loading: Boolean,
	primaryInsights: Array,
	secondaryInsights: Array,
	multiCurrencyTotals: Array,
	creditInvoicesByCurrency: Array,
	returnsByCurrency: Array,
	changeReturnedRows: Array,
	cashExpectedByCurrency: Array,
	cashMovementSummary: Object,
	paymentsByMode: Array,
	taxesCollectedSummary: { type: Object, default: () => ({ company_currency_total: 0, by_account: [], by_currency: [] }) },
	taxesCollectedByAccount: { type: Array, default: () => [] },
	taxesCollectedByCurrency: { type: Array, default: () => [] },
	cashiersBreakdown: { type: Array, default: () => [] },
	overviewCompanyCurrency: String,
	// Functions
	formatCurrencyWithSymbol: Function,
	shouldShowCompanyEquivalent: Function,
	showExchangeRates: Function,
	formatExchangeRates: Function,
	isCashMode: Function,
	overpaymentDeductionForCurrency: Function,
});

const __ = window.__ || ((t) => t);

/*
 * `posting_time` from the server is an ISO-ish "HH:MM:SS.ffffff"
 * string. The cashier-invoice grid only needs HH:MM, so trim the
 * seconds + microseconds before display. Empty / null / unparseable
 * inputs return an empty string so the cell falls back to "—".
 */
function formatInvoiceTime(value) {
	if (!value) return "";
	const text = String(value).trim();
	if (!text) return "";
	const match = text.match(/^(\d{1,2}):(\d{2})/);
	if (!match) return text;
	return `${match[1].padStart(2, "0")}:${match[2]}`;
}
</script>

<style scoped>
.overview-wrapper {
	display: flex;
	flex-direction: column;
	gap: 24px;
	width: 100%;
}

.table-header {
	margin-bottom: 24px;
}

.insight-grid {
	margin-bottom: 8px;
}

.insight-card {
	background: rgb(var(--v-theme-surface));
	border-radius: 12px;
	padding: 16px;
	display: flex;
	align-items: flex-start;
	gap: 16px;
	border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
	box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
	width: 100%;
	transition: all 0.2s ease;
}

.insight-card:hover {
	transform: translateY(-2px);
	box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
	border-color: rgba(var(--v-border-color), 0.5);
}

.insight-card.compact {
	padding: 12px 16px;
}

.insight-icon {
	width: 48px;
	height: 48px;
	border-radius: 12px;
	display: flex;
	align-items: center;
	justify-content: center;
	flex-shrink: 0;
}
.insight-card.compact .insight-icon {
	width: 40px;
	height: 40px;
}

/* Accent Colors for Icons - Theme Aware */
.accent-primary {
	background-color: rgba(var(--v-theme-primary), 0.1);
	color: rgb(var(--v-theme-primary));
}
.accent-success {
	background-color: rgba(var(--v-theme-success), 0.1);
	color: rgb(var(--v-theme-success));
}
.accent-secondary {
	background-color: rgba(var(--v-theme-secondary), 0.1);
	color: rgb(var(--v-theme-secondary));
}
.accent-info {
	background-color: rgba(var(--v-theme-info), 0.1);
	color: rgb(var(--v-theme-info));
}
.accent-warning {
	background-color: rgba(var(--v-theme-warning), 0.1);
	color: rgb(var(--v-theme-warning));
}

.insight-body {
	flex: 1;
	min-width: 0;
}

.insight-label {
	font-size: 0.75rem;
	text-transform: uppercase;
	letter-spacing: 0.5px;
	opacity: 0.7;
	font-weight: 600;
	margin-bottom: 4px;
}

.insight-value {
	font-size: 1.25rem;
	font-weight: 700;
	line-height: 1.2;
}

.insight-card.compact .insight-value {
	font-size: 1.1rem;
}

.insight-caption {
	font-size: 0.75rem;
	opacity: 0.6;
	margin-top: 4px;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.table-section {
	background: rgb(var(--v-theme-surface));
	border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
	border-radius: 12px;
	padding: 24px;
	box-shadow: 0 2px 4px rgba(0, 0, 0, 0.02);
}

.overview-table-wrapper {
	overflow-x: auto;
	width: 100%;
}

.overview-table {
	width: 100%;
	border-collapse: collapse;
	font-size: 0.875rem;
}

.overview-table th {
	text-align: left;
	opacity: 0.7;
	font-weight: 600;
	padding: 12px 16px;
	border-bottom: 2px solid rgba(var(--v-border-color), 0.1);
	white-space: nowrap;
}

.overview-table td {
	padding: 14px 16px;
	border-bottom: 1px solid rgba(var(--v-border-color), 0.05);
	vertical-align: top;
}

.overview-table tbody tr:last-child td {
	border-bottom: none;
}

.overview-table tbody tr:hover {
	background-color: rgba(var(--v-theme-on-surface), 0.02);
}

.text-end {
	text-align: right !important;
}

.amount-with-base {
	display: flex;
	flex-direction: column;
	align-items: flex-end;
}

.amount-primary {
	display: flex;
	flex-direction: column;
	align-items: flex-end;
}

.overview-amount {
	font-weight: 600;
}

.company-equivalent {
	font-size: 0.75rem;
	opacity: 0.6;
	margin-top: 2px;
}

.exchange-note {
	font-size: 0.7rem;
	color: rgb(var(--v-theme-primary));
	background-color: rgba(var(--v-theme-primary), 0.1);
	padding: 2px 6px;
	border-radius: 4px;
	margin-top: 4px;
	display: inline-block;
}

.overview-empty {
	padding: 24px;
	text-align: center;
	background-color: rgba(var(--v-theme-on-surface), 0.03);
	border-radius: 8px;
	opacity: 0.6;
	font-style: italic;
}

/* ── Cashier expansion panels (per-cashier invoice drill-down) ────── */
.cashier-panels {
	border: 1px solid rgba(var(--v-theme-on-surface), 0.08);
	border-radius: 10px;
	overflow: hidden;
	background-color: rgba(var(--v-theme-on-surface), 0.02);
}

.cashier-panels :deep(.v-expansion-panel) {
	background: transparent;
}

.cashier-panels :deep(.v-expansion-panel-title) {
	min-height: 48px;
	padding: 8px 16px;
}

.cashier-panel-summary {
	display: flex;
	flex: 1;
	align-items: center;
	gap: 12px;
	flex-wrap: wrap;
}

.cashier-panel-summary__main {
	display: flex;
	align-items: center;
	flex: 1 1 auto;
	min-width: 0;
}

.cashier-panel-summary__name-block {
	display: flex;
	flex-direction: column;
	min-width: 0;
}

.cashier-panel-summary__name {
	font-weight: 600;
	color: rgba(var(--v-theme-on-surface), 0.95);
	font-size: 0.95rem;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.cashier-panel-summary__sales-person {
	font-size: 0.78rem;
	color: rgba(var(--v-theme-on-surface), 0.6);
}

.cashier-panel-summary__stats {
	display: flex;
	align-items: center;
	gap: 16px;
	flex-shrink: 0;
}

.cashier-panel-summary__count {
	font-size: 0.8rem;
	color: rgba(var(--v-theme-on-surface), 0.6);
	background: rgba(var(--v-theme-primary), 0.08);
	padding: 2px 10px;
	border-radius: 999px;
	white-space: nowrap;
}

.cashier-panel-summary__total {
	font-weight: 700;
	font-variant-numeric: tabular-nums;
	color: rgb(var(--v-theme-primary));
	font-size: 0.95rem;
}

.cashier-panel-text :deep(.v-expansion-panel-text__wrapper) {
	padding: 8px 16px 16px;
}

.cashier-invoice-table th,
.cashier-invoice-table td {
	font-size: 0.85rem;
	padding: 8px 10px;
}

.cashier-invoice-table .invoice-name {
	font-family: "SF Mono", "Roboto Mono", "Consolas", monospace;
	font-size: 0.82rem;
	color: rgba(var(--v-theme-on-surface), 0.92);
}

.cashier-invoice-table .invoice-return-tag {
	display: inline-block;
	margin-inline-start: 8px;
	padding: 1px 6px;
	font-size: 0.7rem;
	font-weight: 600;
	color: rgb(var(--v-theme-warning));
	background: rgba(var(--v-theme-warning), 0.12);
	border-radius: 4px;
	text-transform: uppercase;
	letter-spacing: 0.04em;
}

.cashier-invoice-table tr.is-return td {
	background: rgba(var(--v-theme-warning), 0.04);
}

.cashier-invoice-table .invoice-time {
	font-variant-numeric: tabular-nums;
	white-space: nowrap;
	color: rgba(var(--v-theme-on-surface), 0.7);
}

.cashier-invoice-table tfoot .cashier-subtotal-row td {
	background: rgba(var(--v-theme-primary), 0.04);
	border-top: 2px solid rgba(var(--v-theme-primary), 0.18);
}

.cashier-grand-total-row {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
	padding: 12px 16px;
	background: linear-gradient(
		135deg,
		rgba(var(--v-theme-primary), 0.1),
		rgba(var(--v-theme-secondary), 0.06)
	);
	border: 1px solid rgba(var(--v-theme-primary), 0.22);
	border-radius: 10px;
	font-size: 0.95rem;
}

.cashier-grand-total-row__label {
	display: inline-flex;
	align-items: center;
	font-weight: 600;
	color: rgba(var(--v-theme-on-surface), 0.92);
	letter-spacing: 0.01em;
}

.cashier-grand-total-row__count {
	margin-inline-start: 8px;
	font-weight: 500;
	color: rgba(var(--v-theme-on-surface), 0.6);
	font-size: 0.85rem;
}

.cashier-grand-total-row__value {
	font-weight: 800;
	font-variant-numeric: tabular-nums;
	color: rgb(var(--v-theme-primary));
	font-size: 1.05rem;
}
</style>
