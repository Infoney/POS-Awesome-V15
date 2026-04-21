<template>
	<div class="sticky-header">
		<v-row class="items">
			<v-col
				class="pb-0"
				:cols="posProfile.posa_input_qty ? 8 : 12"
				:sm="posProfile.posa_input_qty ? 9 : 12"
			>
				<v-text-field
					density="compact"
					clearable
					autofocus
					variant="outlined"
					color="primary"
					class="pos-themed-input pos-cmd-search"
					:placeholder="frappe._('Search by SKU, barcode, or product name…')"
					hide-details
					flat
					:model-value="searchInput"
					@update:model-value="
						(val) => {
							$emit('update:searchInput', val);
							$emit('search-input', val);
						}
					"
					@keydown.esc="$emit('esc')"
					@keydown.enter="$emit('enter')"
					@keydown="$emit('search-keydown', $event)"
					@click:clear="$emit('clear-search')"
					@click:prepend-inner="$emit('focus')"
					@paste="$emit('search-paste', $event)"
					prepend-inner-icon="mdi-magnify"
					@focus="$emit('focus')"
					ref="debounce_search"
				>
					<template v-slot:append-inner>
						<v-btn
							v-if="posProfile.posa_enable_camera_scanning"
							icon="mdi-camera"
							size="small"
							color="primary"
							variant="text"
							:disabled="scannerLocked"
							@click="$emit('start-camera')"
							:aria-label="
								scannerLocked
									? __('Camera scanner is locked until the current error is acknowledged')
									: __('Scan with camera')
							"
							:title="
								scannerLocked
									? __('Acknowledge the error to resume scanning')
									: __('Scan with Camera')
							"
						>
						</v-btn>
						<v-btn
							icon="mdi-tune-vertical"
							size="x-small"
							color="primary"
							variant="text"
							class="cmd-search-tools-btn"
							@click.stop="toolsOpen = !toolsOpen"
							:aria-label="toolsOpen ? __('Hide search tools') : __('Show search tools')"
						>
						</v-btn>
						<span
							class="cmd-search-hint"
							:title="__('Press Alt+3 to focus this search')"
							aria-hidden="true"
						>
							<kbd class="cmd-search-hint__key">Alt</kbd>
							<kbd class="cmd-search-hint__key">3</kbd>
						</span>
					</template>
				</v-text-field>
			</v-col>
			<v-col cols="4" sm="3" class="pb-0" v-if="posProfile.posa_input_qty">
				<v-text-field
					density="compact"
					variant="solo"
					color="primary"
					class="pos-themed-input"
					:label="frappe._('QTY')"
					hide-details
					:model-value="qtyInput"
					@update:model-value="$emit('update:qtyInput', $event)"
					type="text"
					inputmode="decimal"
					@keydown.enter="$emit('enter')"
					@keydown.esc="$emit('esc')"
					@focus="$emit('clear-qty')"
					@click="$emit('clear-qty')"
					@blur="$emit('blur-qty')"
				></v-text-field>
			</v-col>
		</v-row>
		<v-expand-transition>
			<div v-if="toolsOpen" class="tools-panel">
				<div class="tools-panel__actions">
					<v-btn
						v-if="context === 'purchase'"
						density="compact"
						variant="text"
						color="primary"
						prepend-icon="mdi-plus"
						@click="$emit('open-new-item')"
						class="settings-btn"
					>
						{{ __("New Item") }}
					</v-btn>
					<v-btn
						density="compact"
						variant="text"
						color="primary"
						prepend-icon="mdi-cog-outline"
						@click="$emit('toggle-settings')"
						class="settings-btn"
					>
						{{ __("Settings") }}
					</v-btn>
					<v-btn
						density="compact"
						variant="text"
						color="primary"
						prepend-icon="mdi-refresh"
						@click="$emit('reload-items')"
						class="settings-btn"
					>
						{{ __("Reload Items") }}
					</v-btn>
				</div>
				<div class="tools-panel__meta">
					<span
						v-if="syncStatus"
						class="text-caption text-info font-weight-bold sync-status-label"
					>
						{{ syncStatus }}
					</span>
					<span
						v-else-if="enableBackgroundSync"
						class="text-caption text-medium-emphasis last-sync-label"
					>
						{{ __("Last sync:") }} {{ lastSyncTime }}
					</span>
				</div>
			</div>
		</v-expand-transition>
	</div>
</template>

<script setup>
import { ref } from "vue";

defineProps({
	searchInput: { type: String, default: "" },
	qtyInput: { type: [String, Number], default: 1 },
	posProfile: { type: Object, required: true },
	scannerLocked: { type: Boolean, default: false },
	enableBackgroundSync: { type: Boolean, default: false },
	lastSyncTime: { type: String, default: "" },
	syncStatus: { type: String, default: "" },
	context: { type: String, default: "pos" },
});

defineEmits([
	"update:searchInput",
	"update:qtyInput",
	"esc",
	"enter",
	"search-keydown",
	"clear-search",
	"search-input",
	"search-paste",
	"focus",
	"clear-qty",
	"blur-qty",
	"start-camera",
	"open-new-item",
	"toggle-settings",
	"reload-items",
]);

const debounce_search = ref(null);
const toolsOpen = ref(false);

defineExpose({
	debounce_search,
});
</script>

<style scoped>
.sticky-header {
	position: sticky;
	top: 0;
	z-index: 5;
	background: transparent;
	padding: 10px 4px 6px;
	margin-bottom: 0;
	border-bottom: none;
}

.items {
	margin: 0;
}

.tools-panel {
	margin-top: 8px;
	padding: 10px 12px;
	border-radius: 16px;
	background: var(--pos-surface-muted);
	border: 1px solid var(--pos-border);
}

.tools-panel__actions {
	display: flex;
	align-items: center;
	flex-wrap: wrap;
	gap: 6px;
}

.tools-panel__meta {
	display: flex;
	align-items: center;
	justify-content: flex-end;
	padding-top: 6px;
}

.settings-btn {
	text-transform: none !important;
	letter-spacing: normal !important;
	font-weight: 500 !important;
	background-color: transparent !important;
	min-height: 40px !important;
}

.last-sync-label {
	white-space: nowrap;
	font-size: 0.75rem;
}

.dynamic-margin-xs {
	margin-top: 4px;
}

/* ── Command-center search field ─────────────────────────────
   Single rounded surface, dark tier-2 background, subtle border,
   pink focus ring. Mirrors the cc ProductSearch input. */
.pos-cmd-search :deep(.v-field) {
	border-radius: 12px !important;
	background: var(--pos-surface-muted, #161c27) !important;
	box-shadow: none !important;
	min-height: 44px;
	transition:
		border-color 0.18s ease,
		box-shadow 0.18s ease;
}

.pos-cmd-search :deep(.v-field__outline) {
	--v-field-border-opacity: 1;
}

.pos-cmd-search :deep(.v-field__outline__start),
.pos-cmd-search :deep(.v-field__outline__end),
.pos-cmd-search :deep(.v-field__outline__notch) {
	border-color: var(--pos-border, #252b37) !important;
	border-width: 1px !important;
}

.pos-cmd-search :deep(.v-field--focused) {
	box-shadow: 0 0 0 3px rgba(226, 54, 112, 0.08) !important;
}

.pos-cmd-search :deep(.v-field--focused .v-field__outline__start),
.pos-cmd-search :deep(.v-field--focused .v-field__outline__end),
.pos-cmd-search :deep(.v-field--focused .v-field__outline__notch) {
	border-color: rgba(226, 54, 112, 0.5) !important;
}

.pos-cmd-search :deep(.v-field__input) {
	min-height: 44px;
	font-size: 0.92rem;
	font-weight: 500;
	letter-spacing: 0.005em;
}

.pos-cmd-search :deep(.v-field__input::placeholder) {
	color: var(--pos-text-secondary, #7b899d);
	opacity: 0.85;
}

.pos-cmd-search :deep(.v-field__prepend-inner .v-icon) {
	color: var(--pos-text-secondary, #7b899d);
	opacity: 0.85;
}

/* Subtle tools toggle so the chrome stays close to the reference. */
.cmd-search-tools-btn {
	opacity: 0.55;
	transition: opacity 0.15s ease;
}

.cmd-search-tools-btn:hover,
.cmd-search-tools-btn:focus-visible {
	opacity: 1;
}

/* Command-center style kbd hint inside the items search field. */
.cmd-search-hint {
	display: inline-flex;
	align-items: center;
	gap: 3px;
	margin-inline-start: 8px;
	font-family:
		ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
	font-size: 0.68rem;
	line-height: 1;
	color: var(--pos-text-secondary, rgba(148, 163, 184, 0.85));
	user-select: none;
	pointer-events: none;
}

.cmd-search-hint__key {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	min-width: 22px;
	padding: 3px 6px;
	border-radius: 6px;
	background: rgba(148, 163, 184, 0.14);
	border: 1px solid rgba(148, 163, 184, 0.22);
	font-weight: 600;
	font-family: inherit;
	font-size: inherit;
	letter-spacing: 0.02em;
	color: var(--pos-text-primary);
}

@media (max-width: 640px) {
	.cmd-search-hint {
		display: none;
	}
}

@media (max-width: 768px) {
	.sticky-header {
		top: 0;
		z-index: 13;
		padding: 12px 12px 2px;
	}

	.tools-panel {
		padding: 8px 10px;
	}

	.tools-panel__meta {
		justify-content: flex-start;
	}
}
</style>
