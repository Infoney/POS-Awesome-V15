<template>
	<v-card
		class="cards mb-0 mt-3 dynamic-padding"
		:class="{ 'cards--with-mobile-offset': reserveBottomDockSpace }"
	>
		<v-row no-gutters align="center" justify="center" class="dynamic-spacing-sm">
			<v-col cols="12" sm="6" class="mb-2 pr-sm-1">
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
					:menu-props="{ contentClass: 'cc-group-picker-menu' }"
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
			<v-col cols="12" sm="6" class="mb-2 pl-sm-1">
				<v-autocomplete
					:items="brandOptions"
					:label="frappe._('Brand')"
					:placeholder="selectedBrandsArray.length ? '' : frappe._('All brands')"
					density="compact"
					variant="outlined"
					hide-details
					hide-no-data
					multiple
					chips
					closable-chips
					clearable
					prepend-inner-icon="mdi-tag-multiple-outline"
					menu-icon="mdi-chevron-down"
					class="cc-group-picker cc-brand-picker"
					:menu-props="{ contentClass: 'cc-group-picker-menu' }"
					:model-value="selectedBrandsArray"
					@update:model-value="onBrandsChange"
				>
					<template #chip="{ props: chipProps, item }">
						<v-chip
							v-bind="chipProps"
							size="small"
							class="cc-group-picker__chip cc-brand-picker__chip"
							:prepend-icon="item.value === 'ALL' ? 'mdi-asterisk' : 'mdi-tag-text-outline'"
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
	// Brand filter — same string contract as modelValue. "ALL" or a single
	// brand name, or several brands joined with "||".
	brandModel: { type: String, default: "ALL" },
	itemsBrand: { type: Array, default: () => [] },
	itemsView: { type: String, default: "card" },
	posProfile: { type: Object, required: true },
	activePriceList: { type: String, default: "" },
	offersCount: { type: Number, default: 0 },
	couponsCount: { type: Number, default: 0 },
	reserveBottomDockSpace: { type: Boolean, default: false },
});

const emit = defineEmits([
	"update:modelValue",
	"update:brandModel",
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

// ── Brand picker (same string-contract / multi-select pattern) ─────
const brandOptions = computed(() => {
	const list = Array.isArray(props.itemsBrand) ? props.itemsBrand : [];
	const seen = new Set();
	const out = [];
	const add = (value) => {
		if (!value || seen.has(value)) return;
		seen.add(value);
		out.push(value);
	};
	add("ALL");
	list.forEach((b) => add(b));
	return out;
});

const selectedBrandsArray = computed(() => {
	const raw = props.brandModel || "";
	if (!raw || raw === "ALL") return [];
	return raw
		.split("||")
		.map((s) => String(s).trim())
		.filter(Boolean);
});

const onBrandsChange = (next) => {
	const arr = Array.isArray(next) ? next.filter(Boolean) : [];
	if (!arr.length || arr.includes("ALL")) {
		emit("update:brandModel", "ALL");
		return;
	}
	emit("update:brandModel", arr.join("||"));
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
	font-family: var(--posa-font-family) !important;
	font-size: 0.875rem !important;
	font-weight: 500 !important;
	letter-spacing: 0.01em !important;
}

.cc-group-picker :deep(.v-label) {
	color: var(--pos-text-secondary, #8595ab) !important;
	font-family: var(--posa-font-family) !important;
	font-size: 0.875rem !important;
	font-weight: 500 !important;
	letter-spacing: 0.01em !important;
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
	font-family: var(--posa-font-family) !important;
	font-weight: 600 !important;
	font-size: 0.75rem !important;
	letter-spacing: 0.02em !important;
	height: 26px !important;
}

.cc-group-picker__chip :deep(.v-icon) {
	color: rgba(139, 92, 246, 0.95) !important;
	font-size: 14px !important;
}

/* Brand picker — same shell, but the pink end of the gradient leads so
   the two filters read as siblings rather than identical pills. */
.cc-brand-picker :deep(.v-field) {
	background: linear-gradient(
		135deg,
		rgba(226, 54, 112, 0.1),
		rgba(139, 92, 246, 0.05)
	), var(--pos-surface-muted, #161c27) !important;
	box-shadow: inset 0 0 0 1px rgba(226, 54, 112, 0.4) !important;
}

.cc-brand-picker :deep(.v-field--focused) {
	box-shadow:
		inset 0 0 0 1.5px rgba(226, 54, 112, 0.85),
		0 0 0 3px rgba(226, 54, 112, 0.18) !important;
}

.cc-brand-picker :deep(.v-field__prepend-inner .v-icon) {
	color: rgba(226, 54, 112, 0.95);
	opacity: 1;
}

.cc-brand-picker__chip {
	background: linear-gradient(
		135deg,
		rgba(226, 54, 112, 0.22),
		rgba(139, 92, 246, 0.14)
	) !important;
	border: 1px solid rgba(226, 54, 112, 0.5) !important;
}

.cc-brand-picker__chip :deep(.v-icon) {
	color: rgba(244, 114, 182, 0.95) !important;
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
	overflow: hidden;
}

/* Default Vuetify v-btn-toggle paints hover/active as a near-black overlay
 * which clashes with the CC theme. Replace with the soft purple→pink wash
 * used elsewhere so the toggle reads as part of the same surface family. */
.view-toggle-btn :deep(.v-btn) {
	background: transparent !important;
	color: var(--pos-text-primary, #e7ebf3) !important;
	transition:
		background 0.18s ease,
		color 0.18s ease !important;
}

.view-toggle-btn :deep(.v-btn .v-btn__overlay),
.view-toggle-btn :deep(.v-btn .v-btn__underlay) {
	background: transparent !important;
	opacity: 0 !important;
}

.view-toggle-btn :deep(.v-btn:hover) {
	background: linear-gradient(
		135deg,
		rgba(var(--cc-purple-rgb, 161, 77, 203), 0.18),
		rgba(var(--cc-pink-rgb, 226, 54, 112), 0.18)
	) !important;
	color: #ffffff !important;
}

.view-toggle-btn :deep(.v-btn.v-btn--active),
.view-toggle-btn :deep(.v-btn[aria-pressed="true"]) {
	background: linear-gradient(
		135deg,
		rgba(var(--cc-purple-rgb, 161, 77, 203), 0.85),
		rgba(var(--cc-pink-rgb, 226, 54, 112), 0.85)
	) !important;
	color: #ffffff !important;
}

.view-toggle-btn :deep(.v-btn.v-btn--active:hover),
.view-toggle-btn :deep(.v-btn[aria-pressed="true"]:hover) {
	background: linear-gradient(
		135deg,
		rgba(var(--cc-purple-rgb, 161, 77, 203), 0.95),
		rgba(var(--cc-pink-rgb, 226, 54, 112), 0.95)
	) !important;
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

<!--
  Unscoped block — Vuetify teleports the autocomplete menu to <body>,
  so the scoped block above can't reach the popup. We tagged the menu
  with `cc-group-picker-menu` via `:menu-props.contentClass` and style
  it here so the dropdown matches the CC violet/pink card aesthetic.
-->
<style>
.cc-group-picker-menu.v-overlay__content {
	border-radius: 14px !important;
	overflow: hidden;
	background: linear-gradient(
		180deg,
		rgba(22, 28, 39, 0.98),
		rgba(17, 21, 30, 0.98)
	) !important;
	border: 1px solid rgba(139, 92, 246, 0.35) !important;
	box-shadow:
		0 18px 40px rgba(0, 0, 0, 0.55),
		0 0 0 1px rgba(226, 54, 112, 0.12) inset !important;
	font-family: var(--posa-font-family) !important;
}

.cc-group-picker-menu .v-list {
	background: transparent !important;
	padding: 6px !important;
}

.cc-group-picker-menu .v-list-item {
	border-radius: 10px !important;
	margin-bottom: 2px;
	min-height: 40px !important;
	color: var(--pos-text-primary, #e7ebf3) !important;
	font-family: var(--posa-font-family) !important;
	transition:
		background 0.15s ease,
		box-shadow 0.15s ease;
}

.cc-group-picker-menu .v-list-item-title {
	font-family: var(--posa-font-family) !important;
	font-size: 0.875rem !important;
	font-weight: 500 !important;
	letter-spacing: 0.01em !important;
	color: var(--pos-text-primary, #e7ebf3) !important;
}

.cc-group-picker-menu .v-list-item:hover {
	background: linear-gradient(
		90deg,
		rgba(139, 92, 246, 0.16),
		rgba(226, 54, 112, 0.08)
	) !important;
	box-shadow: inset 0 0 0 1px rgba(139, 92, 246, 0.35);
}

.cc-group-picker-menu .v-list-item--active,
.cc-group-picker-menu .v-list-item[aria-selected="true"] {
	background: linear-gradient(
		90deg,
		rgba(139, 92, 246, 0.28),
		rgba(226, 54, 112, 0.14)
	) !important;
	box-shadow: inset 0 0 0 1px rgba(139, 92, 246, 0.55);
}

.cc-group-picker-menu .v-list-item--active .v-list-item-title {
	font-weight: 600 !important;
	color: #ffffff !important;
}

.cc-group-picker-menu .v-list-item .v-icon {
	color: rgba(139, 92, 246, 0.95) !important;
}

/* Custom scrollbar so the popup doesn't feel like a default browser dropdown. */
.cc-group-picker-menu ::-webkit-scrollbar {
	width: 8px;
}
.cc-group-picker-menu ::-webkit-scrollbar-track {
	background: transparent;
}
.cc-group-picker-menu ::-webkit-scrollbar-thumb {
	background: linear-gradient(
		180deg,
		rgba(139, 92, 246, 0.45),
		rgba(226, 54, 112, 0.35)
	);
	border-radius: 8px;
}
.cc-group-picker-menu ::-webkit-scrollbar-thumb:hover {
	background: linear-gradient(
		180deg,
		rgba(139, 92, 246, 0.7),
		rgba(226, 54, 112, 0.55)
	);
}
</style>
