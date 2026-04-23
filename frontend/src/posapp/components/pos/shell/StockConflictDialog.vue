<template>
	<!--
		The conflict resolver intentionally does NOT use <v-dialog>. Mounting
		a Vuetify dialog while the Payments <v-dialog> is in its leave
		transition put both dialogs into the global VOverlay stack at the
		same time and pegged the main thread (focus-trap re-entry + scroll
		lock toggling). The browser locked so hard DevTools wouldn't open
		even after the parent dialog had visually closed. A plain teleport
		with a native scrim sidesteps every piece of that machinery.

		See PR notes / commit history for the prior `setTimeout(0)` defer
		attempt — that helped close the parent dialog first but didn't
		break the lockup. The root cause was Vuetify's overlay stack, not
		the timing.
	-->
	<Teleport v-if="open" to="body">
		<div
			class="conflict-overlay"
			role="presentation"
			@click.self="cancelDialog"
		>
			<div
				class="conflict-dialog-card"
				role="dialog"
				aria-modal="true"
				:aria-label="__('Stock has changed')"
				@click.stop
			>
				<!-- ─────────────────── Header ─────────────────── -->
				<div class="conflict-dialog__header">
					<div class="conflict-dialog__icon-wrap">
						<v-icon class="conflict-dialog__icon">mdi-alert-octagon</v-icon>
					</div>
					<div class="conflict-dialog__header-text">
						<h3 class="conflict-dialog__title">
							{{ __("Stock has changed") }}
						</h3>
						<p class="conflict-dialog__subtitle">
							{{ subtitleText }}
						</p>
					</div>
					<button
						type="button"
						class="conflict-dialog__close"
						:aria-label="__('Close')"
						@click="cancelDialog"
					>
						<v-icon>mdi-close</v-icon>
					</button>
				</div>

				<!-- ─────────────────── Body ─────────────────── -->
				<div class="conflict-dialog__body">
					<!-- Shortage summary cards -->
					<section v-if="shortages.length" class="conflict-section">
						<header class="conflict-section__header">
							<v-icon size="16" class="conflict-section__icon">mdi-package-variant-closed-remove</v-icon>
							<span class="conflict-section__title">
								{{ __("Lines that exceed available stock") }}
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
								<div v-if="s.batch_no" class="shortage-card__row">
									<span class="shortage-card__label">{{ __("Batch") }}</span>
									<code class="shortage-card__batch">{{ s.batch_no }}</code>
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

					<!-- Plain-language explainer so the cashier knows what each
					     button does without guessing. Drafts intentionally do
					     NOT reserve stock here — see _collect_stock_errors. -->
					<section class="conflict-section">
						<header class="conflict-section__header">
							<v-icon size="16" class="conflict-section__icon">mdi-information-outline</v-icon>
							<span class="conflict-section__title">
								{{ __("How to proceed") }}
							</span>
						</header>
						<p class="conflict-explainer">
							{{
								__(
									"Drafts don't reserve stock — another terminal may have sold these units in the meantime. Reduce the cart to what's available now, stash the sale as a draft to revisit later, or cancel.",
								)
							}}
						</p>
					</section>
				</div>

				<!-- ─────────────────── Actions ─────────────────── -->
				<hr class="conflict-dialog__divider" />
				<div class="conflict-dialog__actions">
					<button
						type="button"
						class="conflict-action conflict-action--cancel"
						@click="cancelCurrentSale"
					>
						<v-icon start>mdi-cart-remove</v-icon>
						{{ __("Cancel current sale") }}
					</button>
					<button
						type="button"
						class="conflict-action conflict-action--draft"
						@click="saveCurrentAsDraft"
					>
						<v-icon start>mdi-content-save-edit-outline</v-icon>
						{{ __("Save as draft") }}
					</button>
					<span class="conflict-action__spacer" />
					<button
						type="button"
						class="conflict-action conflict-action--primary"
						:disabled="!shortages.length"
						@click="reduceQtyToAvailable"
					>
						<v-icon start>mdi-arrow-collapse-down</v-icon>
						{{ __("Reduce qty & retry") }}
					</button>
				</div>
			</div>
		</div>
	</Teleport>
</template>

<script>
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useToastStore } from "../../../stores/toastStore.js";

export default {
	name: "StockConflictDialog",
	setup() {
		const eventBus = inject("eventBus");
		const toastStore = useToastStore();
		const __ = window.__ || ((t) => t);

		const open = ref(false);
		const shortages = ref([]);
		// Optional context payload passed in by usePaymentSubmission so
		// the dialog knows what to do when the cashier picks "save as
		// draft", "cancel current sale", or "reduce qty & retry". Each
		// handler is optional — if absent, we fall back to a sensible
		// default (emit a bus event the Invoice mixin already listens to).
		const context = ref({
			invoiceName: null,
			invoiceDoctype: null,
			onCancelCurrentSale: null,
			onSaveCurrentAsDraft: null,
			onResolved: null,
		});

		// Two distinct shortage stories drive the subtitle:
		//   1. Batch-specific shortage → name the batch wording so the
		//      cashier knows a different batch may still work.
		//   2. Plain Bin overdraw → just say the qty is below request.
		// Drafts intentionally do NOT factor in here — they don't post
		// SLEs, so they cannot be the cause. Saying "another draft holds
		// this stock" was the old (and misleading) framing.
		const subtitleText = computed(() => {
			const hasBatchShortage = shortages.value.some((s) => !!(s && s.batch_no));
			return hasBatchShortage
				? __(
						"This batch doesn't have enough stock right now. Try a different batch, reduce the qty to what's available, or stash the sale.",
					)
				: __(
						"Available stock is below the requested quantity. Reduce the qty to what's available, stash the sale, or cancel.",
					);
		});

		const formatQty = (value) => {
			const num = Number(value || 0);
			if (!Number.isFinite(num)) return "—";
			return num % 1 === 0 ? num.toFixed(0) : num.toFixed(2);
		};

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
			open.value = true;
		};

		const closeDialog = () => {
			open.value = false;
		};

		const cancelDialog = () => closeDialog();

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

		// "Reduce qty & retry": fire the shortage payload back at the
		// Invoice component, which clamps each short cart line to its
		// available qty (or removes it when zero). Then signal the
		// caller via onResolved so usePaymentSubmission can re-trigger
		// the original submit without the cashier touching anything.
		const reduceQtyToAvailable = () => {
			if (!shortages.value.length) {
				closeDialog();
				return;
			}
			try {
				eventBus?.emit("reduce_qty_for_shortages", {
					shortages: shortages.value,
				});
			} catch (err) {
				console.error("[StockConflictDialog] reduceQtyToAvailable failed", err);
				toastStore.show({
					title: __("Couldn't adjust cart automatically"),
					color: "error",
				});
				return;
			}

			if (typeof context.value.onResolved === "function") {
				try {
					context.value.onResolved({ reducedQty: true });
				} catch (innerErr) {
					console.error(
						"[StockConflictDialog] onResolved callback failed",
						innerErr,
					);
				}
			}
			closeDialog();
		};

		// Escape closes the dialog, mirroring the Vuetify behaviour we
		// replaced. Listener is only attached while the overlay is open
		// so we don't intercept Escape elsewhere.
		const onKeydown = (event) => {
			if (event.key === "Escape" && open.value) {
				event.stopPropagation();
				closeDialog();
			}
		};

		watch(open, (isOpen) => {
			if (typeof document === "undefined") return;
			if (isOpen) {
				document.addEventListener("keydown", onKeydown, true);
				document.body.classList.add("conflict-overlay-open");
			} else {
				document.removeEventListener("keydown", onKeydown, true);
				document.body.classList.remove("conflict-overlay-open");
			}
		});

		onMounted(() => {
			if (eventBus) {
				eventBus.on("open_stock_conflict_dialog", onOpenEvent);
			}
		});
		onBeforeUnmount(() => {
			if (eventBus) {
				eventBus.off("open_stock_conflict_dialog", onOpenEvent);
			}
			if (typeof document !== "undefined") {
				document.removeEventListener("keydown", onKeydown, true);
				document.body.classList.remove("conflict-overlay-open");
			}
		});

		return {
			open,
			shortages,
			subtitleText,
			cancelDialog,
			cancelCurrentSale,
			saveCurrentAsDraft,
			reduceQtyToAvailable,
			formatQty,
			__,
		};
	},
};
</script>

<style scoped>
/* ── Overlay shell (replaces v-dialog) ─────────────────────────── */
.conflict-overlay {
	position: fixed;
	inset: 0;
	z-index: 2400; /* above Vuetify's default 2400-ish v-dialog stack */
	display: flex;
	align-items: center;
	justify-content: center;
	padding: 16px;
	background: rgba(8, 12, 22, 0.62);
	backdrop-filter: blur(2px);
	animation: conflict-overlay-in 140ms ease-out;
}

@keyframes conflict-overlay-in {
	from { opacity: 0; }
	to   { opacity: 1; }
}

/* ── Dialog shell ───────────────────────────────────────────────── */
.conflict-dialog-card {
	width: min(640px, 100%);
	max-height: calc(100vh - 32px);
	overflow: hidden;
	display: flex;
	flex-direction: column;
	border-radius: 18px;
	background: var(--pos-card-bg, #0e131e);
	border: 1px solid rgba(244, 114, 182, 0.25);
	box-shadow:
		0 24px 56px rgba(0, 0, 0, 0.6),
		0 0 0 1px rgba(226, 54, 112, 0.12);
	font-family: var(--posa-font-family, "Space Grotesk", sans-serif);
	color: var(--pos-text-primary, #e7ebf3);
	animation: conflict-card-in 180ms cubic-bezier(0.2, 0.8, 0.3, 1);
}

@keyframes conflict-card-in {
	from { opacity: 0; transform: translateY(6px) scale(0.98); }
	to   { opacity: 1; transform: translateY(0)   scale(1); }
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

.conflict-dialog__close:hover {
	background: rgba(244, 63, 94, 0.15);
	color: #fb7185;
}

/* ── Body ──────────────────────────────────────────────────────── */
.conflict-dialog__body {
	padding: 18px 22px 6px;
	display: flex;
	flex-direction: column;
	gap: 18px;
	background: var(--pos-card-bg, #0e131e);
	overflow-y: auto;
	flex: 1 1 auto;
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

.conflict-explainer {
	margin: 0;
	font-size: 0.84rem;
	line-height: 1.5;
	color: rgba(231, 235, 243, 0.7);
	padding: 10px 12px;
	border-radius: 10px;
	background: rgba(15, 23, 42, 0.4);
	border: 1px solid rgba(167, 139, 250, 0.18);
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

/* ── Footer / actions ──────────────────────────────────────────── */
.conflict-dialog__divider {
	border: 0;
	border-top: 1px solid rgba(139, 92, 246, 0.18);
	margin: 0;
}

.conflict-dialog__actions {
	padding: 14px 18px;
	display: flex;
	align-items: center;
	gap: 8px;
	background: var(--pos-surface-muted, #161c27);
	flex-wrap: nowrap;
}

/* Spacer used to push the primary action to the right on wider rows.
   On the typical 640px dialog the three buttons are tight, so let it
   collapse to nothing rather than forcing a wrap. */
.conflict-action__spacer {
	flex: 0 1 8px;
	min-width: 0;
}

.conflict-action {
	all: unset;
	cursor: pointer;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	gap: 4px;
	padding: 9px 12px;
	border-radius: 10px;
	/* Match the bottom-bar Save & Clear / PAY buttons — medium weight,
	   small font, no extra letter-spacing. The previous bold/0.84rem
	   read heavier than the rest of the UI. */
	font-weight: 500;
	letter-spacing: 0;
	font-size: 0.78rem;
	color: #fff;
	box-sizing: border-box;
	white-space: nowrap;
	flex: 0 1 auto;
	min-width: 0;
	transition: transform 0.18s ease, box-shadow 0.18s ease, filter 0.18s ease;
	font-family: var(--posa-font-family, "Space Grotesk", sans-serif);
}

.conflict-action:not(:disabled):hover {
	transform: translateY(-1px);
	filter: brightness(1.05);
}

.conflict-action:focus-visible {
	outline: 2px solid rgba(167, 139, 250, 0.7);
	outline-offset: 2px;
}

.conflict-action--cancel {
	background: linear-gradient(135deg, rgba(244, 63, 94, 0.95), rgba(225, 29, 72, 0.95));
	box-shadow: 0 4px 14px rgba(244, 63, 94, 0.28);
}

.conflict-action--draft {
	background: linear-gradient(135deg, rgba(59, 130, 246, 0.95), rgba(37, 99, 235, 0.95));
	box-shadow: 0 4px 14px rgba(59, 130, 246, 0.28);
}

.conflict-action--primary {
	background: linear-gradient(
		135deg,
		#8b5cf6 0%,
		#a78bfa 40%,
		#e23670 100%
	);
	border: 1px solid rgba(167, 139, 250, 0.5);
	box-shadow: 0 6px 18px rgba(139, 92, 246, 0.35);
}

.conflict-action[disabled],
.conflict-action--primary:disabled {
	opacity: 0.45;
	filter: grayscale(0.3);
	box-shadow: none;
	cursor: not-allowed;
	pointer-events: none;
}

@media (max-width: 600px) {
	.conflict-dialog__actions {
		padding: 12px 14px;
		flex-wrap: wrap;
	}

	.conflict-action {
		flex: 1 1 calc(50% - 6px);
		justify-content: center;
	}

	.conflict-action__spacer {
		display: none;
	}
}
</style>

<style>
/* Global helper so the underlying page can be locked from scrolling
   while the conflict overlay is up — mirrors what v-dialog does
   without pulling in Vuetify's overlay machinery. */
body.conflict-overlay-open {
	overflow: hidden;
}
</style>
