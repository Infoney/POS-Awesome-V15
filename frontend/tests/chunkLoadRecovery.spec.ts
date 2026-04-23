// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
	buildChunkRecoveryLocation,
	clearChunkRecoveryState,
	isDynamicImportFailure,
	recoverFromChunkLoadError,
	scheduleAfterStableBoot,
} from "../src/posapp/utils/chunkLoadRecovery";

describe("chunk load recovery helpers", () => {
	beforeEach(() => {
		window.sessionStorage.clear();
		window.localStorage.clear();
	});

	afterEach(() => {
		vi.useRealTimers();
		vi.restoreAllMocks();
	});

	it("detects dynamic import failures", () => {
		expect(
			isDynamicImportFailure(
				new TypeError(
					"Failed to fetch dynamically imported module: /assets/x.js",
				),
			),
		).toBe(true);
		expect(
			isDynamicImportFailure("ChunkLoadError: Loading chunk 12 failed."),
		).toBe(true);
		expect(
			isDynamicImportFailure(
				"SyntaxError: The requested module './offline/index.js' does not provide an export named 'ag'",
			),
		).toBe(true);
	});

	it("ignores non-chunk errors", () => {
		expect(isDynamicImportFailure(new Error("Network timeout"))).toBe(
			false,
		);
	});

	it("preserves retry history when clearing transient progress between reloads", async () => {
		const chunkError = new TypeError(
			"Failed to fetch dynamically imported module: /assets/chunk.js",
		);

		await recoverFromChunkLoadError(chunkError, "first-load");
		expect(
			window.sessionStorage.getItem("posa_chunk_reload_once"),
		).toBe("1");

		clearChunkRecoveryState();

		await recoverFromChunkLoadError(chunkError, "after-reload");

		expect(
			window.sessionStorage.getItem("posa_chunk_cache_recovery_once"),
		).toBe("1");
	});

	it("builds chunk recovery URLs against the current POS sub-route", () => {
		expect(
			buildChunkRecoveryLocation(
				{
					pathname: "/app/posapp/payments",
					search: "?draft=1",
					hash: "#totals",
				},
				"_posa_chunk_reload",
				55,
			),
		).toBe(
			"/app/posapp/payments?draft=1&_posa_chunk_reload=55#totals",
		);
	});

	it("swallows rejected stable-boot tasks to avoid unhandled rejections", async () => {
		vi.useFakeTimers();
		const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

		scheduleAfterStableBoot(() => Promise.reject(new Error("boom")));

		await vi.runAllTimersAsync();

		expect(warnSpy).toHaveBeenCalledWith(
			"Chunk recovery: stable boot task failed",
			expect.any(Error),
		);
	});

	it("stops redirecting once both reload and cache-recovery have run, even on repeated failures", async () => {
		const chunkError = new TypeError(
			"Failed to fetch dynamically imported module: /assets/chunk.js",
		);
		const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
		// Pre-populate the retry-history flags as if both branches had already
		// fired in this tab session.
		window.sessionStorage.setItem("posa_chunk_reload_once", "1");
		window.sessionStorage.setItem("posa_chunk_cache_recovery_once", "1");
		window.history.replaceState(
			{},
			"",
			"/app/posapp?_posa_chunk_reload=1&_posa_chunk_cache_recovery=2",
		);

		// Each subsequent call must hit the bounded fall-through path: it must
		// not redirect, must not reset the retry-history flags (so the next
		// failure also lands here instead of restarting the cycle), and must
		// strip the recovery params from the URL.
		const first = await recoverFromChunkLoadError(chunkError, "loop-test-1");
		const second = await recoverFromChunkLoadError(chunkError, "loop-test-2");
		const third = await recoverFromChunkLoadError(chunkError, "loop-test-3");

		expect(first).toBe(false);
		expect(second).toBe(false);
		expect(third).toBe(false);
		expect(window.sessionStorage.getItem("posa_chunk_reload_once")).toBe(
			"1",
		);
		expect(
			window.sessionStorage.getItem("posa_chunk_cache_recovery_once"),
		).toBe("1");
		expect(
			window.sessionStorage.getItem("posa_chunk_recovery_in_progress"),
		).toBeNull();
		expect(window.location.search).not.toContain("_posa_chunk_reload");
		expect(window.location.search).not.toContain(
			"_posa_chunk_cache_recovery",
		);
		expect(errorSpy).toHaveBeenCalled();
	});
});

