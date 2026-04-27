<template>
	<div>
		<v-card class="selection mx-auto mt-3 pos-themed-card" style="max-height: 80vh; height: 80vh">
			<v-card-title>
				<span class="text-h6 text-primary">{{ __("Offers") }}</span>
			</v-card-title>
			<div
				class="my-0 py-0 overflow-y-auto"
				style="max-height: 75vh"
				@mouseover="style = 'cursor: pointer'"
			>
				<v-data-table
					:headers="items_headers"
					:items="pos_offers"
					:single-expand="singleExpand"
					v-model:expanded="expanded"
					show-expand
					item-value="row_id"
					class="elevation-1"
					:items-per-page="itemsPerPage"
					hide-default-footer
				>
					<template v-slot:item.offer_applied="{ item }">
						<v-btn
							v-if="!item.offer_applied"
							color="green"
							@click="applyOffer(item)"
							:disabled="
								(item.offer == 'Give Product' &&
									!item.give_item &&
									!item.replace_cheapest_item &&
									!item.replace_item) ||
								(item.offer == 'Grand Total' &&
									discount_percentage_offer_name &&
									discount_percentage_offer_name != item.name)
							"
						>
							{{ __("Apply") }}
						</v-btn>
						<v-btn v-else color="red" @click="removeOffer(item)">
							{{ __("Remove") }}
						</v-btn>
					</template>
					<template v-slot:expanded-row="{ item }">
						<td :colspan="items_headers.length">
							<v-row class="mt-2">
								<v-col v-if="item.description">
									<div class="text-primary" v-html="handleNewLine(item.description)"></div>
								</v-col>
								<v-col v-if="item.offer == 'Give Product'">
									<!-- Item Group offers — open the card-based
									     picker. Item Code offers stay locked to
									     the configured item, so we just show
									     the item name as a read-only chip. -->
									<template v-if="item.apply_type == 'Item Group'">
										<button
											type="button"
											class="give-item-picker-trigger"
											:disabled="item.replace_item || item.replace_cheapest_item"
											@click="openGiveItemPicker(item)"
										>
											<v-icon size="18" class="give-item-picker-trigger__icon">
												mdi-gift-outline
											</v-icon>
											<span class="give-item-picker-trigger__label">
												<span class="give-item-picker-trigger__eyebrow">
													{{ __("Give Item") }}
												</span>
												<span
													class="give-item-picker-trigger__value"
													:class="{ 'is-empty': !item.give_item }"
												>
													{{
														item.give_item
															? giveItemLabel(item)
															: __("Select an item from this group…")
													}}
												</span>
											</span>
											<v-icon size="18" class="give-item-picker-trigger__chevron">
												mdi-chevron-right
											</v-icon>
										</button>
									</template>
									<template v-else>
										<v-text-field
											:model-value="giveItemLabel(item) || item.give_item"
											:label="frappe._('Give Item')"
											variant="outlined"
											density="compact"
											readonly
											hide-details
										/>
									</template>
								</v-col>
							</v-row>
						</td>
					</template>
				</v-data-table>
			</div>
		</v-card>

		<v-card flat style="max-height: 11vh; height: 11vh" class="cards mb-0 mt-3 py-0">
			<v-row align="start" no-gutters>
				<v-col cols="12">
					<v-btn
						block
						class="pa-1"
						size="large"
						color="warning"
						theme="dark"
						@click="back_to_invoice"
						>{{ __("Back") }}</v-btn
					>
				</v-col>
			</v-row>
		</v-card>

		<!--
			Give-Item picker dialog. Replaces the legacy <v-autocomplete>
			dropdown with a card-based scrollable list — modelled on the
			Top Selling Items style the cashier called out: thumbnail,
			name, progress bar, and the qty number on the right (instead
			of the price). Width is constrained to 460 px so it sits
			comfortably inside the cashier UI without covering the cart.
		-->
		<v-dialog
			v-model="giveItemPickerOpen"
			max-width="460"
			scrollable
			@click:outside="closeGiveItemPicker"
		>
			<v-card class="give-item-picker pos-themed-card">
				<div class="give-item-picker__header">
					<div class="give-item-picker__header-icon">
						<v-icon size="22">mdi-gift-outline</v-icon>
					</div>
					<div class="give-item-picker__header-text">
						<h3 class="give-item-picker__header-title">
							{{ __("Pick a free item") }}
						</h3>
						<p class="give-item-picker__header-subtitle">
							{{
								giveItemPickerOffer
									? giveItemPickerOffer.apply_item_group ||
									  giveItemPickerOffer.name
									: ""
							}}
						</p>
					</div>
					<v-btn
						icon="mdi-close"
						variant="text"
						size="small"
						class="give-item-picker__close"
						:aria-label="__('Close picker')"
						@click="closeGiveItemPicker"
					/>
				</div>

				<div class="give-item-picker__search">
					<v-text-field
						v-model="giveItemPickerSearch"
						prepend-inner-icon="mdi-magnify"
						:placeholder="__('Search by name or code…')"
						variant="outlined"
						density="compact"
						hide-details
						clearable
						autofocus
					/>
				</div>

				<div class="give-item-picker__list">
					<div
						v-if="!giveItemPickerVisibleItems.length"
						class="give-item-picker__empty"
					>
						<v-icon size="32" class="give-item-picker__empty-icon">
							mdi-gift-off-outline
						</v-icon>
						<div class="give-item-picker__empty-title">
							{{ __("No items match this filter") }}
						</div>
						<div class="give-item-picker__empty-subtitle">
							{{
								giveItemPickerSearch
									? __("Try a shorter search term.")
									: __("This item group has no eligible products yet.")
							}}
						</div>
					</div>

					<button
						v-for="item in giveItemPickerVisibleItems"
						:key="item.item_code"
						type="button"
						class="give-item-card"
						:class="{
							'give-item-card--selected':
								giveItemPickerOffer &&
								giveItemPickerOffer.give_item === item.item_code,
							'give-item-card--out': (item.actual_qty || 0) <= 0,
						}"
						@click="selectGiveItem(item)"
					>
						<div class="give-item-card__thumb">
							<v-img
								v-if="item.image"
								:src="item.image"
								:alt="item.item_name"
								cover
							/>
							<v-icon v-else size="22" class="give-item-card__thumb-fallback">
								mdi-package-variant-closed
							</v-icon>
						</div>
						<div class="give-item-card__body">
							<div class="give-item-card__title">{{ item.item_name }}</div>
							<div class="give-item-card__bar">
								<div
									class="give-item-card__bar-fill"
									:style="{ width: giveItemBarWidth(item.actual_qty) + '%' }"
								></div>
							</div>
						</div>
						<div class="give-item-card__qty">
							<span class="give-item-card__qty-value">
								{{ Math.max(0, Math.round(Number(item.actual_qty) || 0)) }}
							</span>
							<span class="give-item-card__qty-unit">
								{{ __("avail") }}
							</span>
						</div>
					</button>
				</div>

				<div class="give-item-picker__footer">
					<v-btn variant="text" @click="closeGiveItemPicker">
						{{ __("Cancel") }}
					</v-btn>
				</div>
			</v-card>
		</v-dialog>
	</div>
</template>

<script>
import format from "../../../format";
import { useCustomersStore } from "../../../stores/customersStore.js";
import { useUIStore } from "../../../stores/uiStore.js";
import { useToastStore } from "../../../stores/toastStore.js";
import { storeToRefs } from "pinia";
export default {
	mixins: [format],
	setup() {
		const customersStore = useCustomersStore();
		const uiStore = useUIStore();
		const toastStore = useToastStore();
		const { selectedCustomer } = storeToRefs(customersStore);
		return { selectedCustomer, uiStore, toastStore };
	},
	data: () => ({
		loading: false,
		pos_profile: "",
		pos_offers: [],
		allItems: [],
		groupItemCache: {},
		discount_percentage_offer_name: null,
		itemsPerPage: 1000,
		expanded: [],
		singleExpand: true,
		items_headers: [
			{ title: __("Name"), value: "name", align: "start" },
			{ title: __("Apply On"), value: "apply_on", align: "start" },
			{ title: __("Offer"), value: "offer", align: "start" },
			{ title: __("Applied"), value: "offer_applied", align: "start" },
		],
		// Give-item picker dialog state. Replaces the legacy
		// <v-autocomplete> dropdown with a card-based scroller so the
		// cashier can see thumbnail / qty bar at a glance and skip the
		// hunt-and-peck search through long group lists.
		giveItemPickerOpen: false,
		giveItemPickerOffer: null,
		giveItemPickerItems: [],
		giveItemPickerSearch: "",
	}),

	computed: {
		offersCount() {
			return this.pos_offers.length;
		},
		appliedOffersCount() {
			return this.pos_offers.filter((el) => !!el.offer_applied).length;
		},
		// Filter the picker rows by the search box (case-insensitive
		// substring match on name + code). Anchors the highest-stock
		// items at the top so the cashier's first glance is on what's
		// most readily available — same intent as the items selector
		// "in stock first" sort.
		giveItemPickerVisibleItems() {
			const term = (this.giveItemPickerSearch || "")
				.toString()
				.trim()
				.toLowerCase();
			let rows = Array.isArray(this.giveItemPickerItems)
				? [...this.giveItemPickerItems]
				: [];
			if (term) {
				rows = rows.filter((it) => {
					const name = (it.item_name || "").toString().toLowerCase();
					const code = (it.item_code || "").toString().toLowerCase();
					return name.includes(term) || code.includes(term);
				});
			}
			rows.sort((a, b) => {
				const aQty = Number(a.actual_qty) || 0;
				const bQty = Number(b.actual_qty) || 0;
				if (aQty === bQty) {
					return (a.item_name || "").localeCompare(b.item_name || "");
				}
				return bQty - aQty;
			});
			return rows;
		},
		giveItemPickerMaxQty() {
			let max = 0;
			(this.giveItemPickerVisibleItems || []).forEach((it) => {
				const qty = Number(it.actual_qty) || 0;
				if (qty > max) max = qty;
			});
			return max;
		},
	},

	methods: {
		// Local helper used by the picker bar widths.
		giveItemBarWidth(qty) {
			const max = this.giveItemPickerMaxQty;
			const value = Number(qty) || 0;
			if (max <= 0 || value <= 0) return 0;
			const pct = (value / max) * 100;
			return Math.min(100, Math.max(6, pct));
		},
		back_to_invoice() {
			this.uiStore.setActiveView("items");
		},
		async fetchGroupItems(group) {
			try {
				const { message } = await frappe.call({
					method: "posawesome.posawesome.api.items.get_items",
					args: {
						pos_profile: JSON.stringify(this.pos_profile),
						item_group: group,
						// fetch complete inventory; backend paginates internally
					},
				});

				const fullItems = message || [];

				// Keep enough fields for the new picker dialog — name + qty
				// progress bar + thumbnail. Previously only `item_code`,
				// `item_name`, `rate` were cached, which forced the picker
				// to show a flat dropdown.
				this.groupItemCache[group] = fullItems.map((it) => ({
					item_code: it.item_code,
					item_name: it.item_name || it.item_code,
					rate: it.price_list_rate,
					actual_qty: Number(it.actual_qty) || 0,
					stock_uom: it.stock_uom || "",
					image: it.image || "",
				}));

				// merge fetched items into allItems so offer application has details
				const existing = new Set(this.allItems.map((it) => it.item_code));
				const newItems = fullItems.filter((it) => !existing.has(it.item_code));
				if (newItems.length) {
					this.allItems.push(...newItems);
					this.eventBus.emit("set_all_items", this.allItems);
				}

				this.forceUpdateItem();
			} catch (error) {
				console.error("Failed to fetch group items", error);
			}
		},
		forceUpdateItem() {
			let list_offers = [];
			list_offers = [...this.pos_offers];
			this.pos_offers = list_offers;
		},
		applyOffer(item) {
			item.offer_applied = true;
			this.forceUpdateItem();
		},
		removeOffer(item) {
			item.offer_applied = false;
			this.forceUpdateItem();
		},
		normalizeOfferRowId(value) {
			return String(value ?? "").trim();
		},
		getOfferId(offer) {
			return this.normalizeOfferRowId(offer?.row_id || offer?.name);
		},
		normalizeOfferIdentity(offer) {
			if (!offer || typeof offer !== "object") return offer;
			const rowId = this.getOfferId(offer);
			if (rowId) {
				offer.row_id = rowId;
			}
			return offer;
		},
		makeid(length) {
			let result = "";
			const characters = "abcdefghijklmnopqrstuvwxyz0123456789";
			const charactersLength = characters.length;
			for (var i = 0; i < length; i++) {
				result += characters.charAt(Math.floor(Math.random() * charactersLength));
			}
			return result;
		},
		updatePosOffers(offers) {
			const incoming = (Array.isArray(offers) ? offers : []).map((offer) =>
				this.normalizeOfferIdentity({ ...offer }),
			);
			const toRemove = [];
			this.pos_offers.forEach((pos_offer) => {
				const offer = incoming.find(
					(offer) => this.getOfferId(offer) === this.getOfferId(pos_offer),
				);
				if (!offer) {
					toRemove.push(this.getOfferId(pos_offer));
				}
			});
			this.removeOffers(toRemove);
			incoming.forEach((offer) => {
				const pos_offer = this.pos_offers.find(
					(pos_offer) => this.getOfferId(offer) === this.getOfferId(pos_offer),
				);
				if (pos_offer) {
					pos_offer.items = offer.items;
					if (
						offer.apply_on == "Item Group" &&
						offer.apply_type == "Item Group" &&
						offer.replace_cheapest_item
					) {
						pos_offer.give_item = offer.give_item;
						pos_offer.apply_item_code = offer.apply_item_code;
					}
				} else {
					const newOffer = { ...offer };
					if (!offer.row_id) {
						newOffer.row_id = this.getOfferId(offer) || this.makeid(20);
					}
					if (offer.apply_type == "Item Code") {
						if (offer.replace_item) {
							newOffer.give_item = offer.item || offer.apply_item_code || null;
						} else {
							newOffer.give_item = offer.apply_item_code || null;
						}
					}
					if (offer.offer_applied) {
						newOffer.offer_applied = !!offer.offer_applied;
					} else {
						if (
							offer.apply_type == "Item Group" &&
							offer.offer == "Give Product" &&
							!offer.replace_cheapest_item &&
							!offer.replace_item
						) {
							newOffer.offer_applied = false;
						} else if (offer.offer === "Grand Total" && this.discount_percentage_offer_name) {
							newOffer.offer_applied = false;
						} else {
							newOffer.offer_applied = !!offer.auto;
						}
					}
					if (newOffer.offer == "Give Product" && !newOffer.give_item) {
						const giveItems = this.get_give_items(newOffer);
						if (giveItems.length) {
							newOffer.give_item = giveItems[0].item_code;
						}
					}
					this.pos_offers.push(newOffer);
					this.toastStore.show({
						title: __("New Offer Available"),
						color: "warning",
					});
				}
			});
		},
		removeOffers(offers_id_list) {
			const normalized = new Set(
				(offers_id_list || []).map((id) => this.normalizeOfferRowId(id)),
			);
			this.pos_offers = this.pos_offers.filter(
				(offer) => !normalized.has(this.getOfferId(offer)),
			);
		},
		handelOffers() {
			const applyedOffers = this.pos_offers.filter((offer) => offer.offer_applied);
			this.eventBus.emit("update_invoice_offers", applyedOffers);
		},
		handleNewLine(str) {
			if (str) {
				return str.replace(/(?:\r\n|\r|\n)/g, "<br />");
			} else {
				return "";
			}
		},
		get_give_items(offer) {
			if (offer.apply_type === "Item Code") {
				return [
					{
						item_code: offer.apply_item_code,
						item_name: offer.apply_item_code,
					},
				];
			} else if (offer.apply_type === "Item Group") {
				const group = offer.apply_item_group;
				if (!this.groupItemCache[group]) {
					this.fetchGroupItems(group);
					return [];
				}
				let filtered_items = this.groupItemCache[group];
				if (offer.less_then > 0) {
					filtered_items = filtered_items.filter((item) => item.rate < offer.less_then);
				}
				const unique = [];
				const seen = new Set();
				filtered_items.forEach((item) => {
					if (!seen.has(item.item_code)) {
						seen.add(item.item_code);
						unique.push({
							item_code: item.item_code,
							item_name: item.item_name || item.item_code,
							actual_qty: Number(item.actual_qty) || 0,
							stock_uom: item.stock_uom || "",
							image: item.image || "",
						});
					}
				});
				return unique;
			}
			return [];
		},
		giveItemLabel(offer) {
			if (!offer?.give_item) return "";
			const candidates = this.get_give_items(offer) || [];
			const match = candidates.find((it) => it.item_code === offer.give_item);
			return match?.item_name || offer.give_item;
		},
		openGiveItemPicker(offer) {
			if (
				offer.apply_type !== "Item Group" ||
				offer.replace_item ||
				offer.replace_cheapest_item
			) {
				return;
			}
			// Pre-warm the cache so the dialog opens populated.
			const items = this.get_give_items(offer);
			this.giveItemPickerOffer = offer;
			this.giveItemPickerItems = Array.isArray(items) ? items : [];
			this.giveItemPickerSearch = "";
			this.giveItemPickerOpen = true;
		},
		selectGiveItem(item) {
			if (this.giveItemPickerOffer && item?.item_code) {
				this.giveItemPickerOffer.give_item = item.item_code;
				this.forceUpdateItem();
			}
			this.closeGiveItemPicker();
		},
		closeGiveItemPicker() {
			this.giveItemPickerOpen = false;
			this.giveItemPickerOffer = null;
			this.giveItemPickerSearch = "";
		},
		updateCounters() {
			// update store
			this.uiStore.setOfferCounts(this.offersCount, this.appliedOffersCount);
		},
		updatePosCoupuns() {
			const applyedOffers = this.pos_offers.filter(
				(offer) => offer.offer_applied && offer.coupon_based,
			);
			this.eventBus.emit("update_pos_coupons", applyedOffers);
		},
	},

	watch: {
		pos_offers: {
			deep: true,
			handler() {
				this.handelOffers();
				this.updateCounters();
				this.updatePosCoupuns();
			},
		},
		selectedCustomer(newCustomer, oldCustomer) {
			if (newCustomer === oldCustomer) {
				return;
			}
			this.pos_offers = [];
		},
	},

	created: function () {
		this.$watch(
			() => this.uiStore.posProfile,
			(profile) => {
				if (profile) this.pos_profile = profile;
			},
			{ deep: true, immediate: true },
		);
		this.$watch(
			() => this.uiStore.applicableOffers,
			(offers) => {
				if (Array.isArray(offers)) {
					this.updatePosOffers(offers);
				}
			},
			{ deep: true, immediate: true },
		);

		/*
		this.$nextTick(function () {
			this.eventBus.on("register_pos_profile", (data) => {
				this.pos_profile = data.pos_profile;
			});
		});
		*/
		this.eventBus.on("update_pos_offers", (data) => {
			this.updatePosOffers(data);
		});
		this.eventBus.on("update_discount_percentage_offer_name", (data) => {
			this.discount_percentage_offer_name = data.value;
		});
		this.eventBus.on("set_all_items", (data) => {
			this.allItems = data;
		});
	},
};
</script>

<style scoped>
/* ─── Give-Item trigger button (replaces the legacy autocomplete) ───────
   Styled to match the CC pill inputs used elsewhere in the offers row
   so it doesn't read as a plain HTML button parachuted into a Vuetify
   form. Disabled state mutes opacity but stays clickable-looking
   enough that the cashier knows the row exists. */
.give-item-picker-trigger {
	display: flex;
	align-items: center;
	gap: 12px;
	width: 100%;
	padding: 10px 14px;
	border-radius: 10px;
	border: 1px solid var(--pos-border, rgba(148, 163, 184, 0.24));
	background: var(--pos-input-bg, rgba(148, 163, 184, 0.08));
	color: var(--pos-text-primary, #edf2f7);
	cursor: pointer;
	transition: border-color 0.15s ease, background 0.15s ease;
	text-align: start;
	font: inherit;
}

.give-item-picker-trigger:hover:not(:disabled) {
	border-color: var(--cc-orange, #f46a25);
	background: rgba(244, 106, 37, 0.06);
}

.give-item-picker-trigger:disabled {
	opacity: 0.55;
	cursor: not-allowed;
}

.give-item-picker-trigger__icon {
	color: var(--cc-orange, #f46a25);
	flex-shrink: 0;
}

.give-item-picker-trigger__label {
	display: flex;
	flex-direction: column;
	min-width: 0;
	flex: 1;
}

.give-item-picker-trigger__eyebrow {
	font-size: 0.7rem;
	letter-spacing: 0.05em;
	text-transform: uppercase;
	color: var(--pos-text-secondary, #94a3b8);
	font-weight: 700;
}

.give-item-picker-trigger__value {
	font-size: 0.9rem;
	font-weight: 600;
	color: var(--pos-text-primary, #edf2f7);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.give-item-picker-trigger__value.is-empty {
	color: var(--pos-text-secondary, #7b899d);
	font-weight: 500;
}

.give-item-picker-trigger__chevron {
	color: var(--pos-text-secondary, #94a3b8);
	flex-shrink: 0;
}

/* ─── Picker dialog ──────────────────────────────────────────────────── */
.give-item-picker {
	border-radius: 16px !important;
	overflow: hidden;
	background: var(--pos-card-bg);
	color: var(--pos-text-primary);
	box-shadow: 0 4px 20px var(--pos-shadow, rgba(0, 0, 0, 0.4)) !important;
	max-height: 88vh;
	display: flex;
	flex-direction: column;
}

.give-item-picker__header {
	position: relative;
	display: flex;
	align-items: center;
	gap: 12px;
	padding: 14px 16px;
	border-bottom: 1px solid var(--pos-border);
	background: var(--pos-card-bg);
}

.give-item-picker__header::before {
	content: "";
	position: absolute;
	top: 0;
	left: 0;
	right: 0;
	height: 3px;
	background: linear-gradient(90deg, #f46a25 0%, #ffb380 100%);
}

.give-item-picker__header-icon {
	width: 38px;
	height: 38px;
	border-radius: 12px;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	color: #fff;
	background: linear-gradient(135deg, #f46a25 0%, #c75418 100%);
	flex-shrink: 0;
}

.give-item-picker__header-text {
	display: flex;
	flex-direction: column;
	min-width: 0;
	flex: 1;
}

.give-item-picker__header-title {
	margin: 0;
	font-size: 1rem;
	font-weight: 700;
	color: var(--pos-text-primary);
	letter-spacing: -0.01em;
}

.give-item-picker__header-subtitle {
	margin: 2px 0 0;
	font-size: 0.74rem;
	color: var(--pos-text-secondary);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.give-item-picker__close {
	flex-shrink: 0;
}

.give-item-picker__search {
	padding: 10px 14px;
	border-bottom: 1px solid var(--pos-border);
	background: var(--pos-card-bg);
}

.give-item-picker__list {
	overflow-y: auto;
	padding: 10px 14px;
	background: var(--pos-bg-secondary, var(--pos-card-bg));
	display: flex;
	flex-direction: column;
	gap: 8px;
	flex: 1 1 auto;
	min-height: 220px;
}

.give-item-picker__empty {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	gap: 6px;
	padding: 24px 16px;
	color: var(--pos-text-secondary);
	text-align: center;
}

.give-item-picker__empty-icon {
	color: var(--pos-text-secondary);
	opacity: 0.7;
}

.give-item-picker__empty-title {
	font-weight: 700;
	font-size: 0.9rem;
	color: var(--pos-text-primary);
}

.give-item-picker__empty-subtitle {
	font-size: 0.78rem;
}

/* ─── Per-row card. Mirrors the "Top Selling Items" reference: thumb,
   name + progress bar stacked, qty number on the right (replacing the
   price). Selected state pulses an orange ring so the cashier sees
   what's currently locked-in if they reopen the dialog. */
.give-item-card {
	display: grid;
	grid-template-columns: 44px 1fr auto;
	gap: 12px;
	align-items: center;
	width: 100%;
	padding: 10px 12px;
	border: 1px solid var(--pos-border);
	background: var(--pos-card-bg);
	border-radius: 10px;
	cursor: pointer;
	transition: transform 0.12s ease, border-color 0.12s ease,
		box-shadow 0.12s ease, background 0.12s ease;
	font: inherit;
	text-align: start;
	color: var(--pos-text-primary);
}

.give-item-card:hover:not(:disabled) {
	transform: translateY(-1px);
	border-color: var(--cc-orange, #f46a25);
	box-shadow: 0 6px 16px rgba(244, 106, 37, 0.18);
}

.give-item-card--selected {
	border-color: var(--cc-orange, #f46a25);
	box-shadow: 0 0 0 2px rgba(244, 106, 37, 0.32);
	background: rgba(244, 106, 37, 0.05);
}

.give-item-card--out {
	opacity: 0.55;
}

.give-item-card__thumb {
	width: 44px;
	height: 44px;
	border-radius: 10px;
	overflow: hidden;
	background: rgba(148, 163, 184, 0.12);
	display: inline-flex;
	align-items: center;
	justify-content: center;
	color: var(--pos-text-secondary);
}

.give-item-card__thumb-fallback {
	color: var(--pos-text-secondary);
}

.give-item-card__body {
	display: flex;
	flex-direction: column;
	gap: 6px;
	min-width: 0;
}

.give-item-card__title {
	font-size: 0.86rem;
	font-weight: 700;
	color: var(--pos-text-primary);
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}

.give-item-card__bar {
	height: 4px;
	border-radius: 999px;
	background: rgba(148, 163, 184, 0.18);
	overflow: hidden;
}

.give-item-card__bar-fill {
	height: 100%;
	border-radius: inherit;
	background: linear-gradient(90deg, #22c55e 0%, #4ade80 100%);
	transition: width 0.2s ease;
}

.give-item-card--out .give-item-card__bar-fill {
	background: linear-gradient(90deg, #ef4444 0%, #f97316 100%);
}

.give-item-card__qty {
	display: flex;
	flex-direction: column;
	align-items: flex-end;
	justify-content: center;
	gap: 1px;
	min-width: 56px;
}

.give-item-card__qty-value {
	font-size: 1rem;
	font-weight: 700;
	color: var(--pos-text-primary);
	font-variant-numeric: tabular-nums;
}

.give-item-card--out .give-item-card__qty-value {
	color: #ef4444;
}

.give-item-card__qty-unit {
	font-size: 0.66rem;
	letter-spacing: 0.04em;
	text-transform: uppercase;
	color: var(--pos-text-secondary);
}

.give-item-picker__footer {
	display: flex;
	justify-content: flex-end;
	padding: 10px 14px;
	border-top: 1px solid var(--pos-border);
	background: var(--pos-card-bg);
}
</style>
