<template>
	<!--
		Both the "Switch cashier" and "Unlock terminal" dialogs intentionally
		do NOT use <v-dialog>. Mounting Vuetify's overlay machinery (focus
		trap + scroll lock + transition stack) on top of the POS payment
		flow caused the same hard browser freeze that the StockConflictDialog
		hit — DevTools wouldn't open even after the dialog had visually
		mounted. Plain <Teleport> + native scrim sidesteps every piece of
		that machinery. See commit 64576349 (StockConflictDialog rewrite)
		for the long-form rationale.
	-->
	<Teleport v-if="switchDialogOpen" to="body">
		<div
			class="employee-switch-overlay"
			role="presentation"
			@click.self="closeSwitch"
		>
			<div
				class="employee-switch-card pos-themed-card"
				role="dialog"
				aria-modal="true"
				:aria-label="relabel(__('Switch Cashier'))"
				@click.stop
			>
				<div class="employee-switch-card__title">
					<div>
						<div class="employee-switch-dialog__eyebrow">{{ __("Shared terminal") }}</div>
						<div class="text-h6">{{ relabel(__("Switch Cashier")) }}</div>
					</div>
					<button
						type="button"
						class="employee-switch-card__close"
						:aria-label="relabel(__('Close cashier switcher'))"
						@click="closeSwitch"
					>
						<v-icon>mdi-close</v-icon>
					</button>
				</div>
				<div class="employee-switch-card__body">
					<div class="employee-switch-dialog__copy">
						{{ relabel(__("Choose the cashier currently operating this terminal.")) }}
					</div>
					<div v-if="!terminalEmployees.length" class="employee-switch-dialog__empty">
						{{ relabel(__("No cashier profiles are available for this POS profile yet.")) }}
					</div>
					<div v-else class="employee-switch-dialog__list">
						<button
							v-for="employee in terminalEmployees"
							:key="employee.user"
							type="button"
							:data-test="`employee-option-${employee.user}`"
							class="employee-switch-dialog__option"
							:class="{ 'employee-switch-dialog__option--active': selectedUser === employee.user }"
							@click="selectEmployee(employee.user)"
						>
							<div>
								<strong>{{ employee.full_name }}</strong>
								<div class="employee-switch-dialog__meta">{{ employee.user }}</div>
							</div>
							<v-icon icon="mdi-check-circle" color="primary" v-if="selectedUser === employee.user" />
						</button>
					</div>
					<v-alert
						variant="tonal"
						type="info"
						density="comfortable"
						class="employee-switch-dialog__help"
						data-test="cashier-pin-help"
					>
						{{ relabel(__("Set each cashier PIN in the User form and keep terminal members assigned in POS Profile User.")) }}
					</v-alert>
					<v-text-field
						v-model="cashierPin"
						:type="showPin ? 'text' : 'password'"
						:append-inner-icon="showPin ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
						variant="outlined"
						density="comfortable"
						hide-details="auto"
						:label="relabel(__('Cashier PIN'))"
						:data-test="'cashier-pin-input'"
						:name="pinFieldName"
						autocomplete="one-time-code"
						inputmode="numeric"
						data-lpignore="true"
						data-1p-ignore="true"
						data-form-type="other"
						spellcheck="false"
						@click:append-inner="showPin = !showPin"
						@keyup.enter="submitSwitch"
					/>
					<v-alert
						v-if="pinError"
						variant="tonal"
						type="error"
						density="comfortable"
						class="employee-switch-dialog__error"
						data-test="cashier-pin-error"
					>
						{{ pinError }}
					</v-alert>
				</div>
				<div class="employee-switch-card__actions">
					<v-btn variant="text" @click="closeSwitch">
						{{ __("Cancel") }}
					</v-btn>
					<v-btn
						color="primary"
						:disabled="!canSubmit"
						:loading="isSubmitting"
						data-test="cashier-pin-submit"
						@click="submitSwitch"
					>
						{{ relabel(__("Use Cashier")) }}
					</v-btn>
				</div>
			</div>
		</div>
	</Teleport>

	<Teleport v-if="lockDialogOpen" to="body">
		<div class="employee-switch-overlay" role="presentation">
			<div
				class="employee-switch-card pos-themed-card"
				role="dialog"
				aria-modal="true"
				:aria-label="__('Unlock POS')"
				@click.stop
			>
				<div class="employee-switch-card__title">
					<div>
						<div class="employee-switch-dialog__eyebrow">{{ __("Terminal locked") }}</div>
						<div class="text-h6">{{ __("Unlock POS") }}</div>
					</div>
				</div>
				<div class="employee-switch-card__body">
					<div class="employee-switch-dialog__copy">
						{{ relabel(__("Select the cashier who is taking over this terminal.")) }}
					</div>
					<div class="employee-switch-dialog__list">
						<button
							v-for="employee in terminalEmployees"
							:key="`unlock-${employee.user}`"
							type="button"
							class="employee-switch-dialog__option"
							:class="{ 'employee-switch-dialog__option--active': selectedUser === employee.user }"
							@click="selectEmployee(employee.user)"
						>
							<div>
								<strong>{{ employee.full_name }}</strong>
								<div class="employee-switch-dialog__meta">{{ employee.user }}</div>
							</div>
							<v-icon icon="mdi-lock-open-outline" color="primary" />
						</button>
					</div>
					<v-alert
						variant="tonal"
						type="info"
						density="comfortable"
						class="employee-switch-dialog__help"
					>
						{{ relabel(__("Set each cashier PIN in the User form and keep terminal members assigned in POS Profile User.")) }}
					</v-alert>
					<v-text-field
						v-model="cashierPin"
						:type="showPin ? 'text' : 'password'"
						:append-inner-icon="showPin ? 'mdi-eye-off-outline' : 'mdi-eye-outline'"
						variant="outlined"
						density="comfortable"
						hide-details="auto"
						:label="relabel(__('Cashier PIN'))"
						:name="pinFieldName"
						autocomplete="one-time-code"
						inputmode="numeric"
						data-lpignore="true"
						data-1p-ignore="true"
						data-form-type="other"
						spellcheck="false"
						@click:append-inner="showPin = !showPin"
						@keyup.enter="submitUnlock"
					/>
					<v-alert
						v-if="pinError"
						variant="tonal"
						type="error"
						density="comfortable"
						class="employee-switch-dialog__error"
					>
						{{ pinError }}
					</v-alert>
				</div>
				<div class="employee-switch-card__actions">
					<v-btn
						color="primary"
						:disabled="!canSubmit"
						:loading="isSubmitting"
						@click="submitUnlock"
					>
						{{ __("Unlock POS") }}
					</v-btn>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { useEmployeeStore } from "../../../stores/employeeStore";
import { useUIStore } from "../../../stores/uiStore";
import { useCashierLabel } from "../../../composables/pos/shared/useCashierLabel";

const employeeStore = useEmployeeStore();
const uiStore = useUIStore();
// `relabel` substitutes the configurable label into pre-translated
// strings only when the operator has overridden the default — see
// useCashierLabel for the full rationale. The "Cashier PIN" / "Use
// Cashier" / "Switch Cashier" copy below flows through it.
const { relabel } = useCashierLabel();
const { terminalEmployees, currentCashier, switchDialogOpen, lockDialogOpen } =
	storeToRefs(employeeStore);
const selectedUser = ref("");
const cashierPin = ref("");
const pinError = ref("");
const isSubmitting = ref(false);
const showPin = ref(false);

// Randomised, non-semantic field name so browser password managers
// (and Chrome's autofill heuristics) can't recognise this as a
// "password" field for the current site and prompt to save it. The
// `autocomplete="one-time-code"` + `data-lpignore` / `data-1p-ignore`
// attributes do most of the work, but giving the field an unstable
// name on every mount is the most reliable way to keep the saved-
// passwords prompt suppressed across Chrome / Firefox / Safari.
const pinFieldName = `pos-cashier-pin-${Math.random().toString(36).slice(2, 10)}`;
const posProfileName = computed(
	() => uiStore.posProfile?.name || window.frappe?.boot?.pos_profile?.name || "",
);

watch(
	[currentCashier, switchDialogOpen, lockDialogOpen, terminalEmployees],
	([cashier, switchOpen, lockOpen]) => {
		if (switchOpen || lockOpen) {
			selectedUser.value = cashier?.user || terminalEmployees.value[0]?.user || "";
			cashierPin.value = "";
			pinError.value = "";
			showPin.value = false;
		}
	},
	{ immediate: true },
);

// Body scroll lock + Escape handling — replaces what v-dialog used to
// give us for free. Only active while one of the two overlays is open
// so we don't intercept Escape elsewhere in the POS.
const isAnyOpen = computed(
	() => switchDialogOpen.value || lockDialogOpen.value,
);

const onKeydown = (event) => {
	if (event.key !== "Escape") return;
	if (switchDialogOpen.value) {
		event.stopPropagation();
		closeSwitch();
	}
	// The lock dialog is intentionally persistent: Escape doesn't close
	// it (mirrors the original `persistent` v-dialog prop).
};

watch(
	isAnyOpen,
	(open) => {
		if (typeof document === "undefined") return;
		if (open) {
			document.addEventListener("keydown", onKeydown, true);
			document.body.classList.add("employee-switch-overlay-open");
		} else {
			document.removeEventListener("keydown", onKeydown, true);
			document.body.classList.remove("employee-switch-overlay-open");
		}
	},
	{ immediate: true },
);

onBeforeUnmount(() => {
	if (typeof document === "undefined") return;
	document.removeEventListener("keydown", onKeydown, true);
	document.body.classList.remove("employee-switch-overlay-open");
});

const selectedCashier = computed(
	() =>
		terminalEmployees.value.find((employee) => employee.user === selectedUser.value) ||
		null,
);

const canSubmit = computed(
	() => Boolean(selectedCashier.value?.user) && Boolean(cashierPin.value.trim()) && !isSubmitting.value,
);

const normalizeErrorMessage = (error) =>
	error?.message ||
	error?.exc ||
	error?.messages?.[0] ||
	relabel(__("Unable to verify cashier PIN."));

const selectEmployee = (user) => {
	selectedUser.value = user;
	pinError.value = "";
};

const closeSwitch = () => {
	employeeStore.closeEmployeeSwitch();
};

const verifySelection = async () => {
	if (!selectedCashier.value) {
		pinError.value = __("Select a cashier first.");
		return null;
	}
	if (!cashierPin.value.trim()) {
		pinError.value = __("Enter the cashier PIN to continue.");
		return null;
	}

	isSubmitting.value = true;
	pinError.value = "";

	try {
		const response = await window.frappe.call({
			method: "posawesome.mizan.api.employees.verify_terminal_employee_pin",
			args: {
				pos_profile: posProfileName.value,
				user: selectedCashier.value.user,
				pin: cashierPin.value.trim(),
			},
		});
		return {
			...selectedCashier.value,
			...(response?.message || {}),
		};
	} catch (error) {
		pinError.value = normalizeErrorMessage(error);
		return null;
	} finally {
		isSubmitting.value = false;
	}
};

const submitSwitch = async () => {
	const verifiedCashier = await verifySelection();
	if (!verifiedCashier) {
		return;
	}
	employeeStore.setCurrentCashier(verifiedCashier);
	employeeStore.closeEmployeeSwitch();
	cashierPin.value = "";
};

const submitUnlock = async () => {
	const verifiedCashier = await verifySelection();
	if (!verifiedCashier) {
		return;
	}
	employeeStore.unlockTerminal(verifiedCashier);
	cashierPin.value = "";
};

const __ = window.__;
</script>

<style scoped>
/* ── Overlay shell (replaces v-dialog) ─────────────────────────── */
.employee-switch-overlay {
	position: fixed;
	inset: 0;
	z-index: 2400; /* above Vuetify's default v-dialog stack */
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 16px;
	background: rgba(8, 12, 22, 0.62);
	backdrop-filter: blur(2px);
	animation: employee-switch-overlay-in 140ms ease-out;
}

@keyframes employee-switch-overlay-in {
	from { opacity: 0; }
	to   { opacity: 1; }
}

.employee-switch-card {
	width: min(520px, 100%);
	max-height: calc(100vh - 32px);
	overflow: hidden;
	display: flex;
	flex-direction: column;
	border-radius: 18px;
	background: var(--pos-card-bg, #0e131e);
	border: 1px solid rgba(244, 114, 182, 0.18);
	box-shadow:
		0 24px 56px rgba(0, 0, 0, 0.6),
		0 0 0 1px rgba(226, 54, 112, 0.08);
	color: var(--pos-text-primary, #e7ebf3);
	animation: employee-switch-card-in 180ms cubic-bezier(0.2, 0.8, 0.3, 1);
}

@keyframes employee-switch-card-in {
	from { opacity: 0; transform: translateY(6px) scale(0.98); }
	to   { opacity: 1; transform: translateY(0)   scale(1); }
}

.employee-switch-card__title {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 16px;
	padding: 18px 22px 12px;
}

.employee-switch-card__close {
	all: unset;
	width: 32px;
	height: 32px;
	display: grid;
	place-items: center;
	border-radius: 8px;
	cursor: pointer;
	color: rgba(231, 235, 243, 0.6);
	transition: background-color 0.18s ease, color 0.18s ease;
}

.employee-switch-card__close:hover {
	background: rgba(244, 63, 94, 0.15);
	color: #fb7185;
}

.employee-switch-card__body {
	padding: 0 22px 12px;
	overflow-y: auto;
	flex: 1 1 auto;
}

.employee-switch-card__actions {
	display: flex;
	justify-content: flex-end;
	gap: 8px;
	padding: 12px 18px 16px;
	border-top: 1px solid rgba(255, 255, 255, 0.04);
}

.employee-switch-dialog__eyebrow {
	font-size: 0.72rem;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: 0.08em;
	color: var(--pos-text-secondary);
}

.employee-switch-dialog__copy {
	margin-bottom: 12px;
	color: var(--pos-text-secondary);
}

.employee-switch-dialog__empty {
	padding: 16px;
	border: 1px dashed var(--pos-border);
	border-radius: 14px;
	color: var(--pos-text-secondary);
}

.employee-switch-dialog__list {
	display: flex;
	flex-direction: column;
	gap: 10px;
}

.employee-switch-dialog__option {
	width: 100%;
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
	padding: 14px 16px;
	border-radius: 16px;
	border: 1px solid rgba(var(--v-theme-primary), 0.12);
	background: var(--pos-surface-muted);
	color: var(--pos-text-primary);
	text-align: left;
	transition:
		transform 0.18s ease,
		box-shadow 0.18s ease,
		border-color 0.18s ease;
	cursor: pointer;
}

.employee-switch-dialog__option:hover,
.employee-switch-dialog__option--active {
	border-color: rgba(var(--v-theme-primary), 0.34);
	box-shadow: 0 10px 18px rgba(15, 23, 42, 0.08);
	transform: translateY(-1px);
}

.employee-switch-dialog__meta {
	margin-top: 4px;
	font-size: 0.82rem;
	color: var(--pos-text-secondary);
}

.employee-switch-dialog__error {
	margin-top: 12px;
	border-radius: 14px;
}

.employee-switch-dialog__help {
	margin: 14px 0 12px;
	border-radius: 14px;
}
</style>

<style>
/* Global helper so the underlying page can be locked from scrolling
   while either the switch or lock overlay is up — mirrors what
   v-dialog used to do without pulling in Vuetify's overlay machinery. */
body.employee-switch-overlay-open {
	overflow: hidden;
}
</style>