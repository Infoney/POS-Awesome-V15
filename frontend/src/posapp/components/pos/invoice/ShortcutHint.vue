<template>
	<span class="shortcut-hint" :class="`shortcut-hint--${tone}`" aria-hidden="true">
		<template v-for="(token, idx) in tokens" :key="idx">
			<kbd v-if="!isSeparator(token)" class="shortcut-hint__key">{{ token }}</kbd>
			<span v-else class="shortcut-hint__sep">{{ token }}</span>
		</template>
	</span>
</template>

<script setup lang="ts">
import { computed } from "vue";

interface Props {
	combo: string;
	tone?: "default" | "light";
}

const props = withDefaults(defineProps<Props>(), {
	tone: "default",
});

// Split "Alt+S" → ["Alt", "+", "S"], preserving "+" as a visual separator.
const tokens = computed(() => {
	const parts = props.combo.split(/(\+)/).filter((p) => p.length > 0);
	return parts;
});

const isSeparator = (token: string) => token === "+";
</script>

<style scoped>
.shortcut-hint {
	display: inline-flex;
	align-items: center;
	gap: 1px;
	margin-inline-start: 8px;
	font-family:
		ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
	font-size: 0.62rem;
	line-height: 1;
	user-select: none;
	pointer-events: none;
	opacity: 0.85;
}

.shortcut-hint__key {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	min-width: 16px;
	padding: 1px 4px;
	border-radius: 4px;
	background: rgba(255, 255, 255, 0.18);
	border: 1px solid rgba(255, 255, 255, 0.3);
	font-weight: 700;
	font-family: inherit;
	font-size: inherit;
	letter-spacing: 0.02em;
	color: inherit;
}

.shortcut-hint--light .shortcut-hint__key {
	background: rgba(0, 0, 0, 0.12);
	border-color: rgba(255, 255, 255, 0.45);
}

.shortcut-hint__sep {
	opacity: 0.55;
	font-weight: 700;
	margin: 0 1px;
}

@media (max-width: 640px) {
	.shortcut-hint {
		display: none;
	}
}
</style>
