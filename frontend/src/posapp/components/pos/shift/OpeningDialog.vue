<template>
	<v-row justify="center">
		<v-dialog v-model="isOpen" persistent max-width="880px" max-height="92vh">
			<v-card elevation="8" class="opening-dialog-card">
				<!-- Header -->
				<div class="opening-dialog-header">
					<div class="opening-dialog-header__icon-wrap">
						<v-icon class="opening-dialog-header__icon">mdi-cash-plus</v-icon>
					</div>
					<div class="opening-dialog-header__text">
						<h5 class="opening-dialog-header__title">{{ __("Create POS Opening Shift") }}</h5>
						<p class="opening-dialog-header__subtitle">
							{{ __("Initialize your shift with opening balances") }}
						</p>
					</div>
				</div>

				<!-- Content -->
				<div class="opening-dialog-content">
					<!-- Company (only shown when there are multiple companies). When a
					     single company is available we silently default to it and hide
					     the picker entirely so cashiers only see the choice they
					     actually have. -->
					<div v-if="showCompanyField" class="opening-dialog-content__row">
						<v-autocomplete
							:items="companies"
							:label="frappe._('Company')"
							v-model="company"
							required
							variant="outlined"
							color="primary"
							density="compact"
							hide-details
							prepend-inner-icon="mdi-domain"
							class="cc-field"
						/>
					</div>

					<!-- POS Profile picker — collapsible list-style card with typeahead
					     search. Closed by default so a tenant with 20–50 profiles
					     doesn't blow out the dialog. The trigger button shows the
					     currently-selected profile (or a prompt) and toggles open. -->
					<div
						class="pos-profile-picker"
						:class="{
							'pos-profile-picker--selected': pos_profile,
							'pos-profile-picker--expanded': pickerExpanded,
						}"
					>
						<div class="pos-profile-picker__header">
							<v-icon size="18" class="pos-profile-picker__header-icon">mdi-point-of-sale</v-icon>
							<span class="pos-profile-picker__title">
								{{ __("Select POS Profile to start") }}
							</span>
						</div>

						<label class="pos-profile-picker__label">
							{{ __("POS Profile") }} <span class="pos-profile-picker__required">*</span>
						</label>

						<button
							type="button"
							class="pos-profile-picker__trigger"
							:class="{ 'pos-profile-picker__trigger--placeholder': !pos_profile }"
							:aria-expanded="pickerExpanded"
							aria-haspopup="listbox"
							@click="togglePicker"
						>
							<v-icon size="18" class="pos-profile-picker__trigger-icon">
								mdi-point-of-sale
							</v-icon>
							<span class="pos-profile-picker__trigger-label">
								{{
									pos_profile
										? pos_profile
										: pos_profiles.length
											? __("Choose a POS profile…")
											: __("No POS profiles available")
								}}
							</span>
							<v-icon
								size="20"
								class="pos-profile-picker__trigger-caret"
								:class="{ 'pos-profile-picker__trigger-caret--open': pickerExpanded }"
							>
								mdi-chevron-down
							</v-icon>
						</button>

						<!-- Expandable panel: search + scrollable list. Hidden when
						     collapsed so tall lists never push the action bar
						     off-screen. -->
						<div v-show="pickerExpanded" class="pos-profile-picker__panel">
							<v-text-field
								v-model="posProfileSearch"
								:placeholder="frappe._('Type to search POS profile...')"
								variant="outlined"
								density="compact"
								hide-details
								prepend-inner-icon="mdi-magnify"
								clearable
								class="pos-profile-picker__search"
								ref="profileSearchField"
							/>

							<div
								class="pos-profile-picker__list"
								role="listbox"
								:aria-label="__('POS profiles')"
							>
								<button
									v-for="item in filteredPosProfiles"
									:key="item"
									type="button"
									class="pos-profile-picker__option"
									:class="{ 'pos-profile-picker__option--active': pos_profile === item }"
									role="option"
									:aria-selected="pos_profile === item"
									@click="selectProfile(item)"
								>
									<v-icon size="16" class="pos-profile-picker__option-icon">
										mdi-point-of-sale
									</v-icon>
									<span class="pos-profile-picker__option-label">{{ item }}</span>
									<v-icon v-if="pos_profile === item" size="16" class="pos-profile-picker__option-check">
										mdi-check-circle
									</v-icon>
								</button>
								<div v-if="!filteredPosProfiles.length" class="pos-profile-picker__empty">
									<v-icon size="20" class="pos-profile-picker__empty-icon">mdi-store-search-outline</v-icon>
									<span>{{ pos_profiles.length
										? __("No POS profiles match your search")
										: __("No POS profiles available for this company") }}</span>
								</div>
							</div>
						</div>
					</div>

					<!-- Payment Methods -->
					<div class="payment-methods-section">
						<div class="payment-methods-section__header">
							<v-icon size="18" class="payment-methods-section__icon">mdi-credit-card-multiple</v-icon>
							<h6 class="payment-methods-section__title">{{ __("Payment Methods") }}</h6>
						</div>

						<v-data-table
							:headers="payments_methods_headers"
							:items="payments_methods"
							item-key="mode_of_payment"
							class="payment-methods-table"
							:items-per-page="itemsPerPage"
							hide-default-footer
							density="compact"
							:height="'260px'"
							fixed-header
						>
							<template v-slot:item.amount="{ item }">
								<v-text-field
									v-model="item.amount"
									:rules="[max25chars]"
									type="number"
									density="compact"
									variant="outlined"
									color="primary"
									hide-details
									:prefix="currencySymbol(item.currency)"
									class="payment-methods-table__amount"
								/>
							</template>
						</v-data-table>
					</div>
				</div>

				<!-- Actions -->
				<div class="dialog-actions-container">
					<v-btn
						theme="dark"
						@click="logout"
						class="pos-action-btn pos-action-btn--logout"
						size="large"
						elevation="0"
					>
						<v-icon start>mdi-logout</v-icon>
						<span>{{ __("Logout") }}</span>
					</v-btn>
					<v-spacer />
					<v-btn
						theme="dark"
						@click="go_desk"
						class="pos-action-btn pos-action-btn--close"
						size="large"
						elevation="0"
					>
						<v-icon start>mdi-close-circle-outline</v-icon>
						<span>{{ __("Close") }}</span>
					</v-btn>
					<v-btn
						theme="dark"
						:disabled="is_loading || !pos_profile || !company"
						:loading="is_loading"
						@click="submit_dialog"
						class="pos-action-btn pos-action-btn--submit"
						size="large"
						elevation="0"
					>
						<v-icon start>mdi-check-circle-outline</v-icon>
						<span>{{ __("Submit") }}</span>
					</v-btn>
				</div>
			</v-card>
		</v-dialog>
	</v-row>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import {
	getOpeningDialogStorage,
	setOpeningDialogStorage,
	setOpeningStorage,
	getBootstrapSnapshot,
	setBootstrapSnapshot,
	initPromise,
	checkDbHealth,
} from "../../../../offline/index";
import { createBootstrapSnapshotFromRegisterData } from "../../../../offline/bootstrapSnapshot";

defineOptions({
	name: "OpeningDialog",
});

const props = defineProps({
	dialog: Boolean,
});

const emit = defineEmits(["close", "register"]);
const __ = window.__ || ((text) => text);
const get_currency_symbol = window.get_currency_symbol;
const BUILD_VERSION =
	typeof __BUILD_VERSION__ !== "undefined" ? __BUILD_VERSION__ : null;

const isOpen = ref(props.dialog ? props.dialog : false);
const is_loading = ref(false);
const companies = ref([]);
const company = ref("");
const pos_profiles_data = ref([]);
const pos_profiles = ref([]);
const pos_profile = ref("");
const posProfileSearch = ref("");
// Picker visibility — closed by default. With 20–50 profiles in some
// tenants an always-open list pushed the action bar off-screen and
// hijacked scroll, so we now require an explicit click to expand.
const pickerExpanded = ref(false);
const profileSearchField = ref(null);
const payments_method_data = ref([]);
const payments_methods = ref([]);
const payments_methods_headers = [
	{
		title: __("Mode of Payment"),
		align: "start",
		sortable: false,
		value: "mode_of_payment",
	},
	{
		title: __("Opening Amount"),
		value: "amount",
		align: "center",
		sortable: false,
	},
];
const itemsPerPage = ref(100);
const max25chars = (v) => v.length <= 12 || "Input too long!";

const currencySymbol = (currency) => get_currency_symbol?.(currency);

// Single-company tenants skip the picker entirely — the default from
// `get_opening_dialog_data` is already correct, so we just hide the field.
const showCompanyField = computed(() => companies.value.length > 1);

const filteredPosProfiles = computed(() => {
	const query = (posProfileSearch.value || "").trim().toLowerCase();
	if (!query) return pos_profiles.value;
	return pos_profiles.value.filter((name) =>
		String(name || "").toLowerCase().includes(query),
	);
});

watch(
	() => props.dialog,
	(val) => {
		isOpen.value = val ? val : false;
	},
);

watch(company, (val) => {
	pos_profiles.value = [];
	pos_profiles_data.value.forEach((element) => {
		if (element.company === val) {
			pos_profiles.value.push(element.name);
		}
		if (pos_profiles.value.length) {
			pos_profile.value = pos_profiles.value[0];
		} else {
			pos_profile.value = "";
		}
	});
	// Clear the search so the newly-loaded list is fully visible when
	// the user switches company.
	posProfileSearch.value = "";
});

watch(pos_profile, (val) => {
	payments_methods.value = [];
	payments_method_data.value.forEach((element) => {
		if (element.parent === val) {
			payments_methods.value.push({
				mode_of_payment: element.mode_of_payment,
				amount: 0,
				currency: element.currency,
			});
		}
	});
});

// ── Picker open/close + selection helpers ──────────────────────────
// `togglePicker` is the trigger button's click handler. Opening the
// picker focuses the search field on next tick so the cashier can
// just type — no extra click required.
function togglePicker() {
	pickerExpanded.value = !pickerExpanded.value;
	if (pickerExpanded.value) {
		nextTick(() => {
			try {
				profileSearchField.value?.focus?.();
			} catch (_e) {
				// Field ref might not be a Vuetify component (test stubs etc.)
			}
		});
	} else {
		// Reset the search filter when collapsing so the next open
		// shows the full list, not the filtered remnant.
		posProfileSearch.value = "";
	}
}

// `selectProfile` collapses the picker on choice — once a profile is
// picked the cashier's next action is the Submit button at the bottom,
// not more list browsing.
function selectProfile(name) {
	pos_profile.value = name;
	pickerExpanded.value = false;
	posProfileSearch.value = "";
}

async function get_opening_dialog_data() {
	await initPromise;
	await checkDbHealth();

	// Load cached data first for offline usage
	const cached = getOpeningDialogStorage();
	if (cached) {
		try {
			companies.value = cached.companies.map((c) => c.name);
			pos_profiles_data.value = cached.pos_profiles_data || [];
			payments_method_data.value = cached.payments_method || [];
			company.value = companies.value[0] || "";
		} catch (e) {
			console.error("Failed to parse opening dialog cache", e);
		}
	}

	frappe.call({
		method: "posawesome.posawesome.api.shifts.get_opening_dialog_data",
		args: {},
		callback: function (r) {
			if (r.message) {
				companies.value = r.message.companies.map((element) => element.name);
				pos_profiles_data.value = r.message.pos_profiles_data;
				payments_method_data.value = r.message.payments_method;
				company.value = companies.value[0] || "";
				try {
					setOpeningDialogStorage(r.message);
				} catch (e) {
					console.error("Failed to cache opening dialog data", e);
				}
			}
		},
	});
}

function submit_dialog() {
	if (!payments_methods.value.length || !company.value || !pos_profile.value) {
		return;
	}

	is_loading.value = true;

	return frappe
		.call("posawesome.posawesome.api.shifts.create_opening_voucher", {
			pos_profile: pos_profile.value,
			company: company.value,
			balance_details: payments_methods.value,
		})
		.then((r) => {
			if (r.message) {
				emit("register", r.message);
				try {
					setOpeningStorage(r.message);
					setBootstrapSnapshot(
						createBootstrapSnapshotFromRegisterData(
							r.message,
							getBootstrapSnapshot(),
							{ buildVersion: BUILD_VERSION },
						),
					);
				} catch (e) {
					console.error("Failed to cache opening data", e);
				}
				// Close handles hiding the dialog, parent handles logic
				emit("close");
				is_loading.value = false;
			}
		});
}

function go_desk() {
	frappe.set_route("/");
	location.reload();
}

function logout() {
	const redirectTarget = "/app/posapp";
	const loginPath = `/login?redirect-to=${encodeURIComponent(redirectTarget)}`;
	frappe.call("logout").finally(() => {
		const loginUrl =
			frappe?.utils?.get_url?.(loginPath) ??
			(frappe?.urllib?.get_base_url?.() ? `${frappe.urllib.get_base_url()}${loginPath}` : loginPath);
		window.location.href = loginUrl;
	});
}

onMounted(() => {
	get_opening_dialog_data();
});
</script>

<style scoped>
/* ── Main dialog card ─────────────────────────────────────────────
   CC-themed: dark tier-1 surface, hairline border, subtle pink glow
   along the top so the card feels like a focused modal, not a pop. */
.opening-dialog-card {
	border-radius: 18px;
	overflow: hidden;
	background: var(--pos-card-bg) !important;
	color: var(--pos-text-primary) !important;
	border: 1px solid var(--pos-border, #252b37);
	box-shadow:
		0 20px 48px rgba(0, 0, 0, 0.55),
		0 0 0 1px rgba(226, 54, 112, 0.08);
	max-height: 92vh;
	display: flex;
	flex-direction: column;
	animation: opening-dialog-slide 0.35s cubic-bezier(0.22, 1, 0.36, 1);
	font-family: var(--posa-font-family, "Space Grotesk", sans-serif);
}

/* Inherit the CC font through every interior label, button, table cell,
   and field input so nothing falls back to the default Vuetify Roboto. */
.opening-dialog-card,
.opening-dialog-card :deep(*) {
	font-family: var(--posa-font-family, "Space Grotesk", sans-serif);
}

@keyframes opening-dialog-slide {
	from {
		opacity: 0;
		transform: translateY(-14px) scale(0.985);
	}
	to {
		opacity: 1;
		transform: translateY(0) scale(1);
	}
}

/* ── Header ──────────────────────────────────────────────────────── */
.opening-dialog-header {
	display: flex;
	align-items: center;
	gap: 14px;
	padding: 18px 24px;
	background:
		linear-gradient(135deg, rgba(226, 54, 112, 0.1), rgba(139, 92, 246, 0.06)),
		var(--pos-surface-muted, #161c27);
	border-bottom: 1px solid var(--pos-border, #252b37);
	flex-shrink: 0;
}

.opening-dialog-header__icon-wrap {
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

.opening-dialog-header__icon {
	font-size: 22px !important;
	color: var(--pos-primary, #e23670) !important;
}

.opening-dialog-header__text {
	flex: 1;
	min-width: 0;
}

.opening-dialog-header__title {
	margin: 0;
	font-size: 1.1rem;
	font-weight: 700;
	line-height: 1.2;
	color: var(--pos-text-primary, #e7ebf3);
	letter-spacing: 0.01em;
}

.opening-dialog-header__subtitle {
	margin: 2px 0 0 0;
	font-size: 0.82rem;
	line-height: 1.3;
	color: var(--pos-text-secondary, #8595ab);
}

/* ── Content ─────────────────────────────────────────────────────── */
.opening-dialog-content {
	padding: 18px 22px 20px;
	background: var(--pos-card-bg, #0e131e);
	flex: 1;
	overflow-y: auto;
	display: flex;
	flex-direction: column;
	gap: 14px;
}

.opening-dialog-content__row {
	width: 100%;
}

/* ── Shared field chrome (Company + search + amounts) ─────────────
   Same flat-hairline treatment we use across the app: zero the three
   Vuetify outline segments, draw a single inset box-shadow, swap the
   overlay. */
.cc-field :deep(.v-field),
.pos-profile-picker__search :deep(.v-field),
.payment-methods-table__amount :deep(.v-field) {
	border-radius: 10px !important;
	background: var(--pos-surface-muted, #161c27) !important;
	min-height: 42px !important;
	box-shadow: inset 0 0 0 1px var(--pos-border, #252b37) !important;
	transition: box-shadow 0.2s ease;
}

.cc-field :deep(.v-field__overlay),
.pos-profile-picker__search :deep(.v-field__overlay),
.payment-methods-table__amount :deep(.v-field__overlay) {
	background: transparent !important;
	opacity: 0 !important;
}

.cc-field :deep(.v-field__outline),
.pos-profile-picker__search :deep(.v-field__outline),
.payment-methods-table__amount :deep(.v-field__outline) {
	display: none !important;
}

.cc-field :deep(.v-field--focused),
.pos-profile-picker__search :deep(.v-field--focused),
.payment-methods-table__amount :deep(.v-field--focused) {
	box-shadow:
		inset 0 0 0 1.5px var(--pos-primary, #e23670),
		0 0 0 3px rgba(226, 54, 112, 0.14) !important;
}

.cc-field :deep(.v-field__input),
.pos-profile-picker__search :deep(.v-field__input) {
	min-height: 42px !important;
	font-size: 0.92rem;
	color: var(--pos-text-primary, #e7ebf3) !important;
}

.cc-field :deep(.v-label),
.pos-profile-picker__search :deep(.v-label) {
	color: var(--pos-text-secondary, #8595ab) !important;
}

.cc-field :deep(.v-field__prepend-inner .v-icon),
.pos-profile-picker__search :deep(.v-field__prepend-inner .v-icon) {
	color: var(--pos-primary, #e23670);
	opacity: 0.9;
}

/* ── POS profile picker ───────────────────────────────────────────
   Card-in-card pattern inspired by the "SELECT WAREHOUSES TO START
   PICKING" picker in the order-pick flow. Violet accent so it reads
   as a primary call-to-action inside the dialog, with a typeahead
   search on top of a scrollable list (no native dropdown). */
.pos-profile-picker {
	border-radius: 14px;
	border: 1px solid rgba(139, 92, 246, 0.35);
	background:
		linear-gradient(135deg, rgba(139, 92, 246, 0.05), rgba(226, 54, 112, 0.03)),
		var(--pos-surface-muted, #161c27);
	padding: 14px 14px 10px;
	display: flex;
	flex-direction: column;
	gap: 8px;
	box-shadow:
		inset 0 0 0 1px rgba(139, 92, 246, 0.15),
		0 4px 18px rgba(139, 92, 246, 0.08);
	transition: box-shadow 0.25s ease, border-color 0.25s ease;
}

.pos-profile-picker--selected {
	border-color: rgba(139, 92, 246, 0.55);
	box-shadow:
		inset 0 0 0 1px rgba(139, 92, 246, 0.35),
		0 6px 22px rgba(139, 92, 246, 0.18);
}

.pos-profile-picker__header {
	display: flex;
	align-items: center;
	gap: 8px;
}

.pos-profile-picker__header-icon {
	color: #a78bfa;
}

.pos-profile-picker__title {
	font-size: 0.76rem;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: 0.12em;
	background: linear-gradient(90deg, #a78bfa, #e23670);
	-webkit-background-clip: text;
	background-clip: text;
	color: transparent;
}

.pos-profile-picker__label {
	font-size: 0.72rem;
	font-weight: 600;
	text-transform: uppercase;
	letter-spacing: 0.08em;
	color: var(--pos-text-secondary, #8595ab);
	margin-top: 2px;
}

.pos-profile-picker__required {
	color: #f43f5e;
	margin-inline-start: 2px;
}

/* ── Collapsible trigger ─────────────────────────────────────────
   This is the always-visible button that summarises the current
   selection and toggles the searchable panel below. We style it
   like a CC field (rounded, subtle violet halo) so it reads as
   part of the form, not a separate dropdown widget. */
.pos-profile-picker__trigger {
	all: unset;
	box-sizing: border-box;
	display: flex;
	align-items: center;
	gap: 10px;
	width: 100%;
	min-height: 44px;
	padding: 10px 14px;
	border-radius: 10px;
	cursor: pointer;
	background: var(--pos-surface-muted, #161c27);
	color: var(--pos-text-primary, #e7ebf3);
	font-size: 0.95rem;
	font-weight: 600;
	box-shadow: inset 0 0 0 1px rgba(139, 92, 246, 0.4);
	transition:
		box-shadow 0.18s ease,
		background-color 0.18s ease;
}

.pos-profile-picker__trigger:hover {
	background: rgba(139, 92, 246, 0.08);
	box-shadow: inset 0 0 0 1.5px rgba(167, 139, 250, 0.6);
}

.pos-profile-picker__trigger:focus-visible {
	box-shadow:
		inset 0 0 0 1.5px #a78bfa,
		0 0 0 3px rgba(139, 92, 246, 0.18);
}

.pos-profile-picker__trigger--placeholder {
	color: var(--pos-text-secondary, #8595ab);
	font-weight: 500;
	font-style: italic;
}

.pos-profile-picker__trigger-icon {
	color: #a78bfa;
	flex-shrink: 0;
}

.pos-profile-picker__trigger-label {
	flex: 1;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	text-align: start;
}

.pos-profile-picker__trigger-caret {
	color: #a78bfa;
	flex-shrink: 0;
	transition: transform 0.2s cubic-bezier(0.22, 1, 0.36, 1);
}

.pos-profile-picker__trigger-caret--open {
	transform: rotate(180deg);
}

/* Expanded panel — the search field + list. Slides in with a quick
   fade so the open/close gesture feels intentional. */
.pos-profile-picker__panel {
	display: flex;
	flex-direction: column;
	gap: 8px;
	margin-top: 4px;
	animation: pos-profile-picker__panel-in 0.22s cubic-bezier(0.22, 1, 0.36, 1);
}

@keyframes pos-profile-picker__panel-in {
	from {
		opacity: 0;
		transform: translateY(-6px);
	}
	to {
		opacity: 1;
		transform: translateY(0);
	}
}

.pos-profile-picker__search :deep(.v-field) {
	min-height: 40px !important;
	box-shadow: inset 0 0 0 1px rgba(139, 92, 246, 0.4) !important;
}

.pos-profile-picker__search :deep(.v-field--focused) {
	box-shadow:
		inset 0 0 0 1.5px #a78bfa,
		0 0 0 3px rgba(139, 92, 246, 0.15) !important;
}

.pos-profile-picker__list {
	display: flex;
	flex-direction: column;
	gap: 4px;
	max-height: 220px;
	overflow-y: auto;
	padding-right: 2px;
	scrollbar-width: thin;
	scrollbar-color: rgba(139, 92, 246, 0.4) transparent;
}

.pos-profile-picker__list::-webkit-scrollbar {
	width: 8px;
}

.pos-profile-picker__list::-webkit-scrollbar-track {
	background: transparent;
}

.pos-profile-picker__list::-webkit-scrollbar-thumb {
	background-color: rgba(139, 92, 246, 0.4);
	border-radius: 4px;
}

.pos-profile-picker__option {
	all: unset;
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 10px 12px;
	border-radius: 10px;
	cursor: pointer;
	color: var(--pos-text-primary, #e7ebf3);
	font-size: 0.92rem;
	font-weight: 500;
	background: transparent;
	border: 1px solid transparent;
	transition:
		background-color 0.18s ease,
		border-color 0.18s ease,
		transform 0.18s ease;
}

.pos-profile-picker__option:hover {
	background: rgba(139, 92, 246, 0.12);
	border-color: rgba(139, 92, 246, 0.3);
}

.pos-profile-picker__option:focus-visible {
	outline: 2px solid rgba(167, 139, 250, 0.7);
	outline-offset: 2px;
}

.pos-profile-picker__option--active {
	background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%) !important;
	color: #ffffff !important;
	border-color: transparent !important;
	box-shadow:
		0 6px 18px rgba(139, 92, 246, 0.38),
		0 0 0 1px rgba(167, 139, 250, 0.4) inset;
}

.pos-profile-picker__option--active .pos-profile-picker__option-icon,
.pos-profile-picker__option--active .pos-profile-picker__option-check {
	color: #ffffff !important;
}

.pos-profile-picker__option-icon {
	color: #a78bfa;
	opacity: 0.85;
	flex-shrink: 0;
}

.pos-profile-picker__option-label {
	flex: 1;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.pos-profile-picker__option-check {
	color: #a78bfa;
	flex-shrink: 0;
}

.pos-profile-picker__empty {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 8px;
	padding: 18px 12px;
	color: var(--pos-text-secondary, #8595ab);
	font-size: 0.85rem;
	font-style: italic;
}

.pos-profile-picker__empty-icon {
	opacity: 0.7;
}

/* ── Payment methods section ─────────────────────────────────────── */
.payment-methods-section {
	display: flex;
	flex-direction: column;
	gap: 8px;
}

.payment-methods-section__header {
	display: flex;
	align-items: center;
	gap: 8px;
}

.payment-methods-section__icon {
	color: var(--pos-primary, #e23670);
}

.payment-methods-section__title {
	margin: 0;
	font-size: 0.78rem;
	font-weight: 700;
	letter-spacing: 0.12em;
	text-transform: uppercase;
	color: var(--pos-text-secondary, #8595ab);
}

.payment-methods-table {
	border-radius: 12px;
	overflow: hidden;
	border: 1px solid var(--pos-border, #252b37);
	background: var(--pos-surface-muted, #161c27) !important;
}

.payment-methods-table :deep(.v-table) {
	background: transparent !important;
	color: var(--pos-text-primary, #e7ebf3) !important;
}

.payment-methods-table :deep(thead) {
	background: linear-gradient(135deg, rgba(226, 54, 112, 0.08), rgba(139, 92, 246, 0.06));
}

.payment-methods-table :deep(th) {
	color: var(--pos-primary, #e23670) !important;
	font-weight: 700 !important;
	font-size: 0.72rem !important;
	letter-spacing: 0.1em;
	text-transform: uppercase;
	border-bottom: 1px solid var(--pos-border, #252b37) !important;
	padding: 10px 14px !important;
	background: transparent !important;
}

.payment-methods-table :deep(td) {
	padding: 8px 14px !important;
	border-bottom: 1px solid rgba(37, 43, 55, 0.6) !important;
	color: var(--pos-text-primary, #e7ebf3) !important;
}

.payment-methods-table :deep(tr:hover td) {
	background: rgba(226, 54, 112, 0.05) !important;
}

.payment-methods-table__amount :deep(.v-field__input) {
	min-height: 36px !important;
	font-size: 0.9rem;
	font-variant-numeric: tabular-nums;
	text-align: center;
}

.payment-methods-table__amount :deep(.v-field__prefix) {
	color: var(--pos-text-secondary, #8595ab);
	font-weight: 600;
	font-size: 0.78rem;
}

/* ── Actions ─────────────────────────────────────────────────────── */
.dialog-actions-container {
	padding: 14px 22px;
	background: var(--pos-surface-muted, #161c27);
	border-top: 1px solid var(--pos-border, #252b37);
	display: flex;
	align-items: center;
	gap: 10px;
}

.pos-action-btn {
	border-radius: 12px !important;
	text-transform: none !important;
	font-weight: 700 !important;
	letter-spacing: 0.02em !important;
	padding: 0 22px !important;
	min-width: 128px !important;
	color: #ffffff !important;
	transition: transform 0.18s ease, box-shadow 0.18s ease !important;
}

.pos-action-btn :deep(.v-btn__overlay) {
	background: transparent !important;
}

/* ── Action buttons (CC violet/pink palette) ──────────────────────
   The original blue / red / green trio pulled the eye away from the
   primary submit action and clashed with the rest of the CC theme.
   Logout is now a muted slate (it's destructive but not the primary
   ask), Close is a hairline ghost, and Submit owns the violet→pink
   gradient that signals the most important action on the page. */
.pos-action-btn--logout {
	background: linear-gradient(135deg, rgba(30, 41, 59, 0.95), rgba(51, 65, 85, 0.95)) !important;
	border: 1px solid rgba(148, 163, 184, 0.25) !important;
	box-shadow: 0 2px 8px rgba(15, 23, 42, 0.35) !important;
}

.pos-action-btn--logout:hover {
	background: linear-gradient(135deg, rgba(51, 65, 85, 0.95), rgba(71, 85, 105, 0.95)) !important;
	box-shadow: 0 6px 18px rgba(15, 23, 42, 0.45) !important;
	border-color: rgba(244, 63, 94, 0.4) !important;
	transform: translateY(-2px);
}

.pos-action-btn--close {
	background: transparent !important;
	border: 1px solid rgba(139, 92, 246, 0.4) !important;
	box-shadow: inset 0 0 0 1px rgba(139, 92, 246, 0.08) !important;
	color: #c7c2f0 !important;
}

.pos-action-btn--close:hover {
	background: rgba(139, 92, 246, 0.1) !important;
	border-color: rgba(167, 139, 250, 0.6) !important;
	box-shadow: 0 6px 18px rgba(139, 92, 246, 0.18) !important;
	transform: translateY(-2px);
}

.pos-action-btn--submit {
	background: linear-gradient(
		135deg,
		#8b5cf6 0%,
		#a78bfa 45%,
		#e23670 100%
	) !important;
	border: 1px solid rgba(167, 139, 250, 0.5) !important;
	box-shadow: 0 6px 18px rgba(139, 92, 246, 0.35) !important;
}

.pos-action-btn--submit:hover {
	filter: brightness(1.07);
	box-shadow:
		0 10px 26px rgba(226, 54, 112, 0.4),
		0 0 0 1px rgba(167, 139, 250, 0.6) inset !important;
	transform: translateY(-2px);
}

.pos-action-btn--submit:disabled {
	opacity: 0.5;
	transform: none !important;
	box-shadow: none !important;
	filter: grayscale(0.3);
	background: linear-gradient(
		135deg,
		rgba(139, 92, 246, 0.6),
		rgba(226, 54, 112, 0.6)
	) !important;
}

/* ── Responsive ──────────────────────────────────────────────────── */
@media (max-width: 768px) {
	.opening-dialog-header {
		padding: 14px 16px;
	}

	.opening-dialog-header__title {
		font-size: 1rem;
	}

	.opening-dialog-content {
		padding: 14px 14px 16px;
	}

	.dialog-actions-container {
		padding: 12px 14px;
		gap: 8px;
	}

	.pos-action-btn {
		min-width: 0 !important;
		padding: 0 14px !important;
	}
}

@media (max-width: 480px) {
	.opening-dialog-header {
		flex-direction: row;
		gap: 10px;
	}

	.opening-dialog-header__icon-wrap {
		width: 36px;
		height: 36px;
	}

	.dialog-actions-container {
		flex-wrap: wrap;
	}

	.pos-action-btn {
		flex: 1 1 auto;
	}
}
</style>
