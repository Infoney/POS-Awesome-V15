<template>
	<transition name="repop-fade">
		<div
			v-if="visible"
			class="repop-indicator"
			:class="{ 'repop-indicator--done': stageState.overall === 'done', 'repop-indicator--error': stageState.overall === 'error' }"
			role="status"
			aria-live="polite"
		>
			<div class="repop-indicator__header">
				<span class="repop-indicator__pulse" :class="{ 'repop-indicator__pulse--done': stageState.overall === 'done' }"></span>
				<span class="repop-indicator__title">{{ headerText }}</span>
				<span v-if="profileLabel" class="repop-indicator__profile">{{ profileLabel }}</span>
			</div>

			<ul class="repop-indicator__rows">
				<li
					v-for="row in rows"
					:key="row.key"
					class="repop-indicator__row"
					:class="`repop-indicator__row--${row.status}`"
				>
					<span class="repop-indicator__icon" aria-hidden="true">
						<template v-if="row.status === 'done'">&#10003;</template>
						<template v-else-if="row.status === 'error'">!</template>
						<template v-else-if="row.status === 'pending'">&#9679;</template>
						<template v-else><span class="repop-indicator__spinner"></span></template>
					</span>
					<span class="repop-indicator__row-name">{{ row.label }}</span>
					<span class="repop-indicator__row-progress">{{ row.progress }}%</span>
					<span class="repop-indicator__bar">
						<span
							class="repop-indicator__bar-fill"
							:style="{ width: row.progress + '%' }"
						></span>
					</span>
					<span v-if="row.message" class="repop-indicator__row-message">{{ row.message }}</span>
				</li>
			</ul>
		</div>
	</transition>
</template>

<script setup lang="ts">
import { computed, inject, onBeforeUnmount, onMounted, reactive, ref } from "vue";

defineOptions({
	name: "ProfileRepopulateIndicator",
});

type EventBus = {
	on: (event: string, handler: (payload: any) => void) => void;
	off?: (event: string, handler: (payload: any) => void) => void;
	emit?: (event: string, payload?: any) => void;
};

type RowKey = "items" | "stock" | "batches";
type RowStatus = "pending" | "loading" | "done" | "error";

interface Row {
	key: RowKey;
	label: string;
	progress: number;
	status: RowStatus;
	message: string;
}

const __ = (window as any).__ || ((s: string) => s);

const eventBus = inject<EventBus | null>("eventBus", null);
const visible = ref(false);
const profileLabel = ref<string | null>(null);

const stageState = reactive({
	overall: "idle" as "idle" | "running" | "done" | "error",
});

const rows = reactive<Row[]>([
	{ key: "items", label: __("Items"), progress: 0, status: "pending", message: "" },
	{ key: "batches", label: __("Batches"), progress: 0, status: "pending", message: "" },
	{ key: "stock", label: __("Stock balances"), progress: 0, status: "pending", message: "" },
]);

const headerText = computed(() => {
	if (stageState.overall === "done") return __("Profile ready");
	if (stageState.overall === "error") return __("Profile refresh failed");
	return __("Refreshing profile data");
});

const resetRows = () => {
	rows.forEach((r) => {
		r.progress = 0;
		r.status = "pending";
		r.message = "";
	});
};

let hideTimer: ReturnType<typeof setTimeout> | null = null;

const scheduleHide = (delay = 1500) => {
	if (hideTimer !== null) {
		clearTimeout(hideTimer);
	}
	hideTimer = setTimeout(() => {
		visible.value = false;
		stageState.overall = "idle";
		profileLabel.value = null;
		resetRows();
		hideTimer = null;
	}, delay);
};

const cancelHide = () => {
	if (hideTimer !== null) {
		clearTimeout(hideTimer);
		hideTimer = null;
	}
};

const handleProgress = (payload: any) => {
	if (!payload) return;
	cancelHide();

	const stage: string = payload.stage;
	const progress: number = Math.max(0, Math.min(100, Number(payload.progress) || 0));
	const message: string = payload.message || "";
	profileLabel.value = payload.profile || profileLabel.value;

	if (stage === "start") {
		visible.value = true;
		stageState.overall = "running";
		resetRows();
		return;
	}

	if (stage === "done") {
		stageState.overall = "done";
		rows.forEach((r) => {
			r.progress = 100;
			r.status = "done";
		});
		scheduleHide(1200);
		return;
	}

	if (stage === "error") {
		stageState.overall = "error";
		rows.forEach((r) => {
			if (r.status !== "done") {
				r.status = "error";
				if (!r.message) r.message = message;
			}
		});
		scheduleHide(3500);
		return;
	}

	const row = rows.find((r) => r.key === stage);
	if (!row) return;

	visible.value = true;
	if (stageState.overall === "idle") stageState.overall = "running";

	row.progress = progress;
	row.message = message;
	if (progress >= 100) {
		row.status = "done";
	} else if (progress > 0) {
		row.status = "loading";
	}
};

onMounted(() => {
	if (eventBus && typeof eventBus.on === "function") {
		eventBus.on("profile_repopulate_progress", handleProgress);
	}
});

onBeforeUnmount(() => {
	cancelHide();
	if (eventBus && typeof eventBus.off === "function") {
		eventBus.off("profile_repopulate_progress", handleProgress);
	}
});
</script>

<style scoped>
.repop-indicator {
	position: fixed;
	right: 24px;
	bottom: 24px;
	z-index: 1900;
	min-width: 320px;
	max-width: 380px;
	padding: 14px 16px 12px;
	background: rgba(20, 14, 38, 0.92);
	border: 1px solid rgba(167, 139, 250, 0.35);
	border-radius: 14px;
	color: #f5f3ff;
	backdrop-filter: blur(8px);
	-webkit-backdrop-filter: blur(8px);
	box-shadow: 0 18px 40px rgba(15, 8, 32, 0.55), 0 0 0 1px rgba(236, 72, 153, 0.08);
	font-size: 0.85rem;
	pointer-events: none;
}

.repop-indicator--done {
	border-color: rgba(74, 222, 128, 0.45);
	box-shadow: 0 18px 40px rgba(15, 8, 32, 0.55), 0 0 0 1px rgba(74, 222, 128, 0.12);
}

.repop-indicator--error {
	border-color: rgba(248, 113, 113, 0.55);
	box-shadow: 0 18px 40px rgba(15, 8, 32, 0.55), 0 0 0 1px rgba(248, 113, 113, 0.18);
}

.repop-indicator__header {
	display: flex;
	align-items: center;
	gap: 8px;
	margin-bottom: 10px;
}

.repop-indicator__pulse {
	width: 8px;
	height: 8px;
	border-radius: 50%;
	background: linear-gradient(135deg, #a78bfa, #ec4899);
	box-shadow: 0 0 0 0 rgba(167, 139, 250, 0.45);
	animation: repop-pulse 1.6s ease-out infinite;
	flex-shrink: 0;
}

.repop-indicator__pulse--done {
	background: #4ade80;
	animation: none;
	box-shadow: 0 0 6px rgba(74, 222, 128, 0.6);
}

@keyframes repop-pulse {
	0% {
		box-shadow: 0 0 0 0 rgba(167, 139, 250, 0.55);
	}
	70% {
		box-shadow: 0 0 0 10px rgba(167, 139, 250, 0);
	}
	100% {
		box-shadow: 0 0 0 0 rgba(167, 139, 250, 0);
	}
}

.repop-indicator__title {
	font-weight: 600;
	font-size: 0.9rem;
	letter-spacing: 0.01em;
}

.repop-indicator__profile {
	margin-left: auto;
	font-size: 0.75rem;
	color: rgba(245, 243, 255, 0.65);
	max-width: 140px;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.repop-indicator__rows {
	list-style: none;
	margin: 0;
	padding: 0;
	display: flex;
	flex-direction: column;
	gap: 8px;
}

.repop-indicator__row {
	display: grid;
	grid-template-columns: 18px 1fr auto;
	grid-template-rows: auto auto;
	column-gap: 10px;
	row-gap: 4px;
	align-items: center;
}

.repop-indicator__icon {
	grid-row: 1 / 2;
	grid-column: 1 / 2;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	width: 18px;
	height: 18px;
	border-radius: 50%;
	font-size: 0.7rem;
	color: #f5f3ff;
	background: rgba(255, 255, 255, 0.08);
}

.repop-indicator__row--done .repop-indicator__icon {
	background: rgba(74, 222, 128, 0.22);
	color: #bbf7d0;
}

.repop-indicator__row--error .repop-indicator__icon {
	background: rgba(248, 113, 113, 0.22);
	color: #fecaca;
}

.repop-indicator__row--loading .repop-indicator__icon {
	background: rgba(167, 139, 250, 0.18);
}

.repop-indicator__spinner {
	width: 10px;
	height: 10px;
	border: 2px solid rgba(245, 243, 255, 0.35);
	border-top-color: #ec4899;
	border-radius: 50%;
	animation: repop-spin 0.8s linear infinite;
}

@keyframes repop-spin {
	to {
		transform: rotate(360deg);
	}
}

.repop-indicator__row-name {
	grid-row: 1 / 2;
	grid-column: 2 / 3;
	font-weight: 500;
	color: #f5f3ff;
}

.repop-indicator__row-progress {
	grid-row: 1 / 2;
	grid-column: 3 / 4;
	font-variant-numeric: tabular-nums;
	font-size: 0.78rem;
	color: rgba(245, 243, 255, 0.7);
}

.repop-indicator__bar {
	grid-row: 2 / 3;
	grid-column: 1 / 4;
	display: block;
	height: 4px;
	border-radius: 999px;
	background: rgba(255, 255, 255, 0.08);
	overflow: hidden;
}

.repop-indicator__bar-fill {
	display: block;
	height: 100%;
	background: linear-gradient(90deg, #a78bfa, #ec4899);
	border-radius: 999px;
	transition: width 0.35s ease;
}

.repop-indicator__row--done .repop-indicator__bar-fill {
	background: linear-gradient(90deg, #34d399, #4ade80);
}

.repop-indicator__row--error .repop-indicator__bar-fill {
	background: linear-gradient(90deg, #f87171, #fb7185);
}

.repop-indicator__row-message {
	grid-row: 2 / 3;
	grid-column: 2 / 4;
	font-size: 0.72rem;
	color: rgba(245, 243, 255, 0.55);
	margin-top: 2px;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.repop-fade-enter-active,
.repop-fade-leave-active {
	transition: opacity 0.25s ease, transform 0.25s ease;
}

.repop-fade-enter-from,
.repop-fade-leave-to {
	opacity: 0;
	transform: translateY(8px);
}
</style>
