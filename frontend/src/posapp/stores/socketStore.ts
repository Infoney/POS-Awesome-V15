/**
 * Frappe realtime WebSocket listener store for background invoice processing.
 *
 * `init()` must be called once at application startup. It attaches five
 * `frappe.realtime` listeners that cover the full background-submission lifecycle:
 *
 * | Event | Effect |
 * |---|---|
 * | `pos_invoice_processed` | Resolves `waitForInvoiceProcessed`; shows success or "processing payments" toast |
 * | `pos_invoice_submit_error` | Rejects `waitForInvoiceProcessed`; shows error toast + `frappe.msgprint` |
 * | `pos_post_submit_payments_started` | Shows loading toast |
 * | `pos_post_submit_payments_completed` | Resolves `waitForPostSubmitPayments`; updates toast to success |
 * | `pos_post_submit_payments_failed` | Rejects `waitForPostSubmitPayments`; shows error toast |
 * | `posa_stock_changed` | Forwards payload to `dispatchRealtimeStockPayload` |
 *
 * **Promise-based waiting**
 * `waitForInvoiceProcessed(invoice, timeoutMs?)` and
 * `waitForPostSubmitPayments(invoice, timeoutMs?)` return Promises that resolve or
 * reject when the corresponding realtime event arrives for that specific invoice
 * name. Both default to a 45-second timeout. If the event has already been
 * received (stored in `processedInvoices` / `postSubmitPayments`) the Promise
 * settles synchronously without registering a waiter.
 *
 * **`has_post_submit_payment_work` flag**
 * When `pos_invoice_processed` includes `has_post_submit_payment_work: true`, a
 * persistent loading toast is shown and callers should also await
 * `waitForPostSubmitPayments` before marking the transaction complete.
 */
import { defineStore } from "pinia";
import { ref } from "vue";
import { useToastStore } from "./toastStore";
import { useUIStore } from "./uiStore";
import { dispatchRealtimeStockPayload } from "../utils/realtimeStock";
import { parseNegativeStockMessage } from "../utils/stock";
import { updateLocalStockCache } from "../../offline/index";
import stockCoordinator from "../utils/stockCoordinator";
import { bus } from "../bus";

type InvoiceProcessingPayload = {
  invoice?: string;
  name?: string;
  doctype?: string;
  error?: string;
  message?: string;
  has_post_submit_payment_work?: boolean;
};

type InvoiceProcessingState = {
  status: "processed" | "failed";
  doctype?: string;
  error?: string;
  hasPostSubmitPaymentWork?: boolean;
  updatedAt: number;
};

type PostSubmitPaymentState = {
  status: "started" | "completed" | "failed";
  doctype?: string;
  error?: string;
  updatedAt: number;
};

export const useSocketStore = defineStore("socket", () => {
  const toastStore = useToastStore();
  const uiStore = useUIStore();
  const processedInvoices = ref<Record<string, InvoiceProcessingState>>({});
  const postSubmitPayments = ref<Record<string, PostSubmitPaymentState>>({});
  const invoiceWaiters = new Map<string, Array<{ resolve: (value?: any) => void; reject: (reason?: any) => void }>>();
  const paymentWaiters = new Map<string, Array<{ resolve: (value?: any) => void; reject: (reason?: any) => void }>>();

  const resolveWaiters = (
    registry: Map<string, Array<{ resolve: (value?: any) => void; reject: (reason?: any) => void }>>,
    key: string,
    payload: any,
    isError = false,
  ) => {
    const waiters = registry.get(key) || [];
    registry.delete(key);
    waiters.forEach(({ resolve, reject }) => {
      if (isError) {
        reject(payload);
      } else {
        resolve(payload);
      }
    });
  };

  const withTimeout = <T>(
    registry: Map<string, Array<{ resolve: (value?: any) => void; reject: (reason?: any) => void }>>,
    key: string,
    timeoutMs: number,
  ) =>
    new Promise<T>((resolve, reject) => {
      const timeoutId = window.setTimeout(() => {
        const waiters = registry.get(key) || [];
        registry.set(
          key,
          waiters.filter((entry) => entry.resolve !== wrappedResolve),
        );
        reject(new Error(`Timed out waiting for ${key}`));
      }, timeoutMs);

      const wrappedResolve = (value?: T) => {
        clearTimeout(timeoutId);
        resolve(value as T);
      };
      const wrappedReject = (reason?: any) => {
        clearTimeout(timeoutId);
        reject(reason);
      };

      const waiters = registry.get(key) || [];
      waiters.push({ resolve: wrappedResolve, reject: wrappedReject });
      registry.set(key, waiters);
    });

  const waitForInvoiceProcessed = async (invoice: string, timeoutMs = 45000) => {
    const existing = processedInvoices.value[invoice];
    if (existing?.status === "processed") {
      return existing;
    }
    if (existing?.status === "failed") {
      throw new Error(existing.error || `Invoice ${invoice} failed to submit`);
    }
    return withTimeout<InvoiceProcessingState>(invoiceWaiters, invoice, timeoutMs);
  };

  const waitForPostSubmitPayments = async (invoice: string, timeoutMs = 45000) => {
    const existing = postSubmitPayments.value[invoice];
    if (existing?.status === "completed") {
      return existing;
    }
    if (existing?.status === "failed") {
      throw new Error(existing.error || `Post-submit payment processing failed for ${invoice}`);
    }
    return withTimeout<PostSubmitPaymentState>(paymentWaiters, invoice, timeoutMs);
  };

  function init() {
    if (typeof frappe === "undefined" || !frappe.realtime) return;

    // Global listener for background submission errors
    frappe.realtime.on("pos_invoice_submit_error", (data: InvoiceProcessingPayload) => {
      const message = data.error || data.message || "Unknown error";
      const invoice = data.invoice || "";
      processedInvoices.value[invoice] = {
        status: "failed",
        doctype: data.doctype,
        error: message,
        updatedAt: Date.now(),
      };
      resolveWaiters(invoiceWaiters, invoice, new Error(message), true);

      // Try to surface a per-batch overdraw as a focused, actionable
      // message instead of pasting the raw HTML-ish ERPNext dump. When
      // the parser recognises a "Batch X has negative stock of [quantity]
      // -N" string we:
      //   - Refresh the items panel cache for that item so the cashier
      //     immediately sees the real on-hand (typically 0) and can't
      //     re-add the same line and re-trigger the same failure.
      //   - Replace the generic "Background processing failed" wall of
      //     text with a one-line summary naming the batch, item, and
      //     warehouse so the cashier knows exactly which DB-stuck draft
      //     to open and adjust.
      // Falls through to the original generic msgprint/toast path when
      // the failure isn't a recognised batch overdraw (timestamp
      // mismatches, permission errors, network drops, etc.).
      const shortage = parseNegativeStockMessage(message);
      if (shortage) {
        try {
          updateLocalStockCache([
            { item_code: shortage.item_code, actual_qty: shortage.available },
          ]);
        } catch (err) {
          console.warn(
            "[socketStore] background-error stock cache refresh failed",
            err,
          );
        }
        try {
          stockCoordinator.updateBaseQuantities(
            [
              {
                item_code: shortage.item_code,
                actual_qty: shortage.available,
              },
            ],
            { source: "stock-conflict" },
          );
        } catch (err) {
          console.warn(
            "[socketStore] background-error stockCoordinator refresh failed",
            err,
          );
        }

        // Notify any listener that wants to react to a background
        // shortage (e.g. surface the StockConflictDialog when the cart
        // still holds the offending line, or jump the cashier to the
        // stuck draft). Decoupled via the bus so socketStore stays a
        // pure transport — Pos.vue / Invoice.vue decides what to do.
        bus.emit("background_invoice_stock_shortage", {
          invoice,
          doctype: data.doctype,
          shortage,
          rawMessage: message,
        });

        const focusedMessage = __(
          "Batch {0} of item {1} can't fulfil the requested {2} (only {3} available in {4}). Open the stuck draft to adjust the qty or pick a different batch, then resubmit.",
          [
            shortage.batch_no,
            shortage.item_code,
            String(shortage.requested),
            String(shortage.available),
            shortage.warehouse,
          ],
        );

        if (typeof frappe.msgprint === "function") {
          frappe.msgprint({
            title: __("Invoice {0} — stock shortage", [invoice || ""]),
            message: focusedMessage,
            indicator: "orange",
          });
        }

        toastStore.show({
          title: __("Stock shortage on Invoice {0}", [invoice || ""]),
          detail: focusedMessage,
          color: "warning",
          timeout: 8000,
        });
        return;
      }

      if (typeof frappe.msgprint === "function") {
        frappe.msgprint({
          title: __("Invoice Submission Failed"),
          message: __("Background processing failed for Invoice {0}: {1}", [invoice, message]),
          indicator: "red",
        });
      }

      toastStore.show({
        title: __("Background Submission Failed"),
        detail: message,
        color: "error",
        timeout: 8000,
      });
    });

    // Global listener for successful background submission
    frappe.realtime.on("pos_invoice_processed", (data: InvoiceProcessingPayload) => {
      const invoice = data.invoice || data.name;
      if (!invoice) return;
      const hasPostSubmitPaymentWork = Boolean(data.has_post_submit_payment_work);

      const state: InvoiceProcessingState = {
        status: "processed",
        doctype: data.doctype,
        hasPostSubmitPaymentWork,
        updatedAt: Date.now(),
      };
      processedInvoices.value[invoice] = state;
      resolveWaiters(invoiceWaiters, invoice, state);

      if (hasPostSubmitPaymentWork) {
        toastStore.show({
          key: `invoice-processing::${invoice}`,
          title: __("Invoice Submitted"),
          detail: __("Processing payment entries for Invoice {0}", [invoice]),
          color: "info",
          timeout: -1,
          loading: true,
        });
      } else {
        toastStore.show({
          key: `invoice-processing::${invoice}`,
          title: __("Invoice Submitted"),
          detail: __("Invoice {0} processed successfully", [invoice]),
          color: "success",
        });
      }
    });

    frappe.realtime.on("pos_post_submit_payments_started", (data: InvoiceProcessingPayload) => {
      const invoice = data.invoice || data.name;
      if (!invoice) return;

      postSubmitPayments.value[invoice] = {
        status: "started",
        doctype: data.doctype,
        updatedAt: Date.now(),
      };

      toastStore.show({
        key: `invoice-processing::${invoice}`,
        title: __("Invoice Submitted"),
        detail: __("Processing payment entries for Invoice {0}", [invoice]),
        color: "info",
        timeout: -1,
        loading: true,
      });
    });

    frappe.realtime.on("pos_post_submit_payments_completed", (data: InvoiceProcessingPayload) => {
      const invoice = data.invoice || data.name;
      if (!invoice) return;

      const state: PostSubmitPaymentState = {
        status: "completed",
        doctype: data.doctype,
        updatedAt: Date.now(),
      };
      postSubmitPayments.value[invoice] = state;
      resolveWaiters(paymentWaiters, invoice, state);

      toastStore.show({
        key: `invoice-processing::${invoice}`,
        title: __("Invoice Submitted"),
        detail: __("Payment entries processed for Invoice {0}", [invoice]),
        color: "success",
        timeout: 4000,
        loading: false,
      });
    });

    frappe.realtime.on("pos_post_submit_payments_failed", (data: InvoiceProcessingPayload) => {
      const invoice = data.invoice || data.name;
      const message = data.error || data.message || __("Unknown error");
      if (!invoice) return;

      postSubmitPayments.value[invoice] = {
        status: "failed",
        doctype: data.doctype,
        error: message,
        updatedAt: Date.now(),
      };
      resolveWaiters(paymentWaiters, invoice, new Error(message), true);

      toastStore.show({
        key: `invoice-processing::${invoice}`,
        title: __("Invoice Submitted"),
        detail: message,
        color: "error",
        timeout: 8000,
        loading: false,
      });
    });

    frappe.realtime.on("posa_stock_changed", (data: unknown) => {
      dispatchRealtimeStockPayload(data, {
        setLastStockAdjustment: uiStore.setLastStockAdjustment,
      });
    });
  }

  return {
    init,
    processedInvoices,
    postSubmitPayments,
    waitForInvoiceProcessed,
    waitForPostSubmitPayments,
  };
});
