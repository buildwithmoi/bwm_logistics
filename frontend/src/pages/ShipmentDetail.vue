<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter, RouterLink } from "vue-router";
import { ArrowLeft, Package, Flag, ReceiptText, Printer } from "lucide-vue-next";
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
import SearchCombo from "@/components/ui/SearchCombo.vue";
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
		loadStock();
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

// ── stock & distribution (trading shipments only) ──────────────────────────
interface BalanceLine {
	product: string;
	unit: string;
	received: number;
	distributed: number;
	remaining: number;
}
interface Balances {
	lines: BalanceLine[];
	received_total: number;
	distributed_total: number;
	remaining_total: number;
}
interface DistRow {
	name: string;
	product: string;
	qty: number;
	unit?: string;
	recipient: string;
	customer?: string | null;
	destination?: string;
	unit_price?: number;
	amount?: number;
	delivery_date?: string;
	sales_invoice?: string | null;
}
const balances = ref<Balances | null>(null);
const distributions = ref<DistRow[]>([]);
const canDistribute = computed(() => session.can("stock", "create") || session.can("shipments", "edit"));
const fmtQty = (v?: number) => (v || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });

async function loadStock() {
	if (data.value?.shipment_type !== "Own Goods (Trading)") return;
	try {
		const [bal, list] = await Promise.all([
			call<Balances>("bwm_logistics.api.stock.shipment_stock_balance", { shipment: name.value }),
			call<{ rows: DistRow[] }>("bwm_logistics.api.stock.list_distributions", {
				shipment: name.value,
				limit: 100,
			}),
		]);
		balances.value = bal;
		distributions.value = list.rows;
	} catch {
		/* card hidden on error */
	}
}

const distOpen = ref(false);
const distSaving = ref(false);
const distForm = reactive({
	product: "",
	qty: null as number | null,
	recipient: "",
	customer: "" as string | null,
	destination: "",
	unit_price: null as number | null,
	delivery_date: new Date().toISOString().slice(0, 10),
	notes: "",
});
const distCustomerDisplay = ref<string | null>(null);

interface CustomerHit extends Record<string, unknown> {
	name: string;
	customer_name: string;
	mobile_no?: string;
}
async function fetchCustomers(q: string): Promise<CustomerHit[]> {
	const res = await call<{ rows: CustomerHit[] }>("bwm_logistics.api.customers.list_customers", {
		search: q || null,
		limit: 20,
	});
	return res.rows;
}

const productOptions = computed(() =>
	(balances.value?.lines || []).map((l) => ({
		value: l.product,
		label: `${l.product} — ${fmtQty(l.remaining)} ${l.unit.toLowerCase()} left`,
	})),
);
const selectedLine = computed(() =>
	balances.value?.lines.find((l) => l.product === distForm.product),
);

function openDist() {
	const firstOpen = balances.value?.lines.find((l) => l.remaining > 0) || balances.value?.lines[0];
	distForm.product = firstOpen?.product || "";
	distForm.qty = null;
	distForm.recipient = "";
	distForm.customer = "";
	distCustomerDisplay.value = null;
	distForm.destination = "";
	distForm.unit_price = null;
	distForm.notes = "";
	distOpen.value = true;
}

async function saveDistribution() {
	if (!distForm.product || !distForm.qty || !distForm.recipient.trim()) {
		toast.warning("Product, quantity and recipient are required");
		return;
	}
	distSaving.value = true;
	try {
		await call("bwm_logistics.api.stock.record_distribution", {
			payload: {
				shipment: name.value,
				product: distForm.product,
				qty: distForm.qty,
				recipient: distForm.recipient,
				customer: distForm.customer || null,
				destination: distForm.destination || null,
				unit_price: distForm.unit_price || null,
				delivery_date: distForm.delivery_date || null,
				notes: distForm.notes || null,
			},
		});
		toast.success("Distribution recorded");
		distOpen.value = false;
		await loadStock();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not record distribution");
	} finally {
		distSaving.value = false;
	}
}

async function deleteDistribution(row: DistRow) {
	try {
		await call("bwm_logistics.api.stock.delete_distribution", { name: row.name });
		toast.info("Entry removed");
		await loadStock();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not delete entry");
	}
}

const invoicingDist = ref("");
async function invoiceDistribution(row: DistRow) {
	invoicingDist.value = row.name;
	try {
		const res = await call<{ sales_invoice: string }>("bwm_logistics.api.stock.invoice_distribution", {
			name: row.name,
		});
		toast.success(`Invoice ${res.sales_invoice} created`);
		await Promise.all([loadStock(), loadPnl()]);
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not invoice entry");
	} finally {
		invoicingDist.value = "";
	}
}

// ── record shipment event ───────────────────────────────────────────────────
const eventOpen = ref(false);
const saving = ref(false);
const form = reactive({ milestone: "", location: "", remarks: "", notify: true });

async function recordEvent() {
	if (!form.milestone) {
		toast.warning("Enter a milestone");
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
			<header class="mb-6 flex flex-wrap items-center gap-3">
				<RouterLink
					to="/shipments"
					class="flex h-9 w-9 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
				>
					<ArrowLeft class="h-4 w-4" />
				</RouterLink>
				<span class="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600/10 text-brand-700">
					<Package class="h-5 w-5" />
				</span>
				<div class="min-w-0 flex-1">
					<div class="flex flex-wrap items-center gap-2">
						<h1 class="text-2xl font-semibold tracking-tight">{{ data.name }}</h1>
						<StatusBadge :status="data.status" />
						<DirectionBadge :direction="data.direction" />
						<span
							v-if="isTrading"
							class="rounded-full bg-brand-600/10 px-2.5 py-0.5 text-[11.5px] font-semibold text-brand-700"
						>Own goods</span>
						<span
							v-if="data.current_milestone === 'Delayed'"
							class="inline-flex items-center rounded-full bg-red-50 px-2.5 py-0.5 text-[11.5px] font-semibold text-red-700 ring-1 ring-red-200"
						>Delayed</span>
					</div>
					<p class="text-sm text-muted-foreground">
						{{ isTrading ? "Trading shipment" : data.customer_name }} · {{ data.destination || "destination not set" }}
						<span v-if="data.current_milestone"> · {{ data.current_milestone }}</span>
					</p>
				</div>
				<Button variant="outline" @click="router.push(`/shipments/${name}/label`)">
					<Printer class="h-4 w-4" /> Labels
				</Button>
				<Button v-if="canEdit" variant="outline" @click="eventOpen = true">
					<Flag class="h-4 w-4" /> Record event
				</Button>
				<Button
					v-if="canBill && !data.invoice && (data.charges || []).length"
					:loading="invoicing"
					@click="makeInvoice"
				>
					<ReceiptText class="h-4 w-4" /> Create invoice
				</Button>
			</header>

			<!-- P&L (Managers/Accounts — server-gated) -->
			<div v-if="canBill && pnl" class="mb-4 rounded-3xl bg-coal-900 p-6 text-white">
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
				<div v-if="pnl.sales.length || pnl.purchases.length" class="mt-4 grid gap-4 border-t border-white/10 pt-4 sm:grid-cols-2">
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

			<div class="grid gap-4 lg:grid-cols-12">
				<div class="space-y-4 lg:col-span-5">
					<!-- Container card -->
					<div v-if="data.container_info" class="rounded-3xl bg-coal-900 p-6 text-white">
						<div class="label-caps !text-brand-400">In container</div>
						<RouterLink
							:to="`/containers/${data.container_info.name}`"
							class="mt-1 block text-lg font-semibold hover:text-brand-300"
						>
							{{ data.container_info.container_no || data.container_info.name }}
						</RouterLink>
						<div class="mt-1 text-sm text-white/60">
							{{ data.container_info.vessel || "vessel TBD" }} ·
							ETA {{ fmtDate(data.container_info.eta) }}
						</div>
					</div>

					<!-- Parties -->
					<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
						<h2 class="label-caps mb-4">Consignee & route</h2>
						<dl class="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
							<div><dt class="label-caps !text-[10px]">Receiver</dt><dd class="mt-0.5">{{ data.consignee_name || "—" }}</dd></div>
							<div><dt class="label-caps !text-[10px]">Phone</dt><dd class="mt-0.5">{{ data.consignee_phone || "—" }}</dd></div>
							<div><dt class="label-caps !text-[10px]">Origin</dt><dd class="mt-0.5">{{ data.origin || "—" }}</dd></div>
							<div><dt class="label-caps !text-[10px]">Destination</dt><dd class="mt-0.5">{{ data.destination || "—" }}</dd></div>
							<div class="col-span-2"><dt class="label-caps !text-[10px]">Delivery address</dt><dd class="mt-0.5">{{ data.delivery_address || "—" }}</dd></div>
						</dl>
					</div>

					<!-- Packages -->
					<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
						<h2 class="label-caps mb-4">Packages ({{ data.total_packages || 0 }})</h2>
						<ul class="divide-y divide-gray-100 text-sm">
							<li v-for="(p, i) in data.packages" :key="i" class="flex items-baseline justify-between gap-3 py-2">
								<span class="min-w-0 flex-1">{{ p.description }} <span class="text-muted-foreground">× {{ p.qty }} {{ String(p.unit || "PIECES").toLowerCase() }}</span></span>
								<span class="shrink-0 tabular-nums text-muted-foreground">{{ fmtWeight(p.weight_kg as number) }}</span>
							</li>
						</ul>
						<div class="mt-3 flex justify-between border-t border-gray-100 pt-3 text-sm">
							<span class="text-muted-foreground">Total weight</span>
							<span class="font-medium tabular-nums">{{ fmtWeight(data.total_weight_kg as number) }}</span>
						</div>
					</div>

					<!-- Billing -->
					<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
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
				</div>

				<!-- Timeline -->
				<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100 lg:col-span-7">
					<h2 class="label-caps mb-4">Tracking timeline</h2>
					<Timeline :events="data.timeline" />
				</div>
			</div>

			<!-- ── Stock & distribution (trading shipments) ─────────────────── -->
			<div v-if="isTrading && balances" class="mt-4 rounded-3xl bg-white p-6 ring-1 ring-gray-100">
				<div class="mb-4 flex flex-wrap items-center gap-2">
					<h2 class="label-caps min-w-0 flex-1">Stock & distribution</h2>
					<span class="text-sm tabular-nums text-muted-foreground">
						{{ fmtQty(balances.distributed_total) }} of {{ fmtQty(balances.received_total) }} distributed ·
						<b class="text-gray-900">{{ fmtQty(balances.remaining_total) }} left</b>
					</span>
					<Button v-if="canDistribute" size="sm" @click="openDist">Record distribution</Button>
				</div>

				<!-- Per-product balance bars -->
				<div class="mb-5 space-y-2.5">
					<div v-for="l in balances.lines" :key="l.product" class="flex items-center gap-3">
						<div class="w-52 min-w-0 shrink-0 sm:w-72">
							<div class="truncate text-sm font-medium">{{ l.product }}</div>
							<div class="text-xs text-muted-foreground">{{ fmtQty(l.received) }} {{ l.unit.toLowerCase() }} received</div>
						</div>
						<div class="h-2.5 min-w-0 flex-1 overflow-hidden rounded-full bg-gray-100">
							<div
								class="h-full rounded-full bg-brand-500"
								:style="{ width: `${Math.min(100, (l.distributed / Math.max(l.received, 1)) * 100)}%` }"
							></div>
						</div>
						<span class="w-28 shrink-0 text-right text-sm font-semibold tabular-nums" :class="l.remaining > 0 ? 'text-brand-800' : 'text-gray-400'">
							{{ fmtQty(l.remaining) }} left
						</span>
					</div>
				</div>

				<!-- Entries -->
				<div v-if="!distributions.length" class="rounded-xl bg-gray-50 px-4 py-6 text-center text-sm text-muted-foreground">
					Nothing distributed yet — record where the goods go (a truck, a buyer, or storage).
				</div>
				<div v-else class="overflow-x-auto">
					<table class="w-full min-w-[680px] text-sm">
						<thead>
							<tr class="text-left">
								<th class="label-caps pb-2 pr-4">Date</th>
								<th class="label-caps pb-2 pr-4">Product</th>
								<th class="label-caps pb-2 pr-4 text-right">Qty</th>
								<th class="label-caps pb-2 pr-4">Recipient</th>
								<th class="label-caps pb-2 pr-4">Destination</th>
								<th class="label-caps pb-2 pr-4 text-right">Amount</th>
								<th class="label-caps pb-2 text-right">Actions</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="d in distributions" :key="d.name" class="border-t border-gray-100">
								<td class="py-2.5 pr-4 tabular-nums text-muted-foreground">{{ fmtDate(d.delivery_date) }}</td>
								<td class="py-2.5 pr-4">{{ d.product }}</td>
								<td class="py-2.5 pr-4 text-right tabular-nums">{{ fmtQty(d.qty) }} {{ (d.unit || "").toLowerCase() }}</td>
								<td class="py-2.5 pr-4 font-medium">{{ d.recipient }}</td>
								<td class="py-2.5 pr-4 text-muted-foreground">{{ d.destination || "—" }}</td>
								<td class="py-2.5 pr-4 text-right tabular-nums">{{ d.amount ? fmtMoney(d.amount) : "—" }}</td>
								<td class="py-2.5 text-right">
									<span class="inline-flex items-center gap-2">
										<RouterLink
											v-if="d.sales_invoice"
											:to="`/billing?tab=sales`"
											class="text-xs font-medium text-emerald-700 hover:underline"
										>{{ d.sales_invoice }}</RouterLink>
										<Button
											v-else-if="canBill && d.customer && (d.unit_price || 0) > 0"
											size="sm"
											variant="outline"
											:loading="invoicingDist === d.name"
											@click="invoiceDistribution(d)"
										>Invoice</Button>
										<button
											v-if="canDistribute && !d.sales_invoice"
											type="button"
											class="text-xs font-medium text-gray-400 hover:text-red-600"
											@click="deleteDistribution(d)"
										>Remove</button>
									</span>
								</td>
							</tr>
						</tbody>
					</table>
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

			<!-- ── Record distribution dialog ────────────────────────────────── -->
			<Dialog v-model:open="distOpen" title="Record distribution" size="wide">
				<div class="space-y-4">
					<div class="grid gap-4 sm:grid-cols-2">
						<div class="space-y-1.5">
							<Label required>Product</Label>
							<Select v-model="distForm.product" :options="productOptions" />
						</div>
						<div class="space-y-1.5">
							<Label required>Quantity</Label>
							<Input v-model.number="distForm.qty" type="number" min="0" :placeholder="selectedLine ? `${fmtQty(selectedLine.remaining)} remaining` : 'Qty'" />
							<p v-if="selectedLine && (distForm.qty || 0) > selectedLine.remaining" class="text-xs font-medium text-red-600">
								Only {{ fmtQty(selectedLine.remaining) }} {{ selectedLine.unit.toLowerCase() }} left on this line.
							</p>
						</div>
						<div class="space-y-1.5">
							<Label required>Recipient</Label>
							<Input v-model="distForm.recipient" placeholder='e.g. "Truck 1", "Ella", "Storage"' />
						</div>
						<div class="space-y-1.5">
							<Label>Destination</Label>
							<Input v-model="distForm.destination" placeholder="Where it's headed (optional)" />
						</div>
						<div class="space-y-1.5">
							<Label>Delivery date</Label>
							<Input v-model="distForm.delivery_date" type="date" />
						</div>
						<div class="space-y-1.5">
							<Label>Unit price (optional)</Label>
							<Input v-model.number="distForm.unit_price" type="number" min="0" placeholder="For invoicing later" />
						</div>
					</div>
					<div class="space-y-1.5">
						<Label>Customer (optional — enables invoicing)</Label>
						<SearchCombo
							v-model="distForm.customer"
							v-model:display-value="distCustomerDisplay"
							:fetcher="fetchCustomers"
							value-key="name"
							label-key="customer_name"
							sublabel-key="mobile_no"
							placeholder="Search customer… (leave empty for trucks/storage)"
						/>
					</div>
					<div class="space-y-1.5">
						<Label>Notes</Label>
						<Textarea v-model="distForm.notes" :rows="2" placeholder="Optional note" />
					</div>
				</div>
				<template #footer>
					<div class="flex justify-end gap-2">
						<Button variant="outline" @click="distOpen = false">Cancel</Button>
						<Button :loading="distSaving" @click="saveDistribution">Record</Button>
					</div>
				</template>
			</Dialog>

			<!-- ── Record event dialog ───────────────────────────────────────── -->
			<Dialog v-model:open="eventOpen" title="Record shipment event">
				<div class="space-y-4">
					<p class="rounded-xl bg-gray-50 px-4 py-3 text-xs text-muted-foreground">
						This event applies to <b>this shipment only</b> (e.g. "Received at warehouse",
						"Out for delivery"). Container-wide milestones are recorded on the container.
					</p>
					<div class="space-y-1.5">
						<Label required>Milestone</Label>
						<Input v-model="form.milestone" placeholder="e.g. Out for Delivery" />
					</div>
					<div class="space-y-1.5">
						<Label>Location</Label>
						<Input v-model="form.location" />
					</div>
					<div class="space-y-1.5">
						<Label>Remarks</Label>
						<Textarea v-model="form.remarks" :rows="2" />
					</div>
					<label class="flex cursor-pointer items-center gap-2.5 rounded-xl bg-brand-50 px-4 py-3">
						<input v-model="form.notify" type="checkbox" class="h-4 w-4 rounded accent-[#b8860b]" />
						<span class="text-sm font-medium">Notify this customer</span>
					</label>
				</div>
				<template #footer>
					<div class="flex justify-end gap-2">
						<Button variant="outline" @click="eventOpen = false">Cancel</Button>
						<Button :loading="saving" @click="recordEvent">Record</Button>
					</div>
				</template>
			</Dialog>
		</template>
	</div>
</template>
