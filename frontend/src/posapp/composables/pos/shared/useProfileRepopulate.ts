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
 *   - `stock_cache_scopes` (since the stock-cache refactor) is a map
 *     of `<profile>_<warehouse>` → entries, with an LRU cap and a
 *     5-minute freshness TTL
 * The in-memory items store still needs to be reset so the UI doesn't
 * keep showing prior-profile rows, but the stock cache itself no
 * longer needs a blind wipe — `initializeStockCache` will switch to
 * the new scope and skip the server fetch if that scope was warmed
 * within the TTL.
 *
 * What it does
 * ------------
 *   1. Watches `uiStore.posProfile.name` — skips the very first value
 *      (initial bootstrap is handled elsewhere by `ItemsSelector`).
 *   2. On change: aborts in-flight loaders, clears the in-memory items
 *      array, re-runs `itemsStore.initialize()` for the new profile,
 *      then asks `initializeStockCache` to ensure the stock scope is
 *      fresh (no-op if recently warmed).
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
	getLocalStock,
	initializeStockCache,
	resolveStockScope,
	setStockCacheReady,
	setStockScope,
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

			// ── 2) Switch the stock cache to the new profile's scope.
			//        No blind wipe — the scope-keyed cache keeps the
			//        previous profile's entries under its own key, so
			//        flipping back later is a cache hit. If the new
			//        scope was warmed recently, `initializeStockCache`
			//        below will see it's fresh and skip the server
			//        round-trip entirely.
			try {
				const nextScope = resolveStockScope(newProfile);
				setStockScope(nextScope);
				emit(
					"stock",
					5,
					nextScope ? `Switched to ${nextScope}` : "Stock scope cleared",
				);
			} catch (err) {
				console.warn("[useProfileRepopulate] stock scope switch failed", err);
			}

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

			// ── 5) Ensure the stock cache for the new scope is fresh.
			//        `initializeStockCache` is a no-op if the scope was
			//        warmed within the TTL, so bouncing between two
			//        recently-used profiles costs nothing.
			emit("stock", 30, "Refreshing stock balances");
			try {
				const items = (itemsStore.items as any[]) || [];
				if (items.length) {
					await initializeStockCache(items, newProfile);
					// Push the cached Bin balances onto the item rows in
					// memory. Without this the cards would keep showing
					// actual_qty = 0 (the default useItemsLoader forces
					// for items that arrive without a stock field). The
					// per-item detail fetcher *also* does this sync on
					// scroll, but waiting for that causes the cashier to
					// see a page of "0" until they interact.
					items.forEach((item) => {
						if (!item || !item.item_code) return;
						const qty = getLocalStock(item.item_code);
						if (qty !== null && qty !== undefined) {
							item.actual_qty = qty;
							item._base_actual_qty = qty;
						}
					});
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
