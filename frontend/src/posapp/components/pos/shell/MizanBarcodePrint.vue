<!--
  Mizan Barcode Print — standalone label print page.

  Sibling of the older `BarcodePrinting.vue` (route `/barcode`) but
  uses the QZ-Tray-driven `BarcodeLabelPrintDialog` instead of
  generating an HTML print window. Pattern matches PI / PR's
  post-submit print flow, just without a Purchase document backing
  the labels.

  Operator flow:
    1. Search and add items one at a time, OR paste a list of
       item codes / barcodes (one per line) into the bulk box and
       hit "Add All".
    2. Adjust qty per row. Optionally fill Batch + Expiry per row
       — both are optional; empty values get hidden on the printed
       label.
    3. Hit "Print Labels" → server builds the labels payload →
       `BarcodeLabelPrintDialog` opens with QZ printer + size
       picker + preview.
-->
<template>
	<div class="pa-0 h-100 mbp-shell">
		<v-card class="h-100 d-flex flex-column mbp-card" flat>
			<div class="mbp-header">
				<div class="mbp-header__icon-wrap">
					<v-icon class="mbp-header__icon">mdi-tag-multiple-outline</v-icon>
				</div>
				<div class="mbp-header__copy">
					<span class="mbp-header__eyebrow">{{ __("Print labels via QZ Tray") }}</span>
					<h3 class="mbp-header__title">{{ __("Mizan Barcode Print") }}</h3>
				</div>
				<v-spacer></v-spacer>
				<button
					type="button"
					class="mbp-header__clear"
					@click="resetForm"
					:title="__('Clear All')"
					:aria-label="__('Clear all label items')"
				>
					<v-icon size="20">mdi-trash-can-outline</v-icon>
				</button>
			</div>

			<v-card-text class="flex-grow-1 overflow-y-auto pa-4 mbp-card__body">
				<!-- Inline single-item search -->
				<div class="mbp-search-bar">
					<v-autocomplete
						v-model="itemSearchSelection"
						:items="itemSearchResults"
						item-title="item_name"
						item-value="name"
						:label="__('Search & add an item (name or code)')"
						density="compact"
						variant="outlined"
						hide-details="auto"
						return-object
						clearable
						:loading="itemSearchLoading"
						@update:search="handleItemSearch"
						@update:model-value="onItemSelected"
						:custom-filter="() => true"
						:no-data-text="
							itemSearchLoading
								? __('Searching items...')
								: __('Type to search items')
						"
						class="pos-themed-input mbp-themed-field mbp-search-bar__input"
						menu-icon=""
					>
						<template #prepend-inner>
							<v-icon size="20" class="mbp-field-icon">mdi-magnify</v-icon>
						</template>
						<template #item="{ props, item: opt }">
							<v-list-item
								v-bind="props"
								:title="opt.raw.item_name"
								:subtitle="opt.raw.name"
							>
								<template #append>
									<span class="mbp-search-bar__rate">
										{{ formatNumber(opt.raw.standard_rate || 0) }}
									</span>
								</template>
							</v-list-item>
						</template>
					</v-autocomplete>
				</div>

				<!--
					Bulk paste — accepts one item code OR barcode per
					line. Each token becomes one row at qty=1; the
					operator then adjusts qty / batch / expiry per row.
				-->
				<v-expansion-panels variant="accordion" class="mbp-bulk-panel">
					<v-expansion-panel>
						<v-expansion-panel-title class="mbp-bulk-panel__title">
							<v-icon size="18" class="me-2">mdi-format-list-bulleted-square</v-icon>
							{{ __("Add multiple items at once") }}
						</v-expansion-panel-title>
						<v-expansion-panel-text>
							<v-textarea
								v-model="bulkText"
								:label="__('Paste item codes or barcodes — one per line')"
								density="compact"
								variant="outlined"
								rows="4"
								auto-grow
								hide-details="auto"
								class="pos-themed-input mbp-themed-field"
							></v-textarea>
							<div class="d-flex justify-end mt-2">
								<v-btn
									:loading="bulkAddLoading"
									:disabled="bulkAddLoading || !bulkText.trim()"
									@click="onBulkAdd"
									color="primary"
									variant="flat"
									size="small"
								>
									<v-icon start size="16">mdi-plus-circle-outline</v-icon>
									{{ __("Add All") }}
								</v-btn>
							</div>
							<div
								v-if="bulkSummary"
								class="text-caption mt-2"
								:class="bulkSummary.color"
							>
								{{ bulkSummary.text }}
							</div>
						</v-expansion-panel-text>
					</v-expansion-panel>
				</v-expansion-panels>

				<v-divider class="my-3 mbp-divider"></v-divider>

				<!-- Items grid -->
				<v-data-table
					v-if="rows.length"
					:headers="itemHeaders"
					:items="rows"
					item-key="line_id"
					density="compact"
					hide-default-footer
					:items-per-page="-1"
					class="elevation-1 border rounded mbp-table"
				>
					<template v-slot:item.item_name="{ item }">
						<div class="py-1">
							<div class="font-weight-bold">{{ item.item_name }}</div>
							<div class="text-caption text-medium-emphasis">
								{{ item.item_code }}
							</div>
						</div>
					</template>

					<template v-slot:item.qty="{ item }">
						<div class="qty-stepper" @click.stop>
							<button
								type="button"
								class="qty-stepper__btn qty-stepper__btn--dec"
								:aria-label="__('Decrease quantity')"
								@click.stop="
									updateQty(item, Math.max(1, (Number(item.qty) || 1) - 1))
								"
							>
								<v-icon size="14">mdi-minus</v-icon>
							</button>
							<input
								type="number"
								min="1"
								inputmode="numeric"
								class="qty-stepper__input"
								:value="item.qty"
								@input="updateQty(item, $event.target.value)"
								@click.stop
							/>
							<button
								type="button"
								class="qty-stepper__btn qty-stepper__btn--inc"
								:aria-label="__('Increase quantity')"
								@click.stop="updateQty(item, (Number(item.qty) || 0) + 1)"
							>
								<v-icon size="14">mdi-plus</v-icon>
							</button>
						</div>
					</template>

					<template v-slot:item.batch_no="{ item }">
						<v-combobox
							:model-value="item.batch_no"
							@update:model-value="(val) => setBatch(item, val)"
							:items="batchOptionLabels(item)"
							:placeholder="__('Pick or type new batch')"
							density="compact"
							variant="outlined"
							hide-details
							clearable
							class="pos-themed-input"
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
							<template #item="{ props: itemProps, item: opt }">
								<v-list-item
									v-bind="itemProps"
									:title="opt.title"
									:subtitle="opt.subtitle"
								>
									<template #append>
										<v-chip
											v-if="opt.raw && opt.raw.is_expired"
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
						<div
							v-if="item.batch_is_new && item.batch_no"
							class="mbp-batch-hint"
						>
							<v-icon size="x-small" class="mbp-batch-hint__icon">
								mdi-tag-plus-outline
							</v-icon>
							{{ __("New batch — type expiry manually") }}
						</div>
					</template>

					<template v-slot:item.batch_expiry_date="{ item }">
						<div class="mbp-date-cell" @click.stop>
							<VueDatePicker
								v-model="item.batch_expiry_date"
								model-type="yyyy-MM-dd"
								format="dd/MM/yyyy"
								:enable-time-picker="false"
								auto-apply
								text-input
								:text-input-options="{
									format: ['dd/MM/yyyy', 'd/M/yyyy', 'dd-MM-yyyy'],
									enterSubmit: true,
									tabSubmit: true,
								}"
								:placeholder="__('Optional')"
								class="pos-themed-input mbp-mini-date"
								:teleport="true"
							/>
						</div>
					</template>

					<template v-slot:item.actions="{ item }">
						<v-btn
							icon="mdi-delete"
							size="small"
							variant="text"
							color="error"
							@click="removeRow(item)"
							:aria-label="__('Remove item')"
						></v-btn>
					</template>
				</v-data-table>

				<div v-else class="mbp-empty">
					<v-icon size="48" class="mbp-empty__icon">mdi-tag-outline</v-icon>
					<div class="mbp-empty__title">{{ __("No items yet") }}</div>
					<div class="mbp-empty__hint">
						{{ __("Search and add items above, or paste a list of codes in the bulk panel.") }}
					</div>
				</div>

				<v-alert
					v-if="errorMessage"
					type="error"
					density="compact"
					class="mt-4"
				>
					{{ errorMessage }}
				</v-alert>
			</v-card-text>

			<v-card-actions class="pa-4 mbp-actions">
				<v-spacer></v-spacer>
				<v-btn
					:loading="submitLoading"
					:disabled="submitLoading || !rows.length"
					@click="onPrint"
					class="mbp-print-btn"
					size="large"
					block
				>
					<v-icon start>mdi-printer</v-icon>
					{{ __("Print {0} Labels", [totalLabelCount]) }}
				</v-btn>
			</v-card-actions>
		</v-card>

		<BarcodeLabelPrintDialog
			v-model="labelDialog"
			:labels="pendingLabels"
			@close="onLabelDialogClose"
		/>
	</div>
</template>

<script>
import format from "../../../format";
import { useUIStore } from "../../../stores/uiStore.js";
import { getOpeningStorage } from "../../../../offline/index";
import { useToastStore } from "../../../stores/toastStore";
import BarcodeLabelPrintDialog from "../purchase/BarcodeLabelPrintDialog.vue";
import { ref, watch, onMounted } from "vue";

let _lineSeq = 0;
const nextLineId = () => `mbp_${Date.now()}_${++_lineSeq}`;

export default {
	mixins: [format],
	components: { BarcodeLabelPrintDialog },
	setup() {
		const uiStore = useUIStore();
		const toastStore = useToastStore();

		const pos_profile = ref({});
		const rows = ref([]);
		const itemSearchSelection = ref(null);
		const itemSearchResults = ref([]);
		const itemSearchLoading = ref(false);
		const itemSearchTimeout = ref(null);

		const bulkText = ref("");
		const bulkAddLoading = ref(false);
		const bulkSummary = ref(null);

		const errorMessage = ref("");
		const submitLoading = ref(false);
		const labelDialog = ref(false);
		const pendingLabels = ref([]);

		// ── Single-item search ────────────────────────────────────
		const handleItemSearch = (term) => {
			if (itemSearchTimeout.value) clearTimeout(itemSearchTimeout.value);
			itemSearchTimeout.value = setTimeout(() => searchItems(term), 250);
		};

		const searchItems = async (searchText = "") => {
			if (!searchText || searchText.trim().length < 1) {
				itemSearchResults.value = [];
				return;
			}
			itemSearchLoading.value = true;
			try {
				const { message } = await frappe.call({
					method:
						"posawesome.mizan.api.barcode_labels.search_items_for_labels",
					args: { search_text: searchText, limit: 20 },
				});
				itemSearchResults.value = Array.isArray(message) ? message : [];
			} catch (error) {
				console.error("Failed to search items:", error);
				itemSearchResults.value = [];
			} finally {
				itemSearchLoading.value = false;
			}
		};

		const addRow = (itemDetails, qty = 1) => {
			if (!itemDetails || !itemDetails.name) return null;
			const itemCode = itemDetails.name;
			// Stack qty on the existing row when the same item gets
			// added twice (typical "scanned this item again" UX).
			const existing = rows.value.find(
				(row) => row.item_code === itemCode,
			);
			if (existing) {
				existing.qty = Math.max(
					1,
					Number(existing.qty || 1) + Number(qty || 1),
				);
				return existing;
			}
			const row = {
				line_id: nextLineId(),
				item_code: itemCode,
				item_name: itemDetails.item_name || itemCode,
				stock_uom: itemDetails.stock_uom || "",
				standard_rate: Number(itemDetails.standard_rate || 0),
				qty: Math.max(1, Number(qty) || 1),
				batch_no: "",
				batch_is_new: false,
				batch_expiry_date: null,
				// Lazy-loaded list of existing Batch records for
				// this item (matches the PR / PI batch-picker
				// pattern). Filled on first focus of the combobox
				// via `ensureBatches`.
				batch_options: [],
				batch_options_loaded: false,
				batch_options_loading: false,
			};
			rows.value.unshift(row);
			return row;
		};

		// ── Batch picker (mirrors usePurchaseReceipt.loadBatchOptions
		//    + setBatch). Items can have existing Batch records; the
		//    combobox lets the operator pick one (auto-fills expiry)
		//    or type a new one (operator fills expiry manually).
		const ensureBatches = async (row, { force = false } = {}) => {
			if (!row || (!force && row.batch_options_loaded)) return;
			row.batch_options_loading = true;
			try {
				const { message } = await frappe.call({
					method:
						"posawesome.mizan.api.purchase_receipts.get_existing_batches",
					args: { item_code: row.item_code },
				});
				row.batch_options = Array.isArray(message) ? message : [];
				row.batch_options_loaded = true;
			} catch (error) {
				console.warn("Failed to load batches", error);
				row.batch_options = [];
			} finally {
				row.batch_options_loading = false;
			}
		};

		const setBatch = (row, value) => {
			// v-combobox emits either a raw string (free text) or
			// the full item object (when picked from the list). Coerce
			// both shapes to a clean string before normalising.
			let raw = value;
			if (raw && typeof raw === "object") {
				raw =
					raw.value ??
					raw.batch_id ??
					raw.name ??
					raw.title ??
					raw.raw?.batch_id ??
					raw.raw?.name ??
					"";
			}
			const batchId = String(raw ?? "").trim();
			row.batch_no = batchId;
			const match = (row.batch_options || []).find(
				(opt) => opt.batch_id === batchId || opt.name === batchId,
			);
			if (match) {
				row.batch_is_new = false;
				row.batch_expiry_date = match.expiry_date || null;
			} else {
				row.batch_is_new = !!batchId;
				if (!batchId) {
					row.batch_expiry_date = null;
				}
			}
		};

		const onItemSelected = (selected) => {
			if (!selected) return;
			addRow(selected, 1);
			itemSearchSelection.value = null;
			itemSearchResults.value = [];
		};

		// ── Bulk paste ────────────────────────────────────────────
		const onBulkAdd = async () => {
			const tokens = bulkText.value
				.split(/[\r\n,]+/)
				.map((t) => t.trim())
				.filter(Boolean);
			if (!tokens.length) return;
			bulkAddLoading.value = true;
			bulkSummary.value = null;
			let added = 0;
			let skipped = 0;
			try {
				for (const token of tokens) {
					try {
						const { message } = await frappe.call({
							method:
								"posawesome.mizan.api.barcode_labels.search_items_for_labels",
							args: { search_text: token, limit: 5 },
						});
						const exact =
							Array.isArray(message)
								? message.find(
										(m) =>
											m.name === token ||
											m.item_name === token,
									) || message[0]
								: null;
						if (exact) {
							addRow(exact, 1);
							added += 1;
						} else {
							skipped += 1;
						}
					} catch (e) {
						console.warn("Bulk lookup failed for token", token, e);
						skipped += 1;
					}
				}
				bulkText.value = "";
				bulkSummary.value = {
					text: __("Added {0} item(s){1}", [
						added,
						skipped ? __(", skipped {0}", [skipped]) : "",
					]),
					color:
						skipped && !added
							? "text-error"
							: skipped
								? "text-warning"
								: "text-success",
				};
			} finally {
				bulkAddLoading.value = false;
			}
		};

		// ── Row helpers ───────────────────────────────────────────
		const updateQty = (row, value) => {
			const parsed = Number(value);
			row.qty = Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
		};

		const removeRow = (row) => {
			rows.value = rows.value.filter((r) => r.line_id !== row.line_id);
		};

		const resetForm = () => {
			rows.value = [];
			bulkText.value = "";
			bulkSummary.value = null;
			itemSearchSelection.value = null;
			itemSearchResults.value = [];
			errorMessage.value = "";
		};

		// ── Submit ────────────────────────────────────────────────
		const onPrint = async () => {
			if (!rows.value.length) {
				errorMessage.value = __("Add at least one item.");
				return;
			}
			errorMessage.value = "";
			submitLoading.value = true;
			try {
				const payload = {
					pos_profile: pos_profile.value?.name || pos_profile.value,
					company: pos_profile.value?.company,
					items: rows.value.map((row) => ({
						item_code: row.item_code,
						item_name: row.item_name,
						qty: row.qty,
						stock_uom: row.stock_uom,
						batch_no: row.batch_no || "",
						batch_expiry_date: row.batch_expiry_date || "",
					})),
				};
				const { message } = await frappe.call({
					method: "posawesome.mizan.api.barcode_labels.build_labels",
					args: { data: JSON.stringify(payload) },
				});
				const labels = Array.isArray(message?.labels)
					? message.labels
					: [];
				if (!labels.length) {
					errorMessage.value = __(
						"No printable labels — check that selected items have barcodes.",
					);
					return;
				}
				pendingLabels.value = labels;
				labelDialog.value = true;
			} catch (error) {
				const msg =
					error?.message ||
					error?.responseJSON?.message ||
					__("Unable to build labels");
				errorMessage.value = msg;
				toastStore.show({ title: msg, color: "error" });
			} finally {
				submitLoading.value = false;
			}
		};

		const onLabelDialogClose = () => {
			pendingLabels.value = [];
			// Keep the rows around — the operator may want to print
			// the same set on a different printer / label size.
			// `resetForm` is the explicit clear button.
		};

		onMounted(async () => {
			const cachedData = getOpeningStorage();
			if (cachedData?.pos_profile) pos_profile.value = cachedData.pos_profile;
			watch(
				() => uiStore.posProfile,
				(p) => {
					if (p) pos_profile.value = p;
				},
				{ immediate: true },
			);
		});

		return {
			pos_profile,
			rows,
			itemSearchSelection,
			itemSearchResults,
			itemSearchLoading,
			bulkText,
			bulkAddLoading,
			bulkSummary,
			errorMessage,
			submitLoading,
			labelDialog,
			pendingLabels,
			handleItemSearch,
			onItemSelected,
			onBulkAdd,
			updateQty,
			removeRow,
			resetForm,
			onPrint,
			onLabelDialogClose,
			ensureBatches,
			setBatch,
			toastStore,
		};
	},
	computed: {
		totalLabelCount() {
			return this.rows.reduce((sum, r) => sum + Number(r.qty || 0), 0);
		},
		itemHeaders() {
			return [
				{
					title: __("Item"),
					key: "item_name",
					align: "start",
					width: "30%",
				},
				{
					title: __("Qty"),
					key: "qty",
					align: "center",
					width: "16%",
					sortable: false,
				},
				{
					title: __("Batch"),
					key: "batch_no",
					align: "start",
					width: "20%",
					sortable: false,
				},
				{
					title: __("Expiry"),
					key: "batch_expiry_date",
					align: "start",
					width: "20%",
					sortable: false,
				},
				{
					title: "",
					key: "actions",
					align: "center",
					width: "50px",
					sortable: false,
				},
			];
		},
	},
	methods: {
		formatNumber(v) {
			return this.formatFloat(v, 2);
		},
		batchOptionLabels(item) {
			const opts = Array.isArray(item.batch_options)
				? item.batch_options
				: [];
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
	},
};
</script>

<style scoped>
.mbp-shell {
	background: var(--pos-surface-bg, #0a0e17);
}

.mbp-card {
	background: var(--pos-card-bg, #0e131e) !important;
	border: 1px solid rgba(139, 92, 246, 0.18);
	border-radius: 14px !important;
	font-family: var(--posa-font-family, "Space Grotesk", sans-serif);
	color: var(--pos-text-primary, #e7ebf3);
	overflow: hidden;
}

.mbp-card__body {
	background: var(--pos-card-bg, #0e131e);
}

.mbp-header {
	display: flex;
	align-items: center;
	gap: 14px;
	padding: 14px 18px;
	background:
		linear-gradient(
			135deg,
			rgba(139, 92, 246, 0.18),
			rgba(226, 54, 112, 0.1)
		),
		var(--pos-surface-muted, #161c27);
	border-bottom: 1px solid rgba(139, 92, 246, 0.28);
}

.mbp-header__icon-wrap {
	width: 44px;
	height: 44px;
	display: grid;
	place-items: center;
	border-radius: 12px;
	flex-shrink: 0;
	background: linear-gradient(
		135deg,
		rgba(139, 92, 246, 0.32),
		rgba(226, 54, 112, 0.22)
	);
	border: 1px solid rgba(139, 92, 246, 0.5);
	box-shadow: 0 6px 18px rgba(139, 92, 246, 0.22);
}

.mbp-header__icon {
	font-size: 24px !important;
	color: #c4b5fd !important;
}

.mbp-header__copy {
	display: flex;
	flex-direction: column;
	gap: 2px;
	min-width: 0;
}

.mbp-header__eyebrow {
	font-size: 0.66rem;
	font-weight: 700;
	letter-spacing: 0.16em;
	text-transform: uppercase;
	color: rgba(231, 235, 243, 0.65);
}

.mbp-header__title {
	margin: 0;
	font-size: 1.1rem;
	font-weight: 700;
	letter-spacing: 0.01em;
	background: linear-gradient(135deg, #f5d0fe 0%, #fb7185 100%);
	background-clip: text;
	-webkit-background-clip: text;
	color: transparent;
	-webkit-text-fill-color: transparent;
}

.mbp-header__clear {
	all: unset;
	width: 36px;
	height: 36px;
	display: grid;
	place-items: center;
	border-radius: 10px;
	cursor: pointer;
	color: rgba(231, 235, 243, 0.7);
	border: 1px solid rgba(244, 63, 94, 0.28);
	background: rgba(244, 63, 94, 0.08);
	transition: background-color 0.18s ease, color 0.18s ease, box-shadow 0.18s ease;
}
.mbp-header__clear:hover {
	background: rgba(244, 63, 94, 0.18);
	color: #fb7185;
	box-shadow: 0 0 0 3px rgba(244, 63, 94, 0.14);
}

.mbp-search-bar {
	margin-bottom: 12px;
}

.mbp-search-bar__input :deep(.v-field) {
	border-radius: 12px !important;
	background: linear-gradient(
		180deg,
		rgba(139, 92, 246, 0.10),
		rgba(226, 54, 112, 0.06)
	) !important;
	border: 1px solid rgba(139, 92, 246, 0.32) !important;
}
.mbp-search-bar__input :deep(.v-field--focused) {
	background: linear-gradient(
		180deg,
		rgba(139, 92, 246, 0.18),
		rgba(226, 54, 112, 0.10)
	) !important;
	border-color: #e23670 !important;
	box-shadow: 0 0 0 3px rgba(226, 54, 112, 0.22) !important;
}

.mbp-search-bar__rate {
	font-size: 0.72rem;
	color: #c4b5fd;
	font-weight: 600;
}

.mbp-field-icon {
	color: #c4b5fd !important;
	margin-right: 6px;
}

.mbp-themed-field :deep(.v-field) {
	border-radius: 10px !important;
	background: rgba(139, 92, 246, 0.05) !important;
}
.mbp-themed-field :deep(.v-field__outline__start),
.mbp-themed-field :deep(.v-field__outline__end),
.mbp-themed-field :deep(.v-field__outline__notch::before),
.mbp-themed-field :deep(.v-field__outline__notch::after) {
	border-color: rgba(139, 92, 246, 0.32) !important;
}

.mbp-bulk-panel {
	margin-bottom: 8px;
	border-radius: 10px;
	overflow: hidden;
	border: 1px solid rgba(139, 92, 246, 0.22);
	background: rgba(139, 92, 246, 0.04);
}

.mbp-bulk-panel :deep(.v-expansion-panel) {
	background: transparent !important;
}

.mbp-bulk-panel__title {
	font-weight: 600;
	color: var(--pos-text-primary);
}

.mbp-divider {
	border-color: rgba(139, 92, 246, 0.18) !important;
	opacity: 1 !important;
}

.mbp-table {
	background: transparent !important;
}

.mbp-table :deep(.v-data-table__th),
.mbp-table :deep(.v-data-table__td) {
	background: transparent !important;
	color: var(--pos-text-primary) !important;
	border-bottom-color: rgba(139, 92, 246, 0.15) !important;
}

.mbp-empty {
	padding: 48px 16px;
	text-align: center;
	color: rgba(231, 235, 243, 0.6);
}
.mbp-empty__icon {
	color: rgba(139, 92, 246, 0.45) !important;
	margin-bottom: 12px;
}
.mbp-empty__title {
	font-size: 1rem;
	font-weight: 700;
	color: rgba(231, 235, 243, 0.85);
	margin-bottom: 4px;
}
.mbp-empty__hint {
	font-size: 0.85rem;
}

/* Reusing the Qty stepper styling from PurchaseReceiptItemsTable —
   inlined here to keep the page self-contained (no shared CSS
   dependency). */
.qty-stepper {
	display: inline-flex;
	align-items: stretch;
	width: 100%;
	max-width: 132px;
	min-width: 96px;
	height: 32px;
	border-radius: 10px;
	background: rgba(139, 92, 246, 0.05);
	border: 1px solid rgba(139, 92, 246, 0.32);
	overflow: hidden;
	box-shadow: 0 1px 3px rgba(0, 0, 0, 0.18);
	transition: border-color 0.18s ease, box-shadow 0.18s ease, background-color 0.18s ease;
	margin: 0 auto;
	box-sizing: border-box;
}
.qty-stepper:hover {
	border-color: rgba(139, 92, 246, 0.55);
	background: rgba(139, 92, 246, 0.10);
}
.qty-stepper:focus-within {
	border-color: #e23670;
	background: rgba(139, 92, 246, 0.12);
	box-shadow:
		0 0 0 3px rgba(226, 54, 112, 0.22),
		0 1px 3px rgba(0, 0, 0, 0.2);
}
.qty-stepper__btn {
	all: unset;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	width: 28px;
	flex: 0 0 28px;
	cursor: pointer;
	color: rgba(231, 235, 243, 0.85);
	background: transparent;
	transition: background-color 0.15s ease, color 0.15s ease;
	user-select: none;
}
.qty-stepper__btn:hover {
	background: rgba(139, 92, 246, 0.20);
	color: #ffffff;
}
.qty-stepper__btn:active {
	background: linear-gradient(135deg, #8b5cf6 0%, #e23670 100%);
	color: #ffffff;
}
.qty-stepper__btn--dec {
	border-right: 1px solid rgba(139, 92, 246, 0.22);
}
.qty-stepper__btn--inc {
	border-left: 1px solid rgba(139, 92, 246, 0.22);
}
.qty-stepper__input {
	flex: 1 1 auto;
	min-width: 0;
	width: 100%;
	height: 100%;
	border: none;
	outline: none;
	background: transparent;
	color: var(--pos-text-primary, #e7ebf3);
	text-align: center;
	font-variant-numeric: lining-nums tabular-nums;
	font-size: 0.9rem;
	font-weight: 600;
	letter-spacing: -0.01em;
	padding: 0 4px;
	-moz-appearance: textfield;
	appearance: textfield;
	box-sizing: border-box;
}
.qty-stepper__input::-webkit-outer-spin-button,
.qty-stepper__input::-webkit-inner-spin-button {
	-webkit-appearance: none;
	appearance: none;
	margin: 0;
}

.mbp-date-cell {
	min-width: 0;
}

.mbp-batch-hint {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	margin-top: 4px;
	font-size: 0.65rem;
	color: #fcd34d;
	letter-spacing: 0.04em;
	background: rgba(252, 211, 77, 0.08);
	border: 1px solid rgba(252, 211, 77, 0.25);
	padding: 2px 8px;
	border-radius: 999px;
	width: fit-content;
}
.mbp-batch-hint__icon {
	color: #fcd34d !important;
}

.mbp-mini-date :deep(.dp__input) {
	border: 1px solid rgba(139, 92, 246, 0.32) !important;
	background: rgba(139, 92, 246, 0.06) !important;
	color: var(--pos-text-primary, #e7ebf3) !important;
	font-family: var(--posa-font-family, "Space Grotesk", sans-serif);
	font-size: 0.85rem;
	font-variant-numeric: tabular-nums;
	border-radius: 6px !important;
	padding: 5px 10px !important;
}

.mbp-actions {
	background: var(--pos-surface-muted, #161c27);
	border-top: 1px solid rgba(139, 92, 246, 0.18);
}

.mbp-print-btn {
	background: linear-gradient(135deg, #8b5cf6 0%, #e23670 100%) !important;
	color: #ffffff !important;
	font-weight: 700 !important;
	letter-spacing: 0.04em !important;
	border-radius: 12px !important;
	min-height: 48px !important;
	box-shadow:
		0 12px 28px rgba(139, 92, 246, 0.28),
		0 0 0 1px rgba(244, 114, 182, 0.32) inset !important;
	text-transform: none !important;
	transition:
		filter 0.18s ease,
		box-shadow 0.18s ease,
		transform 0.18s ease !important;
}
.mbp-print-btn:hover:not(:disabled) {
	filter: brightness(1.08);
	box-shadow:
		0 14px 32px rgba(226, 54, 112, 0.34),
		0 0 0 1px rgba(244, 114, 182, 0.42) inset !important;
	transform: translateY(-1px);
}
.mbp-print-btn:disabled,
.mbp-print-btn.v-btn--disabled {
	opacity: 0.55 !important;
	background: linear-gradient(135deg, #4c4561 0%, #5b3149 100%) !important;
	box-shadow: none !important;
}
</style>
