/**
 * useCashierLabel — single source of truth for the configurable
 * "Cashier" label.
 *
 * Why this exists
 * ---------------
 * The literal "Cashier" wording isn't right for every POSAwesome
 * deployment. A pharmacy wants "Pharmacist", a service shop wants
 * "Engineer", a B2B counter wants "Sales Person", etc. We expose a
 * `posa_cashier_label` Data field on POS Profile (default "Cashier",
 * translatable) and read it through this composable so every UI
 * surface — chip labels, dialog titles, dashboard headings, the
 * closing-shift print receipt — picks up the override automatically.
 *
 * Output
 * ------
 *   const { cashierLabel, cashierLabelPlural, cashierPossessive,
 *           t } = useCashierLabel();
 *
 *   {{ cashierLabel }}                       // "Cashier" / "Pharmacist" / …
 *   {{ cashierLabelPlural }}                 // naive plural — see note
 *   {{ t('Switch') }} {{ cashierLabel }}     // → "Switch Pharmacist"
 *
 * The `t` helper is just a thin wrapper around the existing global
 * `__()` translator so callers can write `t('Switch')` without
 * touching `window.__` directly.
 *
 * Plural caveat
 * -------------
 * We don't ship a separate plural field — the naive `${label}s`
 * works for every default label we ship ("Cashiers", "Pharmacists",
 * "Engineers", "Sales Persons" — admittedly clunky but readable).
 * If a deployment needs a clean plural, swap the inline append for
 * a future `posa_cashier_label_plural` field without touching call
 * sites.
 */

import { computed } from "vue";
import { storeToRefs } from "pinia";
import { useUIStore } from "../../../stores/uiStore";

const DEFAULT_LABEL = "Cashier";

function translate(key: string): string {
	const fn =
		typeof window !== "undefined"
			? (window as unknown as { __?: (k: string, ...args: any[]) => string }).__
			: undefined;
	return typeof fn === "function" ? fn(key) : key;
}

export function useCashierLabel() {
	const uiStore = useUIStore();
	const { posProfile } = storeToRefs(uiStore);

	const overrideRaw = computed(() => {
		const raw = (posProfile.value as any)?.posa_cashier_label;
		return typeof raw === "string" && raw.trim() ? raw.trim() : "";
	});

	const cashierLabel = computed(() =>
		overrideRaw.value ? translate(overrideRaw.value) : translate(DEFAULT_LABEL),
	);

	const cashierLabelPlural = computed(() => `${cashierLabel.value}s`);

	const cashierPossessive = computed(() => `${cashierLabel.value}'s`);

	/**
	 * Surgical substitution for already-translated strings. When no
	 * override is configured we return the input unchanged so the
	 * existing translation pipeline is preserved exactly.
	 *
	 * When an override is configured we replace the English token
	 * "Cashier"/"cashier" wherever it appears. Strings already
	 * translated to non-English languages won't contain the literal
	 * "cashier" token and will pass through unmodified — that's a
	 * known limitation, documented in the field description on POS
	 * Profile.
	 */
	const relabel = (text: string): string => {
		if (!overrideRaw.value) return text;
		if (typeof text !== "string" || !text) return text;
		return text
			.replace(/\bCashier\b/g, cashierLabel.value)
			.replace(/\bcashier\b/g, cashierLabel.value.toLowerCase());
	};

	return {
		cashierLabel,
		cashierLabelPlural,
		cashierPossessive,
		relabel,
		t: translate,
	};
}

/**
 * Plain getter for non-component code (Pinia stores, services,
 * print-template builders) that doesn't have a Vue setup() context.
 * Reads the current POS Profile from the UI store directly.
 */
export function getCashierLabel(): string {
	try {
		const uiStore = useUIStore();
		const raw = (uiStore.posProfile as any)?.posa_cashier_label;
		if (typeof raw === "string" && raw.trim()) {
			return translate(raw.trim());
		}
	} catch {
		// Pinia not initialised yet — fall through to default.
	}
	return translate(DEFAULT_LABEL);
}
