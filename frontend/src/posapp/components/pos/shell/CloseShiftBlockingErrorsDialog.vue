<template>
	<v-dialog v-model="dialogOpen" max-width="700" persistent>
		<v-card class="close-shift-blocking-card pos-themed-card">
			<v-card-title class="close-shift-blocking-header pa-5">
				<div class="close-shift-blocking-header__content">
					<div class="close-shift-blocking-header__icon">
						<v-icon size="22">mdi-alert-octagon</v-icon>
					</div>
					<div class="close-shift-blocking-header__text">
						<h3 class="close-shift-blocking-header__title">
							{{ __("Close shift blocked by draft submit") }}
						</h3>
						<p class="close-shift-blocking-header__subtitle">
							{{ __("A printed draft couldn't be submitted. Delete it to unblock close, or cancel and resolve manually.") }}
						</p>
					</div>
				</div>
			</v-card-title>

			<v-card-text class="pa-0 close-shift-blocking-body">
				<section class="close-shift-blocking-section">
					<header class="close-shift-blocking-section__header">
						<v-icon size="18" color="error">mdi-file-alert-outline</v-icon>
						<span>
							{{ __("Blocking invoices") }} ({{ blockingErrors.length }})
						</span>
					</header>

					<ul class="close-shift-blocking-list">
						<li
							v-for="err in blockingErrors"
							:key="err.invoice"
							class="close-shift-blocking-row"
						>
							<div class="close-shift-blocking-row__head">
								<span class="close-shift-blocking-row__name">{{ err.invoice }}</span>
								<span class="close-shift-blocking-row__customer">
									{{ err.customer || "—" }}
								</span>
								<span class="close-shift-blocking-row__total">
									{{ formatTotal(err.grand_total) }}
								</span>
							</div>
							<div v-if="err.message" class="close-shift-blocking-row__error" v-html="sanitizedMessage(err.message)"></div>
						</li>
					</ul>

					<div class="close-shift-blocking-warning">
						{{ __("Deleting these drafts is irreversible. The cashier may have already issued receipts for them — make sure cash totals are reconciled separately before continuing.") }}
					</div>
				</section>
			</v-card-text>

			<v-card-actions class="close-shift-blocking-actions pa-4">
				<v-btn
					variant="text"
					:disabled="busy"
					@click="onCancel"
				>
					{{ __("Cancel close") }}
				</v-btn>
				<v-spacer />
				<v-btn
					color="error"
					variant="tonal"
					:loading="busy"
					prepend-icon="mdi-delete-sweep"
					@click="onDeleteAndRetry"
				>
					{{ __("Delete blocking drafts and retry close") }}
				</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>

<script setup>
import { ref, watch, getCurrentInstance, inject, onMounted, onBeforeUnmount } from "vue";
import { useToastStore } from "../../../stores/toastStore";

defineOptions({ name: "CloseShiftBlockingErrorsDialog" });

const __ = window.__ || ((value) => value);

const instance = getCurrentInstance();
const eventBus = instance?.proxy?.eventBus || inject("eventBus");
const toastStore = useToastStore();

const dialogOpen = ref(false);
const busy = ref(false);
const blockingErrors = ref([]);
const openingShift = ref(null);
const posProfileName = ref(null);
let resolveDecision = null;

function formatTotal(value) {
	const n = Number(value);
	if (!Number.isFinite(n)) return "—";
	return n.toFixed(3);
}

// The backend bakes Frappe-style HTML (links, <strong>) into the
// message. Strip <script> tags defensively but otherwise let the rich
// markup through so the cashier sees clickable batch / item references.
function sanitizedMessage(value) {
	if (!value) return "";
	return String(value).replace(/<script[\s\S]*?<\/script>/gi, "");
}

function open(payload) {
	blockingErrors.value = payload.blocking_errors || [];
	openingShift.value = payload.opening_shift;
	posProfileName.value = payload.pos_profile;
	resolveDecision = payload.onResolve || null;
	busy.value = false;
	dialogOpen.value = true;
}

function finish(decision) {
	if (resolveDecision) {
		try {
			resolveDecision(decision);
		} catch (error) {
			console.error("CloseShiftBlockingErrorsDialog onResolve threw", error);
		}
	}
	resolveDecision = null;
	dialogOpen.value = false;
}

function onCancel() {
	finish("cancel");
}

async function onDeleteAndRetry() {
	if (busy.value) return;
	busy.value = true;
	const names = blockingErrors.value.map((e) => e.invoice).filter(Boolean);
	if (!names.length) {
		busy.value = false;
		finish("cancel");
		return;
	}
	try {
		const resp = await frappe.call(
			"posawesome.posawesome.doctype.pos_closing_shift.closing_processing.invoices.delete_open_draft_invoices",
			{
				pos_opening_shift: openingShift.value,
				pos_profile: posProfileName.value,
				names,
			},
		);
		const result = resp?.message || {};
		const deletedCount = Array.isArray(result.deleted) ? result.deleted.length : 0;
		const skippedCount = Array.isArray(result.skipped) ? result.skipped.length : 0;
		toastStore.show({
			title: __("Blocking drafts deleted"),
			detail: skippedCount
				? __("{0} deleted, {1} skipped (see Error Log).", [deletedCount, skippedCount])
				: __("{0} draft(s) deleted. Retrying close…", [deletedCount]),
			color: skippedCount ? "warning" : "success",
		});
	} catch (error) {
		console.error("Failed to delete blocking drafts", error);
		toastStore.show({
			title: __("Cleanup failed"),
			detail: __("Could not delete the listed drafts. Try again or remove them from the Desk."),
			color: "error",
		});
		busy.value = false;
		return;
	}
	finish("retry");
}

watch(dialogOpen, (val) => {
	if (!val && resolveDecision) {
		const fn = resolveDecision;
		resolveDecision = null;
		try {
			fn("cancel");
		} catch (error) {
			console.error("CloseShiftBlockingErrorsDialog dismiss handler threw", error);
		}
	}
});

onMounted(() => {
	eventBus?.on?.("open_CloseShiftBlockingErrorsDialog", open);
});

onBeforeUnmount(() => {
	eventBus?.off?.("open_CloseShiftBlockingErrorsDialog", open);
});
</script>

<style scoped>
.close-shift-blocking-card {
	border-radius: 16px !important;
	overflow: hidden;
	background: var(--pos-card-bg);
	color: var(--pos-text-primary);
	box-shadow: 0 4px 20px var(--pos-shadow) !important;
	max-height: 92vh;
}

.close-shift-blocking-header {
	background: var(--pos-card-bg);
	border-bottom: 1px solid var(--pos-border);
	position: relative;
	min-height: auto !important;
}

.close-shift-blocking-header::before {
	content: "";
	position: absolute;
	top: 0;
	left: 0;
	right: 0;
	height: 3px;
	background: linear-gradient(90deg, #ef4444 0%, #f97316 100%);
}

.close-shift-blocking-header__content {
	display: flex;
	align-items: center;
	gap: 14px;
}

.close-shift-blocking-header__icon {
	background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%);
	border-radius: 14px;
	width: 44px;
	height: 44px;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	color: #fff;
	flex-shrink: 0;
}

.close-shift-blocking-header__title {
	margin: 0;
	font-size: 1.05rem;
	font-weight: 700;
	color: var(--pos-text-primary);
}

.close-shift-blocking-header__subtitle {
	margin: 2px 0 0;
	font-size: 0.78rem;
	color: var(--pos-text-secondary);
	line-height: 1.35;
}

.close-shift-blocking-body {
	background: var(--pos-bg-secondary, var(--pos-card-bg));
}

.close-shift-blocking-section {
	padding: 14px 18px;
}

.close-shift-blocking-section__header {
	display: flex;
	align-items: center;
	gap: 8px;
	font-weight: 700;
	font-size: 0.82rem;
	letter-spacing: 0.02em;
	text-transform: uppercase;
	color: var(--pos-text-secondary);
	margin-bottom: 10px;
}

.close-shift-blocking-list {
	margin: 0;
	padding: 0;
	list-style: none;
	display: grid;
	gap: 8px;
	max-height: 320px;
	overflow-y: auto;
}

.close-shift-blocking-row {
	border: 1px solid var(--pos-border);
	border-radius: 10px;
	background: var(--pos-surface, rgba(148, 163, 184, 0.06));
	padding: 10px 12px;
}

.close-shift-blocking-row__head {
	display: grid;
	grid-template-columns: 1.4fr 1fr 0.7fr;
	gap: 10px;
	align-items: center;
	font-size: 0.84rem;
}

.close-shift-blocking-row__name {
	font-weight: 700;
	color: var(--pos-text-primary);
}

.close-shift-blocking-row__customer {
	color: var(--pos-text-secondary);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.close-shift-blocking-row__total {
	text-align: right;
	font-weight: 700;
	color: var(--pos-text-primary);
}

.close-shift-blocking-row__error {
	margin-top: 6px;
	padding: 8px 10px;
	border-radius: 8px;
	background: rgba(239, 68, 68, 0.08);
	border: 1px solid rgba(239, 68, 68, 0.18);
	font-size: 0.78rem;
	line-height: 1.4;
	color: var(--pos-text-primary);
	word-break: break-word;
}

.close-shift-blocking-row__error :deep(a) {
	color: var(--cc-orange, #f46a25);
	text-decoration: underline;
}

.close-shift-blocking-warning {
	margin-top: 14px;
	border: 1px solid rgba(244, 158, 11, 0.32);
	background: rgba(244, 158, 11, 0.08);
	border-radius: 10px;
	padding: 10px 14px;
	font-size: 0.8rem;
	color: var(--pos-text-primary);
	line-height: 1.4;
}

.close-shift-blocking-actions {
	border-top: 1px solid var(--pos-border);
	background: var(--pos-card-bg);
}
</style>
