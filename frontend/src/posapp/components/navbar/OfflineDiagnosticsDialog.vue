<template>
	<v-dialog v-model="dialogOpen" max-width="720" scrollable>
		<v-card class="diagnostics-card pos-themed-card">
			<v-card-title class="diagnostics-header pa-5">
				<div class="diagnostics-header__content">
					<div class="diagnostics-header__icon">
						<v-icon size="22">mdi-stethoscope</v-icon>
					</div>
					<div class="diagnostics-header__text">
						<h3 class="diagnostics-header__title">{{ __("Offline Diagnostics") }}</h3>
						<p class="diagnostics-header__subtitle">
							{{ __("Cache, sync, and pending-queue snapshot for this terminal") }}
						</p>
					</div>
				</div>
				<v-btn
					icon="mdi-close"
					variant="text"
					size="default"
					class="diagnostics-header__close"
					:aria-label="__('Close diagnostics')"
					@click="close"
				/>
			</v-card-title>

			<v-card-text class="pa-0 diagnostics-body">
				<!-- Connectivity strip -->
				<section class="diagnostics-section">
					<header class="diagnostics-section__header">
						<v-icon size="18">mdi-access-point-network</v-icon>
						<span>{{ __("Connectivity") }}</span>
					</header>
					<div class="diagnostics-grid diagnostics-grid--metric">
						<div class="diagnostics-metric">
							<div class="diagnostics-metric__label">{{ __("Network") }}</div>
							<div class="diagnostics-metric__value">
								<v-icon size="14" :color="networkOnline ? 'success' : 'error'">
									{{ networkOnline ? "mdi-check-circle" : "mdi-close-circle" }}
								</v-icon>
								{{ networkOnline ? __("Online") : __("Offline") }}
							</div>
						</div>
						<div class="diagnostics-metric">
							<div class="diagnostics-metric__label">{{ __("Server") }}</div>
							<div class="diagnostics-metric__value">
								<v-icon size="14" :color="serverOnline ? 'success' : 'error'">
									{{ serverOnline ? "mdi-server-network" : "mdi-server-network-off" }}
								</v-icon>
								{{ serverOnline ? __("Reachable") : __("Unreachable") }}
							</div>
						</div>
						<div class="diagnostics-metric">
							<div class="diagnostics-metric__label">{{ __("Manual mode") }}</div>
							<div class="diagnostics-metric__value">
								<v-icon size="14" :color="manualOffline ? 'warning' : 'success'">
									{{ manualOffline ? "mdi-airplane" : "mdi-airplane-off" }}
								</v-icon>
								{{ manualOffline ? __("Forced offline") : __("Auto") }}
							</div>
						</div>
						<div class="diagnostics-metric">
							<div class="diagnostics-metric__label">{{ __("Pending sales") }}</div>
							<div class="diagnostics-metric__value">
								<v-icon size="14" :color="pendingInvoicesCount > 0 ? 'warning' : 'success'">
									{{ pendingInvoicesCount > 0 ? "mdi-cloud-upload-outline" : "mdi-cloud-check-outline" }}
								</v-icon>
								{{ pendingInvoicesCount }}
							</div>
						</div>
					</div>
				</section>

				<v-divider />

				<!-- Cache breakdown -->
				<section class="diagnostics-section">
					<header class="diagnostics-section__header">
						<v-icon size="18">mdi-database-outline</v-icon>
						<span>{{ __("Cache usage") }}</span>
						<v-chip size="x-small" variant="tonal" :color="cacheUsageColor">
							{{ Math.round(cacheUsage || 0) }}%
						</v-chip>
					</header>
					<v-progress-linear
						:model-value="Math.round(cacheUsage || 0)"
						:color="cacheUsageColor"
						height="6"
						rounded
						class="diagnostics-section__bar"
					/>
					<div class="diagnostics-grid diagnostics-grid--metric">
						<div class="diagnostics-metric">
							<div class="diagnostics-metric__label">{{ __("Total stored") }}</div>
							<div class="diagnostics-metric__value">{{ formatBytes(cacheUsageDetails.total) }}</div>
						</div>
						<div class="diagnostics-metric">
							<div class="diagnostics-metric__label">IndexedDB</div>
							<div class="diagnostics-metric__value">
								{{ formatBytes(cacheUsageDetails.indexedDB) }}
							</div>
						</div>
						<div class="diagnostics-metric">
							<div class="diagnostics-metric__label">localStorage</div>
							<div class="diagnostics-metric__value">
								{{ formatBytes(cacheUsageDetails.localStorage) }}
							</div>
						</div>
					</div>
				</section>

				<v-divider />

				<!-- Last sync summary -->
				<section class="diagnostics-section">
					<header class="diagnostics-section__header">
						<v-icon size="18">mdi-sync</v-icon>
						<span>{{ __("Last sync run") }}</span>
					</header>
					<div v-if="lastSync" class="diagnostics-grid diagnostics-grid--metric">
						<div class="diagnostics-metric">
							<div class="diagnostics-metric__label">{{ __("Trigger") }}</div>
							<div class="diagnostics-metric__value">{{ lastSync.trigger || "—" }}</div>
						</div>
						<div class="diagnostics-metric">
							<div class="diagnostics-metric__label">{{ __("Succeeded") }}</div>
							<div class="diagnostics-metric__value diagnostics-metric__value--ok">
								{{ lastSync.succeeded ?? 0 }}
							</div>
						</div>
						<div class="diagnostics-metric">
							<div class="diagnostics-metric__label">{{ __("Failed") }}</div>
							<div
								class="diagnostics-metric__value"
								:class="(lastSync.failed || 0) > 0 ? 'diagnostics-metric__value--err' : ''"
							>
								{{ lastSync.failed ?? 0 }}
							</div>
						</div>
						<div class="diagnostics-metric">
							<div class="diagnostics-metric__label">{{ __("Skipped") }}</div>
							<div class="diagnostics-metric__value">{{ lastSync.skipped ?? 0 }}</div>
						</div>
					</div>
					<div v-else class="diagnostics-empty">
						{{ __("No sync trigger has run yet in this session.") }}
					</div>
				</section>

				<v-divider />

				<!-- Per-resource state -->
				<section class="diagnostics-section">
					<header class="diagnostics-section__header">
						<v-icon size="18">mdi-format-list-bulleted-square</v-icon>
						<span>{{ __("Resource sync state") }}</span>
						<v-chip
							v-if="attentionResources.length"
							size="x-small"
							variant="tonal"
							color="warning"
						>
							{{ attentionResources.length }} {{ __("need attention") }}
						</v-chip>
					</header>
					<div v-if="!sortedResources.length" class="diagnostics-empty">
						{{ __("No tracked resources yet — run a sync to populate this list.") }}
					</div>
					<table v-else class="diagnostics-table">
						<thead>
							<tr>
								<th>{{ __("Resource") }}</th>
								<th>{{ __("Status") }}</th>
								<th>{{ __("Last sync") }}</th>
								<th>{{ __("Last error") }}</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="resource in sortedResources" :key="resource.resourceId">
								<td>{{ resource.label || resource.resourceId }}</td>
								<td>
									<span class="diagnostics-status" :class="`diagnostics-status--${resource.status}`">
										{{ resource.status }}
									</span>
								</td>
								<td>{{ formatTimestamp(resource.lastSyncedAt) }}</td>
								<td class="diagnostics-table__error">
									{{ resource.lastError || "—" }}
								</td>
							</tr>
						</tbody>
					</table>
				</section>

				<v-divider v-if="bootstrapWarning?.active" />

				<!-- Bootstrap warnings -->
				<section v-if="bootstrapWarning?.active" class="diagnostics-section">
					<header class="diagnostics-section__header">
						<v-icon size="18" color="warning">mdi-alert-outline</v-icon>
						<span>{{ __("Bootstrap warnings") }}</span>
					</header>
					<div class="diagnostics-warning">
						<div class="diagnostics-warning__title">
							{{ bootstrapWarning.title }}
						</div>
						<ul v-if="bootstrapWarning.messages?.length" class="diagnostics-warning__messages">
							<li v-for="msg in bootstrapWarning.messages" :key="msg">{{ msg }}</li>
						</ul>
					</div>
				</section>
			</v-card-text>

			<v-card-actions class="diagnostics-actions pa-4">
				<v-btn
					variant="text"
					size="small"
					prepend-icon="mdi-refresh"
					@click="$emit('refresh-cache-usage')"
				>
					{{ __("Refresh cache usage") }}
				</v-btn>
				<v-spacer />
				<v-btn color="primary" @click="close">{{ __("Close") }}</v-btn>
			</v-card-actions>
		</v-card>
	</v-dialog>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { storeToRefs } from "pinia";
import { useOfflineSyncStore } from "../../stores/offlineSyncStore";

defineOptions({ name: "OfflineDiagnosticsDialog" });

const __ = window.__ || ((value) => value);

const props = defineProps({
	modelValue: { type: Boolean, default: false },
	cacheUsage: { type: Number, default: 0 },
	cacheUsageDetails: {
		type: Object,
		default: () => ({ total: 0, indexedDB: 0, localStorage: 0 }),
	},
	pendingInvoicesCount: { type: Number, default: 0 },
	networkOnline: { type: Boolean, default: false },
	serverOnline: { type: Boolean, default: false },
	manualOffline: { type: Boolean, default: false },
	lastSync: { type: Object, default: null },
});

const emit = defineEmits(["update:modelValue", "refresh-cache-usage"]);

const dialogOpen = ref(props.modelValue);
watch(
	() => props.modelValue,
	(val) => {
		dialogOpen.value = val;
	},
);
watch(dialogOpen, (val) => emit("update:modelValue", val));

const offlineSyncStore = useOfflineSyncStore();
const { bootstrapWarning, sortedResources, attentionResources } = storeToRefs(offlineSyncStore);

const cacheUsageColor = computed(() => {
	const pct = Math.round(props.cacheUsage || 0);
	if (pct >= 85) return "error";
	if (pct >= 60) return "warning";
	return "primary";
});

function close() {
	dialogOpen.value = false;
}

function formatBytes(bytes) {
	const value = Number(bytes);
	if (!Number.isFinite(value) || value <= 0) return "—";
	if (value < 1024) return `${value.toFixed(0)} B`;
	if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
	if (value < 1024 * 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
	return `${(value / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function formatTimestamp(ts) {
	if (!ts) return "—";
	try {
		return new Date(ts).toLocaleString();
	} catch {
		return String(ts);
	}
}
</script>

<style scoped>
.diagnostics-card {
	border-radius: 16px !important;
	overflow: hidden;
	background: var(--pos-card-bg);
	color: var(--pos-text-primary);
	box-shadow: 0 4px 20px var(--pos-shadow) !important;
	max-height: 90vh;
}

.diagnostics-header {
	background: var(--pos-card-bg);
	color: var(--pos-text-primary);
	border-bottom: 1px solid var(--pos-border);
	position: relative;
	min-height: auto !important;
}

.diagnostics-header::before {
	content: "";
	position: absolute;
	top: 0;
	left: 0;
	right: 0;
	height: 3px;
	background: linear-gradient(90deg, #f46a25 0%, #ffb380 100%);
}

.diagnostics-header__content {
	display: flex;
	align-items: center;
	gap: 16px;
	padding-right: 60px;
}

.diagnostics-header__icon {
	background: linear-gradient(135deg, #f46a25 0%, #c75418 100%);
	border-radius: 14px;
	width: 44px;
	height: 44px;
	display: flex;
	align-items: center;
	justify-content: center;
	color: #fff;
	flex-shrink: 0;
}

.diagnostics-header__title {
	font-size: 1.1rem;
	font-weight: 700;
	margin: 0;
	color: var(--pos-text-primary);
}

.diagnostics-header__subtitle {
	font-size: 0.78rem;
	margin: 2px 0 0;
	color: var(--pos-text-secondary);
}

.diagnostics-header__close {
	position: absolute;
	top: 12px;
	right: 12px;
}

.diagnostics-body {
	background: var(--pos-bg-secondary, var(--pos-card-bg));
}

.diagnostics-section {
	padding: 16px 20px;
}

.diagnostics-section__header {
	display: flex;
	align-items: center;
	gap: 8px;
	font-weight: 700;
	font-size: 0.82rem;
	letter-spacing: 0.02em;
	text-transform: uppercase;
	color: var(--pos-text-secondary);
	margin-bottom: 10px;
}

.diagnostics-section__bar {
	margin-bottom: 12px;
}

.diagnostics-grid {
	display: grid;
	gap: 10px 16px;
}

.diagnostics-grid--metric {
	grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
}

.diagnostics-metric {
	background: var(--pos-surface, rgba(148, 163, 184, 0.08));
	border: 1px solid var(--pos-border);
	border-radius: 10px;
	padding: 8px 12px;
}

.diagnostics-metric__label {
	font-size: 0.7rem;
	font-weight: 600;
	color: var(--pos-text-secondary);
	text-transform: uppercase;
	letter-spacing: 0.04em;
}

.diagnostics-metric__value {
	display: flex;
	align-items: center;
	gap: 6px;
	font-size: 0.92rem;
	font-weight: 700;
	color: var(--pos-text-primary);
	margin-top: 2px;
}

.diagnostics-metric__value--ok {
	color: #22c55e;
}

.diagnostics-metric__value--err {
	color: #ef4444;
}

.diagnostics-empty {
	font-size: 0.82rem;
	color: var(--pos-text-secondary);
	font-style: italic;
}

.diagnostics-table {
	width: 100%;
	border-collapse: collapse;
	font-size: 0.82rem;
}

.diagnostics-table th,
.diagnostics-table td {
	text-align: left;
	padding: 6px 8px;
	border-bottom: 1px solid var(--pos-border);
	color: var(--pos-text-primary);
}

.diagnostics-table th {
	font-weight: 700;
	font-size: 0.72rem;
	text-transform: uppercase;
	letter-spacing: 0.03em;
	color: var(--pos-text-secondary);
}

.diagnostics-table__error {
	color: var(--pos-text-secondary);
	max-width: 220px;
	word-break: break-word;
}

.diagnostics-status {
	display: inline-block;
	padding: 2px 8px;
	border-radius: 999px;
	font-size: 0.7rem;
	font-weight: 700;
	text-transform: uppercase;
	background: rgba(148, 163, 184, 0.18);
	color: var(--pos-text-secondary);
}

.diagnostics-status--ready,
.diagnostics-status--idle {
	background: rgba(34, 197, 94, 0.16);
	color: #22c55e;
}

.diagnostics-status--syncing {
	background: rgba(59, 130, 246, 0.16);
	color: #3b82f6;
}

.diagnostics-status--stale,
.diagnostics-status--limited {
	background: rgba(244, 158, 11, 0.18);
	color: #f59e0b;
}

.diagnostics-status--error {
	background: rgba(239, 68, 68, 0.18);
	color: #ef4444;
}

.diagnostics-warning {
	border: 1px solid rgba(244, 158, 11, 0.32);
	background: rgba(244, 158, 11, 0.08);
	border-radius: 10px;
	padding: 10px 14px;
}

.diagnostics-warning__title {
	font-weight: 700;
	color: var(--pos-text-primary);
	margin-bottom: 6px;
}

.diagnostics-warning__messages {
	margin: 0;
	padding-left: 18px;
	font-size: 0.82rem;
	color: var(--pos-text-secondary);
}

.diagnostics-actions {
	border-top: 1px solid var(--pos-border);
	background: var(--pos-card-bg);
}
</style>
