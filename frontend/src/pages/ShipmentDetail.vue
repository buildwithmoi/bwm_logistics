<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter, RouterLink } from "vue-router";
import { ReceiptText, Printer } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtMoney, fmtWeight, fmtDate } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Select from "@/components/ui/Select.vue";
import Textarea from "@/components/ui/Textarea.vue";
import Dialog from "@/components/ui/Dialog.vue";
import Sheet from "@/components/ui/Sheet.vue";
import Badge from "@/components/ui/Badge.vue";
import DetailHeader from "@/components/ui/DetailHeader.vue";
import DataList from "@/components/ui/DataList.vue";
import ShipmentGoods from "@/components/shipment/ShipmentGoods.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import DirectionBadge from "@/components/DirectionBadge.vue";
import Timeline, { type TimelineEvent } from "@/components/Timeline.vue";

const route = useRoute();
const router = useRouter();
const toast = useToast();
const session = useSessionStore();

interface ShipmentData extends Record<string, unknown> {
	name: string;
	customer_name?: string;
	status?: string;
	direction?: string;
	current_milestone?: string;
	container?: string;
	timeline: TimelineEvent[];
	packages?: Array<Record<string, unknown>>;
	charges?: Array<Record<string, unknown>>;
	invoice?: { name: string; status: string; grand_total: number; outstanding_amount: number; currency: string };
	container_info?: { name: string; container_no?: string; eta?: string; vessel?: string; current_milestone?: string };
}
const data = ref<ShipmentData | null>(null);
const loading = ref(true);
const name = computed(() => String(route.params.name));

async function load() {
	loading.value = true;
	try {
		data.value = await call<ShipmentData>("bwm_logistics.api.shipments.get_shipment", { name: name.value });
		loadPnl();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load shipment");
		router.push("/shipments");
	} finally {
		loading.value = false;
	}
}
onMounted(load);

const canEdit = computed(() => session.can("shipments", "edit"));
const canBill = computed(() => session.canSee("billing") || session.hasRole("Logistics Manager", "System Manager"));
const isTrading = computed(() => data.value?.shipment_type === "Own Goods (Trading)");

// ── sections ────────────────────────────────────────────────────────────────
// The rail. Goods only exists for own-goods bookings — there is no stock to
// distribute on somebody else's cargo.
interface BoxRow extends Record<string, unknown> {
	container: string;
	container_no?: string;
	status?: string;
	eta?: string;
}
const boxes = computed<BoxRow[]>(() => (data.value?.containers as BoxRow[]) || []);

const sections = computed(() =>
	[
		{ key: "timeline", label: "Timeline" },
		{ key: "containers", label: `Containers${boxes.value.length ? ` (${boxes.value.length})` : ""}` },
		{ key: "voyage", label: "Voyage" },
		{ key: "billing", label: "Charges" },
		...(isTrading.value ? [{ key: "goods", label: "Goods" }] : []),
	].filter(Boolean),
);
const section = ref<string>("timeline");

// Own goods have no customer to consign to, so the receiver fields aren't
// "empty" — they don't apply. Route still does.
const routeRows = computed(() => [
	...(isTrading.value
		? []
		: [
				{ label: "Receiver", value: data.value?.consignee_name as string },
				{ label: "Phone", value: data.value?.consignee_phone as string },
			]),
	{ label: "Origin", value: data.value?.origin as string },
	{ label: "Destination", value: data.value?.destination as string },
	{ label: "Delivery address", value: data.value?.delivery_address as string, wide: true },
]);

// The voyage belongs to the booking — one sailing, however many boxes ride on
// it. DataList drops whatever is blank, so a booking with no vessel yet shows
// nothing here rather than a column of dashes.
const voyageRows = computed(() => [
	{ label: "Shipping line", value: data.value?.shipping_line as string },
	{ label: "Vessel", value: data.value?.vessel as string },
	{ label: "Voyage no", value: data.value?.voyage_no as string },
	{ label: "Booking no", value: data.value?.booking_no as string },
	{ label: "Load port", value: data.value?.port_of_loading as string },
	{ label: "Discharge port", value: data.value?.port_of_discharge as string },
	{ label: "ETD", value: fmtDate(data.value?.etd as string) },
	{ label: "ETA", value: fmtDate(data.value?.eta as string) },
	{ label: "Date received", value: fmtDate(data.value?.date_received as string) },
]);

// The P&L card is a claim that money has moved. Until an invoice or a purchase
// exists it reports "+0.00 · 0 invoice(s) · 0 purchase(s)" in a big black box —
// a prominent statement that nothing has happened. And on customer cargo it is
// not our margin at all, it's their freight bill.
const hasPnlActivity = computed(
	() => !!pnl.value && (pnl.value.sales.length > 0 || pnl.value.purchases.length > 0),
);
const showPnl = computed(() => canBill.value && isTrading.value && hasPnlActivity.value);

// ── P&L (Managers/Accounts only — server enforces too) ─────────────────────
interface Pnl {
	revenue: number;
	cost: number;
	profit: number;
	margin_pct: number | null;
	sales: Array<{ name: string; customer_name?: string; grand_total: number; outstanding_amount: number; status: string }>;
	purchases: Array<{ name: string; supplier_name?: string; grand_total: number; outstanding_amount: number; status: string }>;
}
const pnl = ref<Pnl | null>(null);
async function loadPnl() {
	if (!canBill.value) return;
	try {
		pnl.value = await call<Pnl>("bwm_logistics.api.billing.shipment_pnl", { shipment: name.value });
	} catch {
		/* card hidden on error */
	}
}

// ── update status ───────────────────────────────────────────────────────────
// Recording a milestone IS how a shipment's status changes (Tracking Event →
// Shipment.apply_milestone). The old UI made you type the milestone as free
// text, so unless you already knew the exact strings in MILESTONE_STATUS you
// could not move a shipment at all. Now the server hands over the list and its
// resulting status, and picking one is the whole interaction.
const eventOpen = ref(false);
const saving = ref(false);
const form = reactive({ milestone: "", location: "", remarks: "", notify: true });

interface MilestoneOption {
	milestone: string;
	status: string | null;
}
const milestoneOptions = computed<MilestoneOption[]>(
	() => (data.value?.milestone_options as MilestoneOption[]) || [],
);

function openStatus() {
	form.milestone = "";
	form.location = "";
	form.remarks = "";
	form.notify = !isTrading.value; // no customer to notify on own goods
	eventOpen.value = true;
}

async function recordEvent() {
	if (!form.milestone) {
		toast.warning("Pick the new status");
		return;
	}
	saving.value = true;
	try {
		await call("bwm_logistics.api.shipments.record_event", {
			shipment: name.value,
			milestone: form.milestone,
			location: form.location || null,
			remarks: form.remarks || null,
			notify: form.notify ? 1 : 0,
		});
		toast.success("Event recorded");
		eventOpen.value = false;
		form.milestone = "";
		form.location = "";
		form.remarks = "";
		await load();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not record event");
	} finally {
		saving.value = false;
	}
}

// ── rate card ───────────────────────────────────────────────────────────────
interface RateCardOpt {
	name: string;
	card_name: string;
	direction?: string;
	is_default?: number;
}
const rateOpen = ref(false);
const rateApplying = ref(false);
const rateCards = ref<RateCardOpt[]>([]);
const rateChoice = ref("");

async function openRate() {
	rateOpen.value = true;
	try {
		const cards = await call<RateCardOpt[]>("bwm_logistics.api.billing.list_rate_cards");
		rateCards.value = cards.filter((c) => !c.direction || c.direction === data.value?.direction);
		const preferred = rateCards.value.find((c) => c.is_default) || rateCards.value[0];
		rateChoice.value = preferred?.name || "";
	} catch {
		/* empty select */
	}
}
async function applyRate() {
	if (!rateChoice.value) {
		toast.warning("Pick a rate card");
		return;
	}
	rateApplying.value = true;
	try {
		const res = await call<{ total_charges: number }>("bwm_logistics.api.shipments.apply_rate_card", {
			shipment: name.value,
			rate_card: rateChoice.value,
		});
		toast.success(`Charges set — total ${res.total_charges}`);
		rateOpen.value = false;
		await load();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not apply rate card");
	} finally {
		rateApplying.value = false;
	}
}

// ── invoice ─────────────────────────────────────────────────────────────────
const invoicing = ref(false);
async function makeInvoice() {
	invoicing.value = true;
	try {
		const res = await call<{ sales_invoice: string }>("bwm_logistics.api.shipments.make_invoice", {
			shipment: name.value,
		});
		toast.success(`Invoice ${res.sales_invoice} created`);
		await load();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not create invoice");
	} finally {
		invoicing.value = false;
	}
}
</script>

<template>
	<div class="mx-auto max-w-6xl">
		<div v-if="loading" class="py-16 text-center text-sm text-muted-foreground">Loading…</div>
		<template v-else-if="data">
			<DetailHeader
				:title="data.name"
				back-to="/shipments"
				back-label="Shipments"
				:subtitle="`${isTrading ? 'Trading shipment' : data.customer_name || 'No customer'}${data.destination ? ' · ' + data.destination : ''}${data.current_milestone ? ' · ' + data.current_milestone : ''}`"
				status-action-label="Update status"
				@status-click="canEdit && openStatus()"
			>
				<!-- The badge is the control: tapping it opens the status sheet. -->
				<template v-if="canEdit" #statusAction />
				<template #badges>
					<StatusBadge :status="data.status" />
					<DirectionBadge :direction="data.direction" />
					<Badge v-if="isTrading" tone="brand">Own goods</Badge>
					<Badge v-if="data.current_milestone === 'Delayed'" tone="danger" dot>Delayed</Badge>
				</template>
				<template #actions>
					<Button
						v-if="canBill && !data.invoice && (data.charges || []).length"
						variant="outline"
						:loading="invoicing"
						@click="makeInvoice"
					>
						<ReceiptText class="h-4 w-4" aria-hidden="true" />
						<span class="hidden sm:inline">Create invoice</span>
						<span class="sm:hidden">Invoice</span>
					</Button>
					<Button variant="outline" size="icon" title="Print labels" aria-label="Print labels" @click="router.push(`/shipments/${name}/label`)">
						<Printer class="h-4 w-4" aria-hidden="true" />
					</Button>
				</template>
			</DetailHeader>

			<!-- P&L (Managers/Accounts — server-gated) -->
			<!-- Nothing has moved yet: offer the two actions on one quiet line
			     instead of a prominent card reporting +0.00. -->
			<div
				v-if="canBill && isTrading && !hasPnlActivity"
				class="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-white px-4 py-3 ring-1 ring-gray-100"
			>
				<p class="text-[13px] text-muted-foreground">No costs or sales recorded against this shipment yet.</p>
				<div class="flex shrink-0 gap-2">
					<Button size="sm" variant="outline" @click="router.push(`/billing/purchase/new?shipment=${name}`)">
						Record cost
					</Button>
					<Button size="sm" @click="router.push(`/billing/invoice/new?shipment=${name}`)">Record sale</Button>
				</div>
			</div>

			<div v-if="showPnl && pnl" class="mb-4 rounded-2xl bg-coal-900 p-4 sm:p-6 text-white">
				<div class="flex flex-wrap items-center gap-x-8 gap-y-3">
					<div class="min-w-0">
						<div class="label-caps !text-brand-400">Profit & loss</div>
						<div class="mt-1 text-2xl font-bold tabular-nums" :class="pnl.profit >= 0 ? 'text-emerald-400' : 'text-red-400'">
							{{ pnl.profit >= 0 ? "+" : "" }}{{ fmtMoney(pnl.profit) }}
							<span v-if="pnl.margin_pct !== null" class="ml-1 text-sm font-medium text-white/50">{{ pnl.margin_pct }}% margin</span>
						</div>
					</div>
					<div class="flex gap-8 text-sm">
						<div>
							<div class="text-white/50">Revenue</div>
							<div class="font-semibold tabular-nums">{{ fmtMoney(pnl.revenue) }}</div>
							<div class="text-xs text-white/40">{{ pnl.sales.length }} invoice(s)</div>
						</div>
						<div>
							<div class="text-white/50">Costs</div>
							<div class="font-semibold tabular-nums">{{ fmtMoney(pnl.cost) }}</div>
							<div class="text-xs text-white/40">{{ pnl.purchases.length }} purchase(s)</div>
						</div>
					</div>
					<div class="ml-auto flex flex-wrap gap-2">
						<button
							type="button"
							class="rounded-full border border-white/25 px-4 py-2 text-sm font-semibold transition-colors hover:border-brand-400 hover:text-brand-300"
							@click="router.push(`/billing?tab=purchases&shipment=${name}&new=1`)"
						>
							Record cost
						</button>
						<button
							type="button"
							class="rounded-full bg-brand-500 px-4 py-2 text-sm font-semibold text-coal-900 transition-colors hover:bg-brand-400"
							@click="router.push(`/billing?tab=sales&shipment=${name}&new=1`)"
						>
							Record sale
						</button>
					</div>
				</div>
				<!-- Linked documents -->
				<div v-if="pnl.sales.length || pnl.purchases.length" class="mt-4 grid grid-cols-1 gap-4 border-t border-white/10 pt-4 sm:grid-cols-2">
					<div v-if="pnl.sales.length">
						<div class="label-caps mb-2 !text-white/40">Sales</div>
						<div v-for="s in pnl.sales" :key="s.name" class="flex justify-between py-1 text-sm">
							<span class="truncate text-white/80">{{ s.name }}<span v-if="s.customer_name" class="text-white/40"> · {{ s.customer_name }}</span></span>
							<span class="shrink-0 tabular-nums">{{ fmtMoney(s.grand_total) }}<span v-if="s.outstanding_amount > 0" class="text-amber-400"> ({{ fmtMoney(s.outstanding_amount) }} due)</span></span>
						</div>
					</div>
					<div v-if="pnl.purchases.length">
						<div class="label-caps mb-2 !text-white/40">Purchases</div>
						<div v-for="p in pnl.purchases" :key="p.name" class="flex justify-between py-1 text-sm">
							<span class="truncate text-white/80">{{ p.name }}<span v-if="p.supplier_name" class="text-white/40"> · {{ p.supplier_name }}</span></span>
							<span class="shrink-0 tabular-nums">{{ fmtMoney(p.grand_total) }}<span v-if="p.outstanding_amount > 0" class="text-amber-400"> ({{ fmtMoney(p.outstanding_amount) }} owed)</span></span>
						</div>
					</div>
				</div>
			</div>

			<!-- One section at a time. A shipment carries route, boxes, money,
			     goods and history; showing all five at once made a page nobody
			     could scan, and on a phone it was a very long scroll. The rail
			     is the same control the Reports and Settings screens use. -->
			<div class="flex flex-col gap-4 lg:flex-row lg:gap-6">
				<nav
					class="chip-row shrink-0 lg:mx-0 lg:w-48 lg:flex-col lg:overflow-visible lg:px-0"
					aria-label="Shipment section"
				>
					<button
						v-for="s in sections"
						:key="s.key"
						type="button"
						class="shrink-0 touch-manipulation rounded-lg px-3.5 py-2 text-left text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
						:class="section === s.key ? 'bg-brand-50 text-brand-800' : 'text-gray-600 hover:bg-gray-50'"
						:aria-current="section === s.key ? 'page' : undefined"
						@click="section = s.key"
					>
						{{ s.label }}
					</button>
				</nav>

				<div class="min-w-0 flex-1 space-y-4">
					<!-- Containers: a booking can ride in several boxes -->
					<template v-if="section === 'containers'">
						<div v-if="!boxes.length" class="rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6">
							<p class="text-sm text-muted-foreground">
								Loose cargo — this booking isn't in a container yet.
							</p>
						</div>
						<RouterLink
							v-for="b in boxes"
							:key="b.container"
							:to="`/containers/${b.container}`"
							class="block rounded-2xl bg-coal-900 p-4 text-white transition-colors hover:bg-coal-800 sm:p-6"
						>
							<div class="label-caps !text-brand-400">In container</div>
							<div class="mt-1 text-lg font-semibold">{{ b.container_no || b.container }}</div>
							<div class="mt-1 text-sm text-white/60">
								{{ b.status || "—" }}<template v-if="b.eta"> · ETA {{ fmtDate(b.eta as string) }}</template>
							</div>
						</RouterLink>
					</template>

					<template v-else-if="section === 'voyage'">
<!-- The sailing, and the parties at each end of it -->
		<div class="rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6">
			<h2 class="label-caps mb-2 sm:mb-4">Voyage &amp; dates</h2>
			<DataList :items="voyageRows" empty-text="No sailing recorded yet." />
		</div>
		<div class="mt-4 rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6">
			<h2 class="label-caps mb-2 sm:mb-4">{{ isTrading ? "Route" : "Consignee &amp; route" }}</h2>
			<DataList :items="routeRows" empty-text="No route or consignee recorded yet." />
		</div>
					</template>

					<template v-else-if="section === 'billing'">
<!-- Billing -->
		<div class="rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6">
			<div class="mb-4 flex items-center justify-between">
				<h2 class="label-caps">Charges & billing</h2>
				<button
					v-if="canEdit && !data.invoice"
					type="button"
					class="text-xs font-medium text-brand-700 hover:underline"
					@click="openRate"
				>
					Apply rate card
				</button>
			</div>
			<ul v-if="(data.charges || []).length" class="divide-y divide-gray-100 text-sm">
				<li v-for="(c, i) in data.charges" :key="i" class="flex justify-between py-2">
					<span>{{ c.charge_type }}</span>
					<span class="tabular-nums">{{ fmtMoney(c.amount as number) }}</span>
				</li>
				<li class="flex justify-between py-2 font-semibold">
					<span>Total</span>
					<span class="tabular-nums">{{ fmtMoney(data.total_charges as number) }}</span>
				</li>
			</ul>
			<p v-else class="text-sm text-muted-foreground">No charges added.</p>
			<div v-if="data.invoice" class="mt-3 flex items-center justify-between rounded-xl bg-gray-50 px-4 py-3 text-sm">
				<div>
					<div class="font-medium">{{ data.invoice.name }}</div>
					<div class="text-xs text-muted-foreground">
						Outstanding {{ fmtMoney(data.invoice.outstanding_amount, data.invoice.currency) }}
					</div>
				</div>
				<StatusBadge :status="data.invoice.status" />
			</div>
		</div>
					</template>

					<template v-else-if="section === 'goods'">
						<ShipmentGoods :shipment="name" :can-bill="canBill" @invoiced="loadPnl" />
					</template>

					<template v-else>
<!-- Timeline -->
	<div class="rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6 lg:col-span-7">
		<h2 class="label-caps mb-4">Tracking timeline</h2>
		<Timeline :events="data.timeline" />
	</div>
					</template>
				</div>
			</div>

			<!-- ── Apply rate card dialog ────────────────────────────────────── -->
			<Dialog v-model:open="rateOpen" title="Apply rate card">
				<div class="space-y-4">
					<p class="rounded-xl bg-gray-50 px-4 py-3 text-xs text-muted-foreground">
						Charges are computed from this shipment's package totals
						({{ data.total_packages }} pkg, {{ fmtWeight(data.total_weight_kg as number) }})
						and <b>replace</b> the current charge lines.
					</p>
					<div v-if="!rateCards.length" class="text-sm text-muted-foreground">
						No matching rate cards — create one under
						<RouterLink to="/billing" class="font-medium text-brand-700 hover:underline">Billing</RouterLink>.
					</div>
					<div v-else class="space-y-1.5">
						<Label required>Rate card</Label>
						<Select
							v-model="rateChoice"
							:options="rateCards.map((c) => ({ value: c.name, label: c.card_name + (c.is_default ? ' (default)' : '') }))"
						/>
					</div>
				</div>
				<template #footer>
					<div class="flex justify-end gap-2">
						<Button variant="outline" @click="rateOpen = false">Cancel</Button>
						<Button :disabled="!rateCards.length" :loading="rateApplying" @click="applyRate">Apply</Button>
					</div>
				</template>
			</Dialog>

			<!-- ── Record event dialog ───────────────────────────────────────── -->
			<Sheet
				v-model:open="eventOpen"
				title="Update status"
				:description="`${data.name} is currently ${data.current_milestone || 'not started'}.`"
			>
				<div class="space-y-4">
					<fieldset>
						<legend class="label-caps mb-2">Move to</legend>
						<div class="space-y-1.5">
							<label
								v-for="opt in milestoneOptions"
								:key="opt.milestone"
								class="flex cursor-pointer items-center gap-3 rounded-xl border px-3.5 py-3 transition-colors"
								:class="[
									form.milestone === opt.milestone
										? 'border-brand-400 bg-brand-50'
										: 'border-gray-200 hover:bg-gray-50',
									// Where it already is, so you can see what you're moving from.
									opt.milestone === data.current_milestone && form.milestone !== opt.milestone && 'border-gray-300 bg-gray-50',
								]"
							>
								<input
									v-model="form.milestone"
									type="radio"
									name="milestone"
									:value="opt.milestone"
									class="h-4 w-4 shrink-0 accent-[#b8860b]"
								/>
								<span class="min-w-0 flex-1 text-sm font-medium">
									{{ opt.milestone }}
									<span v-if="opt.milestone === data.current_milestone" class="ml-1.5 text-xs font-normal text-muted-foreground">
										· current
									</span>
								</span>
								<Badge v-if="opt.status" tone="neutral">{{ opt.status }}</Badge>
								<Badge v-else tone="warning">flag only</Badge>
							</label>
						</div>
					</fieldset>

					<div class="space-y-1.5">
						<Label for="ev-location">Location <span class="font-normal text-muted-foreground">(optional)</span></Label>
						<Input id="ev-location" v-model="form.location" placeholder="e.g. Tema Port" />
					</div>
					<div class="space-y-1.5">
						<Label for="ev-remarks">Remarks <span class="font-normal text-muted-foreground">(optional)</span></Label>
						<Textarea id="ev-remarks" v-model="form.remarks" :rows="2" />
					</div>
					<label
						v-if="!isTrading"
						class="flex cursor-pointer items-center gap-2.5 rounded-xl bg-brand-50 px-4 py-3"
					>
						<input v-model="form.notify" type="checkbox" class="h-4 w-4 shrink-0 rounded accent-[#b8860b]" />
						<span class="text-sm">
							<span class="font-medium">Notify {{ data.customer_name || "the customer" }}</span>
							<span class="block text-xs text-muted-foreground">Sends the tracking update by email/SMS</span>
						</span>
					</label>
				</div>
				<template #footer>
					<div class="flex justify-end gap-2">
						<Button variant="outline" @click="eventOpen = false">Cancel</Button>
						<Button :loading="saving" :disabled="!form.milestone" @click="recordEvent">Update status</Button>
					</div>
				</template>
			</Sheet>
		</template>
	</div>
</template>
