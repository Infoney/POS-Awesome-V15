/**
 * useProfileRepopulate — auto-repopulates items / batches / stock when the
 * cashier switches POS Profile (typically by closing one shift and opening
 * another with a different profile).
 *
 * Why this exists
 * ---------------
 * Different POS Profiles can map to different warehouses and item-group
 * filters, so the items list, batch info and Bin balances visible to the
 * cashier are profile-scoped. The on-disk caches already account for
 * this:
 *   - `items` (Dexie) is filtered by `profile_scope` (`<profile>_<warehouse>`)
 *   - `itemsCache` keys include the same scope
 * BUT the in-memory store and the flat `local_stock_cache` don't reset
 * on their own. Without this composable the cashier sees prior-profile
 * rows / stock numbers until they manually refresh.
 *
 * What it does
 * ------------
 *   1. Watches `uiStore.posProfile.name` — skips the very first value
 *      (initial bootstrap is handled elsewhere by `ItemsSelector`).
 *   2. On change: aborts in-flight loaders, clears the in-memory items
 *      array, clears the flat stock cache, then re-runs
 *      `itemsStore.initialize()` for the new profile (which respects
 *      the new scope key).
 *   3. Emits `profile_repopulate_progress` events on the bus so the
 *      indicator chip in Pos.vue can show a per-resource progress bar.
 *
 * Failure mode
 * ------------
 * If any step throws we still emit a "done" event so the indicator
 * doesn't hang on screen forever — the cashier can hit the existing
 * "Refresh items" button to retry.
 */

import { inject, watch } from "vue";
import { storeToRefs } from "pinia";
import { useUIStore } from "../../../stores/uiStore.js";
import { useItemsStore } from "../../../stores/itemsStore.js";
import { useCustomersStore } from "../../../stores/customersStore.js";
import {
	clearLocalStockCache,
	initializeStockCache,
	setStockCacheReady,
} from "../../../../offline/index";

type EventBus = {
	emit: (event: string, payload?: unknown) => void;
};

type ProgressName = "items" | "batches" | "stock";

type ProgressPayload = {
	profile: string | null;
	stage: ProgressName | "done" | "start" | "error";
	progress: number; // 0-100
	message?: string;
};

/**
 * Convenience for emitting consistent progress payloads. The indicator
 * UI listens to a single event and updates its own internal state per
 * `stage`.
 */
const makeEmitter = (eventBus: EventBus | null, profile: string | null) =>
	(stage: ProgressPayload["stage"], progress: number, message?: string) => {
		if (!eventBus) return;
		try {
			eventBus.emit("profile_repopulate_progress", {
				profile,
				stage,
				progress: Math.max(0, Math.min(100, Math.round(progress))),
				message,
			} as ProgressPayload);
		} catch (err) {
			console.warn("[useProfileRepopulate] emit failed", err);
		}
	};

export function useProfileRepopulate() {
	const eventBus = inject<EventBus | null>("eventBus", null);
	const uiStore = useUIStore();
	const itemsStore = useItemsStore();
	const customersStore = useCustomersStore();
	const { posProfile } = storeToRefs(uiStore);

	// Track the last profile we ran the repopulate flow for so we don't
	// re-run on shallow changes (e.g. a no-op write of the same object).
	let lastProfileName: string | null = null;
	let inFlight = false;

	const runRepopulate = async (newProfile: any) => {
		if (inFlight) return;
		inFlight = true;
		const name: string = newProfile?.name || null;
		const emit = makeEmitter(eventBus, name);
		emit("start", 0, name ? `Switching to ${name}` : "Switching profile");

		try {
			// ── 1) Reset in-memory state so the UI doesn't keep showing
			//        stale items from the prior profile while we wait for
			//        the server. The IndexedDB scope is per-profile, so
			//        nothing on disk is lost.
			itemsStore.resetForProfile(newProfile);
			emit("items", 5, "Clearing previous catalogue");

			// ── 2) Stock cache is *flat* (one map for the whole app), so
			//        a profile change must wipe it — different warehouses
			//        could otherwise leak stale Bin balances into the new
			//        profile. We refill it after items load below.
			try {
				clearLocalStockCache();
			} catch (err) {
				console.warn("[useProfileRepopulate] stock clear failed", err);
			}
			emit("stock", 5, "Clearing stock cache");

			// ── 3) Re-point the customers store too — its address list
			//        is tied to profile.customer_groups + payment methods.
			try {
				customersStore.setPosProfile(newProfile);
				await customersStore.get_customer_names();
			} catch (err) {
				console.warn(
					"[useProfileRepopulate] customers refresh failed",
					err,
				);
			}

			// ── 4) Re-initialize the items store for the new profile.
			//        This covers item groups, the cached/server item
			//        fetch, the indexed search rebuild, and per-item
			//        detail seeding (which includes batch metadata).
			emit("items", 15, "Loading product catalogue");
			await itemsStore.initialize(
				newProfile,
				customersStore.selectedCustomer || null,
				newProfile?.selling_price_list || null,
			);
			emit(
				"items",
				100,
				`Catalogue loaded (${itemsStore.totalItemCount || 0})`,
			);

			// Items in the store after `initialize()` already carry batch
			// info from `get_items` (item.batch_no_data). Mark batches as
			// done in lockstep with items — they're not a separate fetch.
			emit("batches", 100, "Batches refreshed");

			// ── 5) Warm the stock cache for the new catalogue so the
			//        first scan / cart-add doesn't pay a round-trip.
			emit("stock", 30, "Refreshing stock balances");
			try {
				const items = (itemsStore.items as any[]) || [];
				if (items.length) {
					await initializeStockCache(items, newProfile);
				} else {
					setStockCacheReady(true);
				}
				emit("stock", 100, "Stock balances ready");
			} catch (err) {
				console.warn(
					"[useProfileRepopulate] stock prefetch failed",
					err,
				);
				// Even on failure, mark the stage so the indicator can
				// dismiss; the regular per-item fetch will fill the gap.
				emit("stock", 100, "Stock will load on demand");
			}

			emit("done", 100, "Profile ready");
			lastProfileName = name;
		} catch (err) {
			console.error("[useProfileRepopulate] failed", err);
			emit("error", 100, "Failed to refresh profile");
		} finally {
			inFlight = false;
		}
	};

	watch(
		() => posProfile.value?.name || null,
		(newName, oldName) => {
			if (!newName) return;
			// Initial mount: just record the baseline. The `ItemsSelector`
			// component already runs the first init, so re-running it here
			// would double-load on app start.
			if (lastProfileName === null && oldName == null) {
				lastProfileName = newName;
				return;
			}
			if (newName === lastProfileName) return;
			runRepopulate(posProfile.value);
		},
		{ immediate: true },
	);
}
