<template>
	<!-- Invisible host — Alt+F opens the overlay, Columns opens via parent ref.
	     Both dialogs teleport to <body> so no visible layout is produced here. -->
	<div class="invoice-items-action-host">
		<v-dialog
			v-model="showSearchDialog"
			:max-width="560"
			scrim="rgba(15, 23, 42, 0.55)"
			transition="dialog-top-transition"
			class="find-in-cart-dialog"
			@after-enter="focusSearchField"
		>
			<v-card class="pos-themed-card find-in-cart-dialog__card">
				<div class="find-in-cart-dialog__header">
					<v-icon size="18" class="find-in-cart-dialog__icon">mdi-magnify</v-icon>
					<span class="find-in-cart-dialog__title">{{ __("Find in Cart") }}</span>
					<v-spacer />
					<span class="find-in-cart-dialog__hint">
						<kbd class="search-shortcut-hint__key">Esc</kbd>
						<span class="ml-1">{{ __("to close") }}</span>
					</span>
					<v-btn
						icon="mdi-close"
						variant="text"
						density="compact"
						class="ml-2"
						:aria-label="__('Close search')"
						@click="showSearchDialog = false"
					/>
				</div>
				<v-divider />
				<div class="find-in-cart-dialog__body">
					<v-text-field
						ref="itemSearchField"
						:model-value="itemSearch"
						@update:model-value="$emit('update:itemSearch', $event)"
						density="comfortable"
						variant="outlined"
						color="primary"
						class="item-search-field pos-themed-input"
						:placeholder="__('Search items or barcode')"
						prepend-inner-icon="mdi-magnify"
						hide-details
						clearable
						autocomplete="off"
						@keydown.esc="showSearchDialog = false"
					/>
				</div>
			</v-card>
		</v-dialog>

		<!-- Columns dialog (unchanged) -->
		<v-dialog v-model="showColumnSelector" max-width="500px" transition="dialog-bottom-transition">
			<v-card class="pos-themed-card">
				<v-card-title class="text-h6 pa-4 d-flex align-center">
					<span>{{ __("Select Columns to Display") }}</span>
					<v-spacer></v-spacer>
					<v-btn
						icon="mdi-close"
						variant="text"
						density="compact"
						:aria-label="__('Close column selector')"
						@click="showColumnSelector = false"
					></v-btn>
				</v-card-title>
				<v-divider></v-divider>
				<v-card-text class="pa-4">
					<v-row dense>
						<v-col
							cols="12"
							v-for="column in availableColumns.filter((col) => !col.required)"
							:key="column.key"
						>
							<v-switch
								v-model="tempSelectedColumns"
								:label="column.title"
								:value="column.key"
								hide-details
								density="compact"
								color="primary"
								class="column-switch mb-1"
								:disabled="column.required"
							></v-switch>
						</v-col>
					</v-row>
					<div class="text-caption mt-2">
						{{ __("Required columns cannot be hidden") }}
					</div>
				</v-card-text>
				<v-card-actions class="pa-4 pt-0">
					<v-btn color="error" variant="text" @click="cancelColumnSelection">{{
						__("Cancel")
					}}</v-btn>
					<v-spacer></v-spacer>
					<v-btn color="primary" variant="tonal" @click="updateSelectedColumns">{{
						__("Apply")
					}}</v-btn>
				</v-card-actions>
			</v-card>
		</v-dialog>
	</div>
</template>

<script setup>
import { ref, nextTick } from "vue";

const props = defineProps({
	itemSearch: {
		type: String,
		default: "",
	},
	availableColumns: {
		type: Array,
		default: () => [],
	},
	selectedColumns: {
		type: Array,
		default: () => [],
	},
});

const emit = defineEmits(["update:itemSearch", "update:selectedColumns"]);

const showColumnSelector = ref(false);
const showSearchDialog = ref(false);
const tempSelectedColumns = ref([]);
const itemSearchField = ref(null);

const toggleColumnSelection = () => {
	tempSelectedColumns.value = [...props.selectedColumns];
	showColumnSelector.value = true;
};

const cancelColumnSelection = () => {
	showColumnSelector.value = false;
};

const updateSelectedColumns = () => {
	emit("update:selectedColumns", tempSelectedColumns.value);
	showColumnSelector.value = false;
};

const focusSearchField = () => {
	nextTick(() => {
		const node = itemSearchField.value;
		if (!node) return;
		if (typeof node.focus === "function") {
			node.focus();
			return;
		}
		node.$el?.querySelector?.("input")?.focus?.();
	});
};

// Alt+F shortcut entry point — called from invoiceShortcuts.ts
const focusSearch = () => {
	if (!showSearchDialog.value) {
		showSearchDialog.value = true;
		// focusSearchField is auto-run via @after-enter on the dialog
		return;
	}
	focusSearchField();
};

const openColumns = () => {
	toggleColumnSelection();
};

defineExpose({
	focusSearch,
	openColumns,
});
</script>

<style scoped>
.invoice-items-action-host {
	display: contents;
}

.search-shortcut-hint {
	display: inline-flex;
	align-items: center;
	gap: 2px;
	padding: 2px 4px;
	font-family:
		ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
	font-size: 0.66rem;
	line-height: 1;
	color: var(--pos-text-secondary, rgba(148, 163, 184, 0.85));
	user-select: none;
	pointer-events: none;
	opacity: 0.85;
}

.search-shortcut-hint__key {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	min-width: 18px;
	padding: 1px 5px;
	border-radius: 5px;
	background: rgba(148, 163, 184, 0.18);
	border: 1px solid rgba(148, 163, 184, 0.28);
	font-weight: 600;
	font-family: inherit;
	font-size: inherit;
	letter-spacing: 0.02em;
}

.search-shortcut-hint__plus {
	opacity: 0.6;
	font-weight: 600;
}

.find-in-cart-dialog__card {
	overflow: hidden;
	border-radius: 14px;
}

.find-in-cart-dialog__header {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 12px 16px;
}

.find-in-cart-dialog__title {
	font-size: 0.78rem;
	font-weight: 700;
	letter-spacing: 0.04em;
	text-transform: uppercase;
	color: var(--pos-text-secondary);
}

.find-in-cart-dialog__icon {
	color: var(--pos-primary);
}

.find-in-cart-dialog__hint {
	display: inline-flex;
	align-items: center;
	font-size: 0.68rem;
	color: var(--pos-text-secondary);
	gap: 4px;
}

.find-in-cart-dialog__body {
	padding: 14px 16px 18px;
}

@media (max-width: 640px) {
	.find-in-cart-dialog__hint {
		display: none;
	}
}
</style>
