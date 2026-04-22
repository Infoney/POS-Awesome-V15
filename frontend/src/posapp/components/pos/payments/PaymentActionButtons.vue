<template>
	<v-card flat :class="['cards mb-0 mt-3 pa-0', { compact }]">
		<v-row align="start" no-gutters>
			<v-col cols="12" sm="6">
				<v-btn
					ref="submitButton"
					block
					size="large"
					color="primary"
					variant="flat"
					class="payment-submit-btn payment-footer-btn"
					@click="$emit('submit')"
					:loading="loading"
					:disabled="loading || validatePayment"
					:class="{ 'submit-highlight': highlightSubmit }"
					:title="__('Submit (Alt+X)')"
				>
					<span class="payment-btn__label">{{ __("Submit") }}</span>
					<ShortcutHint combo="Alt+X" tone="light" />
				</v-btn>
			</v-col>
			<v-col cols="12" sm="6" class="payment-action-col">
				<v-btn
					block
					size="large"
					color="success"
					variant="flat"
					class="payment-submit-print-btn payment-footer-btn"
					@click="$emit('submit-and-print')"
					:loading="loading"
					:disabled="loading || validatePayment"
					:title="__('Submit & Print (Alt+P)')"
				>
					<span class="payment-btn__label">{{ __("Submit & Print") }}</span>
					<ShortcutHint combo="Alt+P" tone="light" />
				</v-btn>
			</v-col>
			<v-col cols="12">
				<v-btn
					block
					size="large"
					color="error"
					variant="flat"
					class="mt-2 pa-1 payment-cancel-btn payment-footer-btn"
					@click="$emit('cancel')"
				>
					{{ __("Cancel Payment") }}
				</v-btn>
			</v-col>
		</v-row>
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

.compact :deep(.v-btn),
:deep(.compact .v-btn) {
	min-height: 40px;
}

.payment-footer-btn {
	--v-theme-overlay-multiplier: 0 !important;
	transition:
		box-shadow 0.18s ease,
		background 0.18s ease,
		transform 0.18s ease,
		filter 0.18s ease !important;
	color: #ffffff !important;
	min-height: 44px !important;
	border-radius: 10px !important;
	font-weight: 700;
	letter-spacing: 0.02em;
}

:deep(.payment-footer-btn .v-btn__content) {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	gap: 4px;
}

.payment-btn__label {
	display: inline-flex;
	align-items: center;
}

/* CC violet → pink Submit button */
.payment-submit-btn {
	background: linear-gradient(
		135deg,
		rgba(139, 92, 246, 0.95),
		rgba(167, 122, 250, 0.95)
	) !important;
	box-shadow: 0 2px 8px rgba(139, 92, 246, 0.25) !important;
	border: 1px solid rgba(139, 92, 246, 0.45) !important;
}

/* CC pink → peach Submit & Print button */
.payment-submit-print-btn {
	background: linear-gradient(
		135deg,
		rgba(226, 54, 112, 0.95),
		rgba(244, 114, 182, 0.95)
	) !important;
	box-shadow: 0 2px 8px rgba(226, 54, 112, 0.25) !important;
	border: 1px solid rgba(226, 54, 112, 0.45) !important;
}

/* Rose-ghost Cancel button */
.payment-cancel-btn {
	background: linear-gradient(
		135deg,
		rgba(244, 63, 94, 0.92),
		rgba(225, 29, 72, 0.95)
	) !important;
	box-shadow: 0 2px 8px rgba(244, 63, 94, 0.25) !important;
	border: 1px solid rgba(244, 63, 94, 0.45) !important;
}

.payment-footer-btn:not(:disabled):hover,
.payment-footer-btn:not(:disabled):focus,
.payment-footer-btn:not(:disabled):focus-visible,
.payment-footer-btn:not(:disabled):active {
	box-shadow: 0 6px 18px rgba(15, 23, 42, 0.22) !important;
	transform: translateY(-1px);
	filter: brightness(1.06);
}

.payment-submit-btn:not(:disabled):hover {
	box-shadow: 0 6px 22px rgba(139, 92, 246, 0.35) !important;
}

.payment-submit-print-btn:not(:disabled):hover {
	box-shadow: 0 6px 22px rgba(226, 54, 112, 0.35) !important;
}

.payment-cancel-btn:not(:disabled):hover {
	box-shadow: 0 6px 22px rgba(244, 63, 94, 0.35) !important;
}

.payment-action-col {
	padding-left: 4px;
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
	.cards {
		margin-top: 0 !important;
	}

	.payment-action-col {
		padding-left: 0;
		padding-top: 6px;
	}

	.payment-footer-btn {
		font-size: 0.82rem !important;
	}

	:deep(.payment-footer-btn.v-btn) {
		min-height: 38px !important;
	}

	:deep(.payment-footer-btn .v-btn__content) {
		font-size: 0.82rem !important;
		line-height: 1.15;
	}
}

@media (max-width: 480px) {
	.payment-footer-btn {
		font-size: 0.76rem !important;
	}

	:deep(.payment-footer-btn.v-btn) {
		min-height: 34px !important;
	}

	:deep(.payment-footer-btn .v-btn__content) {
		font-size: 0.76rem !important;
	}
}
</style>
