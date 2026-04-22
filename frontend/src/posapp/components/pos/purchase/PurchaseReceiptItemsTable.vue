<template>
	<v-data-table
		:headers="headers"
		:items="items"
		item-key="line_id"
		class="elevation-1 border rounded pr-table"
		density="compact"
		hide-default-footer
		:items-per-page="-1"
	>
		<template v-slot:item.item_name="{ item }">
			<div class="py-1">
				<div class="font-weight-bold">{{ item.item_name }}</div>
				<div class="text-caption text-medium-emphasis">
					{{ item.item_code }}
				</div>
				<div
					v-if="item.has_serial_no"
					class="text-caption text-medium-emphasis mt-1"
				>
					{{ __("Serial item") }}
				</div>
			</div>
		</template>

		<template v-slot:item.uom="{ item }">
			<div class="pos-table__editor-box uom-editor" @click.stop>
				<v-btn
					size="x-small"
					variant="flat"
					class="pos-table__editor-btn uom-arrow"
					@click.stop="changeUom(item, -1)"
					:disabled="!item.item_uoms || item.item_uoms.length <= 1"
					:aria-label="__('Previous unit of measure')"
				>
					<v-icon size="small">mdi-chevron-left</v-icon>
				</v-btn>
				<v-select
					:model-value="item.uom"
					@update:model-value="(val) => $emit('update-uom', { item, value: val })"
					:items="item.item_uoms || [{ uom: item.stock_uom, conversion_factor: 1 }]"
					item-title="uom"
					item-value="uom"
					density="compact"
					variant="outlined"
					class="pos-table__editor-input uom-select"
					:class="{ 'uom-display-mode': !item._isEditingUom }"
					hide-details
					@focus="item._isEditingUom = true"
					@blur="item._isEditingUom = false"
				></v-select>
				<v-btn
					size="x-small"
					variant="flat"
					class="pos-table__editor-btn uom-arrow"
					@click.stop="changeUom(item, 1)"
					:disabled="!item.item_uoms || item.item_uoms.length <= 1"
					:aria-label="__('Next unit of measure')"
				>
					<v-icon size="small">mdi-chevron-right</v-icon>
				</v-btn>
			</div>
		</template>

		<template v-slot:item.batch="{ item }">
			<div v-if="item.has_batch_no" class="pr-batch-cell">
				<div class="pr-batch-cell__row">
					<v-combobox
						:model-value="item.batch_no"
						@update:model-value="(val) => $emit('set-batch', { item, value: val })"
						:items="batchOptionLabels(item)"
						:placeholder="__('Pick or type new batch')"
						density="compact"
						variant="outlined"
						hide-details
						clearable
						class="pos-themed-input pr-batch-cell__field"
						menu-icon=""
						@click.stop
						@focus="ensureBatches(item)"
					>
						<template #append-inner>
							<v-progress-circular
								v-if="item.batch_options_loading"
								indeterminate
								size="14"
								width="2"
							/>
						</template>
						<template #item="{ props, item: opt }">
							<v-list-item
								v-bind="props"
								:title="opt.title"
								:subtitle="opt.subtitle"
							>
								<template #append>
									<v-chip
										v-if="opt.raw.is_expired"
										size="x-small"
										color="error"
										variant="tonal"
									>
										{{ __("Expired") }}
									</v-chip>
								</template>
							</v-list-item>
						</template>
					</v-combobox>
					<div class="pr-batch-cell__expiry" @click.stop>
						<VueDatePicker
							:model-value="item.batch_expiry_date || null"
							@update:model-value="(val) => onExpiryChange(item, val)"
							format="dd/MM/yyyy"
							model-type="yyyy-MM-dd"
							:enable-time-picker="false"
							auto-apply
							text-input
							:text-input-options="{ format: ['dd/MM/yyyy', 'd/M/yyyy', 'dd-MM-yyyy'], enterSubmit: true, tabSubmit: true }"
							:teleport="true"
							:placeholder="__('DD/MM/YYYY')"
							input-class-name="pr-mini-date pr-mini-date--picker"
							:title="__('Batch expiry date (required for new batches)')"
						/>
					</div>
				</div>
				<div
					v-if="item.batch_is_new && item.batch_no"
					class="pr-batch-cell__hint"
				>
					<v-icon size="x-small" class="pr-batch-cell__hint-icon">mdi-tag-plus-outline</v-icon>
					{{ __("New batch — will be created on submit") }}
				</div>
			</div>
			<div v-else class="text-caption text-medium-emphasis text-center">—</div>
		</template>

		<template v-slot:item.serial_no="{ item }">
			<div v-if="item.has_serial_no" @click.stop>
				<v-textarea
					:model-value="item.serial_no"
					@update:model-value="(val) => $emit('update-serial', { item, value: val })"
					:placeholder="__('One serial per line')"
					density="compact"
					variant="outlined"
					hide-details
					rows="2"
					auto-grow
					class="pos-themed-input pr-serial-input"
				/>
			</div>
			<div v-else class="text-caption text-medium-emphasis text-center">—</div>
		</template>

		<template v-slot:item.qty="{ item }">
			<div class="pos-table__qty-counter">
				<v-btn
					size="small"
					variant="flat"
					class="pos-table__qty-btn minus-btn qty-control-btn"
					@click.stop="$emit('update-qty', { item, value: Math.max(0, (Number(item.qty) || 0) - 1) })"
					:aria-label="__('Decrease quantity')"
				>
					<v-icon size="small">mdi-minus</v-icon>
				</v-btn>
				<div
					v-if="!item._isEditingQty"
					class="pos-table__qty-display"
					@click.stop="openQtyEdit(item)"
				>
					{{ formatNumber(item.qty) }}
				</div>
				<v-text-field
					v-else
					v-model="item._editingQtyValue"
					density="compact"
					variant="outlined"
					class="pos-table__qty-input"
					@blur="closeQtyEdit(item)"
					@keydown.enter.prevent="closeQtyEdit(item)"
					@click.stop
					autofocus
					type="number"
					min="0"
				></v-text-field>
				<v-btn
					size="small"
					variant="flat"
					class="pos-table__qty-btn plus-btn qty-control-btn"
					@click.stop="$emit('update-qty', { item, value: (Number(item.qty) || 0) + 1 })"
					:aria-label="__('Increase quantity')"
				>
					<v-icon size="small">mdi-plus</v-icon>
				</v-btn>
			</div>
		</template>

		<template v-slot:item.rate="{ item }">
			<div class="pos-table__editor-box">
				<div
					v-if="!item._isEditingRate"
					class="pos-table__editor-display"
					@click.stop="openRateEdit(item)"
				>
					<span class="currency-symbol">{{ currencySymbol }}</span>
					<span class="amount-value">{{ formatCurrency(item.rate) }}</span>
				</div>
				<v-text-field
					v-else
					v-model="item._editingRateValue"
					density="compact"
					variant="outlined"
					class="pos-table__editor-input"
					@blur="closeRateEdit(item)"
					@keydown.enter.prevent="closeRateEdit(item)"
					@click.stop
					autofocus
					type="number"
					min="0"
				></v-text-field>
			</div>
		</template>

		<template v-slot:item.discount_percentage="{ item }">
			<div class="pos-table__editor-box">
				<div
					v-if="!item._isEditingDiscount"
					class="pos-table__editor-display"
					@click.stop="openDiscountEdit(item)"
				>
					<span class="amount-value">{{ formatNumber(item.discount_percentage) }}%</span>
				</div>
				<v-text-field
					v-else
					v-model="item._editingDiscountValue"
					density="compact"
					variant="outlined"
					class="pos-table__editor-input"
					@blur="closeDiscountEdit(item)"
					@keydown.enter.prevent="closeDiscountEdit(item)"
					@click.stop
					autofocus
					type="number"
					min="0"
					max="100"
				></v-text-field>
			</div>
		</template>

		<template v-slot:item.amount="{ item }">
			<div class="text-right font-weight-bold">
				{{ formatCurrency(lineAmount(item)) }}
			</div>
		</template>

		<template v-slot:item.actions="{ item }">
			<v-btn
				icon="mdi-delete"
				variant="text"
				color="error"
				size="small"
				@click="$emit('remove-item', item)"
				:aria-label="__('Remove item')"
			></v-btn>
		</template>

		<template v-slot:bottom>
			<div class="d-flex justify-end pa-4 font-weight-bold text-subtitle-1 border-t">
				<span class="mr-4">{{ __("Total:") }}</span>
				<span>{{ formatCurrency(totalAmount) }}</span>
			</div>
		</template>
	</v-data-table>
</template>

<script>
export default {
	props: {
		headers: Array,
		items: Array,
		currencySymbol: String,
		totalAmount: Number,
		formatCurrency: Function,
		formatNumber: Function,
	},
	emits: [
		"update-uom",
		"update-qty",
		"update-rate",
		"update-discount",
		"update-serial",
		"set-batch",
		"set-batch-expiry",
		"ensure-batches",
		"remove-item",
	],
	methods: {
		onExpiryChange(item, value) {
			// VueDatePicker emits null when cleared and a yyyy-MM-dd string when set.
			this.$emit("set-batch-expiry", { item, value: value || null });
		},
		lineAmount(item) {
			const qty = Number(item.qty) || 0;
			const rate = Number(item.rate) || 0;
			const disc = Number(item.discount_percentage) || 0;
			return qty * rate * (1 - disc / 100);
		},
		batchOptionLabels(item) {
			const opts = Array.isArray(item.batch_options) ? item.batch_options : [];
			return opts.map((opt) => {
				const expiry = opt.expiry_date
					? __("expires {0}", [opt.expiry_date])
					: __("no expiry");
				const supplier = opt.supplier ? ` · ${opt.supplier}` : "";
				return {
					title: opt.batch_id || opt.name,
					subtitle: `${expiry}${supplier}`,
					value: opt.batch_id || opt.name,
					raw: opt,
				};
			});
		},
		ensureBatches(item) {
			if (item.has_batch_no && !item.batch_options_loaded) {
				this.$emit("ensure-batches", item);
			}
		},
		changeUom(item, direction) {
			if (!item.item_uoms || item.item_uoms.length <= 1) return;
			const uoms = item.item_uoms.map((u) => u.uom);
			const currentIndex = uoms.indexOf(item.uom);
			let newIndex = currentIndex + direction;
			if (newIndex < 0) newIndex = uoms.length - 1;
			else if (newIndex >= uoms.length) newIndex = 0;
			const newUom = uoms[newIndex];
			if (newUom !== item.uom) {
				this.$emit("update-uom", { item, value: newUom });
			}
		},
		openQtyEdit(item) {
			item._isEditingQty = true;
			item._editingQtyValue = "";
		},
		closeQtyEdit(item) {
			if (item._isEditingQty) {
				if (item._editingQtyValue !== "" && item._editingQtyValue != null) {
					const val = parseFloat(item._editingQtyValue);
					if (!isNaN(val) && val >= 0) {
						this.$emit("update-qty", { item, value: val });
					}
				}
				item._isEditingQty = false;
			}
		},
		openRateEdit(item) {
			item._isEditingRate = true;
			item._editingRateValue = "";
		},
		closeRateEdit(item) {
			if (item._isEditingRate) {
				if (item._editingRateValue !== "" && item._editingRateValue != null) {
					const val = parseFloat(item._editingRateValue);
					if (!isNaN(val) && val >= 0) {
						this.$emit("update-rate", { item, value: val });
					}
				}
				item._isEditingRate = false;
			}
		},
		openDiscountEdit(item) {
			item._isEditingDiscount = true;
			item._editingDiscountValue = "";
		},
		closeDiscountEdit(item) {
			if (item._isEditingDiscount) {
				if (
					item._editingDiscountValue !== "" &&
					item._editingDiscountValue != null
				) {
					const val = parseFloat(item._editingDiscountValue);
					if (!isNaN(val) && val >= 0 && val <= 100) {
						this.$emit("update-discount", { item, value: val });
					}
				}
				item._isEditingDiscount = false;
			}
		},
	},
};
</script>

<style scoped>
.pr-table :deep(.v-data-table__td),
.pr-table :deep(.v-data-table__th) {
	vertical-align: top;
}

.pr-batch-cell {
	display: flex;
	flex-direction: column;
	gap: 4px;
	min-width: 240px;
	padding: 4px 0;
}

.pr-batch-cell__row {
	display: flex;
	gap: 6px;
	align-items: center;
}

.pr-batch-cell__field {
	flex: 1 1 60%;
	min-width: 0;
}

.pr-batch-cell__field :deep(.v-field__input) {
	min-height: 32px;
	padding-top: 4px;
	padding-bottom: 4px;
}

.pr-batch-cell__expiry {
	flex: 0 0 130px;
	min-width: 0;
}

.pr-mini-date {
	width: 100%;
	min-width: 0;
	font-size: 0.72rem;
	padding: 4px 8px;
	border-radius: 6px;
	border: 1px solid rgba(139, 92, 246, 0.28);
	background: rgba(139, 92, 246, 0.06);
	color: var(--pos-text-primary, #e7ebf3);
	color-scheme: dark;
	transition: border-color 0.18s ease, box-shadow 0.18s ease, background-color 0.18s ease;
}
.pr-mini-date:hover,
.pr-mini-date:focus {
	border-color: rgba(226, 54, 112, 0.55);
	background: rgba(139, 92, 246, 0.1);
	box-shadow: 0 0 0 2px rgba(139, 92, 246, 0.18);
	outline: none;
}

.pr-batch-cell__hint {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	font-size: 0.65rem;
	color: #fcd34d;
	letter-spacing: 0.04em;
	background: rgba(252, 211, 77, 0.08);
	border: 1px solid rgba(252, 211, 77, 0.25);
	padding: 2px 8px;
	border-radius: 999px;
	width: fit-content;
}
.pr-batch-cell__hint-icon {
	color: #fcd34d !important;
}

.pr-serial-input {
	min-width: 180px;
}
.pr-serial-input :deep(textarea) {
	font-family: var(--posa-font-family, "Space Grotesk", sans-serif);
	font-size: 0.75rem;
}

/* shared editor styles re-used from PurchaseItemsTable */
.pos-table__qty-counter {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 2px;
	padding: 2px;
	min-width: 60px;
	max-width: 100px;
	background: var(--pos-surface-variant);
	border-radius: 8px;
	border: 1px solid var(--pos-border-light);
	margin: 0 auto;
}

.pos-table__qty-display {
	min-width: 15px;
	max-width: 40px;
	flex: 1 1 auto;
	text-align: center;
	font-weight: 600;
	padding: 0 2px;
	border-radius: 4px;
	background: var(--pos-primary-container);
	border: 1px solid var(--pos-primary-variant);
	color: var(--pos-primary);
	font-size: 0.75rem;
	display: flex;
	align-items: center;
	justify-content: center;
	height: 24px;
	cursor: pointer;
}

.qty-control-btn {
	width: 24px !important;
	height: 24px !important;
	min-width: 24px !important;
	border-radius: 6px !important;
	font-weight: 600 !important;
}

.qty-control-btn.minus-btn {
	background: var(--pos-button-warning-bg) !important;
	color: var(--pos-button-warning-text) !important;
	border: 2px solid var(--pos-button-warning-border) !important;
}

.qty-control-btn.plus-btn {
	background: var(--pos-button-success-bg) !important;
	color: var(--pos-button-success-text) !important;
	border: 2px solid var(--pos-button-success-border) !important;
}

.pos-table__qty-input {
	max-width: 80px;
	margin: 0 auto;
}
.pos-table__qty-input :deep(input) {
	text-align: center;
	font-weight: 600;
}
/* Strip native browser number spinners (qty / rate / discount editors). */
.pos-table__qty-input :deep(input[type="number"]),
.pos-table__editor-input :deep(input[type="number"]) {
	-moz-appearance: textfield;
	appearance: textfield;
}
.pos-table__qty-input :deep(input[type="number"]::-webkit-outer-spin-button),
.pos-table__qty-input :deep(input[type="number"]::-webkit-inner-spin-button),
.pos-table__editor-input :deep(input[type="number"]::-webkit-outer-spin-button),
.pos-table__editor-input :deep(input[type="number"]::-webkit-inner-spin-button) {
	-webkit-appearance: none;
	margin: 0;
}

.pos-table__editor-box {
	display: flex;
	align-items: center;
	justify-content: center;
	gap: 2px;
	padding: 2px;
	min-width: 60px;
	max-width: 110px;
	background: var(--pos-surface-variant);
	border-radius: 8px;
	border: 1px solid var(--pos-border-light);
	margin: 0 auto;
}

.pos-table__editor-display {
	min-width: 40px;
	max-width: 90px;
	flex: 1 1 auto;
	text-align: center;
	font-weight: 600;
	padding: 0 2px;
	border-radius: 4px;
	background: var(--pos-primary-container);
	border: 1px solid var(--pos-primary-variant);
	color: var(--pos-primary);
	font-size: 0.75rem;
	display: flex;
	align-items: center;
	justify-content: center;
	height: 24px;
	cursor: pointer;
}

.pos-table__editor-btn {
	width: 24px !important;
	height: 24px !important;
	min-width: 24px !important;
	border-radius: 6px !important;
}
.pos-table__editor-input {
	max-width: 90px;
}
.pos-table__editor-input :deep(input) {
	text-align: center;
}

.uom-display-mode :deep(.v-field__outline) {
	display: none;
}
.uom-display-mode :deep(.v-field) {
	background-color: transparent !important;
	border: none !important;
	box-shadow: none !important;
}
.uom-display-mode :deep(.v-field__input) {
	justify-content: center;
	padding: 0;
	font-weight: 600;
	color: var(--pos-primary);
}
.uom-display-mode :deep(.v-select__selection-text) {
	text-align: center;
	color: var(--pos-primary);
	font-size: 0.65rem;
}
.uom-display-mode :deep(.v-field__append-inner) {
	display: none;
}

.amount-value {
	font-weight: 500;
}

.currency-symbol {
	opacity: 0.7;
	margin-right: 2px;
	font-size: 0.85em;
}
</style>

<!-- Unscoped: VueDatePicker teleports to body, so calendar styles must be global. -->
<style>
.dp__theme_dark,
.dp__theme_light {
	--dp-background-color: #161c27;
	--dp-text-color: #e7ebf3;
	--dp-hover-color: rgba(139, 92, 246, 0.28);
	--dp-hover-text-color: #ffffff;
	--dp-hover-icon-color: #ffffff;
	--dp-primary-color: #8b5cf6;
	--dp-primary-text-color: #ffffff;
	--dp-secondary-color: rgba(231, 235, 243, 0.6);
	--dp-border-color: rgba(139, 92, 246, 0.28);
	--dp-menu-border-color: rgba(139, 92, 246, 0.32);
	--dp-border-color-hover: rgba(226, 54, 112, 0.55);
	--dp-disabled-color: rgba(231, 235, 243, 0.18);
	--dp-scroll-bar-background: transparent;
	--dp-scroll-bar-color: rgba(139, 92, 246, 0.4);
	--dp-success-color: #34d399;
	--dp-success-color-disabled: rgba(52, 211, 153, 0.4);
	--dp-icon-color: #c4b5fd;
	--dp-danger-color: #fb7185;
	--dp-highlight-color: rgba(226, 54, 112, 0.32);
}
.dp__menu {
	background: linear-gradient(180deg, #1a2030 0%, #131826 100%) !important;
	border: 1px solid rgba(139, 92, 246, 0.32) !important;
	box-shadow: 0 18px 40px rgba(0, 0, 0, 0.45),
		0 0 0 1px rgba(244, 114, 182, 0.18) inset !important;
	border-radius: 12px !important;
}
.dp__cell_inner.dp__active_date {
	background: linear-gradient(135deg, #8b5cf6 0%, #e23670 100%) !important;
	color: #ffffff !important;
	border: none !important;
}
.dp__cell_inner:hover {
	background: rgba(139, 92, 246, 0.28) !important;
	color: #ffffff !important;
}
.dp__today {
	border: 1px solid rgba(226, 54, 112, 0.55) !important;
}
.dp__action_button.dp__action_select {
	background: linear-gradient(135deg, #8b5cf6 0%, #e23670 100%) !important;
	color: #ffffff !important;
	border: none !important;
}
.dp__action_button.dp__action_cancel {
	background: transparent !important;
	color: rgba(231, 235, 243, 0.7) !important;
}
</style>
