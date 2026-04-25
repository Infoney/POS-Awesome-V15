<template>
	<v-dialog v-model="dialogOpen" max-width="640" persistent>
		<v-card class="pre-close-drafts-card pos-themed-card">
			<v-card-title class="pre-close-drafts-header pa-5">
				<div class="pre-close-drafts-header__content">
					<div class="pre-close-drafts-header__icon">
						<v-icon size="22">mdi-broom</v-icon>
					</div>
					<div class="pre-close-drafts-header__text">
						<h3 class="pre-close-drafts-header__title">
							{{ __("Drafts found in this shift") }}
						</h3>
						<p class="pre-close-drafts-header__subtitle">
							{{ __("Review what's open before closing — clean up unprinted drafts to avoid stock errors.") }}
						</p>
					</div>
				</div>
			</v-card-title>

			<v-card-text class="pa-0 pre-close-drafts-body">
				<!-- Unprinted drafts (safe to delete) -->
				<section class="pre-close-drafts-section">
					<header class="pre-close-drafts-section__header">
						<v-icon size="18">mdi-file-outline</v-icon>
						<span>
							{{ __("Unprinted drafts") }}
							({{ unprinted.length }})
						</span>
						<v-chip v-if="unprinted.length" size="x-small" color="warning" variant="tonal">
							{{ __("Safe to delete") }}
						</v-chip>
						<v-chip v-else size="x-small" color="success" variant="tonal">
							{{ __("None") }}
						</v-chip>
					</header>
					<div v-if="!unprinted.length" class="pre-close-drafts-empty">
						{{ __("No unprinted drafts in this shift.") }}
					</div>
					<ul v-else class="pre-close-drafts-list">
						<li v-for="d in unprinted" :key="d.name" class="pre-close-drafts-row">
							<span class="pre-close-drafts-row__name">{{ d.name }}</span>
							<span class="pre-close-drafts-row__customer">{{ d.customer || "—" }}</span>
							<span class="pre-close-drafts-row__total">
								{{ formatTotal(d.grand_total) }}
							</span>
						</li>
					</ul>
				</section>

				<v-divider />

				<!-- Printed drafts (require manual handling) -->
				<section class="pre-close-drafts-section">
					<header class="pre-close-drafts-section__header">
						<v-icon size="18">mdi-printer-check</v-icon>
						<span>
							{{ __("Printed drafts (auto-submit on close)") }}
							({{ printed.length }})
						</span>
						<v-chip v-if="printed.length" size="x-small" color="error" variant="tonal">
							{{ __("Receipt issued") }}
						</v-chip>
					</header>
					<div v-if="!printed.length" class="pre-close-drafts-empty">
						{{ __("No printed drafts pending submission.") }}
					</div>
					<template v-else>
						<div class="pre-close-drafts-warning">
							{{ __("These invoices already have printed receipts. They'll be auto-submitted at close. If a batch went negative since printing, the submit may still fail — open Invoice Mgmt and resolve them manually first.") }}
						</div>
						<ul class="pre-close-drafts-list">
							<li v-for="d in printed" :key="d.name" class="pre-close-drafts-row">
								<span class="pre-close-drafts-row__name">{{ d.name }}</span>
								<span class="pre-close-drafts-row__customer">{{ d.customer || "—" }}</span>
								<span class="pre-close-drafts-row__total">
									{{ formatTotal(d.grand_total) }}
								</span>
							</li>
						</ul>
					</template>
				</section>
			</v-card-text>

			<v-card-actions class="pre-close-drafts-actions pa-4">
				<v-btn
					variant="text"
					:disabled="busy"
					@click="onCancel"
				>
					{{ __("Cancel close") }}
				</v-btn>
				<v-spacer />
				<v-btn
					v-if="unprinted.length"
					color="warning"
					variant="tonal"
					:loading="busy"
					prepend-icon="mdi-delete-sweep"
					@click="onDeleteAndContinue"
				>
					{{ __("Delete unprinted drafts & continue") }}
				</v-btn>
				<v-btn color="primary" :disabled="busy" @click="onContinue">
					{{ __("Continue without deleting") }}
				</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>

<script setup>
import { ref, watch, getCurrentInstance, inject, onMounted, onBeforeUnmount } from "vue";
import { useToastStore } from "../../../stores/toastStore";

defineOptions({ name: "PreCloseDraftsDialog" });

const __ = window.__ || ((value) => value);

const instance = getCurrentInstance();
const eventBus = instance?.proxy?.eventBus || inject("eventBus");
const toastStore = useToastStore();

const dialogOpen = ref(false);
const busy = ref(false);
const unprinted = ref([]);
const printed = ref([]);
const openingShift = ref(null);
const posProfileName = ref(null);
let resolveDecision = null;

function formatTotal(value) {
	const n = Number(value);
	if (!Number.isFinite(n)) return "—";
	return n.toFixed(3);
}

function open(payload) {
	unprinted.value = payload.unprinted || [];
	printed.value = payload.printed || [];
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
			console.error("PreCloseDraftsDialog onResolve threw", error);
		}
	}
	resolveDecision = null;
	dialogOpen.value = false;
}

function onCancel() {
	finish("cancel");
}

function onContinue() {
	finish("continue");
}

async function onDeleteAndContinue() {
	if (busy.value) return;
	busy.value = true;
	try {
		const resp = await frappe.call(
			"posawesome.posawesome.doctype.pos_closing_shift.closing_processing.invoices.delete_open_draft_invoices",
			{
				pos_opening_shift: openingShift.value,
				pos_profile: posProfileName.value,
			},
		);
		const result = resp?.message || {};
		const deletedCount = Array.isArray(result.deleted) ? result.deleted.length : 0;
		const skippedCount = Array.isArray(result.skipped) ? result.skipped.length : 0;
		toastStore.show({
			title: __("Drafts cleaned up"),
			detail: skippedCount
				? __("{0} deleted, {1} skipped (see Error Log).", [deletedCount, skippedCount])
				: __("{0} draft(s) deleted.", [deletedCount]),
			color: skippedCount ? "warning" : "success",
		});
	} catch (error) {
		console.error("Failed to delete open drafts", error);
		toastStore.show({
			title: __("Cleanup failed"),
			detail: __("Could not delete the listed drafts. Try again or close them manually."),
			color: "error",
		});
		busy.value = false;
		return;
	}
	finish("continue");
}

watch(dialogOpen, (val) => {
	if (!val && resolveDecision) {
		// Dialog dismissed via overlay/escape — treat as cancel.
		const fn = resolveDecision;
		resolveDecision = null;
		try {
			fn("cancel");
		} catch (error) {
			console.error("PreCloseDraftsDialog dismiss handler threw", error);
		}
	}
});

onMounted(() => {
	eventBus?.on?.("open_PreCloseDraftsDialog", open);
});

onBeforeUnmount(() => {
	eventBus?.off?.("open_PreCloseDraftsDialog", open);
});
</script>

<style scoped>
.pre-close-drafts-card {
	border-radius: 16px !important;
	overflow: hidden;
	background: var(--pos-card-bg);
	color: var(--pos-text-primary);
	box-shadow: 0 4px 20px var(--pos-shadow) !important;
	max-height: 90vh;
}

.pre-close-drafts-header {
	background: var(--pos-card-bg);
	border-bottom: 1px solid var(--pos-border);
	position: relative;
	min-height: auto !important;
}

.pre-close-drafts-header::before {
	content: "";
	position: absolute;
	top: 0;
	left: 0;
	right: 0;
	height: 3px;
	background: linear-gradient(90deg, #f46a25 0%, #ffb380 100%);
}

.pre-close-drafts-header__content {
	display: flex;
	align-items: center;
	gap: 14px;
}

.pre-close-drafts-header__icon {
	background: linear-gradient(135deg, #f46a25 0%, #c75418 100%);
	border-radius: 14px;
	width: 44px;
	height: 44px;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	color: #fff;
	flex-shrink: 0;
}

.pre-close-drafts-header__title {
	margin: 0;
	font-size: 1.05rem;
	font-weight: 700;
	color: var(--pos-text-primary);
}

.pre-close-drafts-header__subtitle {
	margin: 2px 0 0;
	font-size: 0.78rem;
	color: var(--pos-text-secondary);
}

.pre-close-drafts-body {
	background: var(--pos-bg-secondary, var(--pos-card-bg));
}

.pre-close-drafts-section {
	padding: 14px 18px;
}

.pre-close-drafts-section__header {
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

.pre-close-drafts-empty {
	font-size: 0.82rem;
	color: var(--pos-text-secondary);
	font-style: italic;
}

.pre-close-drafts-warning {
	border: 1px solid rgba(239, 68, 68, 0.32);
	background: rgba(239, 68, 68, 0.08);
	border-radius: 10px;
	padding: 10px 14px;
	font-size: 0.8rem;
	color: var(--pos-text-primary);
	margin-bottom: 10px;
	line-height: 1.4;
}

.pre-close-drafts-list {
	margin: 0;
	padding: 0;
	list-style: none;
	display: grid;
	gap: 6px;
	max-height: 220px;
	overflow-y: auto;
}

.pre-close-drafts-row {
	display: grid;
	grid-template-columns: 1.4fr 1fr 0.7fr;
	gap: 10px;
	align-items: center;
	padding: 8px 12px;
	border: 1px solid var(--pos-border);
	border-radius: 10px;
	background: var(--pos-surface, rgba(148, 163, 184, 0.06));
	font-size: 0.82rem;
}

.pre-close-drafts-row__name {
	font-weight: 700;
	color: var(--pos-text-primary);
}

.pre-close-drafts-row__customer {
	color: var(--pos-text-secondary);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.pre-close-drafts-row__total {
	text-align: right;
	font-weight: 700;
	color: var(--pos-text-primary);
}

.pre-close-drafts-actions {
	border-top: 1px solid var(--pos-border);
	background: var(--pos-card-bg);
}
</style>
