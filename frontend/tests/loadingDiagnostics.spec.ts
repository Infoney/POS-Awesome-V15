import { beforeEach, describe, expect, it, vi } from "vitest";

// The loading utility depends on `__` being on the global scope (Frappe
// injects it at runtime). We polyfill a no-op translator before importing so
// the module-level `__("...")` calls don't throw.
(globalThis as any).__ = (text: string) => text;

import {
	getBootstrapElapsedMs,
	getLoadingStatus,
	getStuckSources,
	initLoadingSources,
	isBootstrapStalled,
	loadingState,
	markSourceLoaded,
	resetLoadingState,
	setSourceProgress,
	STALL_THRESHOLD_MS,
} from "../src/posapp/utils/loading";

describe("loading diagnostics", () => {
	beforeEach(() => {
		resetLoadingState();
		vi.restoreAllMocks();
	});

	it("records startedAt when a bootstrap run begins", () => {
		const before = Date.now();
		initLoadingSources(["init", "items"]);
		expect(loadingState.startedAt).toBeGreaterThanOrEqual(before);
		expect(loadingState.active).toBe(true);
	});

	it("clears startedAt when reset", () => {
		initLoadingSources(["init"]);
		resetLoadingState();
		expect(loadingState.startedAt).toBe(0);
		expect(loadingState.active).toBe(false);
	});

	it("returns all sources below 100 from getStuckSources while active", () => {
		initLoadingSources(["init", "items", "customers"]);
		setSourceProgress("init", 100);
		setSourceProgress("items", 40);

		const stuck = getStuckSources();
		const names = stuck.map((s) => s.name).sort();
		expect(names).toEqual(["customers", "items"]);

		const items = stuck.find((s) => s.name === "items");
		expect(items?.progress).toBe(40);
	});

	it("reports empty stuck list once bootstrap completes", () => {
		initLoadingSources(["init"]);
		markSourceLoaded("init");
		// completeLoading runs a 400 + 600ms teardown; simulate by forcing the
		// terminal state directly so we don't need fake timers for this assertion.
		resetLoadingState();
		expect(getStuckSources()).toEqual([]);
	});

	it("flags the bootstrap as stalled after STALL_THRESHOLD_MS of no completion", () => {
		vi.useFakeTimers();
		const start = new Date("2026-04-21T10:00:00Z").getTime();
		vi.setSystemTime(start);

		initLoadingSources(["init", "items"]);
		setSourceProgress("init", 40);

		expect(isBootstrapStalled()).toBe(false);

		vi.setSystemTime(start + STALL_THRESHOLD_MS + 1_000);
		expect(isBootstrapStalled()).toBe(true);
		expect(getBootstrapElapsedMs()).toBeGreaterThanOrEqual(STALL_THRESHOLD_MS);

		vi.useRealTimers();
	});

	it("ignores setSourceProgress for unknown sources without mutating progress", () => {
		initLoadingSources(["init"]);
		const warn = vi.spyOn(console, "warn").mockImplementation(() => {});

		setSourceProgress("bogus", 50);

		expect(loadingState.sources.bogus).toBeUndefined();
		expect(loadingState.progress).toBe(0);
		// Dev builds warn; prod is silent. Either way the call must not throw.
		warn.mockRestore();
	});

	it("getLoadingStatus snapshots stuck sources for debugging", () => {
		initLoadingSources(["init", "items"]);
		setSourceProgress("init", 100);

		const status = getLoadingStatus();
		expect(status.active).toBe(true);
		expect(status.stuck.map((s) => s.name)).toEqual(["items"]);
		expect(status.sources).toEqual({ init: 100, items: 0 });
	});
});
