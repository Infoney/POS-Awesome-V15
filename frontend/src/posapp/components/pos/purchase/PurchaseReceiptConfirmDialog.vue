<template>
	<v-dialog
		:model-value="modelValue"
		@update:model-value="(val) => $emit('update:modelValue', val)"
		max-width="540"
		persistent
		scrim="rgba(8, 11, 19, 0.78)"
	>
		<v-card class="pr-confirm-card" flat>
			<div class="pr-confirm-header">
				<v-icon class="pr-confirm-header__icon">mdi-check-decagram</v-icon>
				<div>
					<div class="pr-confirm-header__eyebrow">{{ __("Final review") }}</div>
					<h3 class="pr-confirm-header__title">{{ __("Confirm Purchase Receipt") }}</h3>
				</div>
			</div>

			<v-card-text class="pr-confirm-body">
				<div class="pr-confirm-row">
					<span class="pr-confirm-row__label">{{ __("Supplier") }}</span>
					<span class="pr-confirm-row__value">{{ supplierLabel || "—" }}</span>
				</div>
				<div class="pr-confirm-row">
					<span class="pr-confirm-row__label">{{ __("Warehouse") }}</span>
					<span class="pr-confirm-row__value">{{ warehouse || "—" }}</span>
				</div>
				<div class="pr-confirm-row">
					<span class="pr-confirm-row__label">{{ __("Posting Date") }}</span>
					<span class="pr-confirm-row__value">{{ postingDate || "—" }}</span>
				</div>
				<div class="pr-confirm-row">
					<span class="pr-confirm-row__label">{{ __("Lines") }}</span>
					<span class="pr-confirm-row__value">{{ lineCount }}</span>
				</div>
				<div class="pr-confirm-row">
					<span class="pr-confirm-row__label">{{ __("Total Qty") }}</span>
					<span class="pr-confirm-row__value">{{ formatNumber(totalQty) }}</span>
				</div>
				<div class="pr-confirm-row pr-confirm-row--total">
					<span class="pr-confirm-row__label">{{ __("Total Value") }}</span>
					<span class="pr-confirm-row__value">
						{{ currencySymbol }}{{ formatCurrency(totalAmount) }}
					</span>
				</div>

				<v-divider class="my-3 pr-confirm-divider" />

				<v-switch
					:model-value="updatePriceList"
					@update:model-value="(val) => $emit('update:updatePriceList', !!val)"
					:label="__('Update buying price list with these rates')"
					color="primary"
					density="compact"
					hide-details
					class="ma-0"
					:disabled="!buyingPriceList"
				/>
				<div v-if="buyingPriceList" class="pr-confirm-pl-hint">
					{{ __("Target price list:") }} <strong>{{ buyingPriceList }}</strong>
				</div>
				<div v-else class="pr-confirm-pl-hint pr-confirm-pl-hint--muted">
					{{ __("No buying price list resolved for this supplier — price list update disabled.") }}
				</div>
			</v-card-text>

			<v-card-actions class="pr-confirm-actions">
				<v-btn
					variant="text"
					@click="$emit('update:modelValue', false)"
					:disabled="loading"
				>
					{{ __("Back") }}
				</v-btn>
				<v-spacer />
				<v-btn
					class="pr-confirm-submit-btn"
					size="large"
					:loading="loading"
					:disabled="loading || !canSubmit"
					@click="$emit('confirm')"
				>
					<v-icon start>mdi-package-variant-closed-check</v-icon>
					{{ __("Submit Receipt") }}
				</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>

<script>
export default {
	props: {
		modelValue: Boolean,
		supplierLabel: String,
		warehouse: String,
		postingDate: String,
		lineCount: { type: Number, default: 0 },
		totalQty: { type: Number, default: 0 },
		totalAmount: { type: Number, default: 0 },
		currencySymbol: { type: String, default: "" },
		updatePriceList: { type: Boolean, default: false },
		buyingPriceList: String,
		loading: { type: Boolean, default: false },
		canSubmit: { type: Boolean, default: true },
		formatCurrency: { type: Function, default: (v) => Number(v || 0).toFixed(2) },
		formatNumber: { type: Function, default: (v) => String(v ?? 0) },
	},
	emits: ["update:modelValue", "update:updatePriceList", "confirm"],
};
</script>

<style scoped>
.pr-confirm-card {
	background: var(--pos-card-bg, #0e131e) !important;
	color: var(--pos-text-primary, #e7ebf3);
	font-family: var(--posa-font-family, "Space Grotesk", sans-serif);
	border: 1px solid rgba(139, 92, 246, 0.18);
	border-radius: 16px !important;
	overflow: hidden;
}

.pr-confirm-header {
	display: flex;
	align-items: center;
	gap: 14px;
	padding: 16px 20px;
	background:
		linear-gradient(
			135deg,
			rgba(139, 92, 246, 0.22),
			rgba(226, 54, 112, 0.12)
		),
		var(--pos-surface-muted, #161c27);
	border-bottom: 1px solid rgba(139, 92, 246, 0.28);
}
.pr-confirm-header__icon {
	font-size: 28px !important;
	color: #c4b5fd !important;
}
.pr-confirm-header__eyebrow {
	font-size: 0.66rem;
	font-weight: 700;
	letter-spacing: 0.16em;
	text-transform: uppercase;
	color: rgba(231, 235, 243, 0.65);
}
.pr-confirm-header__title {
	margin: 0;
	font-size: 1.12rem;
	font-weight: 700;
	background: linear-gradient(135deg, #f5d0fe 0%, #fb7185 100%);
	background-clip: text;
	-webkit-background-clip: text;
	color: transparent;
	-webkit-text-fill-color: transparent;
}

.pr-confirm-body {
	padding: 18px 22px !important;
}

.pr-confirm-row {
	display: flex;
	justify-content: space-between;
	align-items: center;
	padding: 6px 0;
	font-size: 0.875rem;
}
.pr-confirm-row__label {
	color: rgba(231, 235, 243, 0.7);
	letter-spacing: 0.02em;
}
.pr-confirm-row__value {
	font-weight: 600;
}
.pr-confirm-row--total {
	margin-top: 8px;
	padding-top: 10px;
	border-top: 1px dashed rgba(139, 92, 246, 0.28);
	font-size: 1.1rem;
}
.pr-confirm-row--total .pr-confirm-row__value {
	background: linear-gradient(135deg, #c4b5fd 0%, #fb7185 100%);
	background-clip: text;
	-webkit-background-clip: text;
	color: transparent;
	-webkit-text-fill-color: transparent;
}

.pr-confirm-divider {
	border-color: rgba(139, 92, 246, 0.18) !important;
	opacity: 1 !important;
}

.pr-confirm-pl-hint {
	margin-top: 6px;
	font-size: 0.78rem;
	color: rgba(231, 235, 243, 0.7);
}
.pr-confirm-pl-hint--muted {
	color: rgba(231, 235, 243, 0.45);
	font-style: italic;
}

.pr-confirm-actions {
	padding: 12px 18px !important;
	background: var(--pos-surface-muted, #161c27);
	border-top: 1px solid rgba(139, 92, 246, 0.18);
}

.pr-confirm-submit-btn {
	background: linear-gradient(135deg, #8b5cf6 0%, #e23670 100%) !important;
	color: #ffffff !important;
	font-weight: 700 !important;
	letter-spacing: 0.04em !important;
	border-radius: 12px !important;
	min-height: 44px !important;
	box-shadow:
		0 12px 28px rgba(139, 92, 246, 0.28),
		0 0 0 1px rgba(244, 114, 182, 0.32) inset !important;
	text-transform: none !important;
}
.pr-confirm-submit-btn:hover:not(:disabled) {
	filter: brightness(1.08);
}
.pr-confirm-submit-btn:disabled,
.pr-confirm-submit-btn.v-btn--disabled {
	opacity: 0.55 !important;
	background: linear-gradient(135deg, #4c4561 0%, #5b3149 100%) !important;
	box-shadow: none !important;
}
</style>
