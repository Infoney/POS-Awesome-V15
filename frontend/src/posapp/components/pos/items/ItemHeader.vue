<template>
	<div class="sticky-header">
		<div class="cmd-search-row">
			<div class="cmd-search-field">
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
						<span
							class="cmd-search-hint"
							:title="__('Press F2 to focus this search')"
							aria-hidden="true"
						>
							<!--
								Single F2 chip — no modifier needed (was
								Ctrl/Cmd+K, but pharmacy cashiers kept
								hitting browser address-bar autocomplete
								on Ctrl+K). The unused modifier-label
								computed below stays in case a future
								shortcut wants it again.
							-->
							<kbd class="cmd-search-hint__key">F2</kbd>
						</span>
					</template>
				</v-text-field>
			</div>
			<v-btn
				v-if="posProfile.posa_enable_camera_scanning"
				icon="mdi-camera"
				size="small"
				color="primary"
				variant="text"
				class="cmd-search-side-btn"
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
			/>
			<v-btn
				icon="mdi-tune-vertical"
				size="small"
				color="primary"
				variant="text"
				class="cmd-search-side-btn"
				@click.stop="toolsOpen = !toolsOpen"
				:aria-label="toolsOpen ? __('Hide search tools') : __('Show search tools')"
				:title="toolsOpen ? __('Hide tools') : __('Show tools')"
			/>
			<div v-if="posProfile.posa_input_qty" class="cmd-search-qty">
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
			</div>
		</div>
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
import { computed, ref } from "vue";

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

const shortcutModifierLabel = computed(() => {
	if (typeof navigator === "undefined") return "Ctrl";
	const platform = (navigator.platform || navigator.userAgent || "").toLowerCase();
	return /mac|iphone|ipad|ipod/.test(platform) ? "⌘" : "Ctrl";
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
	padding: 8px 4px 6px;
	margin-bottom: 0;
	border-bottom: none;
}

.items {
	margin: 0;
}

/* Flex row: [search .........] [camera] [tools] [qty?] */
.cmd-search-row {
	display: flex;
	align-items: center;
	gap: 6px;
	width: 100%;
}

.cmd-search-field {
	flex: 1 1 auto;
	min-width: 0;
}

.cmd-search-qty {
	flex: 0 0 96px;
}

.cmd-search-side-btn {
	flex: 0 0 auto;
	opacity: 0.7;
	transition: opacity 0.15s ease, background-color 0.15s ease;
	border-radius: 10px;
}

.cmd-search-side-btn:hover,
.cmd-search-side-btn:focus-visible {
	opacity: 1;
	background: var(--pos-hover-bg, rgba(148, 163, 184, 0.08));
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
   One clean rounded surface, dark tier-2 background, hairline
   border only (no double outline, no filled variant layer).
   Mirrors the cc ProductSearch input exactly.
   Implementation: we fully zero out the three Vuetify outlined
   segments (start / notch / end) — otherwise you see a visible
   seam where they meet — and draw a single hairline outline via
   an inset box-shadow on the parent `.v-field`. */
.pos-cmd-search :deep(.v-field) {
	border-radius: 14px !important;
	background: var(--pos-surface-muted, #161c27) !important;
	min-height: 46px;
	box-shadow: inset 0 0 0 1px var(--pos-border, #252b37) !important;
	transition: box-shadow 0.18s ease;
}

.pos-cmd-search :deep(.v-field__overlay) {
	background: transparent !important;
	opacity: 0 !important;
}

.pos-cmd-search :deep(.v-field__outline) {
	--v-field-border-opacity: 0 !important;
	--v-field-border-width: 0 !important;
	display: none !important;
}

.pos-cmd-search :deep(.v-field__outline__start),
.pos-cmd-search :deep(.v-field__outline__end),
.pos-cmd-search :deep(.v-field__outline__notch) {
	border: 0 !important;
	border-width: 0 !important;
	--v-field-border-opacity: 0 !important;
}

.pos-cmd-search :deep(.v-field__outline__notch::before),
.pos-cmd-search :deep(.v-field__outline__notch::after) {
	border: 0 !important;
	border-width: 0 !important;
}

.pos-cmd-search :deep(.v-field--focused) {
	box-shadow:
		inset 0 0 0 1px rgba(226, 54, 112, 0.6),
		0 0 0 3px rgba(226, 54, 112, 0.12) !important;
}

.pos-cmd-search :deep(.v-field__input) {
	min-height: 46px;
	font-size: 0.95rem;
	font-weight: 500;
	letter-spacing: 0.005em;
	padding-inline-start: 2px;
}

.pos-cmd-search :deep(.v-field__input::placeholder) {
	color: var(--pos-text-secondary, #7b899d);
	opacity: 0.85;
}

.pos-cmd-search :deep(.v-field__prepend-inner) {
	padding-inline-end: 6px;
}

.pos-cmd-search :deep(.v-field__prepend-inner .v-icon) {
	color: var(--pos-text-secondary, #7b899d);
	opacity: 0.9;
	font-size: 20px;
}

.pos-cmd-search :deep(.v-field__append-inner) {
	align-items: center;
	padding-inline-end: 10px;
}

/* Command-center style kbd hint inside the items search field. */
.cmd-search-hint {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	margin-inline-start: 6px;
	font-family:
		ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
	font-size: 0.72rem;
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

	.cmd-search-qty {
		flex-basis: 72px;
	}
}

@media (max-width: 768px) {
	.sticky-header {
		top: 0;
		z-index: 13;
		padding: 10px 10px 2px;
	}

	.tools-panel {
		padding: 8px 10px;
	}

	.tools-panel__meta {
		justify-content: flex-start;
	}
}
</style>
