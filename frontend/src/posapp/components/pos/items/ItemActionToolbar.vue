<template>
	<v-card
		class="cards mb-0 mt-3 dynamic-padding"
		:class="{ 'cards--with-mobile-offset': reserveBottomDockSpace }"
	>
		<v-row no-gutters align="center" justify="center" class="dynamic-spacing-sm">
			<v-col cols="12" class="mb-2">
				<v-autocomplete
					:items="itemsGroupOptions"
					:label="frappe._('Items Groups')"
					:placeholder="selectedGroupsArray.length ? '' : frappe._('All groups')"
					density="compact"
					variant="outlined"
					hide-details
					hide-no-data
					multiple
					chips
					closable-chips
					clearable
					prepend-inner-icon="mdi-shape-outline"
					menu-icon="mdi-chevron-down"
					class="cc-group-picker"
					:model-value="selectedGroupsArray"
					@update:model-value="onGroupsChange"
				>
					<template #chip="{ props: chipProps, item }">
						<v-chip
							v-bind="chipProps"
							size="small"
							class="cc-group-picker__chip"
							:prepend-icon="item.value === 'ALL' ? 'mdi-asterisk' : 'mdi-tag-outline'"
						>
							{{ item.title }}
						</v-chip>
					</template>
					<template #item="{ props: itemProps, item }">
						<v-list-item
							v-bind="itemProps"
							class="cc-group-picker__option"
							:title="item.title"
						>
							<template #prepend="{ isActive }">
								<v-icon
									:color="isActive ? 'primary' : 'medium-emphasis'"
									size="20"
								>
									{{ isActive ? 'mdi-checkbox-marked' : 'mdi-checkbox-blank-outline' }}
								</v-icon>
							</template>
						</v-list-item>
					</template>
				</v-autocomplete>
			</v-col>
			<v-col cols="12" class="mb-2" v-if="posProfile.posa_enable_price_list_dropdown !== false">
				<v-text-field
					density="compact"
					variant="solo"
					color="primary"
					:label="frappe._('Price List')"
					hide-details
					:model-value="activePriceList"
					readonly
				></v-text-field>
			</v-col>
			<v-col cols="12" sm="4" class="dynamic-margin-xs">
				<v-btn-toggle
					:model-value="itemsView"
					@update:model-value="$emit('update:itemsView', $event)"
					color="primary"
					group
					density="compact"
					rounded
					class="view-toggle-btn"
				>
					<v-btn size="small" value="list">{{ __("List") }}</v-btn>
					<v-btn size="small" value="card">{{ __("Card") }}</v-btn>
				</v-btn-toggle>
			</v-col>
			<v-col cols="6" sm="4" class="dynamic-margin-xs">
				<v-btn
					size="small"
					block
					color="warning"
					variant="text"
					@click="$emit('open-offers')"
					class="action-btn-consistent"
				>
					{{ offersCount }} {{ __("Offers") }}
				</v-btn>
			</v-col>
			<v-col cols="6" sm="4" class="dynamic-margin-xs">
				<v-btn
					size="small"
					block
					color="primary"
					variant="text"
					@click="$emit('open-coupons')"
					class="action-btn-consistent"
				>
					{{ couponsCount }} {{ __("Coupons") }}
				</v-btn>
			</v-col>
		</v-row>
	</v-card>
</template>

<script setup>
import { computed } from "vue";

const __ = window.__;
const frappe = window.frappe;

const props = defineProps({
	// item_group filter — string for back-compat. "ALL" or a single group name,
	// or several groups joined with "||" (e.g. "Cosmetics||Device").
	modelValue: { type: String, default: "ALL" },
	itemsGroup: { type: Array, default: () => [] },
	itemsView: { type: String, default: "card" },
	posProfile: { type: Object, required: true },
	activePriceList: { type: String, default: "" },
	offersCount: { type: Number, default: 0 },
	couponsCount: { type: Number, default: 0 },
	reserveBottomDockSpace: { type: Boolean, default: false },
});

const emit = defineEmits([
	"update:modelValue",
	"update:itemsView",
	"open-offers",
	"open-coupons",
]);

// Always include "ALL" as a sentinel so the user can quickly clear filters
// without having to deselect every chip. We dedupe in case the parent
// already pushed it to the head of the list.
const itemsGroupOptions = computed(() => {
	const list = Array.isArray(props.itemsGroup) ? props.itemsGroup : [];
	const seen = new Set();
	const out = [];
	const add = (value) => {
		if (!value || seen.has(value)) return;
		seen.add(value);
		out.push(value);
	};
	add("ALL");
	list.forEach((g) => add(g));
	return out;
});

// String contract <-> array contract
const selectedGroupsArray = computed(() => {
	const raw = props.modelValue || "";
	if (!raw || raw === "ALL") return [];
	return raw
		.split("||")
		.map((s) => String(s).trim())
		.filter(Boolean);
});

const onGroupsChange = (next) => {
	const arr = Array.isArray(next) ? next.filter(Boolean) : [];
	// Empty selection or explicit "ALL" → clear filter
	if (!arr.length || arr.includes("ALL")) {
		emit("update:modelValue", "ALL");
		return;
	}
	emit("update:modelValue", arr.join("||"));
};
</script>

<style scoped>
/* ── Items Groups multi-select picker (CC violet card style) ────── */
.cc-group-picker :deep(.v-field) {
	border-radius: 12px !important;
	background: linear-gradient(
		135deg,
		rgba(139, 92, 246, 0.08),
		rgba(226, 54, 112, 0.04)
	), var(--pos-surface-muted, #161c27) !important;
	min-height: 44px !important;
	box-shadow: inset 0 0 0 1px rgba(139, 92, 246, 0.35) !important;
	transition: box-shadow 0.2s ease;
}

.cc-group-picker :deep(.v-field__overlay) {
	background: transparent !important;
	opacity: 0 !important;
}

.cc-group-picker :deep(.v-field__outline) {
	display: none !important;
}

.cc-group-picker :deep(.v-field--focused) {
	box-shadow:
		inset 0 0 0 1.5px rgba(139, 92, 246, 0.85),
		0 0 0 3px rgba(139, 92, 246, 0.18) !important;
}

.cc-group-picker :deep(.v-field__input) {
	min-height: 44px !important;
	padding-top: 2px !important;
	padding-bottom: 2px !important;
	color: var(--pos-text-primary, #e7ebf3) !important;
}

.cc-group-picker :deep(.v-label) {
	color: var(--pos-text-secondary, #8595ab) !important;
}

.cc-group-picker :deep(.v-field__prepend-inner .v-icon) {
	color: rgba(139, 92, 246, 0.95);
	opacity: 1;
}

.cc-group-picker__chip {
	background: linear-gradient(
		135deg,
		rgba(139, 92, 246, 0.18),
		rgba(226, 54, 112, 0.12)
	) !important;
	color: var(--pos-text-primary, #e7ebf3) !important;
	border: 1px solid rgba(139, 92, 246, 0.45) !important;
	font-weight: 600 !important;
	font-size: 0.75rem !important;
	height: 26px !important;
}

.cc-group-picker__chip :deep(.v-icon) {
	color: rgba(139, 92, 246, 0.95) !important;
	font-size: 14px !important;
}

.action-btn-consistent {
	height: 36px !important;
	margin-top: var(--dynamic-xs) !important;
	padding: var(--pos-space-2) var(--pos-space-3) !important;
	transition: var(--transition-normal) !important;
	border-radius: var(--pos-radius-sm) !important;
	text-transform: none !important;
	font-weight: 600 !important;
}

.action-btn-consistent:hover {
	background-color: rgba(var(--v-theme-primary), 0.1) !important;
	transform: none !important;
}

.view-toggle-btn {
	height: 36px;
	border: 1px solid var(--pos-border-light);
	border-radius: var(--pos-radius-sm);
}

.dynamic-padding {
	padding: var(--dynamic-sm);
}

.dynamic-spacing-sm {
	padding: var(--dynamic-sm) !important;
}

.cards {
	background-color: var(--pos-surface-muted) !important;
	margin-top: var(--dynamic-sm) !important;
	padding: var(--dynamic-sm) !important;
	border: 1px solid var(--pos-border-light);
	border-radius: var(--pos-radius-md) !important;
	box-shadow: none !important;
	position: sticky;
	bottom: 0;
	z-index: 7;
	min-width: 0;
	overflow: visible;
}

.cards--with-mobile-offset {
	margin-bottom: calc(var(--bottom-safe-space) + 6px) !important;
}

@media (max-width: 1099px) {
	.cards {
		position: static;
	}
}

@media (max-width: 768px) {
	.dynamic-padding {
		padding: var(--dynamic-xs);
	}

	.dynamic-spacing-sm {
		padding: var(--dynamic-xs) !important;
	}

	.view-toggle-btn {
		width: 100%;
	}

	.action-btn-consistent {
		padding: var(--dynamic-xs) !important;
		font-size: 0.875rem !important;
		min-height: 42px !important;
	}
}

@media (max-width: 480px) {
	.cards {
		padding: var(--dynamic-xs) !important;
		position: static;
	}
}
</style>
