<template>
	<v-row justify="center">
		<v-dialog
			v-model="invoicesDialog"
			:max-width="returnsDialogMaxWidth"
			:fullscreen="isCompactReturns"
			:width="returnsDialogWidth"
			scrollable
			class="returns-dialog"
			:theme="isDarkTheme ? 'dark' : 'light'"
		>
			<v-card class="returns-card pos-themed-card" :theme="isDarkTheme ? 'dark' : 'light'">
				<v-card-title class="returns-card__title">
					<div class="returns-card__title-icon-wrap">
						<v-icon class="returns-card__title-icon">mdi-cash-refund</v-icon>
					</div>
					<div class="returns-card__title-copy">
						<span class="returns-card__title-text">{{ __("Select Return Invoice") }}</span>
						<span class="returns-card__subtitle">
							{{ __("Search an invoice and continue the return flow without extra steps.") }}
						</span>
					</div>
					<v-btn
						icon="mdi-close"
						variant="text"
						color="medium-emphasis"
						class="returns-card__close"
						:aria-label="__('Close returns dialog')"
						@click="close_dialog"
					/>
				</v-card-title>
				<v-container class="returns-card__content">
					<!-- Invoice ID and Date Range search -->
					<v-row class="mb-2" v-if="!from_date && !to_date">
						<v-col cols="12">
							<div class="returns-card__hint">
								<v-icon class="returns-card__hint-icon">mdi-information-outline</v-icon>
								<span>{{ __("Use date range to search for older invoices") }}</span>
							</div>
						</v-col>
					</v-row>
					<v-row class="mb-3">
						<v-col cols="12" sm="6">
							<v-text-field
								color="primary"
								:label="frappe._('Invoice ID')"
								class="pos-themed-input cc-field"
								hide-details
								v-model="invoice_name"
								density="compact"
								variant="outlined"
								prepend-inner-icon="mdi-receipt-text-outline"
								clearable
							></v-text-field>
						</v-col>
						<v-col cols="12" sm="3">
							<VueDatePicker
								v-model="from_date"
								model-type="format"
								format="dd-MM-yyyy"
								:enable-time-picker="false"
								auto-apply
								class="pos-themed-input cc-datepicker"
								placeholder="From date"
								@update:model-value="formatFromDate()"
							/>
						</v-col>
						<v-col cols="12" sm="3">
							<VueDatePicker
								v-model="to_date"
								model-type="format"
								format="dd-MM-yyyy"
								:enable-time-picker="false"
								auto-apply
								class="pos-themed-input cc-datepicker"
								placeholder="To date"
								@update:model-value="formatToDate()"
							/>
						</v-col>
					</v-row>

					<!-- Customer search fields -->
					<v-row class="mb-2">
						<v-col cols="12" sm="6">
							<v-text-field
								color="primary"
								:label="frappe._('Customer Name')"
								class="pos-themed-input cc-field"
								hide-details
								v-model="customer_name"
								density="compact"
								variant="outlined"
								prepend-inner-icon="mdi-account-outline"
								clearable
							></v-text-field>
						</v-col>
						<v-col cols="12" sm="6">
							<v-text-field
								color="primary"
								:label="frappe._('Customer ID')"
								class="pos-themed-input cc-field"
								hide-details
								v-model="customer_id"
								density="compact"
								variant="outlined"
								prepend-inner-icon="mdi-identifier"
								clearable
							></v-text-field>
						</v-col>
					</v-row>
					<v-row class="mb-3">
						<v-col cols="12" sm="6">
							<v-text-field
								color="primary"
								:label="frappe._('Mobile Number')"
								class="pos-themed-input cc-field"
								hide-details
								v-model="mobile_no"
								density="compact"
								variant="outlined"
								prepend-inner-icon="mdi-phone-outline"
								clearable
							></v-text-field>
						</v-col>
						<v-col cols="12" sm="6">
							<v-text-field
								color="primary"
								:label="frappe._('Tax ID')"
								class="pos-themed-input cc-field"
								hide-details
								v-model="tax_id"
								density="compact"
								variant="outlined"
								prepend-inner-icon="mdi-shield-account-outline"
								clearable
							></v-text-field>
						</v-col>
					</v-row>

					<!-- Amount Filter -->
					<v-row class="mb-3">
						<v-col cols="12" sm="6">
							<v-text-field
								color="primary"
								:label="frappe._('Minimum Amount')"
								class="pos-themed-input cc-field"
								hide-details
								v-model="min_amount"
								density="compact"
								variant="outlined"
								prepend-inner-icon="mdi-arrow-down-bold-outline"
								clearable
								type="number"
								min="0"
								placeholder="0"
							></v-text-field>
						</v-col>
						<v-col cols="12" sm="6">
							<v-text-field
								color="primary"
								:label="frappe._('Maximum Amount')"
								class="pos-themed-input cc-field"
								hide-details
								v-model="max_amount"
								density="compact"
								variant="outlined"
								prepend-inner-icon="mdi-arrow-up-bold-outline"
								clearable
								type="number"
								min="0"
								placeholder="No limit"
							></v-text-field>
						</v-col>
					</v-row>

					<v-row>
						<v-col cols="12" class="pt-0 pb-0">
							<v-divider class="returns-divider"></v-divider>
						</v-col>
					</v-row>

					<!-- Action buttons -->
					<v-row class="mt-2 mb-2 returns-actions">
						<v-col cols="12" sm="4" md="auto">
							<v-btn
								block
								class="cc-action cc-action--primary"
								@click="search_invoices"
							>
								<v-icon start>mdi-magnify</v-icon>
								{{ __("Search") }}
							</v-btn>
						</v-col>
						<v-col cols="12" sm="4" md="auto">
							<v-btn
								block
								class="cc-action cc-action--ghost"
								@click="clear_search"
							>
								<v-icon start>mdi-refresh</v-icon>
								{{ __("Clear") }}
							</v-btn>
						</v-col>
						<v-col
							cols="12"
							sm="4"
							md="auto"
							v-if="pos_profile.posa_allow_return_without_invoice == 1"
						>
							<v-btn
								block
								class="cc-action cc-action--violet"
								@click="return_without_invoice"
							>
								<v-icon start>mdi-receipt-text-remove-outline</v-icon>
								{{ __("Return without Invoice") }}
							</v-btn>
						</v-col>
					</v-row>

					<!-- Results -->
					<v-row>
						<v-col cols="12" class="pa-0 mt-1" v-if="dialog_data && dialog_data.length > 0">
							<div v-if="isCompactReturns" class="returns-results-list">
								<button
									v-for="item in dialog_data"
									:key="item.name"
									type="button"
									class="returns-result-card"
									:class="{
										'returns-result-card--selected': isSelectedInvoice(item),
										'returns-result-card--expired': item.posa_return_expired,
									}"
									@click="selectInvoice(item)"
								>
									<div class="returns-result-card__top">
										<div class="returns-result-card__identity">
											<strong>{{ item.customer }}</strong>
											<span>{{ item.name }}</span>
										</div>
										<div class="returns-result-card__amount">
											{{ currencySymbol(item.currency) }}{{ formatCurrency(item.grand_total) }}
										</div>
									</div>
									<div class="returns-result-card__meta">
										<span>{{ __("Date") }}: {{ formatDateDisplay(item.posting_date) }}</span>
										<span v-if="item.posa_return_valid_upto">
											{{ __("Valid until") }}:
											{{ formatDateDisplay(item.posa_return_valid_upto) }}
										</span>
									</div>
									<div class="returns-result-card__chips">
										<v-chip
											v-if="item.posa_return_expired"
											color="error"
											size="small"
											label
										>
											{{ __("Return window passed") }}
										</v-chip>
										<v-chip
											v-else-if="isSelectedInvoice(item)"
											color="primary"
											size="small"
											label
										>
											{{ __("Selected") }}
										</v-chip>
									</div>
								</button>
							</div>
							<v-data-table
								v-else
								:headers="headers"
								:items="dialog_data"
								item-key="name"
								class="elevation-1 returns-table"
								show-select
								v-model="selected"
								select-strategy="single"
								return-object
								:row-props="returnRowProps"
								:footer-props="{
									'items-per-page-options': [10, 25, 50, 100],
									'items-per-page-text': 'Invoices per page',
								}"
								:items-per-page="25"
							>
								<template v-slot:item.posting_date="{ item }">
									{{ formatDateDisplay(item.posting_date) }}
								</template>
								<template v-slot:item.posa_return_valid_upto="{ item }">
									<div class="d-flex align-center">
										<span v-if="item.posa_return_valid_upto">
											{{ formatDateDisplay(item.posa_return_valid_upto) }}
										</span>
										<v-chip
											v-if="item.posa_return_expired"
											color="error"
											size="small"
											class="ml-2"
											label
										>
											{{ __("Return window passed") }}
										</v-chip>
									</div>
								</template>
								<template v-slot:item.grand_total="{ item }">
									{{ currencySymbol(item.currency) }}
									{{ formatCurrency(item.grand_total) }}
								</template>
							</v-data-table>

							<!-- Load More button at the bottom of results -->
							<div class="text-center mt-3" v-if="has_more_invoices">
								<v-btn
									color="primary"
									variant="outlined"
									:loading="loading_more"
									@click="load_more_invoices"
								>
									{{ __("Load More Invoices") }}
								</v-btn>
							</div>
						</v-col>
						<v-col
							cols="12"
							class="text-center"
							v-else-if="searched_once && (!dialog_data || dialog_data.length === 0)"
						>
							<v-alert type="warning" text>
								{{ __("No invoices found. Try different search criteria.") }}
							</v-alert>
						</v-col>
					</v-row>
				</v-container>
				<v-card-actions class="mt-1 returns-card__footer">
					<v-btn class="cc-action cc-action--ghost-danger" @click="close_dialog">
						<v-icon start>mdi-close</v-icon>
						{{ __("Close") }}
					</v-btn>
					<v-btn
						v-if="selected.length"
						class="cc-action cc-action--success"
						@click="submit_dialog"
					>
						<v-icon start>mdi-check</v-icon>
						{{ __("Select") }}
					</v-btn>
				</v-card-actions>
			</v-card>
		</v-dialog>
	</v-row>
</template>

<script>
import format, { formatUtils } from "../../../format";
import { useInvoiceStore } from "../../../stores/invoiceStore.js";
import { useUIStore } from "../../../stores/uiStore.js";
import { computed } from "vue";
import { useResponsive } from "../../../composables/core/useResponsive";
import { useTheme } from "../../../composables/core/useTheme";

export default {
	mixins: [format],
	setup() {
		const invoiceStore = useInvoiceStore();
		const uiStore = useUIStore();
		const responsive = useResponsive();
		const theme = useTheme();
		const isCompactReturns = computed(() => responsive.windowWidth.value < 1100);
		const returnsDialogWidth = computed(() =>
			responsive.windowWidth.value < 600 ? "100vw" : "min(1120px, 96vw)",
		);
		const returnsDialogMaxWidth = computed(() =>
			responsive.windowWidth.value < 1100 ? "100vw" : "1120px",
		);
		return {
			invoiceStore,
			uiStore,
			isCompactReturns,
			returnsDialogWidth,
			returnsDialogMaxWidth,
			isDarkTheme: theme.isDark,
		};
	},
	data: () => ({
		invoicesDialog: false,
		singleSelect: true,
		selected: [],
		dialog_data: [],
		company: "",
		invoice_name: "",
		customer_name: "",
		customer_id: "",
		mobile_no: "",
		tax_id: "",
		from_date: null,
		to_date: null,
		from_date_formatted: null,
		to_date_formatted: null,
		min_amount: "",
		max_amount: "",
		pos_profile: "",
		page: 1,
		has_more_invoices: false,
		loading_more: false,
		searched_once: false,
		current_search_params: null,
		headers: [
			{
				title: __("Customer"),
				value: "customer",
				align: "start",
				sortable: true,
			},
			{
				title: __("Date"),
				align: "start",
				sortable: true,
				value: "posting_date",
			},
			{
				title: __("Invoice"),
				value: "name",
				align: "start",
				sortable: true,
			},
			{
				title: __("Return Valid Until"),
				value: "posa_return_valid_upto",
				align: "start",
				sortable: false,
			},
			{
				title: __("Amount"),
				value: "grand_total",
				align: "end",
				sortable: false,
			},
		],
	}),
	computed: {},
	watch: {
		from_date() {
			this.formatFromDate();
		},
		to_date() {
			this.formatToDate();
		},
	},
	methods: {
		isSelectedInvoice(item) {
			return Array.isArray(this.selected) && this.selected.some((entry) => entry?.name === item?.name);
		},
		selectInvoice(item) {
			this.selected = item ? [item] : [];
		},
		returnRowProps({ item }) {
			const rowClass = this.returnRowClass(item);
			return rowClass ? { class: rowClass } : {};
		},
		returnRowClass(item) {
			if (!item || typeof item !== "object") {
				return "";
			}
			return item.posa_return_expired ? "return-expired-row" : "";
		},
		formatDateDisplay(dateStr) {
			if (!dateStr) return "";
			try {
				const western = formatUtils.fromArabicNumerals(String(dateStr));
				const parts = western.split("-");
				if (parts.length === 3) {
					const formatted = `${parts[2]}-${parts[1]}-${parts[0]}`;
					return formatUtils.toArabicNumerals(formatted);
				}
			} catch (error) {
				console.error("Error formatting date:", error);
			}
			return formatUtils.toArabicNumerals(String(dateStr));
		},
		formatFromDate() {
			if (this.from_date) {
				try {
					let dateString = "";

					// Handle Date object
					if (typeof this.from_date === "object" && this.from_date instanceof Date) {
						const day = String(this.from_date.getDate()).padStart(2, "0");
						const month = String(this.from_date.getMonth() + 1).padStart(2, "0");
						const year = this.from_date.getFullYear();
						dateString = `${day}-${month}-${year}`;
					}
					// Handle string in YYYY-MM-DD format
					else if (typeof this.from_date === "string" && this.from_date.includes("-")) {
						const parts = formatUtils.fromArabicNumerals(this.from_date).split("-");
						if (parts.length === 3) {
							dateString = `${parts[2]}-${parts[1]}-${parts[0]}`;
						} else {
							dateString = formatUtils.fromArabicNumerals(this.from_date);
						}
					}
					// Handle any other format - just display as is
					else {
						dateString = formatUtils.fromArabicNumerals(String(this.from_date));
					}

					this.from_date_formatted = formatUtils.toArabicNumerals(dateString);
				} catch (error) {
					console.error("Error formatting from_date:", error);
					this.from_date_formatted = formatUtils.toArabicNumerals(String(this.from_date));
				}
			} else {
				this.from_date_formatted = null;
			}
		},
		formatToDate() {
			if (this.to_date) {
				try {
					let dateString = "";

					// Handle Date object
					if (typeof this.to_date === "object" && this.to_date instanceof Date) {
						const day = String(this.to_date.getDate()).padStart(2, "0");
						const month = String(this.to_date.getMonth() + 1).padStart(2, "0");
						const year = this.to_date.getFullYear();
						dateString = `${day}-${month}-${year}`;
					}
					// Handle string in YYYY-MM-DD format
					else if (typeof this.to_date === "string" && this.to_date.includes("-")) {
						const parts = formatUtils.fromArabicNumerals(this.to_date).split("-");
						if (parts.length === 3) {
							dateString = `${parts[2]}-${parts[1]}-${parts[0]}`;
						} else {
							dateString = formatUtils.fromArabicNumerals(this.to_date);
						}
					}
					// Handle any other format - just display as is
					else {
						dateString = formatUtils.fromArabicNumerals(String(this.to_date));
					}

					this.to_date_formatted = formatUtils.toArabicNumerals(dateString);
				} catch (error) {
					console.error("Error formatting to_date:", error);
					this.to_date_formatted = formatUtils.toArabicNumerals(String(this.to_date));
				}
			} else {
				this.to_date_formatted = null;
			}
		},
		clearFromDate() {
			this.from_date = null;
			this.from_date_formatted = null;
		},
		clearToDate() {
			this.to_date = null;
			this.to_date_formatted = null;
		},
		close_dialog() {
			this.invoicesDialog = false;
		},
		clear_search() {
			this.invoice_name = "";
			this.customer_name = "";
			this.customer_id = "";
			this.mobile_no = "";
			this.tax_id = "";
			this.from_date = null;
			this.to_date = null;
			this.from_date_formatted = null;
			this.to_date_formatted = null;
			this.min_amount = "";
			this.max_amount = "";
			this.dialog_data = [];
			this.page = 1;
			this.has_more_invoices = false;
			this.searched_once = false;
		},
		search_invoices_by_enter(e) {
			if (e.keyCode === 13) {
				this.search_invoices();
			}
		},
		search_invoices() {
			this.page = 1;
			this.dialog_data = [];
			this.perform_search();
		},
		perform_search() {
			const vm = this;
			vm.loading_more = true;

			// Format dates for API call in YYYY-MM-DD format
			let formattedFromDate = null;
			let formattedToDate = null;

			if (vm.from_date) {
				if (typeof vm.from_date === "object" && vm.from_date instanceof Date) {
					// Format Date object to YYYY-MM-DD
					formattedFromDate = [
						vm.from_date.getFullYear(),
						String(vm.from_date.getMonth() + 1).padStart(2, "0"),
						String(vm.from_date.getDate()).padStart(2, "0"),
					].join("-");
				} else if (typeof vm.from_date === "string") {
					const fromStr = formatUtils.fromArabicNumerals(vm.from_date);
					if (fromStr.includes("/")) {
						// Convert DD/MM/YYYY to YYYY-MM-DD
						const parts = fromStr.split("/");
						if (parts.length === 3) {
							formattedFromDate = `${parts[2]}-${parts[1]}-${parts[0]}`;
						}
					} else if (fromStr.includes("-")) {
						const parts = fromStr.split("-");
						if (parts.length === 3) {
							if (parts[0].length === 4) {
								formattedFromDate = fromStr; // Already YYYY-MM-DD
							} else {
								formattedFromDate = `${parts[2]}-${parts[1]}-${parts[0]}`;
							}
						}
					} else {
						// Invalid format, skip date filter
						formattedFromDate = null;
					}
				}
			}

			if (vm.to_date) {
				if (typeof vm.to_date === "object" && vm.to_date instanceof Date) {
					// Format Date object to YYYY-MM-DD
					formattedToDate = [
						vm.to_date.getFullYear(),
						String(vm.to_date.getMonth() + 1).padStart(2, "0"),
						String(vm.to_date.getDate()).padStart(2, "0"),
					].join("-");
				} else if (typeof vm.to_date === "string") {
					const toStr = formatUtils.fromArabicNumerals(vm.to_date);
					if (toStr.includes("/")) {
						// Convert DD/MM/YYYY to YYYY-MM-DD
						const parts = toStr.split("/");
						if (parts.length === 3) {
							formattedToDate = `${parts[2]}-${parts[1]}-${parts[0]}`;
						}
					} else if (toStr.includes("-")) {
						const parts = toStr.split("-");
						if (parts.length === 3) {
							if (parts[0].length === 4) {
								formattedToDate = toStr; // Already YYYY-MM-DD
							} else {
								formattedToDate = `${parts[2]}-${parts[1]}-${parts[0]}`;
							}
						}
					} else {
						// Invalid format, skip date filter
						formattedToDate = null;
					}
				}
			}

			// Process amount filters
			let minAmount = vm.min_amount ? parseFloat(formatUtils.fromArabicNumerals(vm.min_amount)) : null;
			let maxAmount = vm.max_amount ? parseFloat(formatUtils.fromArabicNumerals(vm.max_amount)) : null;

			// Save current search parameters for "load more" functionality
			this.current_search_params = {
				invoice_name: vm.invoice_name,
				customer_name: vm.customer_name,
				customer_id: vm.customer_id,
				mobile_no: vm.mobile_no,
				tax_id: vm.tax_id,
				from_date: formattedFromDate,
				to_date: formattedToDate,
				min_amount: minAmount,
				max_amount: maxAmount,
				company: vm.company,
				page: vm.page,
				pos_profile: vm.pos_profile?.name,
				doctype:
					vm.pos_profile && vm.pos_profile.create_pos_invoice_instead_of_sales_invoice
						? "POS Invoice"
						: "Sales Invoice",
			};

			frappe.call({
				method: "posawesome.mizan.api.invoices.search_invoices_for_return",
				args: this.current_search_params,
				callback: function (r) {
					vm.loading_more = false;
					vm.searched_once = true;

					if (r.message) {
						// If this is page 1, replace data, otherwise append
						if (vm.page === 1) {
							vm.dialog_data = r.message.invoices;
						} else {
							vm.dialog_data = [...vm.dialog_data, ...r.message.invoices];
						}

						// Set flag if there are more invoices to load
						vm.has_more_invoices = r.message.has_more;
					} else {
						vm.dialog_data = [];
						vm.has_more_invoices = false;
						vm.toastStore.show({
							title: __("No invoices found"),
							color: "warning",
						});
					}
				},
				error: function (err) {
					vm.loading_more = false;
					console.error("Error searching invoices:", err);
					vm.toastStore.show({
						title: __("Error searching invoices"),
						color: "error",
					});
				},
			});
		},
		load_more_invoices() {
			this.page += 1;
			this.perform_search();
		},
		return_without_invoice() {
			const invoice_doc = {};
			invoice_doc.items = [];
			invoice_doc.is_return = 1;
			// Pre-fill the customer from the POS profile default (e.g. "Daily
			// Cash Sales") so the cashier doesn't have to re-pick it after
			// every blank return.
			const defaultCustomer =
				this.pos_profile?.customer ||
				this.pos_profile?.posa_default_customer ||
				null;
			if (defaultCustomer) {
				invoice_doc.customer = defaultCustomer;
			}
			const data = { invoice_doc };
			this.eventBus.emit("load_return_invoice", data);
			this.invoicesDialog = false;
		},
		async submit_dialog() {
			if (this.selected.length > 0) {
				const selectedInvoice = this.selected[0];
				const doctype =
					this.pos_profile && this.pos_profile.create_pos_invoice_instead_of_sales_invoice
						? "POS Invoice"
						: "Sales Invoice";

				let return_doc = null;
				try {
					const { message } = await frappe.call({
						method: "posawesome.mizan.api.invoices.get_invoice_for_return",
						args: {
							invoice_name: selectedInvoice.name,
							pos_profile: this.pos_profile?.name,
							doctype,
						},
					});
					return_doc = message;
				} catch (error) {
					console.error("Error loading invoice for return:", error);
					this.toastStore.show({
						title: __("Error loading invoice details"),
						color: "error",
					});
					return;
				}

				if (!return_doc || !Array.isArray(return_doc.items) || return_doc.items.length === 0) {
					this.toastStore.show({
						title: __("No returnable items found for this invoice"),
						color: "warning",
					});
					return;
				}

				const invoice_doc = {};
				const items = [];

				return_doc.items.forEach((item) => {
					const new_item = { ...item };
					// reference original invoice row for backend validation
					if (return_doc.doctype === "POS Invoice") {
						new_item.pos_invoice_item = item.name;
					} else {
						new_item.sales_invoice_item = item.name;
					}
					delete new_item.name;

					// Preserve original pricing and discounts
					new_item.rate = item.rate;
					new_item.price_list_rate = item.price_list_rate;
					new_item.discount_percentage = item.discount_percentage;
					new_item.discount_amount = item.discount_amount;
					new_item.is_free_item = item.is_free_item;
					new_item.net_rate = item.net_rate;
					new_item.net_amount = item.net_amount > 0 ? item.net_amount * -1 : item.net_amount;
					new_item.locked_price = true;

					// Make sure quantities are negative for returns
					new_item.qty = item.qty > 0 ? item.qty * -1 : item.qty;
					new_item.stock_qty = item.stock_qty > 0 ? item.stock_qty * -1 : item.stock_qty;
					new_item.amount = item.amount > 0 ? item.amount * -1 : item.amount;
					items.push(new_item);
				});

				invoice_doc.items = items;
				invoice_doc.is_return = 1;
				invoice_doc.return_against = return_doc.name;
				invoice_doc.customer = return_doc.customer;
				invoice_doc.discount_amount = return_doc.discount_amount;
				invoice_doc.additional_discount_percentage = return_doc.additional_discount_percentage;
				// Carry over MOP shape but ZERO the amounts. The original
				// invoice's `amount` / `base_amount` belong to the original
				// sale's exchange rate snapshot — reusing them on a return
				// drafted today produces stale figures, and on a foreign-
				// currency invoice ERPNext core's `update_multi_mode_option`
				// can confuse pre-stamped `base_amount` with the invoice-
				// currency `amount` and land the wrong value in the saved
				// row. Letting the cashier enter the refund afresh keeps the
				// payment row in sync with today's `conversion_rate`.
				invoice_doc.payments = Array.isArray(return_doc.payments)
					? return_doc.payments.map((payment) => ({
							mode_of_payment: payment.mode_of_payment,
							amount: 0,
							base_amount: 0,
							default: payment.default,
							account: payment.account,
							type: payment.type,
							currency: payment.currency,
						}))
					: [];

				// Make sure grand_total is negative for returns
				if (return_doc.grand_total > 0) {
					invoice_doc.grand_total = return_doc.grand_total * -1;
				} else {
					invoice_doc.grand_total = return_doc.grand_total;
				}

				// These fields ensure proper return handling
				invoice_doc.update_stock = 1;
				invoice_doc.pos_profile = this.pos_profile.name;
				invoice_doc.company = this.company;

				const data = { invoice_doc, return_doc };

				this.eventBus.emit("load_return_invoice", data);
				this.invoicesDialog = false;
			}
		},
	},
	created: function () {
		this.eventBus.on("open_returns", (data) => {
			this.invoicesDialog = true;
			this.company = data;
			this.invoice_name = "";
			this.customer_name = "";
			this.customer_id = "";
			this.mobile_no = "";
			this.tax_id = "";
			this.from_date = null;
			this.to_date = null;
			this.from_date_formatted = null;
			this.to_date_formatted = null;
			this.min_amount = "";
			this.max_amount = "";
			this.dialog_data = [];
			this.selected = [];
			this.page = 1;
			this.has_more_invoices = false;
			this.searched_once = false;
		});

		this.$watch(
			() => this.uiStore.posProfile,
			(profile) => {
				if (profile) this.pos_profile = profile;
			},
			{ deep: false, immediate: true },
		);
	},
	beforeUnmount() {
		this.eventBus.off("open_returns");
	},
};
</script>

<style scoped>
.return-expired-row {
	background-color: color-mix(in srgb, var(--pos-error) 14%, var(--pos-surface)) !important;
}

.returns-card {
	display: flex;
	flex-direction: column;
	max-height: min(92vh, 100%);
	background: var(--pos-card-bg, #0e131e) !important;
	color: var(--pos-text-primary) !important;
	border: 1px solid var(--pos-border, #252b37);
	border-radius: 18px;
	overflow: hidden;
	box-shadow:
		0 20px 48px rgba(0, 0, 0, 0.55),
		0 0 0 1px rgba(226, 54, 112, 0.08);
	animation: returns-card-slide 0.32s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes returns-card-slide {
	from {
		opacity: 0;
		transform: translateY(-12px) scale(0.985);
	}
	to {
		opacity: 1;
		transform: translateY(0) scale(1);
	}
}

.returns-card__title {
	display: flex;
	align-items: center;
	gap: 14px;
	padding: 18px 22px;
	background:
		linear-gradient(135deg, rgba(226, 54, 112, 0.1), rgba(139, 92, 246, 0.06)),
		var(--pos-surface-muted, #161c27);
	border-bottom: 1px solid var(--pos-border, #252b37);
	flex-shrink: 0;
}

.returns-card__title-icon-wrap {
	background: linear-gradient(135deg, rgba(226, 54, 112, 0.22), rgba(139, 92, 246, 0.2));
	border: 1px solid rgba(226, 54, 112, 0.35);
	border-radius: 12px;
	width: 42px;
	height: 42px;
	display: flex;
	align-items: center;
	justify-content: center;
	flex-shrink: 0;
}

.returns-card__title-icon {
	font-size: 22px !important;
	color: var(--pos-primary, #e23670) !important;
}

.returns-card__title-copy {
	display: flex;
	flex-direction: column;
	gap: 2px;
	min-width: 0;
	flex: 1;
}

.returns-card__title-text {
	font-size: 1.1rem;
	font-weight: 700;
	line-height: 1.2;
	color: var(--pos-text-primary, #e7ebf3);
	letter-spacing: 0.01em;
}

.returns-card__subtitle {
	font-size: 0.82rem;
	line-height: 1.35;
	color: var(--pos-text-secondary, #8595ab);
}

.returns-card__close {
	flex-shrink: 0;
	color: var(--pos-text-secondary, #8595ab) !important;
}

.returns-card__close:hover {
	color: var(--pos-text-primary, #e7ebf3) !important;
	background: rgba(226, 54, 112, 0.08) !important;
}

.returns-card__content {
	flex: 1 1 auto;
	overflow: auto;
	padding: 18px 22px 16px;
	background: var(--pos-card-bg, #0e131e);
}

.returns-card__hint {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 10px 14px;
	border-radius: 12px;
	background: linear-gradient(
		135deg,
		rgba(226, 54, 112, 0.08),
		rgba(139, 92, 246, 0.06)
	);
	border: 1px solid rgba(226, 54, 112, 0.22);
	color: var(--pos-text-secondary, #8595ab);
	font-size: 0.82rem;
	line-height: 1.35;
}

.returns-card__hint-icon {
	font-size: 18px !important;
	color: var(--pos-primary, #e23670) !important;
	flex-shrink: 0;
}

.returns-divider {
	border-color: var(--pos-border, #252b37) !important;
	opacity: 0.6;
}

.returns-actions {
	align-items: stretch;
}

/* ── CC field chrome (flat hairline, focus glow) ────────────────── */
.cc-field :deep(.v-field) {
	border-radius: 10px !important;
	background: var(--pos-surface-muted, #161c27) !important;
	min-height: 42px !important;
	box-shadow: inset 0 0 0 1px var(--pos-border, #252b37) !important;
	transition: box-shadow 0.2s ease;
}

.cc-field :deep(.v-field__overlay) {
	background: transparent !important;
	opacity: 0 !important;
}

.cc-field :deep(.v-field__outline) {
	display: none !important;
}

.cc-field :deep(.v-field--focused) {
	box-shadow:
		inset 0 0 0 1.5px var(--pos-primary, #e23670),
		0 0 0 3px rgba(226, 54, 112, 0.14) !important;
}

.cc-field :deep(.v-field__input) {
	min-height: 42px !important;
	font-size: 0.9rem;
	color: var(--pos-text-primary, #e7ebf3) !important;
}

.cc-field :deep(.v-label) {
	color: var(--pos-text-secondary, #8595ab) !important;
}

.cc-field :deep(.v-field__prepend-inner .v-icon) {
	color: var(--pos-primary, #e23670);
	opacity: 0.85;
}

/* Date pickers: align with cc-field chrome */
.cc-datepicker :deep(.dp__input) {
	border-radius: 10px !important;
	background: var(--pos-surface-muted, #161c27) !important;
	min-height: 42px !important;
	border: 1px solid var(--pos-border, #252b37) !important;
	color: var(--pos-text-primary, #e7ebf3) !important;
	font-size: 0.9rem !important;
	padding-left: 38px !important;
	transition: box-shadow 0.2s ease, border-color 0.2s ease;
}

.cc-datepicker :deep(.dp__input:focus) {
	border-color: var(--pos-primary, #e23670) !important;
	box-shadow: 0 0 0 3px rgba(226, 54, 112, 0.14) !important;
}

.cc-datepicker :deep(.dp__input_icon) {
	color: var(--pos-primary, #e23670) !important;
	opacity: 0.85;
}

/* ── CC action buttons ──────────────────────────────────────────── */
.cc-action.v-btn {
	min-height: 42px;
	border-radius: 10px;
	font-weight: 600;
	letter-spacing: 0.02em;
	text-transform: none;
	box-shadow: none !important;
	transition:
		transform 0.15s ease,
		box-shadow 0.2s ease,
		filter 0.15s ease;
}

.cc-action.v-btn:hover {
	transform: translateY(-1px);
}

.cc-action--primary.v-btn {
	background: linear-gradient(135deg, #e23670, #b81e54) !important;
	color: #fff !important;
	border: 1px solid rgba(226, 54, 112, 0.55);
}

.cc-action--primary.v-btn:hover {
	box-shadow: 0 8px 18px rgba(226, 54, 112, 0.32) !important;
	filter: brightness(1.05);
}

.cc-action--violet.v-btn {
	background: linear-gradient(135deg, #8b5cf6, #6d3ee0) !important;
	color: #fff !important;
	border: 1px solid rgba(139, 92, 246, 0.55);
}

.cc-action--violet.v-btn:hover {
	box-shadow: 0 8px 18px rgba(139, 92, 246, 0.32) !important;
	filter: brightness(1.05);
}

.cc-action--success.v-btn {
	background: linear-gradient(135deg, #10b981, #059669) !important;
	color: #fff !important;
	border: 1px solid rgba(16, 185, 129, 0.55);
}

.cc-action--success.v-btn:hover {
	box-shadow: 0 8px 18px rgba(16, 185, 129, 0.32) !important;
	filter: brightness(1.05);
}

.cc-action--ghost.v-btn {
	background: var(--pos-surface-muted, #161c27) !important;
	color: var(--pos-text-primary, #e7ebf3) !important;
	border: 1px solid var(--pos-border, #252b37);
}

.cc-action--ghost.v-btn:hover {
	border-color: rgba(226, 54, 112, 0.45);
	background: rgba(226, 54, 112, 0.06) !important;
}

.cc-action--ghost-danger.v-btn {
	background: transparent !important;
	color: var(--pos-error, #ef4444) !important;
	border: 1px solid rgba(239, 68, 68, 0.45);
}

.cc-action--ghost-danger.v-btn:hover {
	background: rgba(239, 68, 68, 0.08) !important;
	border-color: rgba(239, 68, 68, 0.7);
}

.returns-results-list {
	display: flex;
	flex-direction: column;
	gap: 10px;
	padding: 4px 0;
}

.returns-result-card {
	width: 100%;
	border: 1px solid var(--pos-border);
	border-radius: 18px;
	background: var(--pos-card-bg);
	padding: 14px;
	text-align: left;
	cursor: pointer;
	transition:
		border-color 0.18s ease,
		box-shadow 0.18s ease,
		transform 0.18s ease;
}

.returns-result-card:hover {
	border-color: color-mix(in srgb, var(--pos-primary) 28%, var(--pos-border));
	box-shadow: 0 10px 24px var(--pos-shadow);
	transform: translateY(-1px);
}

.returns-result-card--selected {
	border-color: var(--pos-primary);
	box-shadow: 0 0 0 2px color-mix(in srgb, var(--pos-primary) 14%, transparent);
}

.returns-result-card--expired {
	background: color-mix(in srgb, var(--pos-error) 6%, var(--pos-surface));
}

.returns-result-card__top {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 12px;
}

.returns-result-card__identity {
	display: flex;
	flex-direction: column;
	gap: 3px;
	min-width: 0;
}

.returns-result-card__identity strong,
.returns-result-card__amount {
	color: var(--pos-text-primary);
}

.returns-result-card__identity span,
.returns-result-card__meta {
	color: var(--pos-text-secondary);
	font-size: 0.86rem;
}

.returns-result-card__amount {
	font-weight: 700;
	white-space: nowrap;
}

.returns-result-card__meta {
	display: flex;
	flex-direction: column;
	gap: 4px;
	margin-top: 10px;
}

.returns-result-card__chips {
	display: flex;
	flex-wrap: wrap;
	gap: 8px;
	margin-top: 10px;
}

.returns-card__footer {
	position: sticky;
	bottom: 0;
	display: flex;
	justify-content: flex-end;
	gap: 12px;
	padding: 14px 22px 18px;
	background:
		linear-gradient(135deg, rgba(226, 54, 112, 0.06), rgba(139, 92, 246, 0.04)),
		var(--pos-surface-muted, #161c27);
	border-top: 1px solid var(--pos-border, #252b37);
}

.returns-table :deep(.v-table),
.returns-table :deep(.v-table__wrapper),
.returns-table :deep(table),
.returns-table :deep(thead),
.returns-table :deep(tbody),
.returns-table :deep(tr),
.returns-table :deep(td),
.returns-table :deep(th) {
	background: var(--pos-surface) !important;
	color: var(--pos-text-primary) !important;
}

.returns-table :deep(th) {
	background: var(--pos-table-header-bg) !important;
}

.returns-table :deep(tbody tr:hover) {
	background: var(--pos-table-row-hover) !important;
}

@media (max-width: 1279px) {
	.returns-card {
		max-height: 100vh;
		height: 100vh;
		border-radius: 0;
	}

	.returns-card__title {
		position: sticky;
		top: 0;
		z-index: 2;
		padding: 14px 14px 12px;
		background:
			linear-gradient(135deg, rgba(226, 54, 112, 0.1), rgba(139, 92, 246, 0.06)),
			var(--pos-surface-muted, #161c27);
		border-bottom: 1px solid var(--pos-border, #252b37);
	}

	.returns-card__title-icon-wrap {
		width: 38px;
		height: 38px;
	}

	.returns-card__title-text {
		font-size: 1rem;
	}

	.returns-card__content {
		padding-left: 12px;
		padding-right: 12px;
		padding-bottom: 12px;
	}

	.returns-card__footer {
		padding: 12px;
	}

	.returns-card__footer .v-btn {
		flex: 1 1 0;
		min-height: 46px;
	}
}

@media (max-width: 767px) {
	.returns-result-card {
		padding: 12px;
	}

	.returns-result-card__top {
		flex-direction: column;
	}

	.returns-result-card__amount {
		white-space: normal;
	}

	.returns-card__subtitle {
		font-size: 0.82rem;
	}
}
</style>
