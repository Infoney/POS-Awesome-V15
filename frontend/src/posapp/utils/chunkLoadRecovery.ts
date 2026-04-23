import { buildPosAppRecoveryLocation } from "../../loader-utils";

const POSAPP_ROUTE = "/app/posapp";
const CHUNK_RELOAD_KEY = "posa_chunk_reload_once";
const CHUNK_CACHE_RECOVERY_KEY = "posa_chunk_cache_recovery_once";
const CHUNK_RECOVERY_IN_PROGRESS_KEY = "posa_chunk_recovery_in_progress";
const LOADER_RECOVERY_KEY = "posa_loader_chunk_recovery_once";
const CHUNK_RECOVERY_STABLE_DELAY_MS = 3000;
const RECOVERY_URL_PARAMS = [
	"_posa_chunk_reload",
	"_posa_chunk_cache_recovery",
	"_posa_loader_recovery",
];

// Module-load safety net: any value sitting in `posa_chunk_recovery_in_progress`
// at the start of a fresh page load is stale by definition — the prior page
// that set it is gone. Leaving it set would cause `recoverFromChunkLoadError`
// to short-circuit (return true without doing anything) on the very first
// chunk failure of this boot, masking the real failure and breaking recovery.
if (typeof window !== "undefined" && window.sessionStorage) {
	try {
		window.sessionStorage.removeItem(CHUNK_RECOVERY_IN_PROGRESS_KEY);
	} catch {}
}

function stripRecoveryParamsFromUrl() {
	if (
		typeof window === "undefined" ||
		!window.history ||
		typeof window.history.replaceState !== "function" ||
		!window.location
	) {
		return;
	}

	try {
		const url = new URL(window.location.href);
		let changed = false;
		for (const param of RECOVERY_URL_PARAMS) {
			if (url.searchParams.has(param)) {
				url.searchParams.delete(param);
				changed = true;
			}
		}
		if (changed) {
			const search = url.searchParams.toString();
			const next = `${url.pathname}${search ? `?${search}` : ""}${url.hash || ""}`;
			window.history.replaceState({}, "", next);
		}
	} catch {}
}

function normalizeErrorText(error: unknown): string {
	const message =
		error instanceof Error
			? error.message
			: typeof error === "string"
				? error
				: String(error || "");
	return message.trim().toLowerCase();
}

export function isDynamicImportFailure(error: unknown): boolean {
	const message = normalizeErrorText(error);
	return (
		message.includes("failed to fetch dynamically imported module") ||
		message.includes("loading chunk") ||
		message.includes("chunkloaderror") ||
		message.includes("importing a module script failed") ||
		(message.includes("requested module") &&
			message.includes("does not provide an export named"))
	);
}

function resetRecoveryState() {
	if (typeof window === "undefined" || !window.sessionStorage) {
		return;
	}
	window.sessionStorage.removeItem(CHUNK_RELOAD_KEY);
	window.sessionStorage.removeItem(CHUNK_CACHE_RECOVERY_KEY);
	window.sessionStorage.removeItem(CHUNK_RECOVERY_IN_PROGRESS_KEY);
	window.sessionStorage.removeItem(LOADER_RECOVERY_KEY);
}

export function clearChunkRecoveryState() {
	if (typeof window === "undefined" || !window.sessionStorage) {
		return;
	}
	window.sessionStorage.removeItem(CHUNK_RECOVERY_IN_PROGRESS_KEY);
}

export function resetChunkRecoveryState() {
	resetRecoveryState();
}

export function scheduleChunkRecoveryStateReset() {
	scheduleAfterStableBoot(() => {
		resetRecoveryState();
	});
}

export function scheduleAfterStableBoot(task: () => void | Promise<void>) {
	if (typeof window === "undefined") {
		return;
	}

	window.setTimeout(() => {
		void Promise.resolve(task()).catch((error) => {
			console.warn("Chunk recovery: stable boot task failed", error);
		});
	}, CHUNK_RECOVERY_STABLE_DELAY_MS);
}

export function buildChunkRecoveryLocation(
	locationLike: { pathname?: string; search?: string; hash?: string } | null | undefined,
	param: string,
	token: string | number = Date.now(),
) {
	return buildPosAppRecoveryLocation(locationLike, param, token, POSAPP_ROUTE);
}

function redirectToPosApp(param: string) {
	if (typeof window === "undefined" || !window.location) {
		return false;
	}
	window.location.replace(
		buildChunkRecoveryLocation(window.location, param, Date.now()),
	);
	return true;
}

async function clearServiceWorkersAndCaches() {
	if (typeof window === "undefined") {
		return;
	}

	try {
		if (
			typeof navigator !== "undefined" &&
			"serviceWorker" in navigator &&
			typeof navigator.serviceWorker.getRegistrations === "function"
		) {
			const registrations = await navigator.serviceWorker.getRegistrations();
			await Promise.all(
				registrations.map(async (registration) => {
					try {
						registration.active?.postMessage({
							type: "CLIENT_FORCE_UNREGISTER",
						});
					} catch {}
					try {
						registration.waiting?.postMessage({
							type: "CLIENT_FORCE_UNREGISTER",
						});
					} catch {}
					try {
						registration.installing?.postMessage({
							type: "CLIENT_FORCE_UNREGISTER",
						});
					} catch {}
					await registration.unregister();
				}),
			);
		}
	} catch (err) {
		console.warn("Chunk recovery: failed to cleanup service workers", err);
	}

	try {
		if (typeof caches !== "undefined") {
			const cacheKeys = await caches.keys();
			await Promise.all(cacheKeys.map((key) => caches.delete(key)));
		}
	} catch (err) {
		console.warn("Chunk recovery: failed to cleanup Cache API", err);
	}

	try {
		window.localStorage?.removeItem("posawesome_version");
		window.localStorage?.removeItem("posawesome_update_dismissed");
		window.localStorage?.removeItem("posawesome_update_last_check");
		window.sessionStorage?.removeItem("posawesome_update_snooze_until");
	} catch (err) {
		console.warn("Chunk recovery: failed to cleanup update keys", err);
	}
}

export async function recoverFromChunkLoadError(
	error: unknown,
	source = "runtime",
): Promise<boolean> {
	if (!isDynamicImportFailure(error)) {
		return false;
	}

	if (typeof window === "undefined" || !window.sessionStorage) {
		return false;
	}

	if (
		window.sessionStorage.getItem(CHUNK_RECOVERY_IN_PROGRESS_KEY) === "1"
	) {
		return true;
	}

	window.sessionStorage.setItem(CHUNK_RECOVERY_IN_PROGRESS_KEY, "1");

	const alreadyRetried =
		window.sessionStorage.getItem(CHUNK_RELOAD_KEY) === "1";
	if (!alreadyRetried) {
		window.sessionStorage.setItem(CHUNK_RELOAD_KEY, "1");
		console.warn("Chunk recovery: reloading POS app after chunk failure", {
			source,
			error,
		});
		return redirectToPosApp("_posa_chunk_reload");
	}

	const alreadyRecovered =
		window.sessionStorage.getItem(CHUNK_CACHE_RECOVERY_KEY) === "1";
	if (!alreadyRecovered) {
		window.sessionStorage.setItem(CHUNK_CACHE_RECOVERY_KEY, "1");
		console.warn(
			"Chunk recovery: clearing SW/cache after repeated chunk failure",
			{ source, error },
		);
		await clearServiceWorkersAndCaches();
		return redirectToPosApp("_posa_chunk_cache_recovery");
	}

	// Both recovery branches have already fired in this tab session and the
	// chunk *still* won't load. Anything we do from here would be a redirect
	// loop. Keep the retry-history flags set (they're the gate that makes the
	// next failure land back here instead of restarting the cycle), but clear
	// the in-progress flag so future calls reach this fall-through path
	// cleanly. Strip the recovery params from the URL so it stops collecting
	// stale `?_posa_chunk_reload=...&_posa_chunk_cache_recovery=...` markers.
	console.error(
		"Chunk recovery: chunk failure persists after reload and cache cleanup; " +
			"aborting further recovery attempts to avoid a redirect loop. " +
			"The user may need to hard-refresh (Ctrl+Shift+R) or clear site data.",
		{ source, error },
	);
	stripRecoveryParamsFromUrl();
	window.sessionStorage.removeItem(CHUNK_RECOVERY_IN_PROGRESS_KEY);
	return false;
}
