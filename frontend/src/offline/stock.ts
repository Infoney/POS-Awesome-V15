/**
 * Stock cache — scope-keyed, LRU-bounded, TTL-aware.
 *
 * Prior to this refactor the cashier shared a single flat map
 * `memory.local_stock_cache = { [item_code]: { actual_qty, last_updated } }`
 * for the whole app. That worked as long as only one POS Profile (and
 * therefore one warehouse) was ever in play per session, but the
 * moment a cashier closed a shift and opened another profile pointing
 * at a different warehouse, the old profile's Bin balances leaked into
 * the new one — and the only recovery path was to wipe the whole
 * cache and pay another server fetch.
 *
 * Shape now
 * ---------
 *   memory.stock_cache_scopes = {
 *       "<profile>_<warehouse>": {
 *           entries:     { [item_code]: { actual_qty, last_updated } },
 *           warmed_at:   ISO string — when we last filled from the server
 *           accessed_at: ISO string — bumped on every read/write, drives LRU
 *       },
 *       ...
 *   }
 *   memory.stock_cache_current_scope = "<profile>_<warehouse>" | null
 *   memory.local_stock_cache = { ... flat view of the CURRENT scope ... }
 *
 * `memory.local_stock_cache` is intentionally kept as a synchronized
 * *flat* view of the current scope's entries. Several call sites read
 * it directly (e.g. offline invoice pre-submit validation in
 * `invoices.ts`, the reconciler in `utils/buildCacheReconciler.ts`);
 * rewriting those to go through scope helpers is not worth the
 * churn, and the "flat view" invariant is cheap to maintain.
 *
 * Write helpers (updateLocalStock, updateLocalStockCache,
 * removeLocalStockEntries, setLocalStockCache, clearLocalStockCache)
 * operate on the current scope — they update both the scope record
 * and the flat view.
 *
 * Policies
 * --------
 *   LRU: keep at most MAX_STOCK_SCOPES scopes. When adding another,
 *        evict the one with the oldest `accessed_at`. At ~50k items
 *        * ~200 bytes each * 5 scopes ≈ 50 MB we stay comfortably
 *        under Chrome's IndexedDB quota.
 *   TTL: initializeStockCache() treats a scope as "fresh" if
 *        `warmed_at` is within STOCK_SCOPE_TTL_MS. Fresh scopes skip
 *        the server fetch entirely — a cashier toggling between two
 *        profiles they already warmed pays no round-trip.
 */

import { refreshBootstrapSnapshotFromCacheState } from "./cache";
import { memory, persist } from "./db";

type AnyRecord = Record<string, any>;

type StockEntry = {
	actual_qty: number;
	last_updated: string;
};

type ScopeRecord = {
	entries: Record<string, StockEntry>;
	warmed_at: string | null;
	accessed_at: string;
};

const MAX_STOCK_SCOPES = 5;
const STOCK_SCOPE_TTL_MS = 5 * 60 * 1000;

/**
 * Build the scope key for a POS Profile. Matches the convention used
 * by the items store (`<profile_name>_<warehouse>`) so scope keys
 * stay aligned across item / stock / customer caches.
 */
export function resolveStockScope(posProfile: AnyRecord | null | undefined): string | null {
	if (!posProfile) return null;
	const profileName = posProfile.name || "";
	const warehouse = posProfile.warehouse || "";
	if (!profileName || !warehouse) return null;
	return `${profileName}_${warehouse}`;
}

function ensureScopesMap(): Record<string, ScopeRecord> {
	if (!memory.stock_cache_scopes || typeof memory.stock_cache_scopes !== "object") {
		memory.stock_cache_scopes = {};
	}
	return memory.stock_cache_scopes as Record<string, ScopeRecord>;
}

function persistScopes() {
	persist("stock_cache_scopes");
	persist("stock_cache_current_scope");
	// `local_stock_cache` stays as the synchronized flat view so
	// direct readers (invoices.ts pre-submit guard, etc.) keep working.
	persist("local_stock_cache");
}

function nowIso() {
	return new Date().toISOString();
}

function getScopeRecord(scope: string | null, create = false): ScopeRecord | null {
	if (!scope) return null;
	const scopes = ensureScopesMap();
	let rec = scopes[scope];
	if (!rec && create) {
		rec = {
			entries: {},
			warmed_at: null,
			accessed_at: nowIso(),
		};
		scopes[scope] = rec;
	}
	if (rec) {
		rec.accessed_at = nowIso();
	}
	return rec || null;
}

/**
 * Drop the least-recently-accessed scopes until we're at or below the
 * LRU cap. Called after every write that could add a new scope.
 * Never evicts the currently active scope — if the cashier is looking
 * at it, it's by definition "most recent".
 */
function evictLRUIfNeeded() {
	const scopes = ensureScopesMap();
	const current = memory.stock_cache_current_scope as string | null;
	const keys = Object.keys(scopes);
	if (keys.length <= MAX_STOCK_SCOPES) return;

	const sortable = keys
		.filter((k) => k !== current)
		.map((k) => ({ key: k, accessed_at: scopes[k]?.accessed_at || "" }))
		.sort((a, b) => a.accessed_at.localeCompare(b.accessed_at));

	while (Object.keys(scopes).length > MAX_STOCK_SCOPES && sortable.length) {
		const victim = sortable.shift();
		if (!victim) break;
		delete scopes[victim.key];
	}
}

function syncFlatViewFromScope(scope: string | null) {
	if (!scope) {
		memory.local_stock_cache = {};
		return;
	}
	const rec = getScopeRecord(scope);
	memory.local_stock_cache = rec ? { ...rec.entries } : {};
}

/**
 * Switch the "current" scope. If no scope record exists yet, create
 * an empty one — the caller will typically follow up with a warm via
 * `initializeStockCache`.
 *
 * Idempotent: switching to the already-current scope is a no-op apart
 * from bumping `accessed_at`.
 */
export function setStockScope(scope: string | null) {
	const previous = memory.stock_cache_current_scope as string | null;
	memory.stock_cache_current_scope = scope;

	if (scope) {
		getScopeRecord(scope, /* create */ true);
	}
	syncFlatViewFromScope(scope);
	evictLRUIfNeeded();

	// Readiness flag is per-session, not per-scope: it means "we've
	// at least once warmed *some* scope". Flip it off on an empty
	// scope so the UI falls back to per-item detail fetches until
	// the new scope is filled.
	if (!scope) {
		setStockCacheReady(false);
	} else {
		const rec = getScopeRecord(scope);
		setStockCacheReady(!!(rec && rec.warmed_at));
	}

	if (previous !== scope) {
		persistScopes();
	}
}

export function getStockScope(): string | null {
	return (memory.stock_cache_current_scope as string | null) || null;
}

function isScopeFresh(scope: string | null, ttlMs = STOCK_SCOPE_TTL_MS): boolean {
	if (!scope) return false;
	const rec = getScopeRecord(scope);
	if (!rec || !rec.warmed_at) return false;
	const warmedAt = Date.parse(rec.warmed_at);
	if (!Number.isFinite(warmedAt)) return false;
	return Date.now() - warmedAt < ttlMs;
}

/**
 * Backwards-compatible helper: true iff any scope's been warmed.
 * Reads the derived flag so it stays O(1).
 */
export function isStockCacheReady() {
	return memory.stock_cache_ready || false;
}

export function setStockCacheReady(ready: boolean) {
	memory.stock_cache_ready = ready;
	persist("stock_cache_ready");
	refreshBootstrapSnapshotFromCacheState({
		stockCacheReady: memory.stock_cache_ready,
	});
}

export async function fetchItemStockQuantities(
	items: AnyRecord[],
	pos_profile: AnyRecord,
	chunkSize = 100,
) {
	const allItems: AnyRecord[] = [];
	try {
		for (let i = 0; i < items.length; i += chunkSize) {
			const chunk = items.slice(i, i + chunkSize);
			const response = await new Promise<AnyRecord[]>(
				(resolve, reject) => {
					frappe.call({
						method: "posawesome.mizan.api.items.get_items_details",
						args: {
							pos_profile: JSON.stringify(pos_profile),
							items_data: JSON.stringify(chunk),
						},
						freeze: false,
						callback: function (r) {
							if (r.message) {
								resolve(r.message);
							} else {
								reject(new Error("No response from server"));
							}
						},
						error: function (err) {
							reject(err);
						},
					});
				},
			);
			if (response) {
				allItems.push(...response);
			}
		}
		return allItems;
	} catch (error) {
		console.error("Failed to fetch item stock quantities:", error);
		return null;
	}
}

/**
 * Warm the stock cache for a POS Profile.
 *
 * Behaviour:
 *   1. Resolves the scope from the profile and makes it current.
 *   2. If the scope was warmed within STOCK_SCOPE_TTL_MS, returns true
 *      without touching the server. Switching between recently-used
 *      profiles is effectively free.
 *   3. Otherwise, fetches any missing items and updates the scope's
 *      `entries` + `warmed_at`.
 *
 * Returns true when the cache is considered ready for the current
 * scope (fresh hit or successful warm), false on fetch failure.
 */
export async function initializeStockCache(
	items: AnyRecord[],
	pos_profile: AnyRecord,
) {
	try {
		const scope = resolveStockScope(pos_profile);
		if (!scope) {
			console.warn(
				"initializeStockCache called without a resolvable scope",
			);
			return false;
		}

		// Switch to the target scope first so any concurrent reads see
		// the right flat view.
		setStockScope(scope);

		if (isScopeFresh(scope)) {
			console.info(
				`Stock cache fresh for scope ${scope} — skipping server fetch`,
			);
			setStockCacheReady(true);
			return true;
		}

		const rec = getScopeRecord(scope, /* create */ true)!;
		const existingEntries = rec.entries;
		const missingItems = Array.isArray(items)
			? items.filter((it) => it && it.item_code && !existingEntries[it.item_code])
			: [];

		if (missingItems.length === 0) {
			// Nothing new to fetch, but we still mark warmed so the TTL
			// check has a baseline for next time.
			rec.warmed_at = nowIso();
			setStockCacheReady(true);
			syncFlatViewFromScope(scope);
			persistScopes();
			return true;
		}

		console.info(
			`Initializing stock cache for scope ${scope}:`,
			missingItems.length,
			"new items",
		);

		const updatedItems = await fetchItemStockQuantities(
			missingItems,
			pos_profile,
		);

		if (updatedItems && updatedItems.length > 0) {
			updatedItems.forEach((item) => {
				if (item.actual_qty !== undefined && item.item_code) {
					existingEntries[item.item_code] = {
						actual_qty: item.actual_qty,
						last_updated: nowIso(),
					};
				}
			});

			rec.warmed_at = nowIso();
			syncFlatViewFromScope(scope);
			setStockCacheReady(true);
			persistScopes();
			console.info(
				`Stock cache warmed for scope ${scope} with`,
				Object.keys(existingEntries).length,
				"items",
			);
			return true;
		}
		return false;
	} catch (error) {
		console.error("Failed to initialize stock cache:", error);
		return false;
	}
}

/**
 * Decrement the current-scope cache by the qty sold on a submitted
 * invoice. Only touches items that already exist in the cache — we
 * don't fabricate entries for unknown items.
 */
export function updateLocalStock(items: AnyRecord[]) {
	try {
		const scope = getStockScope();
		const rec = getScopeRecord(scope);
		if (!rec) return;
		const entries = rec.entries;

		items.forEach((item) => {
			const key = item.item_code;
			if (!entries[key]) return;
			const soldQty = Math.abs(item.qty || 0);
			entries[key].actual_qty = Math.max(0, entries[key].actual_qty - soldQty);
			entries[key].last_updated = nowIso();
		});

		syncFlatViewFromScope(scope);
		persistScopes();
	} catch (e) {
		console.error("Failed to update local stock", e);
	}
}

/** Read from the current scope. */
export function getLocalStock(itemCode: string) {
	try {
		const scope = getStockScope();
		const rec = getScopeRecord(scope);
		if (!rec) return null;
		return rec.entries[itemCode]?.actual_qty ?? null;
	} catch {
		return null;
	}
}

/**
 * Upsert the supplied rows into the current scope's entries. Used by
 * the detail fetcher + sync adapter to refresh balances as items are
 * touched.
 */
export function updateLocalStockCache(items: AnyRecord[]) {
	try {
		const scope = getStockScope();
		if (!scope) return;
		const rec = getScopeRecord(scope, /* create */ true)!;
		const entries = rec.entries;

		items.forEach((item) => {
			if (!item || !item.item_code) return;
			if (item.actual_qty !== undefined) {
				entries[item.item_code] = {
					actual_qty: item.actual_qty,
					last_updated: nowIso(),
				};
			}
		});

		syncFlatViewFromScope(scope);
		persistScopes();
	} catch (e) {
		console.error("Failed to refresh local stock cache", e);
	}
}

/**
 * Clear the *current* scope only. Legacy name preserved — most
 * callers historically meant "wipe everything I can see", which is
 * still what this does now that the flat view is scope-bound. Use
 * `clearAllStockScopes()` when you actually want a full wipe (e.g.
 * logout, cache reset).
 */
export function clearLocalStockCache() {
	const scope = getStockScope();
	if (scope) {
		const scopes = ensureScopesMap();
		delete scopes[scope];
	}
	memory.local_stock_cache = {};
	setStockCacheReady(false);
	persistScopes();
}

/** Full wipe — used by the global cache reset flow. */
export function clearAllStockScopes() {
	memory.stock_cache_scopes = {};
	memory.stock_cache_current_scope = null;
	memory.local_stock_cache = {};
	setStockCacheReady(false);
	persistScopes();
}

export function removeLocalStockEntries(itemCodes: string[]) {
	try {
		const normalizedCodes = Array.from(
			new Set(
				(Array.isArray(itemCodes) ? itemCodes : [])
					.map((code) => String(code || "").trim())
					.filter(Boolean),
			),
		);
		if (!normalizedCodes.length) {
			return;
		}
		const scope = getStockScope();
		const rec = getScopeRecord(scope);
		if (!rec) return;
		normalizedCodes.forEach((code) => {
			delete rec.entries[code];
		});
		syncFlatViewFromScope(scope);
		persistScopes();
	} catch (e) {
		console.error("Failed to remove local stock entries", e);
	}
}

/**
 * Reconcile a just-submitted invoice against fresh server balances —
 * initialize any cache entries we didn't have yet, then apply the
 * sold-qty decrement. Operates on the current scope.
 */
export function updateLocalStockWithActualQuantities(
	invoiceItems: AnyRecord[],
	serverItems: AnyRecord[],
) {
	try {
		const scope = getStockScope();
		if (!scope) return;
		const rec = getScopeRecord(scope, /* create */ true)!;
		const entries = rec.entries;

		invoiceItems.forEach((invoiceItem) => {
			const key = invoiceItem.item_code;

			const serverItem = serverItems.find(
				(item) => item.item_code === invoiceItem.item_code,
			);

			if (serverItem && serverItem.actual_qty !== undefined) {
				if (!entries[key]) {
					entries[key] = {
						actual_qty: serverItem.actual_qty,
						last_updated: nowIso(),
					};
				} else {
					entries[key].actual_qty = serverItem.actual_qty;
					entries[key].last_updated = nowIso();
				}

				const soldQty = Math.abs(invoiceItem.qty || 0);
				entries[key].actual_qty = Math.max(
					0,
					entries[key].actual_qty - soldQty,
				);
			}
		});

		syncFlatViewFromScope(scope);
		persistScopes();
	} catch (e) {
		console.error("Failed to update local stock with actual quantities", e);
	}
}

/** Current-scope flat view. */
export function getLocalStockCache() {
	return memory.local_stock_cache || {};
}

/** Replace the current-scope entries wholesale. */
export function setLocalStockCache(cache: AnyRecord) {
	const scope = getStockScope();
	if (!scope) {
		memory.local_stock_cache = cache || {};
		persist("local_stock_cache");
		return;
	}
	const rec = getScopeRecord(scope, /* create */ true)!;
	const next: Record<string, StockEntry> = {};
	Object.entries(cache || {}).forEach(([code, value]) => {
		if (!code) return;
		const v = value as AnyRecord;
		if (v && typeof v.actual_qty === "number") {
			next[code] = {
				actual_qty: v.actual_qty,
				last_updated: v.last_updated || nowIso(),
			};
		}
	});
	rec.entries = next;
	rec.warmed_at = nowIso();
	syncFlatViewFromScope(scope);
	persistScopes();
}

/**
 * Diagnostic helper — lets debuggers (and the forthcoming test suite)
 * introspect the LRU list without reaching into `memory`.
 */
export function listStockScopes(): Array<{ scope: string; warmed_at: string | null; accessed_at: string; size: number }> {
	const scopes = ensureScopesMap();
	return Object.entries(scopes).map(([scope, rec]) => ({
		scope,
		warmed_at: rec.warmed_at,
		accessed_at: rec.accessed_at,
		size: Object.keys(rec.entries || {}).length,
	}));
}
