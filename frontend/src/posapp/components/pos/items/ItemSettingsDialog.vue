<template>
	<v-dialog v-model="dialogModel" max-width="440px">
		<v-card class="item-settings-card">
			<!-- 2px CC pink->orange accent bar across the top of the dialog
			     card, matching the Invoice Management treatment. -->
			<div class="item-settings-card__accent" aria-hidden="true"></div>
			<v-card-title class="item-settings-card__title">
				<div class="item-settings-card__title-text">
					<span class="item-settings-card__eyebrow">{{ __("Item Selector") }}</span>
					<span class="item-settings-card__heading">{{ __("Settings") }}</span>
				</div>
				<v-spacer></v-spacer>
				<v-btn
					icon="mdi-close"
					variant="text"
					density="compact"
					class="item-settings-card__close"
					@click="dialogModel = false"
					:aria-label="__('Close Settings')"
				>
				</v-btn>
			</v-card-title>
			<v-divider class="item-settings-card__divider"></v-divider>
			<v-card-text class="item-settings-card__body">
				<v-switch
					v-if="props.allowNewLineSetting"
					v-model="form.new_line"
					:label="__('Add on New Line')"
					hide-details
					density="compact"
					color="primary"
					class="item-settings-card__row"
				></v-switch>
				<v-switch
					v-model="form.hide_qty_decimals"
					:label="__('Hide quantity decimals')"
					hide-details
					density="compact"
					color="primary"
					class="item-settings-card__row"
				></v-switch>
				<v-switch
					v-model="form.hide_zero_rate_items"
					:label="__('Hide zero rated items')"
					hide-details
					density="compact"
					color="primary"
					class="item-settings-card__row"
				></v-switch>
				<v-switch
					v-model="form.show_last_invoice_rate"
					:label="__('Show last invoice rate')"
					hide-details
					density="compact"
					color="primary"
					class="item-settings-card__row"
				></v-switch>
				<v-switch
					v-model="form.enable_background_sync"
					:label="__('Enable background sync')"
					hide-details
					density="compact"
					color="primary"
					class="item-settings-card__row"
				></v-switch>
				<v-text-field
					v-model="form.background_sync_interval"
					:label="__('Background sync interval (seconds)')"
					type="number"
					density="compact"
					variant="outlined"
					color="primary"
					hide-details
					class="item-settings-card__row pos-themed-input"
					:min="10"
					:disabled="!form.enable_background_sync"
				></v-text-field>
				<v-switch
					v-model="form.enable_custom_items_per_page"
					:label="__('Custom items per page')"
					hide-details
					density="compact"
					color="primary"
					class="item-settings-card__row"
				>
				</v-switch>
				<v-checkbox
					v-model="form.force_server_items"
					:label="__('Always fetch items from server (ignore local cache)')"
					hide-details
					density="compact"
					color="primary"
					class="item-settings-card__row item-settings-card__row--checkbox"
				></v-checkbox>
				<v-text-field
					v-if="form.enable_custom_items_per_page"
					v-model="form.items_per_page"
					type="number"
					density="compact"
					variant="outlined"
					color="primary"
					hide-details
					:label="__('Items per page')"
					class="item-settings-card__row pos-themed-input"
				>
				</v-text-field>
			</v-card-text>
			<v-divider class="item-settings-card__divider"></v-divider>
			<v-card-actions class="item-settings-card__actions">
				<v-spacer></v-spacer>
				<v-btn
					variant="text"
					class="item-settings-card__cancel"
					@click="dialogModel = false"
				>
					{{ __("Cancel") }}
				</v-btn>
				<v-btn
					variant="flat"
					class="item-settings-card__save"
					@click="onSave"
				>
					{{ __("Save Settings") }}
				</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>

<script setup>
import { computed, reactive, watch } from "vue";

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	initialSettings: { type: Object, required: true },
	allowNewLineSetting: { type: Boolean, default: false },
});

const emit = defineEmits(["update:modelValue", "save"]);

const dialogModel = computed({
	get: () => props.modelValue,
	set: (val) => emit("update:modelValue", val),
});

const form = reactive({
	new_line: false,
	hide_qty_decimals: false,
	hide_zero_rate_items: false,
	show_last_invoice_rate: true,
	enable_background_sync: true,
	background_sync_interval: 30,
	enable_custom_items_per_page: false,
	items_per_page: 50,
	force_server_items: false,
});

watch(
	() => props.modelValue,
	(val) => {
		if (val) {
			// Initialize form with current settings when dialog opens
			Object.assign(form, props.initialSettings);
		}
	},
);

const onSave = () => {
	emit("save", { ...form });
	dialogModel.value = false;
};
</script>

<style scoped>
/* CC pass — Item Selector Settings dialog now matches the Command
   Center palette used by Invoice Management and the rest of the POS.
   Pink/orange tint over --cc-bg-card, 2px brand accent bar across the
   top, themed switches/inputs/buttons. */
.item-settings-card {
	background:
		radial-gradient(circle at top right, rgba(var(--cc-pink-rgb), 0.14), transparent 32%),
		radial-gradient(circle at top left, rgba(var(--cc-orange-rgb), 0.1), transparent 28%),
		var(--cc-bg-card) !important;
	color: var(--cc-text) !important;
	border: 1px solid var(--cc-border);
	border-radius: 14px;
	overflow: hidden;
	position: relative;
	box-shadow: var(--cc-shadow-md);
	font-family: var(--posa-font-family, "Space Grotesk", sans-serif);
}

.item-settings-card__accent {
	position: absolute;
	inset: 0 0 auto 0;
	height: 2px;
	background: linear-gradient(90deg, var(--cc-pink), var(--cc-orange));
	opacity: 0.85;
	pointer-events: none;
	z-index: 2;
}

.item-settings-card__title {
	display: flex;
	align-items: center;
	gap: 12px;
	padding: 18px 20px 14px !important;
	background: linear-gradient(
		135deg,
		rgba(var(--cc-pink-rgb), 0.08),
		rgba(var(--cc-orange-rgb), 0.05)
	);
	border-bottom: 1px solid rgba(var(--cc-pink-rgb), 0.14);
}

.item-settings-card__title-text {
	display: flex;
	flex-direction: column;
	gap: 2px;
	min-width: 0;
}

.item-settings-card__eyebrow {
	font-size: 0.66rem;
	font-weight: 700;
	letter-spacing: 0.18em;
	text-transform: uppercase;
	color: var(--cc-pink);
	opacity: 0.95;
}

.item-settings-card__heading {
	font-size: 1.05rem;
	font-weight: 700;
	letter-spacing: 0.01em;
	color: var(--cc-text);
}

.item-settings-card__close :deep(.v-btn__overlay),
.item-settings-card__close :deep(.v-btn__underlay) {
	display: none !important;
}

.item-settings-card__close {
	color: var(--cc-muted) !important;
	transition:
		background-color var(--cc-ease-base),
		color var(--cc-ease-base);
}

.item-settings-card__close:hover {
	background: rgba(var(--cc-pink-rgb), 0.1) !important;
	color: var(--cc-pink) !important;
}

.item-settings-card__divider {
	border-color: var(--cc-border) !important;
	opacity: 0.6;
}

.item-settings-card__body {
	padding: 18px 20px 8px !important;
	background: transparent;
	display: flex;
	flex-direction: column;
	gap: 4px;
}

.item-settings-card__row {
	margin-block: 0 !important;
	padding-block: 6px;
}

/* Vuetify switches default to Material primary; recolour the on-state
   track + thumb to the CC pink so toggles match the brand bar. */
.item-settings-card__body :deep(.v-switch) {
	--v-theme-primary: var(--cc-pink);
}

.item-settings-card__body :deep(.v-switch .v-label) {
	color: var(--cc-text) !important;
	opacity: 0.92;
	font-size: 0.9rem;
	letter-spacing: 0.005em;
}

.item-settings-card__body :deep(.v-switch__track) {
	background: rgba(var(--cc-pink-rgb), 0.16) !important;
	opacity: 1;
	border: 1px solid rgba(var(--cc-pink-rgb), 0.18);
}

.item-settings-card__body :deep(.v-switch--inset .v-switch__track) {
	background: rgba(255, 255, 255, 0.08) !important;
	border-color: rgba(255, 255, 255, 0.06);
}

.item-settings-card__body :deep(.v-switch.v-switch--inset .v-selection-control--dirty .v-switch__track) {
	background: linear-gradient(135deg, var(--cc-pink), var(--cc-orange)) !important;
	border-color: transparent;
	box-shadow: 0 0 12px rgba(var(--cc-pink-rgb), 0.35);
}

.item-settings-card__body :deep(.v-switch__thumb) {
	background: var(--cc-bg-ter) !important;
	border: 1px solid var(--cc-border-hover);
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.45);
}

.item-settings-card__body :deep(.v-selection-control--dirty .v-switch__thumb) {
	background: #fff !important;
	border-color: rgba(var(--cc-pink-rgb), 0.5);
}

/* Checkbox follows the same brand-accent rule. */
.item-settings-card__row--checkbox :deep(.v-selection-control__input) {
	color: var(--cc-pink) !important;
}

.item-settings-card__row--checkbox :deep(.v-label) {
	color: var(--cc-text) !important;
	opacity: 0.92;
	font-size: 0.9rem;
}

/* Text field gets a CC-tinted outline + focus glow. */
.item-settings-card__body :deep(.v-text-field .v-field) {
	background: rgba(var(--cc-pink-rgb), 0.04) !important;
	border-radius: 10px;
}

.item-settings-card__body :deep(.v-text-field .v-field__outline__start),
.item-settings-card__body :deep(.v-text-field .v-field__outline__notch::before),
.item-settings-card__body :deep(.v-text-field .v-field__outline__notch::after),
.item-settings-card__body :deep(.v-text-field .v-field__outline__end) {
	border-color: rgba(var(--cc-pink-rgb), 0.25) !important;
}

.item-settings-card__body :deep(.v-text-field .v-field--focused .v-field__outline__start),
.item-settings-card__body :deep(.v-text-field .v-field--focused .v-field__outline__notch::before),
.item-settings-card__body :deep(.v-text-field .v-field--focused .v-field__outline__notch::after),
.item-settings-card__body :deep(.v-text-field .v-field--focused .v-field__outline__end) {
	border-color: var(--cc-pink) !important;
	box-shadow: 0 0 0 2px rgba(var(--cc-pink-rgb), 0.15);
}

.item-settings-card__body :deep(.v-text-field input) {
	color: var(--cc-text) !important;
	font-variant-numeric: tabular-nums;
}

.item-settings-card__body :deep(.v-text-field .v-label) {
	color: var(--cc-muted) !important;
}

.item-settings-card__body :deep(.v-text-field .v-field--focused .v-label),
.item-settings-card__body :deep(.v-text-field .v-field--active .v-label) {
	color: var(--cc-pink) !important;
}

/* Disabled background-sync interval reads as muted instead of opaque. */
.item-settings-card__body :deep(.v-text-field .v-field--disabled) {
	opacity: 0.55;
}

/* Footer actions — Cancel as ghost, Save as CC gradient. */
.item-settings-card__actions {
	padding: 14px 20px 16px !important;
	gap: 8px;
	background: rgba(var(--cc-pink-rgb), 0.04);
}

.item-settings-card__cancel {
	color: var(--cc-muted) !important;
	font-weight: 600;
	letter-spacing: 0.02em;
	text-transform: none !important;
	transition:
		background-color var(--cc-ease-base),
		color var(--cc-ease-base);
}

.item-settings-card__cancel :deep(.v-btn__overlay),
.item-settings-card__cancel :deep(.v-btn__underlay) {
	display: none !important;
}

.item-settings-card__cancel:hover {
	background: rgba(var(--cc-pink-rgb), 0.08) !important;
	color: var(--cc-text) !important;
}

.item-settings-card__save {
	background: linear-gradient(135deg, var(--cc-pink), var(--cc-orange)) !important;
	color: #ffffff !important;
	border: 1px solid transparent;
	font-weight: 700;
	letter-spacing: 0.02em;
	text-transform: none !important;
	box-shadow: var(--cc-shadow-sm);
	transition:
		filter var(--cc-ease-base),
		transform var(--cc-ease-base),
		box-shadow var(--cc-ease-base);
}

.item-settings-card__save :deep(.v-btn__overlay),
.item-settings-card__save :deep(.v-btn__underlay) {
	display: none !important;
}

.item-settings-card__save:hover {
	filter: brightness(1.08);
	transform: translateY(-1px);
	box-shadow: var(--cc-shadow-md), var(--cc-glow-pink);
}
</style>
