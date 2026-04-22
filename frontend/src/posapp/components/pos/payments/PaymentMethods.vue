<template>
	<div v-if="payments && payments.length" class="payment-methods">
		<div v-for="payment in payments" :key="payment.name" class="payment-method-card">
			<div class="payment-method-card__header">
				<div>
					<p class="payment-method-card__label">{{ frappe._("Method") }}</p>
					<h4 class="payment-method-card__title">{{ payment.mode_of_payment }}</h4>
				</div>
				<div class="payment-method-card__badges">
					<span v-if="isReturn" class="payment-method-card__badge payment-method-card__badge--refund">
						{{ __("Refund") }}
					</span>
					<span v-if="payment.default === 1" class="payment-method-card__badge">
						{{ __("Default") }}
					</span>
				</div>
			</div>

			<v-row class="payments ma-0" dense>
				<v-col cols="12" v-if="!isMpesaC2bPayment(payment)" class="pa-0">
					<div class="payment-method-row">
						<v-text-field
							density="compact"
							variant="solo"
							:color="isReturn ? 'error' : 'primary'"
							:label="frappe._('Amount')"
							:class="['sleek-field pos-themed-input payment-method-amount', isReturn ? 'pos-themed-input--refund' : '']"
							hide-details
							:model-value="formatCurrency(payment.amount)"
							@change="$emit('update-amount', payment, $event)"
							:rules="[isNumber]"
							:prefix="currencySymbol(currency)"
							@focus="$emit('set-rest-amount', payment, isReturn)"
							:readonly="isGiftCardPayment(payment)"
						></v-text-field>
						<v-btn
							color="primary"
							variant="flat"
							class="payment-method-action-btn payment-method-action-btn--inline"
							:data-test="`payment-method-action-${payment.mode_of_payment}`"
							@click="handlePrimaryAction(payment)"
						>
							{{
								isGiftCardPayment(payment)
									? __("Redeem / Scan")
									: payment.mode_of_payment
							}}
						</v-btn>
					</div>
				</v-col>

				<v-col
					cols="12"
					v-if="
						payment.default === 1 &&
						isCashLikePayment(payment) &&
						getVisibleDenominations(payment).length
					"
					class="pa-0"
				>
					<div class="payment-denominations">
						<v-btn
							v-for="d in getVisibleDenominations(payment)"
							:key="d"
							size="small"
							color="secondary"
							variant="tonal"
							class="payment-denominations__btn"
							@click="$emit('set-denomination', payment, d)"
						>
							{{ formatCurrency(d) }}
						</v-btn>
					</div>
				</v-col>

				<v-col cols="12" v-if="isMpesaC2bPayment(payment)" class="pa-0">
					<v-btn
						block
						color="success"
						variant="flat"
						class="payment-method-action-btn payment-method-action-btn--success"
						@click="$emit('mpesa-dialog', payment)"
					>
						{{ __("Get Payments") }}
					</v-btn>
				</v-col>

				<v-col
					cols="12"
					v-if="payment.type === 'Phone' && payment.amount > 0 && requestPaymentField"
					class="pa-0"
				>
					<v-btn
						block
						color="success"
						variant="tonal"
						class="payment-method-action-btn payment-method-action-btn--secondary"
						:disabled="payment.amount === 0"
						@click="$emit('request-payment', payment)"
					>
						{{ __("Request Payment") }}
					</v-btn>
				</v-col>
			</v-row>
		</div>
	</div>
</template>

<script setup>
const frappe = window.frappe;
const __ = window.__;

const props = defineProps({
	payments: Array,
	currency: String,
	isReturn: Boolean,
	requestPaymentField: Boolean,
	currencySymbol: Function,
	formatCurrency: Function,
	isNumber: Function,
	getVisibleDenominations: Function,
	isCashLikePayment: Function,
	isMpesaC2bPayment: Function,
	isGiftCardPayment: {
		type: Function,
		default: () => false,
	},
});

const emit = defineEmits([
	"update-amount",
	"set-full-amount",
	"set-denomination",
	"mpesa-dialog",
	"request-payment",
	"set-rest-amount",
	"open-gift-card",
]);

const handlePrimaryAction = (payment) => {
	if (props.isGiftCardPayment(payment)) {
		emit("open-gift-card", payment);
		return;
	}
	emit("set-full-amount", payment, props.isReturn);
};
</script>

<style scoped>
.payment-methods {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: var(--pos-space-2);
}

.payment-method-card {
	background: var(--pos-surface-raised);
	border: 1px solid var(--pos-border-light);
	border-radius: var(--pos-radius-md);
	padding: 12px;
	display: flex;
	flex-direction: column;
	gap: 10px;
}

.payment-method-card__header {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: var(--pos-space-2);
}

.payment-method-card__label {
	/* Eyebrow label sits tight above the MOP name. Smaller, lighter,
	   and snug so the title reads as the primary content. */
	margin: 0 0 2px;
	font-size: 0.62rem;
	font-weight: 600;
	line-height: 1;
	letter-spacing: 0.12em;
	text-transform: uppercase;
	color: var(--pos-text-secondary);
	opacity: 0.75;
}

.payment-method-card__title {
	margin: 0;
	font-size: 1rem;
	line-height: 1.15;
	font-weight: 700;
	color: var(--pos-text-primary);
}

.payment-method-card__badges {
	display: flex;
	gap: var(--pos-space-1);
	align-items: center;
	flex-wrap: wrap;
	justify-content: flex-end;
}

.payment-method-card__badge {
	padding: 5px 10px;
	border-radius: 999px;
	background: rgba(139, 92, 246, 0.16);
	border: 1px solid rgba(139, 92, 246, 0.32);
	color: rgb(167, 122, 250);
	font-size: 0.72rem;
	font-weight: 700;
	white-space: nowrap;
	letter-spacing: 0.02em;
	text-transform: uppercase;
}

.payment-method-card__badge--refund {
	background: rgba(var(--v-theme-error), 0.12);
	color: rgb(var(--v-theme-error));
}

:deep(.pos-themed-input--refund input) {
	color: rgb(var(--v-theme-error)) !important;
	font-weight: 700;
}

.payment-method-row {
	display: flex;
	align-items: stretch;
	gap: 8px;
	min-width: 0;
}

.payment-method-row .payment-method-amount {
	flex: 1 1 auto;
	min-width: 0;
}

.payment-method-action-btn {
	--v-theme-overlay-multiplier: 0 !important;
	min-height: 40px;
	border-radius: 10px;
	font-weight: 700;
	text-transform: none;
	letter-spacing: 0.01em;
	transition:
		box-shadow 0.18s ease,
		background 0.18s ease,
		transform 0.18s ease,
		filter 0.18s ease !important;
	background: linear-gradient(
		135deg,
		rgba(139, 92, 246, 0.95),
		rgba(167, 122, 250, 0.95)
	) !important;
	border: 1px solid rgba(139, 92, 246, 0.45) !important;
	box-shadow: 0 2px 8px rgba(139, 92, 246, 0.25) !important;
	color: #ffffff !important;
}

.payment-method-action-btn--inline {
	flex: 0 0 auto;
	max-width: 45%;
	min-height: 40px;
	height: auto;
	padding-inline: 12px !important;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}

.payment-method-actions {
	display: block;
}

.payment-method-action-btn:not(:disabled):hover,
.payment-method-action-btn:not(:disabled):focus,
.payment-method-action-btn:not(:disabled):focus-visible,
.payment-method-action-btn:not(:disabled):active {
	box-shadow: 0 6px 18px rgba(139, 92, 246, 0.35) !important;
	transform: translateY(-1px);
	filter: brightness(1.06);
}

.payment-method-action-btn:active {
	transform: translateY(0);
}

:deep(.payment-method-action-btn .v-btn__overlay),
:deep(.payment-method-action-btn .v-btn__underlay) {
	opacity: 0 !important;
	background: transparent !important;
}

.payment-method-action-btn--success {
	background: linear-gradient(
		135deg,
		rgba(34, 197, 94, 0.95),
		rgba(74, 222, 128, 0.95)
	) !important;
	border: 1px solid rgba(34, 197, 94, 0.45) !important;
	box-shadow: 0 2px 8px rgba(34, 197, 94, 0.25) !important;
	color: #ffffff !important;
}

.payment-method-action-btn--success:not(:disabled):hover {
	box-shadow: 0 6px 18px rgba(34, 197, 94, 0.35) !important;
}

.payment-method-action-btn--secondary {
	background: rgba(34, 197, 94, 0.14) !important;
	border: 1px solid rgba(34, 197, 94, 0.35) !important;
	box-shadow: none !important;
	color: rgb(74, 222, 128) !important;
}

.payment-method-action-btn--secondary:not(:disabled):hover {
	background: rgba(34, 197, 94, 0.22) !important;
	box-shadow: 0 4px 14px rgba(34, 197, 94, 0.18) !important;
}

.payment-denominations {
	display: flex;
	flex-wrap: wrap;
	gap: var(--pos-space-2);
}

.payment-denominations__btn {
	border-radius: var(--pos-radius-sm);
	text-transform: none;
	font-weight: 600;
}

@media (max-width: 768px) {
	.payment-methods {
		grid-template-columns: 1fr;
	}

	.payment-method-card {
		padding: var(--pos-space-2);
		gap: var(--pos-space-2);
	}

	.payment-method-actions {
		grid-template-columns: 1fr;
	}

	.payment-method-row {
		flex-direction: column;
		gap: 6px;
	}

	.payment-method-action-btn--inline {
		max-width: 100%;
		width: 100%;
	}
}
</style>
