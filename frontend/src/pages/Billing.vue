<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter, RouterLink } from "vue-router";
import {
	ReceiptText,
	Search,
	Wallet,
	AlertTriangle,
	HandCoins,
	Package,
	Plus,
	Trash2,
	ExternalLink,
	BadgePercent,
} from "lucide-vue-next";
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
import StatusBadge from "@/components/StatusBadge.vue";

const router = useRouter();
const toast = useToast();
const session = useSessionStore();
const canBill = computed(() =>
	session.hasRole("Logistics Manager", "Logistics Accounts", "System Manager", "Administrator"),
);

// ── overview ────────────────────────────────────────────────────────────────
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

// ── invoices ────────────────────────────────────────────────────────────────
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
onMounted(() => {
	loadOverview();
	loadInvoices();
	loadRateCards();
});

const columns: Column[] = [
	{ key: "name", label: "Invoice" },
	{ key: "customer_name", label: "Customer" },
	{ key: "posting_date", label: "Date" },
	{ key: "status", label: "Status" },
	{ key: "grand_total", label: "Total", numeric: true },
	{ key: "outstanding_amount", label: "Due", numeric: true },
	{ key: "actions", label: "", class: "w-36" },
];

function pdfUrl(name: string): string {
	return `/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Invoice&name=${encodeURIComponent(name)}`;
}

// ── create invoice from uninvoiced shipment ────────────────────────────────
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

// ── record payment ──────────────────────────────────────────────────────────
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

async function openPay(row: InvoiceRow) {
	payFor.value = row;
	payForm.amount = row.outstanding_amount;
	payForm.reference = "";
	try {
		const m = await call<string[]>("bwm_logistics.api.billing.modes_of_payment");
		if (m.length) {
			modes.value = m;
			if (!m.includes(payForm.mode)) payForm.mode = m[0];
		}
	} catch {
		/* keep Cash */
	}
}

async function recordPayment() {
	if (!payFor.value) return;
	paySaving.value = true;
	try {
		const res = await call<{ outstanding: number }>("bwm_logistics.api.billing.record_payment", {
			invoice: payFor.value.name,
			amount: payForm.amount,
			mode_of_payment: payForm.mode,
			reference: payForm.reference || null,
		});
		toast.success(
			res.outstanding > 0
				? `Payment recorded — ${fmtMoney(res.outstanding)} still due`
				: "Payment recorded — invoice settled",
		);
		payFor.value = null;
		await Promise.all([loadOverview(), loadInvoices()]);
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not record payment");
	} finally {
		paySaving.value = false;
	}
}

// ── rate cards ──────────────────────────────────────────────────────────────
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
</script>

<template>
	<div class="mx-auto max-w-6xl">
		<header class="mb-5">
			<h1 class="text-2xl font-semibold tracking-tight">Billing</h1>
			<p class="mt-1 text-sm text-muted-foreground">Invoices, payments, and your rate cards.</p>
		</header>

		<!-- KPI strip -->
		<div class="mb-5 grid grid-cols-2 gap-4 lg:grid-cols-4">
			<div class="rounded-3xl bg-white p-5 ring-1 ring-gray-100">
				<span class="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/10 text-amber-600"><Wallet class="h-5 w-5" /></span>
				<div class="text-2xl font-semibold tabular-nums">{{ fmtMoney(overview?.unpaid_total) }}</div>
				<div class="text-[13px] text-muted-foreground">Outstanding ({{ overview?.unpaid_count ?? "…" }} invoices)</div>
			</div>
			<div class="rounded-3xl bg-white p-5 ring-1 ring-gray-100">
				<span class="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-red-500/10 text-red-600"><AlertTriangle class="h-5 w-5" /></span>
				<div class="text-2xl font-semibold tabular-nums">{{ overview?.overdue_count ?? "…" }}</div>
				<div class="text-[13px] text-muted-foreground">Overdue invoices</div>
			</div>
			<div class="rounded-3xl bg-white p-5 ring-1 ring-gray-100">
				<span class="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600"><HandCoins class="h-5 w-5" /></span>
				<div class="text-2xl font-semibold tabular-nums">{{ fmtMoney(overview?.collected_this_month) }}</div>
				<div class="text-[13px] text-muted-foreground">Collected this month</div>
			</div>
			<div class="rounded-3xl bg-white p-5 ring-1 ring-gray-100">
				<span class="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600/10 text-brand-700"><Package class="h-5 w-5" /></span>
				<div class="text-2xl font-semibold tabular-nums">{{ overview?.uninvoiced?.length ?? "…" }}</div>
				<div class="text-[13px] text-muted-foreground">Shipments to invoice</div>
			</div>
		</div>

		<!-- Uninvoiced shipments -->
		<div v-if="overview?.uninvoiced?.length && canBill" class="mb-6 rounded-3xl bg-brand-50 p-5 ring-1 ring-brand-200">
			<div class="label-caps mb-3 !text-brand-800">Ready to invoice</div>
			<div class="flex flex-wrap gap-2">
				<div
					v-for="s in overview.uninvoiced.slice(0, 6)"
					:key="s.name"
					class="flex items-center gap-3 rounded-xl bg-white px-4 py-2.5 shadow-xs"
				>
					<RouterLink :to="`/shipments/${s.name}`" class="text-sm font-medium text-brand-700 hover:underline">{{ s.name }}</RouterLink>
					<span class="text-xs text-muted-foreground">{{ s.customer_name }} · {{ fmtMoney(s.total_charges) }}</span>
					<Button size="sm" :loading="invoicing === s.name" @click="makeInvoice(s.name)">Invoice</Button>
				</div>
				<span v-if="overview.uninvoiced.length > 6" class="self-center text-xs text-muted-foreground">
					+{{ overview.uninvoiced.length - 6 }} more
				</span>
			</div>
		</div>

		<!-- Invoice filters -->
		<div class="mb-4 flex flex-wrap items-center gap-2">
			<div class="relative min-w-56 flex-1 sm:max-w-xs">
				<Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
				<Input v-model="search" placeholder="Search invoice, customer…" class="pl-9" />
			</div>
			<div class="flex gap-1.5">
				<button
					v-for="s in ['', 'Unpaid', 'Overdue', 'Paid']"
					:key="s"
					type="button"
					class="rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors"
					:class="statusFilter === s ? 'bg-brand-600 text-white' : 'bg-white text-gray-600 ring-1 ring-gray-200 hover:bg-gray-50'"
					@click="statusFilter = s"
				>
					{{ s || "All" }}
				</button>
			</div>
		</div>

		<DataTable
			:columns="columns"
			:rows="rows"
			:loading="loading"
			:total="total"
			empty-text="No invoices match."
			@load-more="loadInvoices(true)"
		>
			<template #cell-name="{ row }">
				<div>
					<span class="inline-flex items-center gap-2 font-medium"><ReceiptText class="h-4 w-4 text-brand-700" /> {{ row.name }}</span>
					<RouterLink
						v-if="row.shipment"
						:to="`/shipments/${row.shipment}`"
						class="block text-xs text-brand-700 hover:underline"
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
						title="Download PDF"
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

		<!-- Rate cards -->
		<div class="mt-8">
			<div class="mb-3 flex items-center justify-between">
				<h2 class="flex items-center gap-2 text-lg font-semibold tracking-tight">
					<BadgePercent class="h-5 w-5 text-brand-700" /> Rate cards
				</h2>
				<Button v-if="canBill" variant="outline" @click="openCard()"><Plus class="h-4 w-4" /> New rate card</Button>
			</div>
			<div v-if="!rateCards.length" class="rounded-3xl bg-white p-10 text-center text-sm text-muted-foreground ring-1 ring-gray-100">
				No rate cards yet — define your pricing once, then apply it to any shipment with one click.
			</div>
			<div v-else class="grid gap-4 sm:grid-cols-2">
				<div v-for="c in rateCards" :key="c.name" class="rounded-3xl bg-white p-5 ring-1 ring-gray-100">
					<div class="mb-3 flex items-start justify-between gap-2">
						<div>
							<div class="font-semibold">{{ c.card_name }}</div>
							<div class="text-xs text-muted-foreground">
								{{ c.direction || "Any direction" }}
								<span v-if="c.is_default" class="ml-1 rounded-full bg-brand-600/10 px-2 py-0.5 text-[10.5px] font-bold text-brand-700">DEFAULT</span>
							</div>
						</div>
						<div v-if="canBill" class="flex gap-1">
							<Button size="sm" variant="ghost" @click="openCard(c)">Edit</Button>
							<button
								type="button"
								class="flex h-8 w-8 items-center justify-center rounded-lg text-gray-400 hover:bg-red-50 hover:text-red-600"
								@click="deleteCard(c)"
							>
								<Trash2 class="h-4 w-4" />
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
		</div>

		<!-- ── Record payment dialog ─────────────────────────────────────── -->
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

		<!-- ── Rate card editor ──────────────────────────────────────────── -->
		<Dialog v-model:open="cardOpen" :title="cardForm.name ? 'Edit rate card' : 'New rate card'" size="wide">
			<div class="grid gap-4 sm:grid-cols-3">
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
				<div class="space-y-2">
					<div v-for="(i, idx) in cardForm.items" :key="idx" class="flex items-center gap-2">
						<Input v-model="i.charge_type" placeholder="Charge (e.g. Freight)" class="flex-1" />
						<Select v-model="i.calc_basis" :options="['Flat', 'Per KG', 'Per CBM', 'Per Package']" class="w-36" />
						<Input v-model.number="i.rate" type="number" min="0" step="0.01" placeholder="Rate" class="w-28" />
						<Input v-model.number="i.minimum" type="number" min="0" step="0.01" placeholder="Min" class="w-24" />
						<button
							type="button"
							class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-gray-400 hover:bg-red-50 hover:text-red-600"
							:disabled="cardForm.items.length === 1"
							@click="cardForm.items.splice(idx, 1)"
						>
							<Trash2 class="h-4 w-4" />
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
