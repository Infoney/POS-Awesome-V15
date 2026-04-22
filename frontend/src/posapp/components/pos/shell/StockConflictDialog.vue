<template>
	<v-dialog
		v-model="open"
		max-width="780px"
		:persistent="resolving"
		scrollable
	>
		<v-card class="conflict-dialog-card" elevation="10">
			<!-- ─────────────────── Header ─────────────────── -->
			<div class="conflict-dialog__header">
				<div class="conflict-dialog__icon-wrap">
					<v-icon class="conflict-dialog__icon">mdi-alert-octagon</v-icon>
				</div>
				<div class="conflict-dialog__header-text">
					<h3 class="conflict-dialog__title">
						{{ __("Stock conflict detected") }}
					</h3>
					<p class="conflict-dialog__subtitle">
						{{ subtitleText }}
					</p>
				</div>
				<button
					type="button"
					class="conflict-dialog__close"
					:disabled="resolving"
					:aria-label="__('Close')"
					@click="cancelDialog"
				>
					<v-icon>mdi-close</v-icon>
				</button>
			</div>

			<!-- ─────────────────── Body ─────────────────── -->
			<v-card-text class="conflict-dialog__body">
				<!-- Shortage summary cards -->
				<section v-if="shortages.length" class="conflict-section">
					<header class="conflict-section__header">
						<v-icon size="16" class="conflict-section__icon">mdi-package-variant-closed-remove</v-icon>
						<span class="conflict-section__title">
							{{ __("What's blocking the sale") }}
						</span>
					</header>
					<div class="shortage-grid">
						<div
							v-for="s in shortages"
							:key="`${s.item_code}::${s.batch_no}::${s.warehouse}`"
							class="shortage-card"
						>
							<div class="shortage-card__head">
								<span class="shortage-card__item">{{ s.label || s.item_code }}</span>
								<span class="shortage-card__warehouse" :title="s.warehouse">
									<v-icon size="12">mdi-warehouse</v-icon>
									{{ s.warehouse }}
								</span>
							</div>
							<div class="shortage-card__row">
								<span class="shortage-card__label">{{ __("Batch") }}</span>
								<code class="shortage-card__batch">{{ s.batch_no || "—" }}</code>
							</div>
							<div class="shortage-card__numbers">
								<div class="shortage-card__metric">
									<span class="shortage-card__metric-label">{{ __("Available") }}</span>
									<strong class="shortage-card__metric-value shortage-card__metric-value--warn">
										{{ formatQty(s.available) }}
									</strong>
								</div>
								<v-icon size="14" class="shortage-card__arrow">mdi-arrow-right</v-icon>
								<div class="shortage-card__metric">
									<span class="shortage-card__metric-label">{{ __("Requested") }}</span>
									<strong class="shortage-card__metric-value">
										{{ formatQty(s.requested) }}
									</strong>
								</div>
							</div>
						</div>
					</div>
				</section>

				<!-- Drafts list -->
				<section class="conflict-section">
					<header class="conflict-section__header">
						<v-icon size="16" class="conflict-section__icon">mdi-file-document-multiple-outline</v-icon>
						<span class="conflict-section__title">
							{{ __("Draft invoices holding this stock") }}
						</span>
						<span v-if="loading" class="conflict-section__hint">
							<v-progress-circular size="14" width="2" indeterminate color="#a78bfa" />
							{{ __("Searching…") }}
						</span>
						<span v-else-if="!drafts.length" class="conflict-section__hint">
							{{ __("No related drafts found") }}
						</span>
					</header>

					<div
						v-if="!loading && !drafts.length"
						class="conflict-empty"
					>
						<v-icon size="22" class="conflict-empty__icon">mdi-information-outline</v-icon>
						<p>
							{{
								__(
									"We couldn't find a draft invoice claiming this batch. The actual stock may have just been depleted on another terminal — please refresh availability and try again.",
								)
							}}
						</p>
					</div>

					<ul v-if="drafts.length" class="draft-list">
						<li
							v-for="draft in drafts"
							:key="`${draft.doctype}::${draft.name}`"
							class="draft-card"
							:class="{ 'draft-card--selected': isSelected(draft) }"
						>
							<label class="draft-card__check">
								<input
									type="checkbox"
									:checked="isSelected(draft)"
									:disabled="resolving"
									@change="toggleSelected(draft)"
								/>
								<span class="draft-card__check-mark"></span>
							</label>

							<div class="draft-card__body">
								<div class="draft-card__top">
									<span class="draft-card__name">{{ draft.name }}</span>
									<span class="draft-card__doctype">{{ draft.doctype }}</span>
									<span class="draft-card__customer">{{ draft.customer_name || draft.customer || __("No customer") }}</span>
								</div>
								<div class="draft-card__meta">
									<span class="draft-card__meta-chip">
										<v-icon size="12">mdi-calendar</v-icon>
										{{ formatDate(draft.posting_date || draft.modified) }}
									</span>
									<span class="draft-card__meta-chip">
										<v-icon size="12">mdi-account-circle-outline</v-icon>
										{{ draft.owner }}
									</span>
									<span v-if="draft.conflict_qty" class="draft-card__meta-chip draft-card__meta-chip--warn">
										<v-icon size="12">mdi-package-variant-closed</v-icon>
										{{ __("Holds") }} {{ formatQty(draft.conflict_qty) }}
									</span>
								</div>
								<div class="draft-card__items">
									<span
										v-for="(line, idx) in draft.items"
										:key="`${draft.name}-${idx}`"
										class="draft-card__line"
									>
										{{ line.item_name || line.item_code }}
										<small v-if="line.batch_no">· {{ line.batch_no }}</small>
										<small>· {{ formatQty(line.stock_qty || line.qty) }}</small>
									</span>
								</div>
							</div>

							<button
								type="button"
								class="draft-card__view"
								:disabled="resolving"
								:aria-label="__('Open invoice in new tab')"
								@click="openDraft(draft)"
							>
								<v-icon size="18">mdi-open-in-new</v-icon>
							</button>
						</li>
					</ul>

					<div v-if="drafts.length" class="draft-list__footer">
						<button
							type="button"
							class="draft-list__select-all"
							:disabled="resolving"
							@click="toggleSelectAll"
						>
							{{ allSelected ? __("Clear selection") : __("Select all") }}
						</button>
						<span class="draft-list__counter">
							{{ __("{0} of {1} selected", [selectedKeys.size, drafts.length]) }}
						</span>
					</div>
				</section>
			</v-card-text>

			<!-- ─────────────────── Actions ─────────────────── -->
			<v-divider class="conflict-dialog__divider" />
			<v-card-actions class="conflict-dialog__actions">
				<v-btn
					theme="dark"
					class="conflict-action conflict-action--ghost"
					:disabled="resolving"
					size="large"
					@click="refreshDrafts"
				>
					<v-icon start>mdi-refresh</v-icon>
					{{ __("Refresh") }}
				</v-btn>
				<v-spacer />
				<v-btn
					theme="dark"
					class="conflict-action conflict-action--cancel"
					:disabled="resolving"
					size="large"
					@click="cancelCurrentSale"
				>
					<v-icon start>mdi-cart-remove</v-icon>
					{{ __("Cancel current sale") }}
				</v-btn>
				<v-btn
					theme="dark"
					class="conflict-action conflict-action--draft"
					:disabled="resolving"
					size="large"
					@click="saveCurrentAsDraft"
				>
					<v-icon start>mdi-content-save-edit-outline</v-icon>
					{{ __("Save as draft") }}
				</v-btn>
				<v-btn
					theme="dark"
					class="conflict-action conflict-action--primary"
					:disabled="!selectedKeys.size || resolving"
					:loading="resolving"
					size="large"
					@click="deleteSelectedDrafts"
				>
					<v-icon start>mdi-trash-can-outline</v-icon>
					{{ __("Delete & retry") }}
				</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>

<script>
import { computed, inject, onBeforeUnmount, onMounted, ref } from "vue";
import { useToastStore } from "../../../stores/toastStore.js";

export default {
	name: "StockConflictDialog",
	setup() {
		const eventBus = inject("eventBus");
		const toastStore = useToastStore();
		const __ = window.__ || ((t) => t);

		const open = ref(false);
		const loading = ref(false);
		const resolving = ref(false);
		const shortages = ref([]);
		const drafts = ref([]);
		const selectedKeys = ref(new Set());
		// Optional context payload passed in by usePaymentSubmission so
		// the dialog knows what to do when the cashier picks "save as draft"
		// or "cancel current sale". Each handler is optional — if absent,
		// we fall back to a sensible default (just close the dialog).
		const context = ref({
			invoiceName: null,
			invoiceDoctype: null,
			onCancelCurrentSale: null,
			onSaveCurrentAsDraft: null,
			onResolved: null,
		});

		const allSelected = computed(
			() => drafts.value.length > 0 && selectedKeys.value.size === drafts.value.length,
		);

		// The dialog handles two distinct shortage reasons:
		//   1. Batch claimed by another draft  → "same batch is already claimed…"
		//   2. Bin total too low / non-batched → "stock is below the requested qty…"
		// Only show the batch wording when at least one shortage actually
		// references a batch_no — otherwise the cashier sees a confusing
		// "claimed by other invoices" line for an item that isn't even batched.
		const subtitleText = computed(() => {
			const hasBatchShortage = shortages.value.some((s) => !!(s && s.batch_no));
			return hasBatchShortage
				? __(
						"Your sale cannot be completed because the same batch is already claimed by other invoices that haven't been submitted yet.",
					)
				: __(
						"Your sale cannot be completed because the available stock is below the requested quantity.",
					);
		});

		const keyFor = (draft) => `${draft.doctype}::${draft.name}`;
		const isSelected = (draft) => selectedKeys.value.has(keyFor(draft));

		const formatQty = (value) => {
			const num = Number(value || 0);
			if (!Number.isFinite(num)) return "—";
			return num % 1 === 0 ? num.toFixed(0) : num.toFixed(2);
		};

		const formatDate = (raw) => {
			if (!raw) return "—";
			try {
				const date = new Date(raw);
				if (Number.isNaN(date.getTime())) return raw;
				return date.toLocaleDateString(undefined, {
					year: "numeric",
					month: "short",
					day: "numeric",
				});
			} catch {
				return raw;
			}
		};

		const toggleSelected = (draft) => {
			const next = new Set(selectedKeys.value);
			const key = keyFor(draft);
			if (next.has(key)) next.delete(key);
			else next.add(key);
			selectedKeys.value = next;
		};

		const toggleSelectAll = () => {
			if (allSelected.value) {
				selectedKeys.value = new Set();
			} else {
				selectedKeys.value = new Set(drafts.value.map(keyFor));
			}
		};

		const openDraft = (draft) => {
			try {
				const slug = draft.doctype.toLowerCase().replace(/\s+/g, "-");
				const url = `/app/${slug}/${encodeURIComponent(draft.name)}`;
				window.open(url, "_blank", "noopener");
			} catch (err) {
				console.error("[StockConflictDialog] failed to open draft", err);
			}
		};

		const fetchDrafts = async () => {
			if (!shortages.value.length) {
				drafts.value = [];
				return;
			}
			loading.value = true;
			try {
				const payload = shortages.value.map((s) => ({
					item_code: s.item_code,
					batch_no: s.batch_no || null,
					warehouse: s.warehouse || null,
				}));
				const resp = await frappe.call({
					method:
						"posawesome.posawesome.api.item_processing.stock.get_draft_invoices_for_items",
					args: {
						items: payload,
						exclude_invoice: context.value.invoiceName || null,
					},
				});
				const list = Array.isArray(resp?.message?.drafts)
					? resp.message.drafts
					: [];
				drafts.value = list;
				// Pre-select all by default — the cashier almost always
				// wants to delete every blocker in one shot.
				selectedKeys.value = new Set(list.map(keyFor));
			} catch (err) {
				console.error("[StockConflictDialog] fetchDrafts failed", err);
				toastStore.show({
					title: __("Couldn't load conflicting drafts"),
					color: "error",
				});
				drafts.value = [];
			} finally {
				loading.value = false;
			}
		};

		const refreshDrafts = () => fetchDrafts();

		const onOpenEvent = (payload) => {
			shortages.value = Array.isArray(payload?.shortages)
				? payload.shortages
				: [];
			context.value = {
				invoiceName: payload?.invoiceName || null,
				invoiceDoctype: payload?.invoiceDoctype || null,
				onCancelCurrentSale: payload?.onCancelCurrentSale || null,
				onSaveCurrentAsDraft: payload?.onSaveCurrentAsDraft || null,
				onResolved: payload?.onResolved || null,
			};
			selectedKeys.value = new Set();
			drafts.value = [];
			open.value = true;
			fetchDrafts();
		};

		const closeDialog = () => {
			open.value = false;
			resolving.value = false;
			selectedKeys.value = new Set();
		};

		const cancelDialog = () => {
			if (resolving.value) return;
			closeDialog();
		};

		const cancelCurrentSale = () => {
			try {
				if (typeof context.value.onCancelCurrentSale === "function") {
					context.value.onCancelCurrentSale();
				} else {
					eventBus?.emit("cancel_current_sale");
				}
			} catch (err) {
				console.error("[StockConflictDialog] cancelCurrentSale failed", err);
			}
			closeDialog();
		};

		const saveCurrentAsDraft = () => {
			try {
				if (typeof context.value.onSaveCurrentAsDraft === "function") {
					context.value.onSaveCurrentAsDraft();
				} else {
					eventBus?.emit("save_current_invoice_as_draft");
				}
				toastStore.show({
					title: __("Sale saved as draft for later"),
					color: "info",
				});
			} catch (err) {
				console.error("[StockConflictDialog] saveCurrentAsDraft failed", err);
				toastStore.show({
					title: __("Couldn't save current sale as draft"),
					color: "error",
				});
			}
			closeDialog();
		};

		const deleteSelectedDrafts = async () => {
			if (!selectedKeys.value.size) return;
			const targets = drafts.value.filter((d) => selectedKeys.value.has(keyFor(d)));
			if (!targets.length) return;

			resolving.value = true;
			try {
				const resp = await frappe.call({
					method:
						"posawesome.posawesome.api.item_processing.stock.delete_draft_invoices",
					args: {
						invoices: targets.map((d) => ({
							doctype: d.doctype,
							name: d.name,
						})),
					},
				});
				const result = resp?.message || {};
				const deleted = Array.isArray(result.deleted) ? result.deleted : [];
				const failed = Array.isArray(result.failed) ? result.failed : [];

				if (deleted.length) {
					toastStore.show({
						title: __("Deleted {0} draft invoice(s)", [deleted.length]),
						color: "success",
					});
				}
				if (failed.length) {
					const detail = failed
						.map((f) => `${f.name}: ${f.error || __("Unknown error")}`)
						.join("\n");
					toastStore.show({
						title: __("Couldn't delete {0} invoice(s)", [failed.length]),
						color: "warning",
						detail,
					});
				}

				// If everything went away, close + signal the caller so it
				// can retry the original submission.
				if (!failed.length && deleted.length) {
					if (typeof context.value.onResolved === "function") {
						try {
							context.value.onResolved({ deleted });
						} catch (innerErr) {
							console.error(
								"[StockConflictDialog] onResolved callback failed",
								innerErr,
							);
						}
					}
					closeDialog();
					return;
				}

				// Otherwise reload the list so the cashier can see what's left
				await fetchDrafts();
			} catch (err) {
				console.error("[StockConflictDialog] deleteSelectedDrafts failed", err);
				toastStore.show({
					title: __("Failed to delete drafts"),
					color: "error",
				});
			} finally {
				resolving.value = false;
			}
		};

		onMounted(() => {
			if (eventBus) {
				eventBus.on("open_stock_conflict_dialog", onOpenEvent);
			}
		});
		onBeforeUnmount(() => {
			if (eventBus) {
				eventBus.off("open_stock_conflict_dialog", onOpenEvent);
			}
		});

		return {
			open,
			loading,
			resolving,
			shortages,
			drafts,
			selectedKeys,
			allSelected,
			subtitleText,
			isSelected,
			toggleSelected,
			toggleSelectAll,
			openDraft,
			refreshDrafts,
			cancelDialog,
			cancelCurrentSale,
			saveCurrentAsDraft,
			deleteSelectedDrafts,
			formatQty,
			formatDate,
			__,
		};
	},
};
</script>

<style scoped>
/* ── Dialog shell ───────────────────────────────────────────────── */
.conflict-dialog-card {
	border-radius: 18px;
	overflow: hidden;
	background: var(--pos-card-bg, #0e131e) !important;
	border: 1px solid rgba(244, 114, 182, 0.25);
	box-shadow:
		0 24px 56px rgba(0, 0, 0, 0.6),
		0 0 0 1px rgba(226, 54, 112, 0.12);
	font-family: var(--posa-font-family, "Space Grotesk", sans-serif);
	color: var(--pos-text-primary, #e7ebf3);
}

.conflict-dialog-card,
.conflict-dialog-card :deep(*) {
	font-family: var(--posa-font-family, "Space Grotesk", sans-serif);
}

/* ── Header ────────────────────────────────────────────────────── */
.conflict-dialog__header {
	display: flex;
	align-items: flex-start;
	gap: 14px;
	padding: 18px 22px 16px;
	background:
		linear-gradient(135deg, rgba(244, 63, 94, 0.16), rgba(226, 54, 112, 0.08)),
		var(--pos-surface-muted, #161c27);
	border-bottom: 1px solid rgba(244, 114, 182, 0.2);
}

.conflict-dialog__icon-wrap {
	width: 44px;
	height: 44px;
	display: grid;
	place-items: center;
	border-radius: 12px;
	flex-shrink: 0;
	background: linear-gradient(135deg, rgba(244, 63, 94, 0.28), rgba(226, 54, 112, 0.22));
	border: 1px solid rgba(244, 63, 94, 0.45);
	box-shadow: 0 4px 14px rgba(244, 63, 94, 0.22);
}

.conflict-dialog__icon {
	font-size: 26px !important;
	color: #fb7185 !important;
}

.conflict-dialog__header-text {
	flex: 1;
	min-width: 0;
}

.conflict-dialog__title {
	margin: 0 0 4px;
	font-size: 1.1rem;
	font-weight: 700;
	letter-spacing: 0.01em;
	color: #f5d0fe;
}

.conflict-dialog__subtitle {
	margin: 0;
	font-size: 0.86rem;
	line-height: 1.45;
	color: rgba(231, 235, 243, 0.72);
}

.conflict-dialog__close {
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

.conflict-dialog__close:hover:not(:disabled) {
	background: rgba(244, 63, 94, 0.15);
	color: #fb7185;
}

.conflict-dialog__close:disabled {
	opacity: 0.35;
	cursor: not-allowed;
}

/* ── Body ──────────────────────────────────────────────────────── */
.conflict-dialog__body {
	padding: 18px 22px 6px !important;
	max-height: 60vh;
	display: flex;
	flex-direction: column;
	gap: 18px;
	background: var(--pos-card-bg, #0e131e);
}

.conflict-section {
	display: flex;
	flex-direction: column;
	gap: 8px;
}

.conflict-section__header {
	display: flex;
	align-items: center;
	gap: 8px;
}

.conflict-section__icon {
	color: #a78bfa;
}

.conflict-section__title {
	font-size: 0.74rem;
	font-weight: 700;
	letter-spacing: 0.12em;
	text-transform: uppercase;
	color: rgba(231, 235, 243, 0.75);
}

.conflict-section__hint {
	margin-left: auto;
	display: inline-flex;
	align-items: center;
	gap: 6px;
	font-size: 0.78rem;
	color: rgba(231, 235, 243, 0.6);
}

/* ── Shortage cards ────────────────────────────────────────────── */
.shortage-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
	gap: 10px;
}

.shortage-card {
	border-radius: 12px;
	padding: 12px 14px;
	background: linear-gradient(
		135deg,
		rgba(244, 63, 94, 0.08),
		rgba(139, 92, 246, 0.06)
	);
	border: 1px solid rgba(244, 114, 182, 0.25);
	display: flex;
	flex-direction: column;
	gap: 8px;
}

.shortage-card__head {
	display: flex;
	align-items: baseline;
	justify-content: space-between;
	gap: 8px;
}

.shortage-card__item {
	font-size: 0.95rem;
	font-weight: 700;
	color: #f5d0fe;
}

.shortage-card__warehouse {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	font-size: 0.7rem;
	color: rgba(231, 235, 243, 0.55);
	max-width: 50%;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.shortage-card__row {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: 0.78rem;
}

.shortage-card__label {
	color: rgba(231, 235, 243, 0.55);
	text-transform: uppercase;
	letter-spacing: 0.08em;
	font-size: 0.66rem;
	font-weight: 600;
}

.shortage-card__batch {
	font-family: "Space Grotesk", monospace;
	background: rgba(139, 92, 246, 0.15);
	color: #d8b4fe;
	padding: 2px 8px;
	border-radius: 6px;
	font-size: 0.78rem;
	letter-spacing: 0.04em;
}

.shortage-card__numbers {
	display: flex;
	align-items: center;
	gap: 10px;
}

.shortage-card__metric {
	display: flex;
	flex-direction: column;
	gap: 0;
}

.shortage-card__metric-label {
	font-size: 0.65rem;
	font-weight: 600;
	letter-spacing: 0.1em;
	text-transform: uppercase;
	color: rgba(231, 235, 243, 0.5);
}

.shortage-card__metric-value {
	font-size: 1.05rem;
	font-weight: 700;
	color: #fff;
	font-variant-numeric: tabular-nums;
}

.shortage-card__metric-value--warn {
	color: #fb7185;
}

.shortage-card__arrow {
	color: rgba(231, 235, 243, 0.4);
}

/* ── Drafts list ───────────────────────────────────────────────── */
.draft-list {
	list-style: none;
	margin: 0;
	padding: 0;
	display: flex;
	flex-direction: column;
	gap: 8px;
}

.draft-card {
	display: flex;
	align-items: stretch;
	gap: 10px;
	padding: 12px 14px;
	border-radius: 12px;
	background: var(--pos-surface-muted, #161c27);
	border: 1px solid rgba(139, 92, 246, 0.18);
	transition: border-color 0.18s ease, background-color 0.18s ease;
}

.draft-card:hover {
	border-color: rgba(167, 139, 250, 0.4);
}

.draft-card--selected {
	border-color: rgba(244, 114, 182, 0.55);
	background: linear-gradient(
		135deg,
		rgba(244, 63, 94, 0.06),
		rgba(139, 92, 246, 0.04)
	);
}

.draft-card__check {
	display: grid;
	place-items: center;
	align-self: flex-start;
	margin-top: 2px;
	cursor: pointer;
	user-select: none;
}

.draft-card__check input {
	position: absolute;
	opacity: 0;
	pointer-events: none;
}

.draft-card__check-mark {
	width: 18px;
	height: 18px;
	border-radius: 5px;
	border: 1.5px solid rgba(167, 139, 250, 0.5);
	background: rgba(15, 23, 42, 0.6);
	display: grid;
	place-items: center;
	transition: background-color 0.18s ease, border-color 0.18s ease;
}

.draft-card__check-mark::after {
	content: "";
	width: 10px;
	height: 10px;
	border-radius: 3px;
	background: linear-gradient(135deg, #a78bfa, #e23670);
	transform: scale(0);
	transition: transform 0.18s cubic-bezier(0.22, 1, 0.36, 1);
}

.draft-card__check input:checked + .draft-card__check-mark {
	border-color: #e23670;
	background: rgba(244, 63, 94, 0.15);
}

.draft-card__check input:checked + .draft-card__check-mark::after {
	transform: scale(1);
}

.draft-card__body {
	flex: 1;
	min-width: 0;
	display: flex;
	flex-direction: column;
	gap: 6px;
}

.draft-card__top {
	display: flex;
	align-items: baseline;
	gap: 8px;
	flex-wrap: wrap;
}

.draft-card__name {
	font-weight: 700;
	font-size: 0.92rem;
	color: #fff;
	letter-spacing: 0.01em;
}

.draft-card__doctype {
	font-size: 0.66rem;
	font-weight: 600;
	letter-spacing: 0.1em;
	text-transform: uppercase;
	padding: 2px 8px;
	border-radius: 999px;
	background: rgba(139, 92, 246, 0.18);
	color: #d8b4fe;
}

.draft-card__customer {
	font-size: 0.84rem;
	color: rgba(231, 235, 243, 0.7);
}

.draft-card__meta {
	display: flex;
	flex-wrap: wrap;
	gap: 6px;
}

.draft-card__meta-chip {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	font-size: 0.72rem;
	color: rgba(231, 235, 243, 0.55);
	padding: 2px 8px;
	border-radius: 999px;
	background: rgba(15, 23, 42, 0.45);
	border: 1px solid rgba(148, 163, 184, 0.2);
}

.draft-card__meta-chip--warn {
	color: #fb7185;
	background: rgba(244, 63, 94, 0.12);
	border-color: rgba(244, 63, 94, 0.3);
}

.draft-card__items {
	display: flex;
	flex-wrap: wrap;
	gap: 6px;
}

.draft-card__line {
	font-size: 0.78rem;
	color: rgba(231, 235, 243, 0.7);
	background: rgba(139, 92, 246, 0.06);
	border: 1px solid rgba(139, 92, 246, 0.18);
	border-radius: 8px;
	padding: 3px 8px;
}

.draft-card__line small {
	color: rgba(231, 235, 243, 0.5);
	margin-left: 4px;
}

.draft-card__view {
	all: unset;
	width: 36px;
	height: 36px;
	display: grid;
	place-items: center;
	border-radius: 8px;
	background: rgba(15, 23, 42, 0.45);
	border: 1px solid rgba(148, 163, 184, 0.2);
	color: rgba(231, 235, 243, 0.7);
	cursor: pointer;
	align-self: center;
	transition: background-color 0.18s ease, color 0.18s ease;
}

.draft-card__view:hover:not(:disabled) {
	background: rgba(139, 92, 246, 0.18);
	color: #a78bfa;
}

.draft-card__view:disabled {
	opacity: 0.4;
	cursor: not-allowed;
}

.draft-list__footer {
	display: flex;
	align-items: center;
	justify-content: space-between;
	padding-top: 4px;
}

.draft-list__select-all {
	all: unset;
	cursor: pointer;
	font-size: 0.78rem;
	font-weight: 600;
	letter-spacing: 0.04em;
	color: #a78bfa;
	padding: 4px 10px;
	border-radius: 8px;
	transition: background-color 0.18s ease;
}

.draft-list__select-all:hover:not(:disabled) {
	background: rgba(139, 92, 246, 0.12);
}

.draft-list__select-all:disabled {
	opacity: 0.4;
	cursor: not-allowed;
}

.draft-list__counter {
	font-size: 0.78rem;
	color: rgba(231, 235, 243, 0.55);
}

/* ── Empty state ───────────────────────────────────────────────── */
.conflict-empty {
	display: flex;
	gap: 10px;
	padding: 14px 16px;
	border-radius: 10px;
	background: rgba(15, 23, 42, 0.45);
	border: 1px dashed rgba(148, 163, 184, 0.25);
	color: rgba(231, 235, 243, 0.7);
	font-size: 0.86rem;
}

.conflict-empty p {
	margin: 0;
	line-height: 1.5;
}

.conflict-empty__icon {
	color: #fbbf24;
	flex-shrink: 0;
}

/* ── Footer / actions ──────────────────────────────────────────── */
.conflict-dialog__divider {
	border-color: rgba(139, 92, 246, 0.18) !important;
}

.conflict-dialog__actions {
	padding: 14px 22px !important;
	gap: 10px;
	background: var(--pos-surface-muted, #161c27);
	flex-wrap: wrap;
}

.conflict-action {
	border-radius: 10px !important;
	text-transform: none !important;
	font-weight: 700 !important;
	letter-spacing: 0.02em !important;
	color: #fff !important;
	transition: transform 0.18s ease, box-shadow 0.18s ease, filter 0.18s ease !important;
}

.conflict-action:not(:disabled):hover {
	transform: translateY(-1px);
	filter: brightness(1.05);
}

.conflict-action--ghost {
	background: transparent !important;
	border: 1px solid rgba(167, 139, 250, 0.35) !important;
	color: #c7c2f0 !important;
}

.conflict-action--ghost:not(:disabled):hover {
	background: rgba(139, 92, 246, 0.12) !important;
}

.conflict-action--cancel {
	background: linear-gradient(135deg, rgba(244, 63, 94, 0.95), rgba(225, 29, 72, 0.95)) !important;
	box-shadow: 0 4px 14px rgba(244, 63, 94, 0.28) !important;
}

.conflict-action--draft {
	background: linear-gradient(135deg, rgba(59, 130, 246, 0.95), rgba(37, 99, 235, 0.95)) !important;
	box-shadow: 0 4px 14px rgba(59, 130, 246, 0.28) !important;
}

.conflict-action--primary {
	background: linear-gradient(
		135deg,
		#8b5cf6 0%,
		#a78bfa 40%,
		#e23670 100%
	) !important;
	border: 1px solid rgba(167, 139, 250, 0.5) !important;
	box-shadow: 0 6px 18px rgba(139, 92, 246, 0.35) !important;
}

.conflict-action--primary:disabled {
	opacity: 0.45;
	filter: grayscale(0.3);
	box-shadow: none !important;
}

@media (max-width: 600px) {
	.conflict-dialog__actions {
		padding: 12px 14px !important;
	}

	.conflict-action {
		flex: 1 1 calc(50% - 6px);
	}
}
</style>
