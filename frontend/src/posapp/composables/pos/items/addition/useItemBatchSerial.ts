import { nextTick } from "vue";
import { getDisplayableBatchOptions } from "../../shared/useBatchSerial";

declare const frappe: any;
declare const __: (_text: string) => string;

// Strict check — `has_batch_no` may arrive as "0" / "1" (string) from the
// worker cache, and a bare truthy test lets non-batched items through.
const isBatched = (item: any): boolean =>
	Number(item?.has_batch_no ?? 0) > 0;
const hasSerial = (item: any): boolean =>
	Number(item?.has_serial_no ?? 0) > 0;

export function useItemBatchSerial() {
	const shouldAutoSetBatch = (context: any, item: any) => {
		// NOTE: we intentionally do NOT require `context.setBatchQty` to exist
		// here. The `callSetBatchQty` helper in useItemAddition already falls
		// back to the shared `useBatchSerial().setBatchQty` when the context
		// doesn't inject one (e.g. ItemsSelector's add-to-cart path), so
		// gating on `context.setBatchQty` here would silently defer the
		// allocation to the much later `update_items_details` round-trip and
		// the cashier would watch the cart sit without a batch pill for 5–10s
		// even though the batch data is already cached locally.
		if (!context?.pos_profile?.posa_auto_set_batch) {
			return false;
		}
		if (!isBatched(item) || item.batch_no) {
			return false;
		}
		return (
			Array.isArray(item.batch_no_data) && item.batch_no_data.length > 0
		);
	};

	const showBatchDialog = (item: any, context: any) => {
		const opts = Array.isArray(item.batch_no_data)
			? getDisplayableBatchOptions(item.batch_no_data)
			: [];
		if (opts.length > 0) {
			const dialog = new frappe.ui.Dialog({
				title: __("Select Batch"),
				fields: [
					{
						fieldtype: "Select",
						fieldname: "batch",
						label: __("Batch"),
						options: opts
							.map((b) => `${b.batch_no} | ${b.batch_qty}`)
							.join("\n"),
						reqd: !context.pos_profile.posa_allow_free_batch_return,
					},
				],
				primary_action_label: __("Select"),
				primary_action(values) {
					const selected = values.batch
						? values.batch.split("|")[0].trim()
						: null;
					context.setBatchQty(item, selected, false);
					dialog.hide();
				},
			});
			dialog.onhide = () => {
				if (!item.batch_no) {
					context.setBatchQty(item, null, false);
				}
			};
			dialog.show();
		} else {
			context.setBatchQty(item, null, false);
		}
	};

	const handleItemExpansion = (item: any, context: any) => {
		if (!item || !context?.pos_profile) {
			return;
		}

		if (
			(!context.pos_profile.posa_auto_set_batch && isBatched(item)) ||
			hasSerial(item)
		) {
			nextTick(() => {
				if (!item.posa_row_id) {
					return;
				}

				if (Array.isArray(context.expanded)) {
					context.expanded.push(item.posa_row_id);
				} else {
					context.expanded = [item.posa_row_id];
				}
			});
		}
	};

	return {
		shouldAutoSetBatch,
		showBatchDialog,
		handleItemExpansion,
	};
}
