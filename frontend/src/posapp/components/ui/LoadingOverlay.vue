<template>
	<transition name="fade">
		<div v-if="isVisible" class="loading-overlay" role="status" aria-live="polite">
			<div class="spinner" :class="{ reduce: prefersReduced }"></div>
			<p v-if="message" class="message">{{ message }}</p>

			<!-- Stall diagnostic — surfaces after STALL_THRESHOLD_MS so operators
			     know *why* the splash won't go away. Hidden on fast boots. -->
			<div v-if="showStallDiagnostic" class="stall-panel">
				<p class="stall-panel__title">
					{{ __("Still loading after {0}s — something is stuck.", [elapsedSeconds]) }}
				</p>
				<ul class="stall-panel__list">
					<li v-for="src in stuckSources" :key="src.name">
						<span class="stall-panel__name">{{ src.message }}</span>
						<span class="stall-panel__progress">{{ src.progress }}%</span>
					</li>
				</ul>
				<div class="stall-panel__actions">
					<button type="button" class="stall-panel__button" @click="reloadApp">
						{{ __("Reload app") }}
					</button>
				</div>
			</div>
		</div>
	</transition>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from "vue";
import { useLoading } from "../../composables/core/useLoading";
import {
	getStuckSources,
	loadingState,
	resetLoadingState,
	STALL_THRESHOLD_MS,
} from "../../utils/loading";

defineOptions({
	name: "LoadingOverlay",
});

interface Props {
	visible?: boolean;
	message?: string;
}

const props = withDefaults(defineProps<Props>(), {
	message: "",
});

const __ = (window as any).__ || ((s: string, args: any[] = []) => {
	if (!Array.isArray(args) || !args.length) return s;
	return s.replace(/\{(\d+)\}/g, (_match, idx) => String(args[Number(idx)] ?? ""));
});

const { overlayVisible } = useLoading();
const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const isVisible = computed(() =>
	props.visible !== undefined ? props.visible : overlayVisible.value,
);

// Elapsed-time ticker — only runs while the overlay is visible so we don't
// keep a timer burning in the background after bootstrap succeeds.
const nowTick = ref(Date.now());
let tickerId: ReturnType<typeof setInterval> | null = null;

const startTicker = () => {
	if (tickerId !== null) return;
	nowTick.value = Date.now();
	tickerId = setInterval(() => {
		nowTick.value = Date.now();
	}, 1000);
};

const stopTicker = () => {
	if (tickerId !== null) {
		clearInterval(tickerId);
		tickerId = null;
	}
};

onMounted(() => {
	if (isVisible.value) startTicker();
});

onBeforeUnmount(() => {
	stopTicker();
});

watch(isVisible, (v) => (v ? startTicker() : stopTicker()));

const elapsedMs = computed(() => {
	if (!loadingState.startedAt) return 0;
	return Math.max(0, nowTick.value - loadingState.startedAt);
});

const elapsedSeconds = computed(() => Math.round(elapsedMs.value / 1000));

const stuckSources = computed(() => getStuckSources());

const showStallDiagnostic = computed(
	() =>
		isVisible.value &&
		loadingState.active &&
		elapsedMs.value >= STALL_THRESHOLD_MS &&
		stuckSources.value.length > 0,
);

const reloadApp = () => {
	try {
		resetLoadingState();
	} finally {
		// Hard reload so the service worker picks up any new bundle.
		window.location.reload();
	}
};
</script>

<style scoped>
.loading-overlay {
	position: fixed;
	inset: 0;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	gap: 12px;
	background: var(--overlay-bg, rgba(0, 0, 0, 0.4));
	pointer-events: all;
	z-index: 2000;
	padding: 20px;
}
.spinner {
	width: 48px;
	height: 48px;
	border: 4px solid var(--spinner-fg, #fff);
	border-bottom-color: transparent;
	border-radius: 50%;
	animation: spin var(--loading-duration, 0.6s) linear infinite;
}
.spinner.reduce {
	animation-duration: 0.001s;
	animation-iteration-count: 1;
}
@keyframes spin {
	from {
		transform: rotate(0deg);
	}
	to {
		transform: rotate(360deg);
	}
}
.fade-enter-active,
.fade-leave-active {
	transition: opacity 0.2s ease;
}
.fade-enter-from,
.fade-leave-to {
	opacity: 0;
}
.message {
	margin: 0;
	color: var(--spinner-fg, #fff);
}

.stall-panel {
	max-width: 380px;
	width: 100%;
	margin-top: 8px;
	padding: 14px 18px;
	background: rgba(255, 255, 255, 0.08);
	border: 1px solid rgba(255, 255, 255, 0.18);
	border-radius: 12px;
	color: var(--spinner-fg, #fff);
	backdrop-filter: blur(6px);
	box-shadow: 0 12px 30px rgba(0, 0, 0, 0.35);
}

.stall-panel__title {
	margin: 0 0 8px;
	font-size: 0.9rem;
	font-weight: 600;
}

.stall-panel__list {
	list-style: none;
	padding: 0;
	margin: 0 0 10px;
	display: flex;
	flex-direction: column;
	gap: 4px;
	font-size: 0.82rem;
}

.stall-panel__list li {
	display: flex;
	justify-content: space-between;
	gap: 12px;
}

.stall-panel__name {
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.stall-panel__progress {
	font-variant-numeric: tabular-nums;
	opacity: 0.8;
	flex-shrink: 0;
}

.stall-panel__actions {
	display: flex;
	justify-content: flex-end;
}

.stall-panel__button {
	padding: 6px 14px;
	border-radius: 8px;
	font-size: 0.82rem;
	font-weight: 600;
	color: #1f2937;
	background: #fff;
	border: none;
	cursor: pointer;
	transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.stall-panel__button:hover {
	transform: translateY(-1px);
	box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
}

.stall-panel__button:active {
	transform: translateY(0);
}
</style>
