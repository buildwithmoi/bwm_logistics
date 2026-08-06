<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute, useRouter, RouterLink } from "vue-router";
import { Search, Package, Plus, Trash2, ExternalLink, ShoppingCart } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtDate, fmtMoney } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Select from "@/components/ui/Select.vue";
import Dialog from "@/components/ui/Dialog.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
import PageHeader from "@/components/ui/PageHeader.vue";
import StatCard from "@/components/ui/StatCard.vue";
import StatusBadge from "@/components/StatusBadge.vue";

const route = useRoute();
const router = useRouter();
const toast = useToast();
const session = useSessionStore();
const canBill = computed(() =>
	session.hasRole("Logistics Manager", "Logistics Accounts", "System Manager", "Administrator"),
);

// ── tabs (query-param driven so other pages can deep-link) ──────────────────
const TABS = [
	{ key: "sales", label: "Sales" },
	{ key: "purchases", label: "Purchases" },
	{ key: "ratecards", label: "Rate cards" },
] as const;
type TabKey = (typeof TABS)[number]["key"];
const tab = ref<TabKey>((route.query.tab as TabKey) || "sales");
watch(tab, (t) => router.replace({ query: { ...route.query, tab: t } }));

// ═══════════════════════════ SALES ══════════════════════════════════════════
interface Overview {
	unpaid_total: number;
	unpaid_count: number;
	overdue_count: number;
	collected_this_month: number;
	uninvoiced: Array<{ name: string; customer_name?: string; total_charges: number }>;
}
const overview = ref<Overview | null>(null);
async function loadOverview() {
	try {
		overview.value = await call<Overview>("bwm_logistics.api.billing.overview");
	} catch {
		/* tiles degrade */
	}
}

const rows = ref<Record<string, unknown>[]>([]);
const total = ref(0);
const loading = ref(false);
const search = ref("");
const statusFilter = ref("Unpaid");
const PAGE = 25;

async function loadInvoices(append = false) {
	loading.value = true;
	try {
		const res = await call<{ rows: Record<string, unknown>[]; total: number }>(
			"bwm_logistics.api.billing.list_invoices",
			{
				status: statusFilter.value || null,
				search: search.value || null,
				start: append ? rows.value.length : 0,
				limit: PAGE,
			},
		);
		rows.value = append ? [...rows.value, ...res.rows] : res.rows;
		total.value = res.total;
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load invoices");
	} finally {
		loading.value = false;
	}
}
let searchTimer: ReturnType<typeof setTimeout>;
watch(search, () => {
	clearTimeout(searchTimer);
	searchTimer = setTimeout(() => loadInvoices(), 300);
});
watch(statusFilter, () => loadInvoices());

const invoiceColumns: Column[] = [
	{ key: "name", label: "Invoice", primary: true, nowrap: true },
	{ key: "customer_name", label: "Customer" },
	{ key: "posting_date", label: "Date", nowrap: true },
	{ key: "status", label: "Status", trailing: true },
	{ key: "grand_total", label: "Total", numeric: true },
	{ key: "outstanding_amount", label: "Due", numeric: true },
	{ key: "actions", label: "", class: "w-36", trailing: true },
];

// Branded server PDF (BWM Invoice print format).
function pdfUrl(name: string): string {
	return `/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Invoice&name=${encodeURIComponent(name)}&format=BWM%20Invoice&no_letterhead=1`;
}

const invoicing = ref<string | null>(null);
async function makeInvoice(shipment: string) {
	invoicing.value = shipment;
	try {
		const res = await call<{ sales_invoice: string }>("bwm_logistics.api.shipments.make_invoice", {
			shipment,
		});
		toast.success(`Invoice ${res.sales_invoice} created`);
		await Promise.all([loadOverview(), loadInvoices()]);
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not create invoice");
	} finally {
		invoicing.value = null;
	}
}

// New invoices are created on their own page (/billing/invoice/new) — a
// dialog couldn't hold the line-item table on a phone.

// ── record customer payment ─────────────────────────────────────────────────
interface InvoiceRow extends Record<string, unknown> {
	name: string;
	customer_name?: string;
	outstanding_amount: number;
	currency?: string;
}
const payFor = ref<InvoiceRow | null>(null);
const paySaving = ref(false);
const payForm = reactive({ amount: 0, mode: "Cash", reference: "" });
const modes = ref<string[]>(["Cash"]);

async function loadModes() {
	try {
		const m = await call<string[]>("bwm_logistics.api.billing.modes_of_payment");
		if (m.length) modes.value = m;
	} catch {
		/* keep Cash */
	}
}
function openPay(row: InvoiceRow) {
	payFor.value = row;
	payForm.amount = row.outstanding_amount;
	payForm.reference = "";
	if (!modes.value.includes(payForm.mode)) payForm.mode = modes.value[0];
}
async function recordPayment() {
	if (!payFor.value) return;
	paySaving.value = true;
	try {
		const res = await call<{ outstanding: number; payment_entry: string }>(
			"bwm_logistics.api.billing.record_payment",
			{
				invoice: payFor.value.name,
				amount: payForm.amount,
				mode_of_payment: payForm.mode,
				reference: payForm.reference || null,
			},
		);
		toast.success(
			res.outstanding > 0 ? `Payment recorded — ${fmtMoney(res.outstanding)} still due` : "Invoice settled",
		);
		payFor.value = null;
		router.push(`/billing/receipt/${res.payment_entry}`);
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not record payment");
	} finally {
		paySaving.value = false;
	}
}

// ═════════════════════════ PURCHASES ════════════════════════════════════════
interface PurchOverview {
	owed_total: number;
	owed_count: number;
	spent_this_month: number;
}
const purchOverview = ref<PurchOverview | null>(null);
const purchases = ref<Record<string, unknown>[]>([]);
const purchTotal = ref(0);
const purchLoading = ref(false);
const purchStatus = ref("Unpaid");
const purchSearch = ref("");

async function loadPurchases(append = false) {
	purchLoading.value = true;
	try {
		const [ov, res] = await Promise.all([
			call<PurchOverview>("bwm_logistics.api.purchasing.purchases_overview"),
			call<{ rows: Record<string, unknown>[]; total: number }>(
				"bwm_logistics.api.purchasing.list_purchases",
				{
					status: purchStatus.value || null,
					search: purchSearch.value || null,
					start: append ? purchases.value.length : 0,
					limit: PAGE,
				},
			),
		]);
		purchOverview.value = ov;
		purchases.value = append ? [...purchases.value, ...res.rows] : res.rows;
		purchTotal.value = res.total;
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load purchases");
	} finally {
		purchLoading.value = false;
	}
}
let purchTimer: ReturnType<typeof setTimeout>;
watch(purchSearch, () => {
	clearTimeout(purchTimer);
	purchTimer = setTimeout(() => loadPurchases(), 300);
});
watch(purchStatus, () => loadPurchases());
watch(tab, (t) => {
	if (t === "purchases" && !purchOverview.value) loadPurchases();
});

const purchaseColumns: Column[] = [
	{ key: "name", label: "Purchase", primary: true, nowrap: true },
	{ key: "supplier_name", label: "Supplier" },
	{ key: "posting_date", label: "Date", nowrap: true },
	{ key: "bwm_shipment", label: "Shipment" },
	{ key: "grand_total", label: "Total", numeric: true },
	{ key: "outstanding_amount", label: "Owed", numeric: true },
	{ key: "pactions", label: "", class: "w-32", trailing: true },
];

// Purchases likewise get a page (/billing/purchase/new).

// ── pay supplier ────────────────────────────────────────────────────────────
interface PurchaseRow extends Record<string, unknown> {
	name: string;
	supplier_name?: string;
	outstanding_amount: number;
	currency?: string;
}
const payPurchFor = ref<PurchaseRow | null>(null);
const payPurchSaving = ref(false);
const payPurchForm = reactive({ amount: 0, mode: "Cash", reference: "" });
function openPayPurchase(row: PurchaseRow) {
	payPurchFor.value = row;
	payPurchForm.amount = row.outstanding_amount;
	payPurchForm.reference = "";
}
async function paySupplier() {
	if (!payPurchFor.value) return;
	payPurchSaving.value = true;
	try {
		const res = await call<{ outstanding: number }>("bwm_logistics.api.purchasing.pay_supplier", {
			purchase_invoice: payPurchFor.value.name,
			amount: payPurchForm.amount,
			mode_of_payment: payPurchForm.mode,
			reference: payPurchForm.reference || null,
		});
		toast.success(
			res.outstanding > 0 ? `Paid — ${fmtMoney(res.outstanding)} still owed` : "Supplier bill settled",
		);
		payPurchFor.value = null;
		await loadPurchases();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not record payment");
	} finally {
		payPurchSaving.value = false;
	}
}

// ═════════════════════════ RATE CARDS ═══════════════════════════════════════
interface RateItem {
	charge_type: string;
	calc_basis: string;
	rate: number | null;
	minimum?: number | null;
}
interface RateCard {
	name?: string;
	card_name: string;
	direction?: string;
	is_default?: number;
	items: RateItem[];
}
const rateCards = ref<RateCard[]>([]);
async function loadRateCards() {
	try {
		rateCards.value = await call<RateCard[]>("bwm_logistics.api.billing.list_rate_cards");
	} catch {
		/* section degrades */
	}
}
const cardOpen = ref(false);
const cardSaving = ref(false);
const cardForm = reactive<RateCard>({ card_name: "", direction: "", is_default: 0, items: [] });
function openCard(card?: RateCard) {
	Object.assign(cardForm, {
		name: card?.name,
		card_name: card?.card_name || "",
		direction: card?.direction || "",
		is_default: card?.is_default || 0,
		items: card ? card.items.map((i) => ({ ...i })) : [{ charge_type: "", calc_basis: "Flat", rate: null }],
	});
	cardOpen.value = true;
}
async function saveCard() {
	if (!cardForm.card_name.trim() || !cardForm.items.some((i) => i.charge_type && i.rate)) {
		toast.warning("Name the card and add at least one charge with a rate");
		return;
	}
	cardSaving.value = true;
	try {
		await call("bwm_logistics.api.billing.save_rate_card", { payload: { ...cardForm } });
		toast.success("Rate card saved");
		cardOpen.value = false;
		await loadRateCards();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not save rate card");
	} finally {
		cardSaving.value = false;
	}
}
async function deleteCard(card: RateCard) {
	if (!card.name) return;
	try {
		await call("bwm_logistics.api.billing.delete_rate_card", { name: card.name });
		toast.info(`Deleted ${card.card_name}`);
		await loadRateCards();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not delete");
	}
}

// ── boot + deep links (?tab=&shipment=&new=1) ───────────────────────────────
onMounted(() => {
	// `?new=1` used to pop a dialog here; the create screens are pages now, so
	// the old links (and any bookmarks) forward to them, carrying the shipment.
	if (route.query.new === "1") {
		const shipment = route.query.shipment as string | undefined;
		router.replace({
			path: tab.value === "purchases" ? "/billing/purchase/new" : "/billing/invoice/new",
			query: shipment ? { shipment } : {},
		});
		return;
	}
	loadOverview();
	loadInvoices();
	loadRateCards();
	loadModes();
	if (tab.value === "purchases") loadPurchases();
});
</script>

<template>
	<div class="mx-auto max-w-6xl">
		<PageHeader title="Billing" subtitle="Sales, purchases, and your rate cards.">
			<template v-if="canBill" #actions>
				<Button v-if="tab === 'purchases'" @click="router.push('/billing/purchase/new')">
					<ShoppingCart class="h-4 w-4" aria-hidden="true" /> Record purchase
				</Button>
				<Button v-else-if="tab === 'sales'" @click="router.push('/billing/invoice/new')">
					<Plus class="h-4 w-4" aria-hidden="true" /> New invoice
				</Button>
				<Button v-else variant="outline" @click="openCard()"><Plus class="h-4 w-4" aria-hidden="true" /> New rate card</Button>
			</template>
		</PageHeader>

		<!-- Tabs -->
		<div class="chip-row mb-5" role="group" aria-label="Billing section">
			<button
				v-for="t in TABS"
				:key="t.key"
				type="button"
				class="chip !px-4 !py-2 !text-sm"
				:class="tab === t.key ? 'chip-seg-on' : 'chip-off'"
				:aria-pressed="tab === t.key"
				@click="tab = t.key"
			>
				{{ t.label }}
			</button>
		</div>

		<!-- ═════════════ SALES ═════════════ -->
		<template v-if="tab === 'sales'">
			<div class="mb-5 grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
				<StatCard :value="fmtMoney(overview?.unpaid_total)" :label="`Outstanding (${overview?.unpaid_count ?? '…'} invoices)`" />
				<StatCard :value="overview?.overdue_count ?? '…'" label="Overdue invoices" />
				<StatCard :value="fmtMoney(overview?.collected_this_month)" label="Collected this month" />
				<StatCard :value="overview?.uninvoiced?.length ?? '…'" label="Shipments to invoice" />
			</div>

			<div v-if="overview?.uninvoiced?.length && canBill" class="mb-5 rounded-2xl bg-brand-50 p-4 ring-1 ring-brand-200 sm:p-5">
				<div class="label-caps mb-3 !text-brand-800">Ready to invoice</div>
				<div class="flex flex-wrap gap-2">
					<div
						v-for="s in overview.uninvoiced.slice(0, 6)"
						:key="s.name"
						class="flex min-w-0 max-w-full items-center gap-3 rounded-xl bg-white px-3.5 py-2.5 shadow-xs"
					>
						<div class="min-w-0">
							<RouterLink :to="`/shipments/${s.name}`" class="block truncate text-sm font-medium text-brand-700 hover:underline">{{ s.name }}</RouterLink>
							<span class="block truncate text-xs text-muted-foreground">{{ s.customer_name }} · {{ fmtMoney(s.total_charges) }}</span>
						</div>
						<Button size="sm" class="shrink-0" :loading="invoicing === s.name" @click="makeInvoice(s.name)">Invoice</Button>
					</div>
					<span v-if="overview.uninvoiced.length > 6" class="self-center text-xs text-muted-foreground">
						+{{ overview.uninvoiced.length - 6 }} more
					</span>
				</div>
			</div>

			<div class="mb-4 space-y-3">
				<div class="relative sm:max-w-xs">
					<Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" aria-hidden="true" />
					<Input v-model="search" type="search" aria-label="Search invoices" placeholder="Search invoice, customer…" class="pl-9" />
				</div>
				<div class="chip-row" role="group" aria-label="Invoice status">
					<button
						v-for="s in ['', 'Unpaid', 'Overdue', 'Paid']"
						:key="s"
						type="button"
						class="chip"
						:class="statusFilter === s ? 'chip-on' : 'chip-off'"
						:aria-pressed="statusFilter === s"
						@click="statusFilter = s"
					>
						{{ s || "All" }}
					</button>
				</div>
			</div>

			<DataTable
				:columns="invoiceColumns"
				:rows="rows"
				:loading="loading"
				:total="total"
				empty-text="No invoices match."
				@load-more="loadInvoices(true)"
			>
				<template #cell-name="{ row }">
					<div class="min-w-0">
						<span class="font-medium">{{ row.name }}</span>
						<RouterLink
							v-if="row.shipment"
							:to="`/shipments/${row.shipment}`"
							class="block truncate text-xs text-brand-700 hover:underline"
							@click.stop
						>{{ row.shipment }}</RouterLink>
					</div>
				</template>
				<template #cell-posting_date="{ value }">{{ fmtDate(value as string) }}</template>
				<template #cell-status="{ value }"><StatusBadge :status="String(value)" /></template>
				<template #cell-grand_total="{ row }">{{ fmtMoney(row.grand_total as number, row.currency as string) }}</template>
				<template #cell-outstanding_amount="{ row }">
					<span :class="(row.outstanding_amount as number) > 0 ? 'font-semibold text-amber-700' : 'text-muted-foreground'">
						{{ fmtMoney(row.outstanding_amount as number, row.currency as string) }}
					</span>
				</template>
				<template #cell-actions="{ row }">
					<div class="flex items-center justify-end gap-1.5">
						<a
							:href="pdfUrl(String(row.name))"
							target="_blank"
							rel="noopener"
							class="flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
							title="Download branded PDF"
							@click.stop
						>
							<ExternalLink class="h-4 w-4" />
						</a>
						<Button
							v-if="canBill && (row.outstanding_amount as number) > 0"
							size="sm"
							variant="outline"
							@click.stop="openPay(row as InvoiceRow)"
						>
							Record payment
						</Button>
					</div>
				</template>
			</DataTable>
		</template>

		<!-- ═════════════ PURCHASES ═════════════ -->
		<template v-else-if="tab === 'purchases'">
			<div class="mb-5 grid grid-cols-2 gap-3 sm:gap-4">
				<StatCard
					:value="fmtMoney(purchOverview?.owed_total)"
					:label="`Owed to suppliers (${purchOverview?.owed_count ?? '…'} bills)`"
				/>
				<StatCard :value="fmtMoney(purchOverview?.spent_this_month)" label="Purchased this month" />
			</div>

			<div class="mb-4 space-y-3">
				<div class="relative sm:max-w-xs">
					<Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" aria-hidden="true" />
					<Input v-model="purchSearch" type="search" aria-label="Search purchases" placeholder="Search purchase, supplier, bill no…" class="pl-9" />
				</div>
				<div class="chip-row" role="group" aria-label="Purchase status">
					<button
						v-for="s in ['', 'Unpaid', 'Paid']"
						:key="s"
						type="button"
						class="chip"
						:class="purchStatus === s ? 'chip-on' : 'chip-off'"
						:aria-pressed="purchStatus === s"
						@click="purchStatus = s"
					>
						{{ s || "All" }}
					</button>
				</div>
			</div>

			<DataTable
				:columns="purchaseColumns"
				:rows="purchases"
				:loading="purchLoading"
				:total="purchTotal"
				empty-text="No purchases yet — record your first supplier bill."
				@load-more="loadPurchases(true)"
			>
				<template #cell-name="{ row }">
					<div>
						<span class="inline-flex items-center gap-2 font-medium"><ShoppingCart class="h-4 w-4 text-brand-700" /> {{ row.name }}</span>
						<span v-if="row.bill_no" class="block text-xs text-muted-foreground">Bill: {{ row.bill_no }}</span>
					</div>
				</template>
				<template #cell-posting_date="{ value }">{{ fmtDate(value as string) }}</template>
				<template #cell-bwm_shipment="{ value }">
					<RouterLink
						v-if="value"
						:to="`/shipments/${value}`"
						class="text-brand-700 hover:underline"
						@click.stop
					>{{ value }}</RouterLink>
					<span v-else class="text-gray-400">—</span>
				</template>
				<template #cell-grand_total="{ row }">{{ fmtMoney(row.grand_total as number, row.currency as string) }}</template>
				<template #cell-outstanding_amount="{ row }">
					<span :class="(row.outstanding_amount as number) > 0 ? 'font-semibold text-amber-700' : 'text-muted-foreground'">
						{{ fmtMoney(row.outstanding_amount as number, row.currency as string) }}
					</span>
				</template>
				<template #cell-pactions="{ row }">
					<div class="flex justify-end">
						<Button
							v-if="canBill && (row.outstanding_amount as number) > 0"
							size="sm"
							variant="outline"
							@click.stop="openPayPurchase(row as PurchaseRow)"
						>
							Pay supplier
						</Button>
					</div>
				</template>
			</DataTable>
		</template>

		<!-- ═════════════ RATE CARDS ═════════════ -->
		<template v-else>
			<div v-if="!rateCards.length" class="rounded-2xl bg-white p-10 text-center text-sm text-muted-foreground ring-1 ring-gray-100">
				No rate cards yet — define your pricing once, then apply it to any shipment with one click.
			</div>
			<div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2">
				<div v-for="c in rateCards" :key="c.name" class="rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-5">
					<div class="mb-3 flex items-start justify-between gap-2">
						<div class="min-w-0">
							<div class="truncate font-semibold">{{ c.card_name }}</div>
							<div class="text-xs text-muted-foreground">
								{{ c.direction || "Any direction" }}
								<span v-if="c.is_default" class="ml-1 rounded-full bg-brand-600/10 px-2 py-0.5 text-[10.5px] font-bold text-brand-700">DEFAULT</span>
							</div>
						</div>
						<div v-if="canBill" class="flex shrink-0 gap-1">
							<Button size="sm" variant="ghost" @click="openCard(c)">Edit</Button>
							<button
								type="button"
								class="flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
								:aria-label="`Delete rate card ${c.card_name}`"
								@click="deleteCard(c)"
							>
								<Trash2 class="h-4 w-4" aria-hidden="true" />
							</button>
						</div>
					</div>
					<ul class="divide-y divide-gray-100 text-sm">
						<li v-for="(i, idx) in c.items" :key="idx" class="flex justify-between py-1.5">
							<span>{{ i.charge_type }} <span class="text-xs text-muted-foreground">({{ i.calc_basis }})</span></span>
							<span class="tabular-nums">{{ fmtMoney(i.rate) }}<span v-if="i.minimum" class="text-xs text-muted-foreground"> min {{ fmtMoney(i.minimum) }}</span></span>
						</li>
					</ul>
				</div>
			</div>
		</template>

		<!-- ══ New invoice dialog ══ -->


		<!-- ══ Record customer payment ══ -->
		<Dialog :open="!!payFor" title="Record payment" @update:open="payFor = null">
			<div class="space-y-4">
				<p class="rounded-xl bg-gray-50 px-4 py-3 text-sm">
					<b>{{ payFor?.name }}</b> · {{ payFor?.customer_name }}
					<span class="block text-xs text-muted-foreground">
						Outstanding: {{ fmtMoney(payFor?.outstanding_amount, payFor?.currency) }} — partial amounts are fine.
					</span>
				</p>
				<div class="grid grid-cols-2 gap-3">
					<div class="space-y-1.5">
						<Label required>Amount</Label>
						<Input v-model.number="payForm.amount" type="number" min="0" step="0.01" />
					</div>
					<div class="space-y-1.5">
						<Label>Mode</Label>
						<Select v-model="payForm.mode" :options="modes" />
					</div>
				</div>
				<div class="space-y-1.5">
					<Label>Reference (receipt no, MoMo ID…)</Label>
					<Input v-model="payForm.reference" />
				</div>
			</div>
			<template #footer>
				<div class="flex justify-end gap-2">
					<Button variant="outline" @click="payFor = null">Cancel</Button>
					<Button :loading="paySaving" @click="recordPayment">Record payment</Button>
				</div>
			</template>
		</Dialog>

		<!-- ══ Pay supplier ══ -->
		<Dialog :open="!!payPurchFor" title="Pay supplier" @update:open="payPurchFor = null">
			<div class="space-y-4">
				<p class="rounded-xl bg-gray-50 px-4 py-3 text-sm">
					<b>{{ payPurchFor?.name }}</b> · {{ payPurchFor?.supplier_name }}
					<span class="block text-xs text-muted-foreground">
						Owed: {{ fmtMoney(payPurchFor?.outstanding_amount, payPurchFor?.currency) }} — partial amounts are fine.
					</span>
				</p>
				<div class="grid grid-cols-2 gap-3">
					<div class="space-y-1.5">
						<Label required>Amount</Label>
						<Input v-model.number="payPurchForm.amount" type="number" min="0" step="0.01" />
					</div>
					<div class="space-y-1.5">
						<Label>Mode</Label>
						<Select v-model="payPurchForm.mode" :options="modes" />
					</div>
				</div>
				<div class="space-y-1.5">
					<Label>Reference</Label>
					<Input v-model="payPurchForm.reference" />
				</div>
			</div>
			<template #footer>
				<div class="flex justify-end gap-2">
					<Button variant="outline" @click="payPurchFor = null">Cancel</Button>
					<Button :loading="payPurchSaving" @click="paySupplier">Pay supplier</Button>
				</div>
			</template>
		</Dialog>

		<!-- ══ Rate card editor ══ -->
		<Dialog v-model:open="cardOpen" :title="cardForm.name ? 'Edit rate card' : 'New rate card'" size="wide">
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
				<div class="space-y-1.5 sm:col-span-2">
					<Label required>Name</Label>
					<Input v-model="cardForm.card_name" placeholder="e.g. Standard Import Rates" />
				</div>
				<div class="space-y-1.5">
					<Label>Direction</Label>
					<Select v-model="cardForm.direction" :options="[{ value: '', label: 'Any' }, 'Import', 'Export']" />
				</div>
			</div>
			<label class="mt-3 flex cursor-pointer items-center gap-2.5 text-sm">
				<input
					type="checkbox"
					class="h-4 w-4 rounded accent-[#b8860b]"
					:checked="!!cardForm.is_default"
					@change="cardForm.is_default = cardForm.is_default ? 0 : 1"
				/>
				Use as the default card
			</label>
			<div class="mt-5">
				<div class="mb-2 flex items-center justify-between">
					<Label required>Charges</Label>
					<button
						type="button"
						class="text-xs font-medium text-brand-700 hover:underline"
						@click="cardForm.items.push({ charge_type: '', calc_basis: 'Flat', rate: null })"
					>+ Add charge</button>
				</div>
				<div class="space-y-3">
					<div
						v-for="(i, idx) in cardForm.items"
						:key="idx"
						class="rounded-xl border border-border p-3 sm:flex sm:items-center sm:gap-2 sm:border-0 sm:p-0"
					>
						<Input v-model="i.charge_type" placeholder="Charge (e.g. Freight)" class="sm:min-w-0 sm:flex-1" />
						<div class="mt-2 grid grid-cols-3 gap-2 sm:mt-0 sm:flex sm:items-center">
							<Select v-model="i.calc_basis" :options="['Flat', 'Per KG', 'Per CBM', 'Per Package']" class="sm:w-36" />
							<Input v-model.number="i.rate" type="number" min="0" step="0.01" placeholder="Rate" class="sm:w-28" />
							<Input v-model.number="i.minimum" type="number" min="0" step="0.01" placeholder="Min" class="sm:w-24" />
						</div>
						<button
							type="button"
							class="mt-2 flex h-9 w-full shrink-0 items-center justify-center gap-1.5 rounded-lg text-[13px] text-gray-500 hover:bg-red-50 hover:text-red-600 disabled:opacity-40 sm:mt-0 sm:w-9 sm:text-transparent"
							:disabled="cardForm.items.length === 1"
							:aria-label="`Remove charge ${idx + 1}`"
							@click="cardForm.items.splice(idx, 1)"
						>
							<Trash2 class="h-4 w-4 text-gray-400" aria-hidden="true" />
							<span class="sm:hidden">Remove</span>
						</button>
					</div>
				</div>
			</div>
			<template #footer>
				<div class="flex justify-end gap-2">
					<Button variant="outline" @click="cardOpen = false">Cancel</Button>
					<Button :loading="cardSaving" @click="saveCard">Save rate card</Button>
				</div>
			</template>
		</Dialog>
	</div>
</template>
