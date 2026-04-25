<template>
	<div class="notification-bell-btn">
		<v-menu v-model="open" :close-on-content-click="false" offset="[0, 8]" location="bottom end">
			<template #activator="{ props }">
				<v-btn
					v-bind="props"
					icon
					variant="elevated"
					size="small"
					class="pos-themed-button notification-bell-trigger"
					:aria-label="__('View notifications') + (unreadCount ? ` (${unreadCount})` : '')"
				>
					<v-badge
						:model-value="unreadCount > 0"
						:content="unreadCount"
						color="error"
						floating
						v-if="notifications.length"
					>
						<v-icon class="pos-text-primary">mdi-bell-outline</v-icon>
					</v-badge>
					<v-icon v-else class="pos-text-primary">mdi-bell-outline</v-icon>
				</v-btn>
			</template>

			<v-card class="pos-themed-card notification-card" elevation="12">
				<div class="notification-card__header">
					<div class="header-text">
						<div class="notification-heading">{{ __("Notifications") }}</div>
						<div class="subtitle">
							{{
								notifications.length
									? __("Recent updates about your invoices")
									: __("You have no notifications right now")
							}}
						</div>
					</div>
					<v-btn
						v-if="notifications.length"
						variant="text"
						size="small"
						class="clear-btn"
						@click="clearAll"
					>
						<v-icon start size="16">mdi-broom</v-icon>
						{{ __("Clear All") }}
					</v-btn>
				</div>

				<v-divider></v-divider>

				<div class="notification-list">
					<div v-if="!notifications.length" class="empty-state">
						<v-icon size="36" class="empty-icon">mdi-bell-off-outline</v-icon>
						<div class="empty-title">{{ __("No notifications yet") }}</div>
						<div class="empty-subtitle">
							{{ __("We'll let you know if an invoice fails to submit") }}
						</div>
					</div>
					<v-list v-else density="compact" class="notification-items">
						<v-list-item v-for="item in notifications" :key="item.id" class="notification-item">
							<template #prepend>
								<div class="notification-icon" :class="item.color || 'error'">
									<v-icon size="18">mdi-bell-alert-outline</v-icon>
								</div>
							</template>
							<div class="notification-content">
								<div class="notification-title">{{ item.title }}</div>
								<div v-if="item.detail" class="notification-detail">
									{{ item.detail }}
								</div>
								<div class="notification-time">{{ formatTimestamp(item.timestamp) }}</div>
							</div>
						</v-list-item>
					</v-list>
				</div>
			</v-card>
		</v-menu>
	</div>
</template>

<script setup lang="ts">
import { ref, toRefs, watch } from "vue";

defineOptions({
	name: "NotificationBell",
});

interface NotificationItem {
	id: string | number;
	title: string;
	detail?: string;
	timestamp: string | number | Date;
	color?: string;
}

interface Props {
	notifications?: NotificationItem[];
	unreadCount?: number;
}

const props = withDefaults(defineProps<Props>(), {
	notifications: () => [],
	unreadCount: 0,
});
const { notifications, unreadCount } = toRefs(props);

const emit = defineEmits<{
	(_event: "mark-read"): void;
	(_event: "clear"): void;
}>();

// @ts-ignore
const __ = (window as any).__ || ((text: string) => text);
const open = ref(false);

watch(open, (value) => {
	if (value) {
		emit("mark-read");
	}
});

function clearAll() {
	emit("clear");
}

function formatTimestamp(ts: string | number | Date) {
	if (!ts) {
		return "";
	}
	try {
		const date = new Date(ts);
		return date.toLocaleString();
	} catch {
		return String(ts);
	}
}
</script>

<style scoped>
.notification-bell-btn {
	display: flex;
	align-items: center;
}

.notification-bell-trigger {
	box-shadow: 0 4px 12px var(--pos-shadow, rgba(0, 0, 0, 0.18)) !important;
}

/* Solid opaque card so the dropdown is readable over whatever sits
   behind it (the previous translucent surface bled the page through —
   user flagged it as "fix notification visuals"). The CC theme tokens
   are used so the popup stays on-brand in both light and dark modes. */
.notification-card {
	min-width: 360px;
	max-width: 420px;
	background: var(--pos-popover-bg, #161c27) !important;
	border: 1px solid rgba(255, 255, 255, 0.06);
	border-radius: 16px !important;
	box-shadow:
		0 24px 48px rgba(0, 0, 0, 0.55),
		0 4px 12px rgba(0, 0, 0, 0.32),
		0 0 0 1px rgba(244, 106, 37, 0.06) !important;
	overflow: hidden;
}

.notification-card__header {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 12px;
	padding: 14px 16px 12px;
	background: linear-gradient(
		180deg,
		rgba(244, 106, 37, 0.08) 0%,
		rgba(244, 106, 37, 0) 100%
	);
}

.header-text .notification-heading {
	font-weight: 700;
	font-size: 1rem;
	color: var(--pos-text-primary, #edf2f7);
	letter-spacing: -0.01em;
}

.header-text .subtitle {
	font-size: 0.78rem;
	color: var(--pos-text-secondary, #7b899d);
	margin-top: 2px;
}

.clear-btn {
	text-transform: none;
	font-weight: 600;
	border-radius: 10px;
	color: var(--cc-orange, #f46a25) !important;
	background: rgba(244, 106, 37, 0.08) !important;
	border: 1px solid rgba(244, 106, 37, 0.18);
	padding: 0 10px !important;
	min-width: auto !important;
	height: 30px !important;
	font-size: 0.76rem !important;
	letter-spacing: 0;
}

.clear-btn:hover {
	background: rgba(244, 106, 37, 0.16) !important;
	border-color: rgba(244, 106, 37, 0.32);
}

.notification-list {
	max-height: 360px;
	overflow-y: auto;
}

.notification-items {
	padding: 0;
	background: transparent !important;
}

.notification-item {
	border-bottom: 1px solid rgba(255, 255, 255, 0.04);
	padding: 10px 16px !important;
	min-height: auto !important;
	transition: background-color 0.18s ease;
}

/* Vuetify's compact v-list-item collapses the prepend slot's
   margin-inline-end to ~8 px which left the bell badge crowding the
   "Invoice Submitted" title. Bump the gap so the badge breathes. */
.notification-item :deep(.v-list-item__prepend) {
	margin-inline-end: 14px !important;
}

/* And give the prepend wrapper a guaranteed inline gap regardless of
   how Vuetify versions tweak the slot internals. */
.notification-item :deep(.v-list-item__spacer) {
	width: 14px !important;
}

.notification-item:hover {
	background: rgba(255, 255, 255, 0.025);
}

.notification-item:last-child {
	border-bottom: none;
}

/* Icon badge — softer red gradient with inset highlight so it doesn't
   read as a "danger" pure-red marker. Matches the CC chip aesthetic. */
.notification-icon {
	width: 32px;
	height: 32px;
	border-radius: 10px;
	display: flex;
	align-items: center;
	justify-content: center;
	color: white;
	flex-shrink: 0;
	box-shadow:
		inset 0 1px 0 rgba(255, 255, 255, 0.15),
		0 4px 10px rgba(0, 0, 0, 0.25);
}

.notification-icon.error {
	background: linear-gradient(135deg, #ef4444 0%, #b91c1c 100%);
	box-shadow:
		inset 0 1px 0 rgba(255, 255, 255, 0.18),
		0 4px 10px rgba(220, 38, 38, 0.32);
}

.notification-icon.warning {
	background: linear-gradient(135deg, #f97316 0%, #c2410c 100%);
	box-shadow:
		inset 0 1px 0 rgba(255, 255, 255, 0.18),
		0 4px 10px rgba(244, 106, 37, 0.32);
}

.notification-icon.info {
	background: linear-gradient(135deg, #60a5fa 0%, #2563eb 100%);
	box-shadow:
		inset 0 1px 0 rgba(255, 255, 255, 0.18),
		0 4px 10px rgba(37, 99, 235, 0.32);
}

.notification-icon.success {
	background: linear-gradient(135deg, #22c55e 0%, #15803d 100%);
	box-shadow:
		inset 0 1px 0 rgba(255, 255, 255, 0.18),
		0 4px 10px rgba(34, 197, 94, 0.32);
}

.notification-content {
	display: flex;
	flex-direction: column;
	gap: 2px;
	min-width: 0;
}

.notification-title {
	font-weight: 600;
	font-size: 0.84rem;
	line-height: 1.3;
	color: var(--pos-text-primary, #edf2f7);
}

.notification-detail {
	font-size: 0.78rem;
	color: var(--pos-text-secondary, #7b899d);
	white-space: pre-wrap;
	line-height: 1.4;
}

.notification-time {
	font-size: 0.7rem;
	color: var(--cc-subtle, #4a5568);
	font-weight: 500;
	margin-top: 2px;
	letter-spacing: 0.01em;
}

.empty-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 32px 16px;
	text-align: center;
	color: var(--pos-text-secondary, #7b899d);
	gap: 4px;
}

.empty-icon {
	color: var(--cc-muted, #7b899d);
	margin-bottom: 8px;
	opacity: 0.6;
}

.empty-title {
	font-weight: 700;
	color: var(--pos-text-primary, #edf2f7);
	margin-bottom: 4px;
	font-size: 0.92rem;
}

.empty-subtitle {
	font-size: 0.8rem;
	line-height: 1.4;
}

/* Light-theme override — keep the popup readable on the light palette. */
:global(.v-theme--light) .notification-card,
:global(:root:not(.v-theme--dark)) .notification-card {
	background: #ffffff !important;
	border-color: rgba(15, 23, 42, 0.08);
	box-shadow:
		0 24px 48px rgba(15, 23, 42, 0.18),
		0 4px 12px rgba(15, 23, 42, 0.08) !important;
}

:global(.v-theme--light) .notification-item,
:global(:root:not(.v-theme--dark)) .notification-item {
	border-bottom-color: rgba(15, 23, 42, 0.06);
}
</style>
