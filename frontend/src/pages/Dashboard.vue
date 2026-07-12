<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import {
	Container,
	Package,
	ReceiptText,
	Wallet,
	HandCoins,
	AlertTriangle,
	TrendingUp,
	Activity,
	Ship,
	ArrowRight,
} from "lucide-vue-next";
import { RouterLink } from "vue-router";
import { useSessionStore } from "@/stores/session";
import { call } from "@/lib/frappe";
import { fmtDate, fmtDateTime, fmtMoney } from "@/lib/format";
import BarChart, { type BarGroup } from "@/components/BarChart.vue";
import DirectionBadge from "@/components/DirectionBadge.vue";
import StatusBadge from "@/components/StatusBadge.vue";

// Executive dashboard (P7): money, operations, risk, and movement in one
// screen. Profit renders only when the server includes it (Managers/Accounts).
const session = useSessionStore();

const firstName = computed(
	() => (session.user?.full_name || session.user?.first_name || "").split(/\s+/)[0] || "there",
);
const today = new Date().toLocaleDateString(undefined, {
	weekday: "long",
	month: "long",
	day: "numeric",
});

interface Overview {
	revenue_mtd: number;
	collected_mtd: number;
	outstanding_total: number;
	overdue_count: number;
	containers_active: number;
	containers_import: number;
	containers_export: number;
	shipments_active: number;
	shipments_import: number;
	shipments_export: number;
	pipeline: Array<{ status: string; count: number }>;
	demurrage_risk: Array<{ name: string; container_no?: string; days_left: number }>;
	cod_unreconciled: number;
	arriving_week: Array<{ name: string; container_no?: string; eta?: string; vessel?: string; port_of_discharge?: string; direction?: string }>;
	top_customers: Array<{ customer: string; total: number }>;
	recent_payments: Array<{ name: string; posting_date: string; party_name?: string; paid_amount: number; mode_of_payment?: string }>;
	revenue_months: Array<{ label: string; invoiced: number; collected: number }>;
	shipment_months: Array<{ label: string; imports: number; exports: number }>;
	recent_events: Array<{ name: string; event_datetime: string; milestone: string; location?: string; container?: string; shipment?: string }>;
	profit_mtd?: number;
	spent_mtd?: number;
}
const data = ref<Overview | null>(null);
const loading = ref(true);

onMounted(async () => {
	try {
		data.value = await call<Overview>("bwm_logistics.api.dashboard.get_overview");
	} finally {
		loading.value = false;
	}
});

const revenueGroups = computed<BarGroup[]>(
	() => data.value?.revenue_months.map((m) => ({ label: m.label, a: m.invoiced, b: m.collected })) || [],
);
const shipmentGroups = computed<BarGroup[]>(
	() => data.value?.shipment_months.map((m) => ({ label: m.label, a: m.imports, b: m.exports })) || [],
);
const pipelineTotal = computed(() => data.value?.pipeline.reduce((n, p) => n + p.count, 0) || 0);
const hasProfit = computed(() => data.value?.profit_mtd !== undefined);
</script>

<template>
	<div class="mx-auto max-w-7xl">
		<!-- Greeting -->
		<header class="mb-6 flex flex-wrap items-center gap-4">
			<div class="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-400 to-brand-600 text-lg font-bold text-coal-900">
				{{ firstName[0]?.toUpperCase() || "B" }}
			</div>
			<div class="min-w-0 flex-1">
				<h1 class="text-2xl font-semibold tracking-tight sm:text-3xl">Good day, {{ firstName }} 👋</h1>
			</div>
			<span class="rounded-full bg-gray-100 px-4 py-1.5 text-sm text-gray-600">{{ today }}</span>
		</header>

		<div v-if="loading" class="py-16 text-center text-sm text-muted-foreground">Loading…</div>
		<template v-else-if="data">
			<!-- Demurrage banner -->
			<div
				v-if="data.demurrage_risk.length"
				class="mb-4 flex flex-wrap items-center gap-3 rounded-2xl bg-red-50 px-5 py-3.5 ring-1 ring-red-200"
			>
				<AlertTriangle class="h-5 w-5 shrink-0 text-red-600" />
				<span class="min-w-0 flex-1 text-sm text-red-800">
					<b>{{ data.demurrage_risk.length }}</b> container(s) at demurrage risk:
					<template v-for="(c, i) in data.demurrage_risk.slice(0, 3)" :key="c.name">
						<RouterLink :to="`/containers/${c.name}`" class="font-semibold underline underline-offset-2">{{ c.container_no || c.name }}</RouterLink>
						<span v-if="c.days_left > 0"> (in {{ c.days_left }}d)</span><span v-else> (running)</span
						><span v-if="i < Math.min(data.demurrage_risk.length, 3) - 1">, </span>
					</template>
				</span>
				<RouterLink to="/containers" class="shrink-0 text-sm font-semibold text-red-700 hover:underline">Review →</RouterLink>
			</div>

			<!-- ── Money row ─────────────────────────────────────────────── -->
			<div class="grid grid-cols-2 gap-4 lg:grid-cols-4" :class="hasProfit && 'xl:grid-cols-5'">
				<div class="rounded-3xl bg-white p-5 ring-1 ring-gray-100">
					<span class="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600/10 text-brand-700"><ReceiptText class="h-5 w-5" /></span>
					<div class="text-2xl font-semibold tabular-nums">{{ fmtMoney(data.revenue_mtd) }}</div>
					<div class="text-[13px] text-muted-foreground">Invoiced this month</div>
				</div>
				<div class="rounded-3xl bg-white p-5 ring-1 ring-gray-100">
					<span class="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-600"><HandCoins class="h-5 w-5" /></span>
					<div class="text-2xl font-semibold tabular-nums">{{ fmtMoney(data.collected_mtd) }}</div>
					<div class="text-[13px] text-muted-foreground">Collected this month</div>
				</div>
				<div class="rounded-3xl bg-white p-5 ring-1 ring-gray-100">
					<span class="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/10 text-amber-600"><Wallet class="h-5 w-5" /></span>
					<div class="text-2xl font-semibold tabular-nums">{{ fmtMoney(data.outstanding_total) }}</div>
					<div class="text-[13px] text-muted-foreground">Outstanding · <span class="font-medium text-red-600">{{ data.overdue_count }} overdue</span></div>
				</div>
				<div class="rounded-3xl bg-white p-5 ring-1 ring-gray-100">
					<span class="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-500/10 text-cyan-600"><HandCoins class="h-5 w-5" /></span>
					<div class="text-2xl font-semibold tabular-nums">{{ fmtMoney(data.cod_unreconciled) }}</div>
					<div class="text-[13px] text-muted-foreground">COD awaiting reconciliation</div>
				</div>
				<!-- Profit — present only when the server says so -->
				<div v-if="hasProfit" class="col-span-2 rounded-3xl bg-coal-900 p-5 text-white lg:col-span-4 xl:col-span-1">
					<span class="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-brand-500/20 text-brand-400"><TrendingUp class="h-5 w-5" /></span>
					<div class="text-2xl font-bold tabular-nums" :class="(data.profit_mtd || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'">
						{{ (data.profit_mtd || 0) >= 0 ? "+" : "" }}{{ fmtMoney(data.profit_mtd) }}
					</div>
					<div class="text-[13px] text-white/50">Gross this month <span class="text-white/35">(inv {{ fmtMoney(data.revenue_mtd) }} − pur {{ fmtMoney(data.spent_mtd) }})</span></div>
				</div>
			</div>

			<!-- ── Operations row ────────────────────────────────────────── -->
			<div class="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
				<RouterLink to="/containers" class="group rounded-3xl bg-white p-5 ring-1 ring-gray-100 transition-shadow hover:shadow-pop">
					<span class="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600/10 text-brand-700 transition-transform group-hover:scale-105"><Container class="h-5 w-5" /></span>
					<div class="text-2xl font-semibold tabular-nums">{{ data.containers_active }}</div>
					<div class="text-[13px] text-muted-foreground">Active containers · <span class="text-sky-700">{{ data.containers_import }} in</span> / <span class="text-violet-700">{{ data.containers_export }} out</span></div>
				</RouterLink>
				<RouterLink to="/shipments" class="group rounded-3xl bg-white p-5 ring-1 ring-gray-100 transition-shadow hover:shadow-pop">
					<span class="mb-3 flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10 text-purple-600 transition-transform group-hover:scale-105"><Package class="h-5 w-5" /></span>
					<div class="text-2xl font-semibold tabular-nums">{{ data.shipments_active }}</div>
					<div class="text-[13px] text-muted-foreground">Active shipments · <span class="text-sky-700">{{ data.shipments_import }} in</span> / <span class="text-violet-700">{{ data.shipments_export }} out</span></div>
				</RouterLink>
				<!-- Pipeline -->
				<div class="col-span-2 rounded-3xl bg-white p-5 ring-1 ring-gray-100">
					<div class="label-caps mb-3">Shipment pipeline ({{ pipelineTotal }})</div>
					<div class="space-y-2">
						<div v-for="p in data.pipeline.slice(0, 4)" :key="p.status" class="flex items-center gap-3">
							<div class="w-32 shrink-0"><StatusBadge :status="p.status" /></div>
							<div class="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-gray-100">
								<div class="h-full rounded-full bg-brand-500" :style="{ width: `${Math.max(3, (p.count / Math.max(pipelineTotal, 1)) * 100)}%` }"></div>
							</div>
							<span class="w-8 shrink-0 text-right text-sm tabular-nums">{{ p.count }}</span>
						</div>
					</div>
				</div>
			</div>

			<!-- ── Charts row ────────────────────────────────────────────── -->
			<div class="mt-4 grid gap-4 lg:grid-cols-2">
				<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
					<h2 class="mb-4 text-[15px] font-semibold tracking-tight">Revenue — invoiced vs collected (12m)</h2>
					<BarChart :groups="revenueGroups" series-a="Invoiced" series-b="Collected" :height="180" />
				</div>
				<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
					<h2 class="mb-4 text-[15px] font-semibold tracking-tight">Shipments — imports vs exports (12m)</h2>
					<BarChart :groups="shipmentGroups" series-a="Imports" series-b="Exports" :height="180" />
				</div>
			</div>

			<!-- ── Lists row ─────────────────────────────────────────────── -->
			<div class="mt-4 grid gap-4 lg:grid-cols-3">
				<!-- Arriving this week -->
				<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
					<div class="mb-3 flex items-center gap-2">
						<Ship class="h-4 w-4 text-brand-700" />
						<h2 class="text-[15px] font-semibold tracking-tight">Arriving this week</h2>
					</div>
					<div v-if="!data.arriving_week.length" class="rounded-xl bg-gray-50 px-4 py-6 text-center text-sm text-muted-foreground">Nothing due this week.</div>
					<div v-for="c in data.arriving_week" :key="c.name" class="flex items-center justify-between gap-2 border-t border-gray-100 py-2.5 text-sm first:border-0">
						<div class="min-w-0">
							<RouterLink :to="`/containers/${c.name}`" class="font-medium text-brand-700 hover:underline">{{ c.container_no || c.name }}</RouterLink>
							<div class="truncate text-xs text-muted-foreground">{{ c.vessel }} → {{ c.port_of_discharge }}</div>
						</div>
						<div class="shrink-0 text-right">
							<DirectionBadge :direction="c.direction" />
							<div class="mt-0.5 text-xs tabular-nums text-muted-foreground">{{ fmtDate(c.eta) }}</div>
						</div>
					</div>
				</div>

				<!-- Top customers MTD -->
				<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
					<h2 class="mb-3 text-[15px] font-semibold tracking-tight">Top customers (this month)</h2>
					<div v-if="!data.top_customers.length" class="rounded-xl bg-gray-50 px-4 py-6 text-center text-sm text-muted-foreground">No invoices yet this month.</div>
					<div v-for="(c, i) in data.top_customers" :key="c.customer" class="flex items-center gap-3 border-t border-gray-100 py-2.5 text-sm first:border-0">
						<span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-600/10 text-xs font-bold text-brand-700">{{ i + 1 }}</span>
						<span class="min-w-0 flex-1 truncate">{{ c.customer }}</span>
						<span class="shrink-0 font-medium tabular-nums">{{ fmtMoney(c.total) }}</span>
					</div>
				</div>

				<!-- Recent payments -->
				<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
					<h2 class="mb-3 text-[15px] font-semibold tracking-tight">Recent payments</h2>
					<div v-if="!data.recent_payments.length" class="rounded-xl bg-gray-50 px-4 py-6 text-center text-sm text-muted-foreground">No payments yet.</div>
					<div v-for="p in data.recent_payments" :key="p.name" class="flex items-center justify-between gap-2 border-t border-gray-100 py-2.5 text-sm first:border-0">
						<div class="min-w-0">
							<div class="truncate font-medium">{{ p.party_name }}</div>
							<div class="text-xs text-muted-foreground">{{ fmtDate(p.posting_date) }} · {{ p.mode_of_payment || "—" }}</div>
						</div>
						<span class="shrink-0 font-semibold tabular-nums text-emerald-700">+{{ fmtMoney(p.paid_amount) }}</span>
					</div>
				</div>
			</div>

			<!-- ── Activity + quick actions ──────────────────────────────── -->
			<div class="mt-4 grid gap-4 lg:grid-cols-12">
				<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100 lg:col-span-7">
					<div class="mb-4 flex items-center gap-2">
						<Activity class="h-4 w-4 text-brand-700" />
						<h2 class="text-[15px] font-semibold tracking-tight">Latest milestones</h2>
					</div>
					<div v-if="!data.recent_events.length" class="rounded-xl bg-gray-50 px-4 py-8 text-center text-sm text-muted-foreground">
						No activity yet.
					</div>
					<ul v-else class="divide-y divide-gray-100">
						<li v-for="e in data.recent_events" :key="e.name" class="flex items-baseline gap-3 py-2.5">
							<span class="w-28 shrink-0 text-xs tabular-nums text-muted-foreground">{{ fmtDateTime(e.event_datetime) }}</span>
							<span class="min-w-0 flex-1 truncate">
								<span class="font-medium">{{ e.milestone }}</span>
								<span v-if="e.location" class="text-muted-foreground"> · {{ e.location }}</span>
							</span>
							<RouterLink v-if="e.shipment" :to="`/shipments/${e.shipment}`" class="shrink-0 text-xs font-medium text-brand-700 hover:underline">{{ e.shipment }}</RouterLink>
							<RouterLink v-else-if="e.container" :to="`/containers/${e.container}`" class="shrink-0 text-xs font-medium text-brand-700 hover:underline">{{ e.container }}</RouterLink>
						</li>
					</ul>
				</div>
				<div class="flex flex-col justify-between gap-6 rounded-3xl bg-gray-900 p-7 text-white lg:col-span-5">
					<div>
						<h2 class="text-lg font-semibold tracking-tight text-white">Move something today</h2>
						<p class="mt-1 text-sm text-white/60">
							Create a container, tag shipments, record costs and sales — the P&L
							takes care of itself.
						</p>
					</div>
					<div class="flex flex-wrap gap-2">
						<RouterLink to="/containers" class="inline-flex items-center gap-2 rounded-full bg-brand-500 px-5 py-2.5 text-sm font-semibold text-coal-900 transition-colors hover:bg-brand-400">
							New container <ArrowRight class="h-4 w-4" />
						</RouterLink>
						<RouterLink to="/shipments" class="inline-flex items-center gap-2 rounded-full border border-white/25 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:border-brand-400 hover:text-brand-300">
							New shipment
						</RouterLink>
						<RouterLink to="/billing?tab=purchases" class="inline-flex items-center gap-2 rounded-full border border-white/25 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:border-brand-400 hover:text-brand-300">
							Record purchase
						</RouterLink>
					</div>
				</div>
			</div>
		</template>
	</div>
</template>
