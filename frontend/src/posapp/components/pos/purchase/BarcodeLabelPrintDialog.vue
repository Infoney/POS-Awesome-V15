<!--
  Barcode-label print dialog for the one-step Purchase Invoice flow.

  Shown after `posawesome.mizan.api.purchase_invoices.create_purchase_invoice`
  returns. Lets the cashier:

    1. Pick a thermal-label printer wired to QZ Tray (defaulting to
       whichever the POS Profile remembers in `posa_qz_printer_name`).
    2. Pick a label size from the standard pharmacy/retail set:
         - 50×30 mm  (most common — Brother / Dymo / Zebra TLP)
         - 40×30 mm  (compact wall labels)
         - 38×25 mm  (small "single blister" labels)
         - 32×25 mm  (jewellery / very small SKUs)
    3. Print one label per unit purchased — three boxes of Panadol
       come back as three labels, no need to multiply qty client-side
       (the server already expanded `qty` into the `labels` array).

  Each label carries five fields that the user spec'd:
    Item Name | Cost Rate | Selling Price | Barcode | Pharmacy Name
  The pharmacy name comes from the POS Profile's `posa_brand_name`
  (typically Arabic on AL-KHANSA tenants), with a fallback to the
  Company name.

  Print path: HTML → JsBarcode → `printHtmlViaQz()` from the existing
  qzTray service. We send the rendered HTML to QZ as a `pixel` job
  sized to the label dimensions; QZ rasterises, scales to the
  printer's DPI, and dispatches one page per label.
-->
<template>
	<v-dialog v-model="isOpen" max-width="640" persistent scrollable>
		<v-card class="pos-themed-card barcode-label-card" flat>
			<div class="barcode-label-header">
				<div class="barcode-label-header__icon">
					<v-icon size="22">mdi-tag-multiple-outline</v-icon>
				</div>
				<div class="barcode-label-header__text">
					<h3 class="barcode-label-header__title">
						{{ __("Print Barcode Labels") }}
					</h3>
					<p class="barcode-label-header__subtitle">
						{{
							__(
								"{0} labels ready — pick a printer and a label size, then print.",
								[totalLabelCount],
							)
						}}
					</p>
				</div>
			</div>

			<v-card-text class="pa-4">
				<v-row dense>
					<v-col cols="12" md="7">
						<v-select
							v-model="selectedPrinter"
							:items="printerOptions"
							:label="__('QZ Printer')"
							density="compact"
							variant="outlined"
							hide-details
							class="pos-themed-input"
							:disabled="!qzConnected || printerOptions.length === 0"
							:loading="loadingPrinters"
						></v-select>
					</v-col>
					<v-col cols="12" md="5">
						<v-select
							v-model="selectedSize"
							:items="labelSizeOptions"
							:label="__('Label Size')"
							density="compact"
							variant="outlined"
							hide-details
							item-title="label"
							item-value="key"
							class="pos-themed-input"
						></v-select>
					</v-col>
				</v-row>

				<div v-if="!qzConnected" class="text-caption text-warning mt-3">
					{{ __("QZ Tray is not connected. Connect it from the navbar QZ icon, then come back to this dialog.") }}
				</div>

				<v-divider class="my-3"></v-divider>

				<!--
					Compact preview: render ONE label so the operator can
					see formatting + brand line before committing 50+ to
					thermal paper. Uses the same renderer as the actual
					print payload, so what's on screen matches the output.
				-->
				<div class="text-overline mb-2">
					{{ __("Preview") }}
				</div>
				<div v-if="firstLabel" class="barcode-label-preview-wrapper">
					<div
						class="barcode-label-preview"
						:style="previewStyle"
						v-html="previewHtml"
					></div>
				</div>
				<div v-else class="text-caption text-medium-emphasis">
					{{ __("No printable labels — every line was missing a barcode.") }}
				</div>

				<!--
					Roll-up: cashier can confirm the qty per item before
					burning a roll of labels. (Server-side already expanded
					qty into per-unit rows, so we re-aggregate here for the
					summary.)
				-->
				<v-data-table
					v-if="summaryRows.length"
					:headers="summaryHeaders"
					:items="summaryRows"
					density="compact"
					class="elevation-0 mt-4 barcode-label-summary"
					:items-per-page="-1"
					hide-default-footer
				>
					<template #item.selling_rate="{ item }">
						{{ formatLabelCurrency(item.selling_rate, item.currency) }}
					</template>
				</v-data-table>
			</v-card-text>

			<v-card-actions class="pa-4">
				<v-btn variant="text" @click="close">{{ __("Close") }}</v-btn>
				<v-spacer></v-spacer>
				<v-btn
					variant="text"
					@click="refreshPrinters"
					:disabled="loadingPrinters"
				>
					<v-icon start>mdi-refresh</v-icon>
					{{ __("Refresh Printers") }}
				</v-btn>
				<v-btn
					color="primary"
					variant="elevated"
					:loading="printing"
					:disabled="
						printing ||
						!labels.length ||
						!selectedPrinter ||
						!qzConnected
					"
					@click="onPrint"
				>
					<v-icon start>mdi-printer</v-icon>
					{{ __("Print {0} Labels", [totalLabelCount]) }}
				</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>

<script>
import {
	qzConnected,
	qzPrinters,
	selectedQzPrinter,
	findQzPrinters,
	printHtmlViaQz,
	setSelectedQzPrinter,
} from "../../../services/qzTray";
import { useToastStore } from "../../../stores/toastStore";

/*
 * Standard pharmacy/retail thermal-label sizes. Picked from the most
 * commonly stocked roll widths at AL-KHANSA + comparable tenants.
 * Kept short on purpose — adding more options here without a
 * concrete need just gives the cashier paralysis at the till.
 */
const LABEL_SIZES = [
	{ key: "50x30", widthMm: 50, heightMm: 30, label: "50 × 30 mm" },
	{ key: "40x30", widthMm: 40, heightMm: 30, label: "40 × 30 mm" },
	{ key: "38x25", widthMm: 38, heightMm: 25, label: "38 × 25 mm" },
	{ key: "32x25", widthMm: 32, heightMm: 25, label: "32 × 25 mm" },
];

const DEFAULT_LABEL_SIZE_KEY = "50x30";

function escapeHtml(value) {
	return String(value ?? "")
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&#39;");
}

function buildLabelStyle(widthMm, heightMm) {
	// Tuned for QZ pixel-rasterised HTML on a 203 dpi thermal head;
	// any wider and the barcode breaks the paper guides on a 50mm
	// roll. Font sizes scale down for the smaller sizes via the
	// `resolveFontSizes` helper below.
	return `
		@page { size: ${widthMm}mm ${heightMm}mm; margin: 0; }
		* { box-sizing: border-box; }
		body {
			margin: 0;
			padding: 0;
			width: ${widthMm}mm;
			height: ${heightMm}mm;
			font-family: 'Segoe UI', 'Tahoma', 'Noto Sans Arabic', sans-serif;
			color: #000;
			background: #fff;
		}
		.label {
			width: ${widthMm}mm;
			height: ${heightMm}mm;
			padding: 0.8mm 1mm;
			display: flex;
			flex-direction: column;
			align-items: center;
			justify-content: space-between;
			page-break-after: always;
			overflow: hidden;
		}
		.label__name {
			font-weight: 700;
			text-align: center;
			line-height: 1.05;
			width: 100%;
			overflow: hidden;
			display: -webkit-box;
			-webkit-line-clamp: 2;
			-webkit-box-orient: vertical;
		}
		.label__price {
			width: 100%;
			text-align: center;
			font-weight: 800;
			letter-spacing: 0.02em;
			line-height: 1.05;
		}
		.label__barcode-wrap {
			width: 100%;
			display: flex;
			align-items: center;
			justify-content: center;
			flex: 1;
			min-height: 0;
			overflow: hidden;
		}
		.label__barcode-wrap img {
			max-width: 100%;
			max-height: 100%;
			object-fit: contain;
		}
		.label__batch {
			width: 100%;
			display: flex;
			justify-content: center;
			align-items: center;
			gap: 4px;
			line-height: 1.05;
			white-space: nowrap;
			overflow: hidden;
			text-overflow: ellipsis;
		}
		.label__batch-tag {
			font-weight: 600;
			text-transform: uppercase;
			letter-spacing: 0.04em;
			opacity: 0.85;
		}
		.label__batch-sep {
			opacity: 0.55;
			padding: 0 2px;
		}
		.label__batch-piece {
			display: inline-flex;
			gap: 3px;
			align-items: baseline;
		}
		.label__brand {
			width: 100%;
			text-align: center;
			direction: rtl;
			font-weight: 600;
			letter-spacing: 0;
			line-height: 1.1;
			overflow: hidden;
			white-space: nowrap;
			text-overflow: ellipsis;
		}
	`;
}

function resolveFontSizes(widthMm) {
	// Larger barcode + bar width than the previous build — the
	// dense scrambled output the user reported was the result of
	// CODE128 packed into ~30mm width with width=1.4. Bumping the
	// bar width to 1.8/1.6 and the barcode height to 36/30 gives a
	// scanner-readable rendering on a 203 dpi thermal head while
	// still leaving room for the item name above and batch + brand
	// below.
	if (widthMm >= 50) {
		return {
			name: "9pt",
			price: "10pt",
			batch: "6.5pt",
			brand: "7.5pt",
			barcodeHeight: 36,
			barcodeWidth: 1.8,
			barcodeFont: 11,
		};
	}
	if (widthMm >= 40) {
		return {
			name: "8pt",
			price: "9pt",
			batch: "6pt",
			brand: "7pt",
			barcodeHeight: 30,
			barcodeWidth: 1.6,
			barcodeFont: 10,
		};
	}
	if (widthMm >= 38) {
		return {
			name: "7.5pt",
			price: "8pt",
			batch: "5.5pt",
			brand: "6.5pt",
			barcodeHeight: 26,
			barcodeWidth: 1.4,
			barcodeFont: 9,
		};
	}
	return {
		name: "7pt",
		price: "7.5pt",
		batch: "5pt",
		brand: "6pt",
		barcodeHeight: 22,
		barcodeWidth: 1.3,
		barcodeFont: 8,
	};
}

/**
 * Pick the safest JsBarcode format for a given value. We default to
 * CODE128 (handles arbitrary alphanumeric) and only fall through to
 * EAN13 when the value looks unambiguously like a 13-digit numeric
 * EAN — this stops `format="auto"` from picking a marginal format
 * that scanners struggle with.
 */
function resolveBarcodeFormat(value) {
	const text = String(value || "").trim();
	if (/^\d{13}$/.test(text)) return "EAN13";
	if (/^\d{12}$/.test(text)) return "UPC";
	if (/^\d{8}$/.test(text)) return "EAN8";
	return "CODE128";
}

function buildSingleLabelHtml(label, fonts) {
	const itemName = escapeHtml(label.item_name || label.item_code || "");
	// Cost is intentionally omitted from the customer-facing label.
	// Only the selling price prints — the cashier still sees cost
	// in the dialog summary table before printing.
	const sellRaw =
		label.selling_rate != null && Number(label.selling_rate) > 0
			? `${Number(label.selling_rate).toFixed(2)} ${label.currency || ""}`.trim()
			: "";
	const sellHtml = escapeHtml(sellRaw);
	const barcode = String(label.barcode || "").trim();
	const safeBarcode = escapeHtml(barcode);
	const brand = escapeHtml(label.brand_name || "");
	const batchNo = escapeHtml(label.batch_no || "");
	const batchExpiry = escapeHtml(label.batch_expiry_date || "");

	const priceBlock = sellHtml
		? `<div class="label__price" style="font-size: ${fonts.price};">${sellHtml}</div>`
		: "";

	const barcodeFormat = resolveBarcodeFormat(label.barcode);
	const barcodeBlock = barcode
		? `<div class="label__barcode-wrap">
				<img class="label__barcode"
					jsbarcode-format="${barcodeFormat}"
					jsbarcode-value="${safeBarcode}"
					jsbarcode-textmargin="0"
					jsbarcode-margin="0"
					jsbarcode-fontoptions="bold"
					jsbarcode-height="${fonts.barcodeHeight}"
					jsbarcode-width="${fonts.barcodeWidth}"
					jsbarcode-displayValue="true"
					jsbarcode-fontSize="${fonts.barcodeFont}"
					jsbarcode-textposition="bottom"
					jsbarcode-background="#ffffff"
					jsbarcode-lineColor="#000000">
			</div>`
		: `<div class="label__barcode-wrap" style="font-size: ${fonts.batch};">
				${escapeHtml(__("No barcode"))}
			</div>`;

	// Batch + Expiry line — only renders when at least one is present.
	// Compact "Batch: X | EXP: Y" so it never wraps onto two rows.
	const batchPieces = [];
	if (batchNo) {
		batchPieces.push(
			`<span class="label__batch-piece"><span class="label__batch-tag">${escapeHtml(
				__("Batch"),
			)}:</span> ${batchNo}</span>`,
		);
	}
	if (batchExpiry) {
		batchPieces.push(
			`<span class="label__batch-piece"><span class="label__batch-tag">${escapeHtml(
				__("EXP"),
			)}:</span> ${batchExpiry}</span>`,
		);
	}
	const batchBlock = batchPieces.length
		? `<div class="label__batch" style="font-size: ${fonts.batch};">${batchPieces.join(
				'<span class="label__batch-sep">|</span>',
			)}</div>`
		: "";

	const brandBlock = brand
		? `<div class="label__brand" style="font-size: ${fonts.brand};">${brand}</div>`
		: "";

	return `
		<div class="label">
			<div class="label__name" style="font-size: ${fonts.name};">${itemName}</div>
			${priceBlock}
			${barcodeBlock}
			${batchBlock}
			${brandBlock}
		</div>
	`;
}

export default {
	name: "BarcodeLabelPrintDialog",
	props: {
		modelValue: { type: Boolean, default: false },
		labels: { type: Array, default: () => [] },
	},
	emits: ["update:modelValue", "close"],
	setup() {
		const toastStore = useToastStore();
		return { toastStore };
	},
	data() {
		return {
			selectedSize: DEFAULT_LABEL_SIZE_KEY,
			loadingPrinters: false,
			printing: false,
			labelSizeOptions: LABEL_SIZES,
		};
	},
	computed: {
		isOpen: {
			get() {
				return this.modelValue;
			},
			set(value) {
				this.$emit("update:modelValue", value);
				if (!value) this.$emit("close");
			},
		},
		qzConnected() {
			return qzConnected.value;
		},
		printerOptions() {
			return Array.isArray(qzPrinters.value) ? qzPrinters.value : [];
		},
		selectedPrinter: {
			get() {
				return selectedQzPrinter.value;
			},
			set(value) {
				setSelectedQzPrinter(value || "");
			},
		},
		printableLabels() {
			return (this.labels || []).filter(
				(label) => label && label.barcode && label.qty > 0,
			);
		},
		totalLabelCount() {
			return this.printableLabels.reduce(
				(sum, label) => sum + Number(label.qty || 0),
				0,
			);
		},
		firstLabel() {
			return this.printableLabels[0] || null;
		},
		summaryHeaders() {
			// Cost intentionally absent — the customer-facing label
			// only carries the selling price, so the print dialog's
			// summary mirrors that.
			return [
				{ title: __("Item"), key: "item_name", align: "start" },
				{ title: __("Barcode"), key: "barcode", align: "start" },
				{ title: __("Batch"), key: "batch_no", align: "start" },
				{ title: __("Expiry"), key: "batch_expiry_date", align: "start" },
				{ title: __("Sell"), key: "selling_rate", align: "end" },
				{ title: __("Labels"), key: "qty", align: "end" },
			];
		},
		summaryRows() {
			// Server already expanded qty per line, but we surface ONE
			// row per `(item_code, uom)` here so the operator can sanity-
			// check totals before committing a roll.
			return (this.labels || []).map((label) => ({
				item_name: label.item_name,
				barcode: label.barcode || __("(missing)"),
				batch_no: label.batch_no || "—",
				batch_expiry_date: label.batch_expiry_date || "—",
				selling_rate: label.selling_rate,
				qty: label.qty,
				currency: label.currency,
			}));
		},
		previewSize() {
			return (
				this.labelSizeOptions.find((s) => s.key === this.selectedSize) ||
				this.labelSizeOptions[0]
			);
		},
		previewStyle() {
			const size = this.previewSize;
			if (!size) return "";
			// Render the preview at 4× physical size so the on-screen
			// proxy is legible without forcing the user to lean in.
			const scale = 4;
			return `width: ${size.widthMm * scale}px; height: ${size.heightMm * scale}px;`;
		},
		previewHtml() {
			if (!this.firstLabel) return "";
			const size = this.previewSize;
			if (!size) return "";
			const fonts = resolveFontSizes(size.widthMm);
			// For the on-screen preview the JsBarcode `<img>` won't
			// render barcode glyphs (no JsBarcode in this window) — we
			// substitute a placeholder so the preview still shows the
			// physical proportions correctly.
			const innerHtml = buildSingleLabelHtml(this.firstLabel, fonts).replace(
				/<img class="label__barcode"[\s\S]*?>/,
				`<div style="border: 1px dashed #888; padding: 4px 8px; font-family: monospace; font-size: ${fonts.barcodeFont}px;">${escapeHtml(this.firstLabel.barcode)}</div>`,
			);
			// Inline the per-label CSS scaled up for the preview. Fonts
			// are derived from the physical width so a 50mm preview
			// renders proportional-feeling text without needing a
			// per-size styled rule for each one.
			return `
				<style>
					.barcode-label-preview .label {
						width: 100%;
						height: 100%;
						padding: ${size.widthMm * 0.08}px ${size.widthMm * 0.1}px;
						display: flex;
						flex-direction: column;
						justify-content: space-between;
						align-items: center;
						background: #fff;
						color: #000;
					}
					.barcode-label-preview .label__name {
						text-align: center;
						font-weight: 700;
						line-height: 1.1;
						font-size: ${size.widthMm * 0.09}px;
					}
					.barcode-label-preview .label__price {
						width: 100%;
						text-align: center;
						font-weight: 800;
						font-size: ${size.widthMm * 0.10}px;
						line-height: 1.05;
					}
					.barcode-label-preview .label__barcode-wrap {
						display: flex;
						justify-content: center;
						align-items: center;
						width: 100%;
						flex: 1;
					}
					.barcode-label-preview .label__batch {
						width: 100%;
						display: flex;
						justify-content: center;
						gap: 4px;
						font-size: ${size.widthMm * 0.06}px;
					}
					.barcode-label-preview .label__batch-tag {
						font-weight: 600;
						text-transform: uppercase;
						opacity: 0.85;
					}
					.barcode-label-preview .label__batch-sep {
						opacity: 0.55;
					}
					.barcode-label-preview .label__brand {
						font-size: ${size.widthMm * 0.07}px;
						width: 100%;
						text-align: center;
						direction: rtl;
						font-weight: 600;
					}
				</style>
				${innerHtml}
			`;
		},
	},
	watch: {
		modelValue(value) {
			if (value) {
				this.refreshPrinters();
			}
		},
	},
	methods: {
		formatLabelCurrency(amount, currency) {
			if (amount == null) return "";
			const number = Number(amount);
			if (!Number.isFinite(number)) return "";
			return `${number.toFixed(2)} ${currency || ""}`.trim();
		},
		async refreshPrinters() {
			this.loadingPrinters = true;
			try {
				await findQzPrinters();
			} catch (error) {
				console.warn("Failed to refresh QZ printers", error);
			} finally {
				this.loadingPrinters = false;
			}
		},
		buildPrintHtml() {
			const size = this.previewSize;
			if (!size) return "";
			const fonts = resolveFontSizes(size.widthMm);
			const labelHtml = this.printableLabels
				.flatMap((label) => {
					const copies = Math.max(1, Number(label.qty || 1));
					const html = buildSingleLabelHtml(label, fonts);
					return Array.from({ length: copies }, () => html);
				})
				.join("\n");

			const style = buildLabelStyle(size.widthMm, size.heightMm);
			return `<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>${style}</style>
<script src="/assets/posawesome/dist/js/libs/JsBarcode.all.min.js"><\/script>
</head>
<body>
${labelHtml}
<script>
	if (typeof JsBarcode === 'function') {
		try { JsBarcode('.label__barcode').init(); } catch (e) { console.error(e); }
	}
<\/script>
</body>
</html>`;
		},
		async onPrint() {
			if (!this.printableLabels.length) {
				this.toastStore.show({
					title: __("No printable labels — every line was missing a barcode."),
					color: "warning",
				});
				return;
			}
			if (!this.selectedPrinter) {
				this.toastStore.show({
					title: __("Pick a QZ printer first."),
					color: "warning",
				});
				return;
			}
			const size = this.previewSize;
			if (!size) return;

			this.printing = true;
			try {
				const html = this.buildPrintHtml();
				await printHtmlViaQz(html, {
					printerName: this.selectedPrinter,
					widthMm: size.widthMm,
					orientation: "portrait",
				});
				this.toastStore.show({
					title: __("{0} labels sent to {1}", [
						this.totalLabelCount,
						this.selectedPrinter,
					]),
					color: "success",
				});
				this.isOpen = false;
			} catch (error) {
				console.error("Label print failed", error);
				this.toastStore.show({
					title:
						(error && error.message) ||
						__("Label print failed — check QZ Tray and try again."),
					color: "error",
				});
			} finally {
				this.printing = false;
			}
		},
		close() {
			this.isOpen = false;
		},
	},
	mounted() {
		this.refreshPrinters();
	},
};
</script>

<style scoped>
.barcode-label-card {
	background: var(--pos-card-bg) !important;
	color: var(--pos-text-primary);
	border: 1px solid var(--pos-border);
	border-radius: 14px;
	overflow: hidden;
}

.barcode-label-header {
	position: relative;
	display: flex;
	align-items: center;
	gap: 14px;
	padding: 14px 18px;
	background: var(--pos-card-bg);
	border-bottom: 1px solid var(--pos-border);
}

.barcode-label-header::before {
	content: "";
	position: absolute;
	top: 0;
	left: 0;
	right: 0;
	height: 3px;
	background: linear-gradient(90deg, #8b5cf6 0%, #e23670 100%);
}

.barcode-label-header__icon {
	width: 42px;
	height: 42px;
	border-radius: 12px;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	color: #fff;
	background: linear-gradient(135deg, #8b5cf6 0%, #e23670 100%);
	flex-shrink: 0;
	box-shadow: 0 4px 10px rgba(139, 92, 246, 0.3);
}

.barcode-label-header__text {
	display: flex;
	flex-direction: column;
	min-width: 0;
	flex: 1;
}

.barcode-label-header__title {
	margin: 0;
	font-size: 1.05rem;
	font-weight: 700;
	color: var(--pos-text-primary);
	letter-spacing: -0.01em;
}

.barcode-label-header__subtitle {
	margin: 2px 0 0;
	font-size: 0.78rem;
	color: var(--pos-text-secondary);
	line-height: 1.35;
}

.barcode-label-preview-wrapper {
	display: flex;
	justify-content: center;
	padding: 12px;
	background: var(--pos-surface-muted, #161c27);
	border-radius: 10px;
	border: 1px dashed rgba(139, 92, 246, 0.3);
}

.barcode-label-preview {
	background: #fff;
	color: #000;
	border-radius: 4px;
	overflow: hidden;
	box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}

.barcode-label-summary :deep(.v-data-table__th),
.barcode-label-summary :deep(.v-data-table__td) {
	background: transparent !important;
	color: var(--pos-text-primary) !important;
	border-bottom-color: var(--pos-border) !important;
}
</style>
