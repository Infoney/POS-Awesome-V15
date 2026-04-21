import { reactive } from "vue";
import {
	startBootstrapLoading,
	stopBootstrapLoading,
	setScopeMeta,
} from "../composables/core/useLoading";

/**
 * Interface representing the global loading state.
 */
export interface LoadingState {
	active: boolean;
	progress: number;
	sources: Record<string, number>;
	message: string;
	sourceMessages: Record<string, string>;
	/** Epoch-ms when the active bootstrap run started; 0 when idle. */
	startedAt: number;
}

// Internal tracking variables
let sourceCount = 0;
let completedSum = 0;
let isCompleting = false;

/**
 * Stuck-source reporting — after this many ms of continuous active loading
 * without reaching 100%, we consider the bootstrap "stalled" and the UI can
 * surface a diagnostic banner with the per-source breakdown.
 */
export const STALL_THRESHOLD_MS = 30_000;

/**
 * Tracks whether we're in a non-production build so dev-only warnings don't
 * leak to production logs.
 */
const isDevBuild = (() => {
	try {
		// `import.meta.env` is the canonical Vite signal; fall back to process.env.
		// Wrap in try/catch because `process` may be defined as a plain object in
		// the bundled output without `.env`.
		const viteEnv = (import.meta as any)?.env;
		if (viteEnv) return !!viteEnv.DEV;
		return (globalThis as any).process?.env?.NODE_ENV !== "production";
	} catch {
		return false;
	}
})();

/**
 * Reactive loading state used by the UI.
 */
export const loadingState = reactive<LoadingState>({
	active: false,
	progress: 0,
	sources: {},
	message: __("Loading app data..."),
	sourceMessages: {
		init: __("Initializing application..."),
		items: __("Loading product catalog..."),
		customers: __("Loading customer database..."),
	},
	startedAt: 0,
});

/**
 * Initializes the loading sources.
 * @param list List of source names to track
 */
export function initLoadingSources(list: string[]): void {
	// Reset state
	loadingState.sources = {};
	sourceCount = list.length;
	completedSum = 0;
	isCompleting = false;
	loadingState.startedAt = Date.now();

	// Validate input
	if (!list || list.length === 0) {
		console.warn("No loading sources provided");
		loadingState.startedAt = 0;
		return;
	}

	list.forEach((name) => {
		loadingState.sources[name] = 0;
	});

	loadingState.progress = 0;
	loadingState.active = true;
	startBootstrapLoading();
	setScopeMeta("bootstrap", {
		kind: "bootstrap",
		blocking: true,
		message: loadingState.message,
		progress: 0,
	});
}

/**
 * Sets the progress of a specific source.
 * @param name The source name
 * @param value Progress value (0-100)
 */
export function setSourceProgress(name: string, value: number): void {
	// Safety checks — with dev visibility so silent drops can be debugged.
	if (!(name in loadingState.sources)) {
		if (isDevBuild) {
			console.warn(
				`[loading] setSourceProgress ignored — unknown source "${name}". ` +
					`Known: [${Object.keys(loadingState.sources).join(", ") || "<none>"}]. ` +
					`Did initLoadingSources register it?`,
			);
		}
		return;
	}
	if (isCompleting || sourceCount === 0) {
		if (isDevBuild) {
			console.warn(
				`[loading] setSourceProgress ignored for "${name}" (value=${value}) — ` +
					`${isCompleting ? "loading already completing" : "no sources registered"}.`,
			);
		}
		return;
	}

	// Clamp value between 0 and 100 and prevent regressions
	const clampedValue = Math.max(0, Math.min(100, value));
	const oldValue = loadingState.sources[name] || 0;
	const newValue = Math.max(oldValue, clampedValue);

	loadingState.sources[name] = newValue;

	// Update message only if it changed
	const newMessage =
		loadingState.sourceMessages[name] || __(`Loading ${name}...`);
	if (loadingState.message !== newMessage) {
		loadingState.message = newMessage;
	}
	setScopeMeta("bootstrap", {
		message: loadingState.message,
		progress: loadingState.progress,
	});

	// Only update totals when progress increases
	if (newValue > oldValue) {
		completedSum += newValue - oldValue;
		const newProgress = Math.round(completedSum / sourceCount);

		// Only animate if progress actually changed
		if (newProgress !== loadingState.progress && newProgress <= 100) {
			animateProgress(loadingState.progress, newProgress);
		}

		if (newProgress >= 100 && !isCompleting) {
			completeLoading();
		}
	}
}

/**
 * Animates the progress bar from one value to another.
 */
function animateProgress(from: number, to: number): void {
	if (from === to) return;

	const startTime = performance.now();
	const duration = 300;

	function updateProgress(currentTime: number) {
		const elapsed = currentTime - startTime;
		const progress = Math.min(elapsed / duration, 1);

		// Use easing function for smoother animation
		const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
		loadingState.progress = Math.round(from + (to - from) * eased);

		if (progress < 1) {
			requestAnimationFrame(updateProgress);
		} else {
			loadingState.progress = to;
		}
		setScopeMeta("bootstrap", {
			message: loadingState.message,
			progress: loadingState.progress,
		});
	}

	requestAnimationFrame(updateProgress);
}

/**
 * Finalizes the loading process.
 */
function completeLoading(): void {
	// Prevent multiple completion calls
	if (isCompleting) return;
	isCompleting = true;

	loadingState.progress = 100;
	loadingState.message = __("Setup complete!");
	setScopeMeta("bootstrap", {
		message: loadingState.message,
		progress: 100,
	});

	// Brief completion phase, then show ready
	setTimeout(() => {
		if (!loadingState.active) return; // Check if still active
		loadingState.message = __("Ready!");
		setScopeMeta("bootstrap", {
			message: loadingState.message,
			progress: 100,
		});

		// Hide after showing ready message
		setTimeout(() => {
			loadingState.active = false;
			loadingState.message = __("Loading app data...");
			loadingState.startedAt = 0;
			stopBootstrapLoading();
			// Reset for next use
			sourceCount = 0;
			completedSum = 0;
			isCompleting = false;
		}, 600);
	}, 400);
}

/**
 * Marks a specific source as 100% loaded.
 */
export function markSourceLoaded(name: string): void {
	setSourceProgress(name, 100);
}

/**
 * Manually resets the loading state.
 */
export function resetLoadingState(): void {
	loadingState.active = false;
	loadingState.progress = 0;
	loadingState.message = __("Loading app data...");
	loadingState.sources = {};
	loadingState.startedAt = 0;
	sourceCount = 0;
	completedSum = 0;
	isCompleting = false;
	stopBootstrapLoading();
}

/**
 * Returns the elapsed ms since the current bootstrap run started, or 0
 * when no run is active.
 */
export function getBootstrapElapsedMs(): number {
	if (!loadingState.active || !loadingState.startedAt) return 0;
	return Math.max(0, Date.now() - loadingState.startedAt);
}

/**
 * Returns the sources that have not yet reported 100% while loading is still
 * active. Intended for the stall-diagnostic UI so operators can see *which*
 * source is holding up the splash screen.
 */
export function getStuckSources(): Array<{
	name: string;
	progress: number;
	message: string;
}> {
	if (!loadingState.active) return [];
	return Object.entries(loadingState.sources)
		.filter(([, progress]) => (progress ?? 0) < 100)
		.map(([name, progress]) => ({
			name,
			progress: progress ?? 0,
			message: loadingState.sourceMessages[name] || name,
		}));
}

/**
 * True when the bootstrap has been active for longer than STALL_THRESHOLD_MS
 * without reaching 100%. Pairs with `getStuckSources()` for UI reporting.
 */
export function isBootstrapStalled(): boolean {
	return getBootstrapElapsedMs() >= STALL_THRESHOLD_MS;
}

/**
 * Gets current loading status for debugging.
 */
export function getLoadingStatus() {
	return {
		active: loadingState.active,
		progress: loadingState.progress,
		sources: { ...loadingState.sources },
		sourceCount,
		completedSum,
		isCompleting,
		startedAt: loadingState.startedAt,
		elapsedMs: getBootstrapElapsedMs(),
		stuck: getStuckSources(),
	};
}
