<template>
	<v-dialog
		v-model="closingDialog"
		:max-width="shiftSubmitted ? '620px' : '900px'"
		persistent
	>
		<v-card elevation="8" class="closing-dialog-card">
			<ClosingHeader @close="onHeaderClose" />

			<!-- ─────────────── Pre-submit / form view ─────────────── -->
			<template v-if="!shiftSubmitted">
				<!-- Action bar pinned right under the header so the cashier
				     never has to scroll past Payment Reconciliation /
				     Shift Overview to hit Submit. The detailed sections
				     stay below for reference. -->
				<v-card-actions class="dialog-actions-container dialog-actions-container--top">
					<v-btn
						theme="dark"
						@click="printReceipt"
						class="pos-action-btn print-action-btn print-receipt-btn"
						size="large"
						elevation="2"
						:disabled="overviewLoading"
					>
						<v-icon start>mdi-printer-pos</v-icon>
						<span>{{ __("Print Receipt") }}</span>
					</v-btn>
					<v-btn
						theme="dark"
						@click="printA4"
						class="pos-action-btn print-action-btn print-a4-btn"
						size="large"
						elevation="2"
						:disabled="overviewLoading"
					>
						<v-icon start>mdi-file-pdf-box</v-icon>
						<span>{{ __("Print A4") }}</span>
					</v-btn>
					<v-spacer></v-spacer>
					<v-btn
						theme="dark"
						@click="closeDialog"
						class="pos-action-btn cancel-action-btn"
						size="large"
						elevation="2"
					>
						<v-icon start>mdi-close-circle-outline</v-icon>
						<span>{{ __("Close") }}</span>
					</v-btn>
					<v-btn
						theme="dark"
						@click="onSubmit"
						class="pos-action-btn submit-action-btn"
						size="large"
						elevation="2"
						:disabled="submitInFlight"
						:loading="submitInFlight"
					>
						<v-icon start>mdi-check-circle-outline</v-icon>
						<span>{{ __("Submit") }}</span>
					</v-btn>
				</v-card-actions>

				<v-divider></v-divider>

				<v-card-text class="pa-0 white-background">
					<v-container class="pa-6">
						<!-- Payment Reconciliation moved above Shift Overview —
						     it's the active input the cashier needs to fill in
						     to close, so it should be the first thing they see
						     after the action bar. Shift Overview is reference
						     data and lives below. -->
						<v-row class="mb-6">
							<v-col cols="12" class="pa-1">
								<PaymentReconciliation
									:payments="dialog_data.payment_reconciliation"
									:headers="headers"
									:items-per-page="itemsPerPage"
									:company-currency-symbol="companyCurrencySymbol"
									:format-currency="formatCurrency"
									:format-float="formatFloat"
								/>
							</v-col>
						</v-row>
						<v-row>
							<v-col cols="12" class="pa-1">
								<ShiftOverview
									:loading="overviewLoading"
									:primary-insights="primaryInsights"
									:secondary-insights="secondaryInsights"
									:multi-currency-totals="multiCurrencyTotals"
									:credit-invoices-by-currency="creditInvoicesByCurrency"
									:returns-by-currency="returnsByCurrency"
									:change-returned-rows="changeReturnedRows"
									:cash-expected-by-currency="cashExpectedByCurrency"
									:cash-movement-summary="cashMovementSummary"
									:payments-by-mode="paymentsByMode"
									:overview-company-currency="overviewCompanyCurrency"
									:format-currency-with-symbol="formatCurrencyWithSymbol"
									:should-show-company-equivalent="shouldShowCompanyEquivalent"
									:show-exchange-rates="showExchangeRates"
									:format-exchange-rates="formatExchangeRates"
									:is-cash-mode="isCashMode"
									:overpayment-deduction-for-currency="overpaymentDeductionForCurrency"
								/>
							</v-col>
						</v-row>
					</v-container>
				</v-card-text>
			</template>

			<!-- ────────────── Post-submit prompt view ────────────── -->
			<template v-else>
				<v-card-text class="pa-0 post-submit-card">
					<div class="post-submit">
						<div class="post-submit__icon-wrap">
							<v-icon class="post-submit__icon">
								mdi-check-circle
							</v-icon>
						</div>
						<h3 class="post-submit__title">
							{{ __("Shift Closed Successfully") }}
						</h3>
						<p class="post-submit__subtitle">
							{{
								__(
									"Choose what to do next. You can print a final summary, log out, or go back to open a new shift.",
								)
							}}
						</p>

						<div class="post-submit__actions">
							<v-btn
								theme="dark"
								@click="printReceipt"
								class="pos-action-btn print-action-btn print-receipt-btn"
								size="large"
								elevation="2"
							>
								<v-icon start>mdi-printer-pos</v-icon>
								<span>{{ __("Print Receipt") }}</span>
							</v-btn>
							<v-btn
								theme="dark"
								@click="printA4"
								class="pos-action-btn print-action-btn print-a4-btn"
								size="large"
								elevation="2"
							>
								<v-icon start>mdi-file-pdf-box</v-icon>
								<span>{{ __("Print A4") }}</span>
							</v-btn>
						</div>

						<div class="post-submit__divider">
							<span>{{ __("or") }}</span>
						</div>

						<div class="post-submit__nav">
							<v-btn
								theme="dark"
								@click="onBackToOpening"
								class="pos-action-btn post-nav-btn post-nav-btn--primary"
								size="large"
								elevation="2"
							>
								<v-icon start>mdi-arrow-left-circle</v-icon>
								<span>{{ __("Back to Opening Shift") }}</span>
							</v-btn>
							<v-btn
								theme="dark"
								@click="onLogout"
								class="pos-action-btn post-nav-btn post-nav-btn--logout"
								size="large"
								elevation="2"
							>
								<v-icon start>mdi-logout</v-icon>
								<span>{{ __("Logout") }}</span>
							</v-btn>
						</div>
					</div>
				</v-card-text>
			</template>
		</v-card>
	</v-dialog>
</template>

<script>
import { useUIStore } from "../../../stores/uiStore.js";
import { useToastStore } from "../../../stores/toastStore.js";
import { ref, inject, onMounted, onBeforeUnmount, watch } from "vue";
import { useClosingShift } from "../../../composables/pos/closing/useClosingShift";
import { useClosingSummary } from "../../../composables/pos/closing/useClosingSummary";
import {
	printReceiptClosingShift,
	printA4ClosingShift,
} from "../../../composables/pos/closing/usePrintClosingShift";

import ClosingHeader from "../closing/ClosingHeader.vue";
import ShiftOverview from "../closing/ShiftOverview.vue";
import PaymentReconciliation from "../closing/PaymentReconciliation.vue";

export default {
	name: "ClosingDialog",
	components: {
		ClosingHeader,
		ShiftOverview,
		PaymentReconciliation,
	},
	setup() {
		const uiStore = useUIStore();
		const toastStore = useToastStore();
		const eventBus = inject("eventBus");
		const __ = window.__ || ((t) => t);

		// ── Post-submit state ──────────────────────────────────────────
		// `submitInFlight`  → true while the close API is executing
		// `shiftSubmitted`  → true once the API confirmed success; the
		//                     dialog flips to the post-submit prompt
		const shiftSubmitted = ref(false);
		const submitInFlight = ref(false);

		// Initialize composables
		const {
			closingDialog,
			dialog_data,
			overview,
			overviewLoading,
			pos_profile,
			closeDialog,
			fetchOverview,
			submitDialog,
		} = useClosingShift(eventBus);

		// Formatters
		//
		// `formatCurrency` is intentionally a NUMBER-ONLY formatter. Call sites
		// (PaymentReconciliation cells, the print HTML, formatCurrencyWithSymbol)
		// stamp the currency code/symbol themselves; routing through Frappe's
		// `format_currency` here was double-stamping the symbol — every row in
		// the closing dialog rendered as "KWD KWD 3,959.000" / "SAR KWD 48,100.835"
		// because the company-currency code from format_currency stacked on top
		// of the row-currency symbol added by formatCurrencyWithSymbol or the
		// `companyCurrencySymbol` prefix in PaymentReconciliation. `format_number`
		// keeps the grouping + precision without adding a symbol.
		const formatNumberSafe = (v, decimals) => {
			const fn = typeof window?.format_number === "function" ? window.format_number : null;
			const num = Number(v) || 0;
			const prec = Number.isFinite(decimals) ? decimals : undefined;
			if (fn) {
				try {
					return fn(num, undefined, prec);
				} catch {
					/* fall through to toLocaleString */
				}
			}
			return num.toLocaleString(undefined, {
				minimumFractionDigits: prec ?? 2,
				maximumFractionDigits: prec ?? 2,
			});
		};
		const formatCurrency = (v, decimals) => formatNumberSafe(v, decimals);
		const formatFloat = (v, d) => window.flt(v, d);
		const currencySymbol = (c) => window.get_currency_symbol(c);
		const translate = (t) => window.__(t);

		const summaryFormatters = {
			// Returns "<symbol> <amount>" formatted in the row's own currency so
			// SAR rows render as "SAR 48,100.835" and KWD (company-currency) rows
			// render as "KWD 3,959.000". Routing through Frappe's format_currency
			// with an explicit currency arg keeps each row's locale-aware
			// precision and currency code correct, instead of always borrowing
			// the company-currency code (the source of the "KWD KWD" duplication
			// users hit when transactions were in SAR but the company was KWD).
			formatCurrencyWithSymbol: (amount, currency) => {
				const resolvedCurrency = currency || "";
				const numeric = Number(amount) || 0;
				const fc =
					typeof window?.format_currency === "function" ? window.format_currency : null;
				if (fc) {
					try {
						return fc(numeric, resolvedCurrency || undefined);
					} catch {
						/* fall through */
					}
				}
				const symbol = currencySymbol(resolvedCurrency) || resolvedCurrency;
				const formatted = formatNumberSafe(numeric);
				return symbol ? `${symbol} ${formatted}`.trim() : formatted;
			},
			formatCount: (value) => formatFloat(value || 0, 0),
			formatCurrency,
			currencySymbol,
			__: translate,
		};

		const summary = useClosingSummary(overview, pos_profile, dialog_data, summaryFormatters);

		// ── Print actions ─────────────────────────────────────────────
		// Build a self-contained payload from the dialog's already-loaded
		// reactive state. The two print helpers open a new window with
		// inline HTML+CSS, so no extra network calls are needed.
		const buildPrintPayload = () => {
			const data = dialog_data.value || {};
			const profile = pos_profile.value || {};
			const ov = overview.value || {};
			const session = (typeof window !== "undefined" && window.frappe?.session) || {};

			const companyCurrency =
				summary.overviewCompanyCurrency.value ||
				profile.currency ||
				data.currency ||
				"";

			const cashMovementCompanyTotal =
				summary.cashMovementSummary.value?.company_currency_total || 0;

			const periodStart =
				data.period_start_date ||
				ov.period_start_date ||
				ov.start_date ||
				"";
			const periodEnd =
				data.period_end_date ||
				ov.period_end_date ||
				ov.end_date ||
				new Date().toLocaleString();

			return {
				// `shiftClosed` flips the print banner from
				// "OPEN SHIFT — printed before closing" (still draft)
				// to "CLOSED SHIFT — printed after closing"
				shiftClosed: shiftSubmitted.value,
				shiftName:
					data.name ||
					data.pos_opening_shift ||
					ov.pos_opening_shift ||
					"",
				companyName:
					data.company || profile.company || ov.company || "",
				posProfileName:
					data.pos_profile ||
					profile.name ||
					profile.pos_profile ||
					"",
				cashierName:
					data.user ||
					session.user_fullname ||
					session.user ||
					profile.user ||
					"",
				periodStart: String(periodStart || ""),
				periodEnd: String(periodEnd || ""),
				companyCurrency,
				companyCurrencySymbol: summary.companyCurrencySymbol.value || companyCurrency,
				primaryInsights: summary.primaryInsights.value || [],
				secondaryInsights: summary.secondaryInsights.value || [],
				multiCurrencyTotals: summary.multiCurrencyTotals.value || [],
				paymentsByMode: summary.paymentsByMode.value || [],
				reconciliation:
					data.payment_reconciliation || data.payments || [],
				creditInvoicesByCurrency:
					summary.creditInvoicesByCurrency.value || [],
				returnsByCurrency: summary.returnsByCurrency.value || [],
				cashMovementCompanyTotal,
				formatCurrencyWithSymbol: summaryFormatters.formatCurrencyWithSymbol,
				formatCurrency,
				formatFloat,
			};
		};

		const printReceipt = () => {
			try {
				printReceiptClosingShift(buildPrintPayload());
			} catch (err) {
				console.error("[POSA] Failed to print receipt closing shift", err);
			}
		};

		const printA4 = () => {
			try {
				printA4ClosingShift(buildPrintPayload());
			} catch (err) {
				console.error("[POSA] Failed to print A4 closing shift", err);
			}
		};

		const headers = ref([]);
		const baseHeaders = [
			{
				title: __("Mode of Payment"),
				value: "mode_of_payment",
				align: "start",
				sortable: true,
			},
			{
				title: __("Opening Amount"),
				align: "end",
				sortable: true,
				value: "opening_amount",
			},
			{
				title: __("Closing Amount"),
				value: "closing_amount",
				align: "end",
				sortable: true,
			},
		];
		const extendedHeaders = [
			{
				title: __("Expected Amount (In Company Currency)"),
				value: "expected_amount",
				align: "end",
				sortable: false,
			},
			{
				title: __("Difference (In Company Currency)"),
				value: "difference",
				align: "end",
				sortable: false,
			},
			{
				title: __("Variance %"),
				value: "variance_percent",
				align: "end",
				sortable: false,
			},
		];

		// ── Submit / post-submit lifecycle ────────────────────────────
		// `onSubmit` is the click handler on the Submit button. It
		// flips `submitInFlight` immediately for instant UI feedback,
		// then defers to `submitDialog()` (which emits the bus event
		// usePosShift listens to). The actual flip to `shiftSubmitted`
		// happens via the eventBus listeners below.
		const onSubmit = () => {
			if (submitInFlight.value) return;
			submitInFlight.value = true;
			const ok = submitDialog();
			if (!ok) {
				// Validation failure (NaN closing amount). Reset and
				// surface a toast so the user knows why nothing happened.
				submitInFlight.value = false;
				toastStore.show({
					title: __("Please fill in all closing amounts."),
					color: "warning",
				});
			}
		};

		// Header close button — refuse while a submit is mid-flight,
		// otherwise behave like the cancel button.
		const onHeaderClose = () => {
			if (submitInFlight.value) return;
			closeDialog();
			// Reset post-submit state so a re-open starts fresh.
			shiftSubmitted.value = false;
		};

		// "Back to Opening Shift" — close the dialog and ask Pos.vue
		// to re-run check_opening_entry, which pops the OpeningDialog.
		const onBackToOpening = () => {
			shiftSubmitted.value = false;
			closeDialog();
			if (eventBus) {
				eventBus.emit("request_check_opening_entry");
			}
		};

		// "Logout" — uses Frappe's logout helper. Falls back to a
		// hard navigation if the helper isn't present.
		const onLogout = () => {
			try {
				const fr = window.frappe;
				if (fr?.app?.logout) {
					fr.app.logout();
					return;
				}
				if (fr?.call) {
					fr.call({
						method: "logout",
						callback: () => {
							window.location.href = "/login";
						},
					});
					return;
				}
			} catch (err) {
				console.error("[POSA] Logout failed", err);
			}
			window.location.href = "/login";
		};

		const handleKeydown = (event) => {
			if (event.key === "Escape" && closingDialog.value) {
				if (submitInFlight.value) return;
				if (shiftSubmitted.value) {
					// Treat Escape on the post-submit prompt as
					// "Back to Opening Shift" rather than a silent close.
					onBackToOpening();
					return;
				}
				closeDialog();
			}
		};

		// ── Submit lifecycle event listeners ──────────────────────────
		const onSubmitStarted = () => {
			submitInFlight.value = true;
		};

		const onSubmitFinished = (payload) => {
			submitInFlight.value = false;
			if (payload?.success) {
				shiftSubmitted.value = true;
			} else {
				toastStore.show({
					title: __("Failed to close shift. Please try again."),
					color: "error",
				});
			}
		};

		onMounted(() => {
			headers.value = [...baseHeaders];
			window.addEventListener("keydown", handleKeydown);

			if (eventBus) {
				eventBus.on("open_ClosingDialog", (data) => {
					// Reset state every time the dialog re-opens so a
					// fresh shift starts from the form view, not the
					// stale post-submit prompt.
					shiftSubmitted.value = false;
					submitInFlight.value = false;
					closingDialog.value = true;
					dialog_data.value = data;
					fetchOverview(data.pos_opening_shift, pos_profile.value?.currency);
				});
				eventBus.on("closing_pos_submit_started", onSubmitStarted);
				eventBus.on("closing_pos_submitted", onSubmitFinished);
			} else {
				console.error("ClosingDialog: eventBus not provided");
			}
		});

		onBeforeUnmount(() => {
			window.removeEventListener("keydown", handleKeydown);
			if (eventBus) {
				eventBus.off("open_ClosingDialog");
				eventBus.off("closing_pos_submit_started", onSubmitStarted);
				eventBus.off("closing_pos_submitted", onSubmitFinished);
			}
		});

		watch(
			() => uiStore.posProfile,
			(profile) => {
				if (profile) {
					pos_profile.value = profile;
					if (!pos_profile.value.hide_expected_amount) {
						headers.value = [...baseHeaders, ...extendedHeaders];
					} else {
						headers.value = [...baseHeaders];
					}
				}
			},
			{ deep: true, immediate: true },
		);

		return {
			uiStore,
			eventBus,
			closingDialog,
			dialog_data,
			overview,
			overviewLoading,
			pos_profile,
			closeDialog,
			fetchOverview,
			submitDialog,
			printReceipt,
			printA4,
			// Post-submit state + handlers exposed to the template
			shiftSubmitted,
			submitInFlight,
			onSubmit,
			onHeaderClose,
			onBackToOpening,
			onLogout,
			...summary,
			// Expose formatters used in template
			formatCurrency,
			formatFloat,
			formatCurrencyWithSymbol: summaryFormatters.formatCurrencyWithSymbol,
			shouldShowCompanyEquivalent: summary.shouldShowCompanyEquivalent,
			showExchangeRates: summary.showExchangeRates,
			formatExchangeRates: summary.formatExchangeRates,
			isCashMode: summary.isCashMode,
			overpaymentDeductionForCurrency: summary.overpaymentDeductionForCurrency,
			headers,
			itemsPerPage: 20,
		};
	},
};
</script>

<style scoped>
.closing-dialog-card {
	border-radius: 16px;
	overflow: hidden;
}

.white-background {
	background-color: rgb(var(--v-theme-surface));
}

.dialog-actions-container {
	padding: 16px 24px;
	border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

/* When the action bar is pinned to the top of the dialog (right under
   the header) instead of floating at the bottom, the border-top above
   reads as a stray line between the header and the buttons. Drop it
   and let the existing <v-divider> below the bar handle the separator
   into the form area. */
.dialog-actions-container--top {
	border-top: none;
	padding-top: 12px;
	padding-bottom: 12px;
	background: var(--pos-card-bg);
	position: sticky;
	top: 0;
	z-index: 2;
}

.pos-action-btn {
	border-radius: 8px;
	text-transform: none;
	font-weight: 600;
	letter-spacing: 0.5px;
	padding: 0 24px;
}

.cancel-action-btn {
	border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
}

.submit-action-btn {
	margin-left: 16px;
}

/* ── Print buttons (CC violet/pink theme) ─────────────────────── */
.print-action-btn {
	margin-right: 8px;
	color: #fff !important;
	border: 1px solid rgba(139, 92, 246, 0.45) !important;
	box-shadow: 0 2px 6px rgba(139, 92, 246, 0.18) !important;
	transition: transform 0.15s ease, box-shadow 0.15s ease,
		filter 0.15s ease;
}

.print-action-btn:not(:disabled):hover {
	transform: translateY(-1px);
	box-shadow: 0 4px 14px rgba(139, 92, 246, 0.35) !important;
	filter: brightness(1.04);
}

.print-receipt-btn {
	background: linear-gradient(
		135deg,
		rgba(139, 92, 246, 0.95),
		rgba(167, 122, 250, 0.95)
	) !important;
}

.print-a4-btn {
	background: linear-gradient(
		135deg,
		rgba(226, 54, 112, 0.95),
		rgba(244, 114, 182, 0.95)
	) !important;
}

@media (max-width: 600px) {
	.dialog-actions-container {
		flex-wrap: wrap;
		gap: 8px;
	}

	.print-action-btn,
	.cancel-action-btn,
	.submit-action-btn {
		flex: 1 1 calc(50% - 8px);
		margin: 0 !important;
	}
}

/* ────────────────── Post-submit prompt panel ────────────────── */
/* Shown after the closing API confirms success. Replaces the form
   view entirely. Styling pulls from the CC violet/pink palette so
   the success state feels celebratory but on-brand. */

.post-submit-card {
	background:
		radial-gradient(
			ellipse at top,
			rgba(139, 92, 246, 0.12),
			transparent 60%
		),
		rgb(var(--v-theme-surface));
	padding: 36px 32px 32px;
}

.post-submit {
	display: flex;
	flex-direction: column;
	align-items: center;
	text-align: center;
	font-family: var(--posa-font-family, "Space Grotesk", sans-serif);
}

.post-submit__icon-wrap {
	width: 72px;
	height: 72px;
	display: grid;
	place-items: center;
	border-radius: 50%;
	margin-bottom: 14px;
	background: linear-gradient(
		135deg,
		rgba(34, 197, 94, 0.18),
		rgba(139, 92, 246, 0.18)
	);
	border: 1px solid rgba(34, 197, 94, 0.45);
	box-shadow: 0 8px 28px rgba(34, 197, 94, 0.18);
}

.post-submit__icon {
	font-size: 44px !important;
	color: #22c55e !important;
}

.post-submit__title {
	margin: 0 0 6px;
	font-size: 1.3rem;
	font-weight: 700;
	letter-spacing: 0.01em;
	background: linear-gradient(135deg, #e23670, #f59e0b);
	-webkit-background-clip: text;
	background-clip: text;
	color: transparent;
}

.post-submit__subtitle {
	margin: 0 0 20px;
	max-width: 420px;
	color: rgba(var(--v-theme-on-surface), 0.7);
	font-size: 0.88rem;
	line-height: 1.5;
}

.post-submit__actions {
	display: flex;
	gap: 12px;
	flex-wrap: wrap;
	justify-content: center;
	width: 100%;
	max-width: 520px;
}

.post-submit__actions .pos-action-btn {
	flex: 1 1 200px;
	min-width: 180px;
}

.post-submit__divider {
	display: flex;
	align-items: center;
	gap: 12px;
	width: 100%;
	max-width: 360px;
	margin: 18px 0;
	color: rgba(var(--v-theme-on-surface), 0.5);
	font-size: 0.78rem;
	letter-spacing: 0.08em;
	text-transform: uppercase;
}

.post-submit__divider::before,
.post-submit__divider::after {
	content: "";
	flex: 1;
	height: 1px;
	background: linear-gradient(
		90deg,
		transparent,
		rgba(139, 92, 246, 0.35),
		transparent
	);
}

.post-submit__nav {
	display: flex;
	gap: 12px;
	flex-wrap: wrap;
	justify-content: center;
	width: 100%;
	max-width: 520px;
	padding-bottom: 8px;
}

.post-nav-btn {
	flex: 1 1 200px;
	min-width: 180px;
	color: #fff !important;
	border-radius: 10px !important;
	border: 1px solid transparent !important;
	transition: transform 0.15s ease, box-shadow 0.15s ease,
		filter 0.15s ease;
}

.post-nav-btn:not(:disabled):hover {
	transform: translateY(-1px);
	filter: brightness(1.05);
}

.post-nav-btn--primary {
	background: linear-gradient(
		135deg,
		rgba(139, 92, 246, 0.95),
		rgba(226, 54, 112, 0.95)
	) !important;
	box-shadow: 0 4px 14px rgba(139, 92, 246, 0.3) !important;
	border-color: rgba(167, 122, 250, 0.5) !important;
}

.post-nav-btn--primary:not(:disabled):hover {
	box-shadow: 0 6px 22px rgba(226, 54, 112, 0.4) !important;
}

.post-nav-btn--logout {
	background: linear-gradient(
		135deg,
		rgba(30, 41, 59, 0.95),
		rgba(51, 65, 85, 0.95)
	) !important;
	border-color: rgba(148, 163, 184, 0.35) !important;
	box-shadow: 0 2px 8px rgba(15, 23, 42, 0.3) !important;
}

.post-nav-btn--logout:not(:disabled):hover {
	box-shadow: 0 4px 16px rgba(15, 23, 42, 0.45) !important;
	border-color: rgba(244, 63, 94, 0.45) !important;
}

@media (max-width: 600px) {
	.post-submit-card {
		padding: 28px 20px 24px;
	}

	.post-submit__title {
		font-size: 1.15rem;
	}

	.post-submit__actions .pos-action-btn,
	.post-nav-btn {
		flex: 1 1 100%;
	}
}
</style>
