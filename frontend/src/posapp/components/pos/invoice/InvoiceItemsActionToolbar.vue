<template>
	<div class="column-selector-container">
		<v-text-field
			ref="itemSearchField"
			:model-value="itemSearch"
			@update:model-value="$emit('update:itemSearch', $event)"
			density="compact"
			variant="solo"
			color="primary"
			class="item-search-field pos-themed-input"
			:label="__('Search items or barcode')"
			prepend-inner-icon="mdi-magnify"
			hide-details
			clearable
			autocomplete="off"
		>
			<template #append-inner>
				<span
					class="search-shortcut-hint"
					:title="__('Press Alt+F to focus this search')"
					aria-hidden="true"
				>
					<kbd class="search-shortcut-hint__key">Alt</kbd>
					<span class="search-shortcut-hint__plus">+</span>
					<kbd class="search-shortcut-hint__key">F</kbd>
				</span>
			</template>
		</v-text-field>
		<v-btn
			density="compact"
			variant="text"
			color="primary"
			prepend-icon="mdi-cog-outline"
			@click="toggleColumnSelection"
			class="column-selector-btn"
		>
			{{ __("Columns") }}
		</v-btn>
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
import { ref } from "vue";

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

const focusSearch = () => {
	itemSearchField.value?.focus?.();
};

defineExpose({
	focusSearch,
});
</script>

<style scoped>
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

@media (max-width: 640px) {
	.search-shortcut-hint {
		display: none;
	}
}
</style>
