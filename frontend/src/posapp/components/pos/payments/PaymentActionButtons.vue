<template>
	<v-card flat :class="['payment-actions', 'cards', { compact }]">
		<v-btn
			class="payment-cancel-btn payment-footer-btn"
			variant="flat"
			size="large"
			@click="$emit('cancel')"
			:title="__('Cancel Payment')"
		>
			<v-icon start size="18">mdi-close-circle-outline</v-icon>
			<span class="payment-btn__label">{{ __("Cancel") }}</span>
		</v-btn>

		<v-btn
			ref="submitButton"
			class="payment-submit-btn payment-footer-btn"
			variant="flat"
			size="large"
			color="primary"
			@click="$emit('submit')"
			:loading="loading"
			:disabled="loading || validatePayment"
			:class="{ 'submit-highlight': highlightSubmit }"
			:title="__('Submit (Alt+X)')"
		>
			<v-icon start size="18">mdi-check-circle-outline</v-icon>
			<span class="payment-btn__label">{{ __("Submit") }}</span>
			<ShortcutHint combo="Alt+X" tone="light" class="payment-btn__hint" />
		</v-btn>

		<v-btn
			class="payment-submit-print-btn payment-footer-btn"
			variant="flat"
			size="large"
			color="success"
			@click="$emit('submit-and-print')"
			:loading="loading"
			:disabled="loading || validatePayment"
			:title="__('Submit & Print (Alt+P)')"
		>
			<v-icon start size="18">mdi-printer-check</v-icon>
			<span class="payment-btn__label">{{ __("Submit & Print") }}</span>
			<ShortcutHint combo="Alt+P" tone="light" class="payment-btn__hint" />
		</v-btn>
	</v-card>
</template>

<script setup>
import ShortcutHint from "../invoice/ShortcutHint.vue";

defineProps({
	loading: Boolean,
	validatePayment: Boolean,
	highlightSubmit: Boolean,
	compact: Boolean,
});

defineEmits(["submit", "submit-and-print", "cancel"]);

const __ = window.__;
</script>

<style scoped>
.cards {
	background: transparent !important;
}

.payment-actions {
	display: flex;
	align-items: stretch;
	gap: 12px;
	padding: 0;
	margin: 0;
}

/* Cancel takes a smaller share of the row, the two submits get the rest. */
.payment-actions .payment-cancel-btn {
	flex: 0 0 auto;
	min-width: 140px;
}

.payment-actions .payment-submit-btn,
.payment-actions .payment-submit-print-btn {
	flex: 1 1 0;
	min-width: 0;
}

.compact :deep(.v-btn),
:deep(.compact .v-btn) {
	min-height: 42px;
}

.payment-footer-btn {
	--v-theme-overlay-multiplier: 0 !important;
	transition:
		box-shadow 0.18s ease,
		background 0.18s ease,
		transform 0.18s ease,
		filter 0.18s ease !important;
	color: #ffffff !important;
	min-height: 46px !important;
	border-radius: 12px !important;
	font-weight: 700;
	letter-spacing: 0.02em;
	text-transform: none !important;
}

:deep(.payment-footer-btn .v-btn__content) {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	gap: 6px;
}

.payment-btn__label {
	display: inline-flex;
	align-items: center;
}

.payment-btn__hint {
	margin-inline-start: 4px;
	opacity: 0.85;
}

/* CC violet → pink Submit button */
.payment-submit-btn {
	background: linear-gradient(
		135deg,
		rgba(139, 92, 246, 0.95),
		rgba(167, 122, 250, 0.95)
	) !important;
	box-shadow:
		0 6px 18px rgba(139, 92, 246, 0.28),
		0 0 0 1px rgba(167, 122, 250, 0.4) inset !important;
	border: 1px solid rgba(139, 92, 246, 0.5) !important;
}

/* CC pink → peach Submit & Print button */
.payment-submit-print-btn {
	background: linear-gradient(
		135deg,
		rgba(226, 54, 112, 0.95),
		rgba(244, 114, 182, 0.95)
	) !important;
	box-shadow:
		0 6px 18px rgba(226, 54, 112, 0.28),
		0 0 0 1px rgba(244, 114, 182, 0.4) inset !important;
	border: 1px solid rgba(226, 54, 112, 0.5) !important;
}

/* Cancel demoted to a quiet ghost button — destructive but not loud. */
.payment-cancel-btn {
	background: transparent !important;
	color: #fda4af !important;
	box-shadow: none !important;
	border: 1px solid rgba(244, 63, 94, 0.4) !important;
}

.payment-cancel-btn :deep(.v-btn__content) {
	color: #fda4af;
}

.payment-cancel-btn:not(:disabled):hover {
	background: rgba(244, 63, 94, 0.12) !important;
	border-color: rgba(244, 63, 94, 0.6) !important;
	box-shadow: 0 4px 14px rgba(244, 63, 94, 0.18) !important;
	color: #fb7185 !important;
}

.payment-footer-btn:not(:disabled):hover,
.payment-footer-btn:not(:disabled):focus,
.payment-footer-btn:not(:disabled):focus-visible,
.payment-footer-btn:not(:disabled):active {
	transform: translateY(-1px);
	filter: brightness(1.06);
}

.payment-submit-btn:not(:disabled):hover {
	box-shadow:
		0 10px 26px rgba(139, 92, 246, 0.4),
		0 0 0 1px rgba(167, 122, 250, 0.5) inset !important;
}

.payment-submit-print-btn:not(:disabled):hover {
	box-shadow:
		0 10px 26px rgba(226, 54, 112, 0.4),
		0 0 0 1px rgba(244, 114, 182, 0.5) inset !important;
}

.payment-footer-btn:active {
	transform: translateY(0);
}

:deep(.payment-footer-btn .v-btn__overlay),
:deep(.payment-footer-btn .v-btn__underlay) {
	opacity: 0 !important;
	background: transparent !important;
}

@media (max-width: 768px) {
	.payment-actions {
		flex-wrap: wrap;
		gap: 8px;
	}

	.payment-actions .payment-cancel-btn {
		flex: 1 1 100%;
		min-width: 0;
		order: 3;
	}

	.payment-actions .payment-submit-btn,
	.payment-actions .payment-submit-print-btn {
		flex: 1 1 calc(50% - 4px);
	}

	.payment-footer-btn {
		font-size: 0.84rem !important;
		min-height: 42px !important;
	}

	:deep(.payment-footer-btn.v-btn) {
		min-height: 42px !important;
	}

	:deep(.payment-footer-btn .v-btn__content) {
		font-size: 0.84rem !important;
		line-height: 1.15;
	}
}

@media (max-width: 480px) {
	.payment-actions {
		flex-direction: column;
		gap: 6px;
	}

	.payment-actions .payment-cancel-btn,
	.payment-actions .payment-submit-btn,
	.payment-actions .payment-submit-print-btn {
		flex: 1 1 100%;
		min-width: 0;
	}

	.payment-footer-btn {
		font-size: 0.78rem !important;
	}

	:deep(.payment-footer-btn.v-btn) {
		min-height: 40px !important;
	}

	:deep(.payment-footer-btn .v-btn__content) {
		font-size: 0.78rem !important;
	}
}
</style>
