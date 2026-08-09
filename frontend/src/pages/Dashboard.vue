<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { useSessionStore } from "@/stores/session";
import { call } from "@/lib/frappe";
import { fmtDate, fmtDateTime, fmtMoney } from "@/lib/format";
import BarChart, { type BarGroup } from "@/components/BarChart.vue";
import DirectionBadge from "@/components/DirectionBadge.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import StatCard from "@/components/ui/StatCard.vue";

// Executive dashboard (P7): money, operations, risk, and movement in one
// screen. Profit renders only when the server includes it (Managers/Accounts).
// The figures carry the page — no decorative icon sits beside a number.
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
	stock_on_hand?: { products: Array<{ product: string; unit: string; remaining: number }>; product_count: number };
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

// A chart with no data is an empty axis pretending to be information. Only
// draw one once a bar would have height.
const hasRevenue = computed(() => revenueGroups.value.some((g) => g.a || g.b));
const hasShipmentHistory = computed(() => shipmentGroups.value.some((g) => g.a || g.b));

// Money: one card with a breakdown rather than five tiles reading 0.00. The
// tiles come back the moment any of them has a figure worth its own card.
const moneyMoved = computed(() => {
	const d = data.value;
	if (!d) return false;
	return !!(d.revenue_mtd || d.collected_mtd || d.outstanding_total || d.cod_unreconciled);
});

// Three cards each saying "nothing" is worse than one line saying it once.
const quietWeek = computed(() => {
	const d = data.value;
	if (!d) return false;
	return !d.arriving_week.length && !d.top_customers.length && !d.recent_payments.length;
});
</script>

<template>
	<div class="mx-auto max-w-7xl">
		<!-- Greeting — one quiet line, so the figures start at the top of the fold -->
		<header class="mb-5 flex items-baseline justify-between gap-3">
			<h1 class="min-w-0 truncate text-base font-semibold tracking-tight sm:text-lg">
				Good day, {{ firstName }}
			</h1>
			<span class="shrink-0 text-[13px] text-muted-foreground">{{ today }}</span>
		</header>

		<div v-if="loading" class="py-16 text-center text-sm text-muted-foreground">Loading…</div>
		<template v-else-if="data">
			<!-- Demurrage banner -->
			<div
				v-if="data.demurrage_risk.length"
				class="mb-4 flex flex-wrap items-center gap-3 rounded-2xl bg-red-50 px-4 py-3.5 ring-1 ring-red-200 sm:px-5"
			>
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

			<!-- ── Money ─────────────────────────────────────────────────── -->
			<!-- Nothing has been billed yet: one line and the action that starts
			     it, not five tiles reading 0.00. -->
			<div
				v-if="!moneyMoved"
				class="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-white px-4 py-3.5 ring-1 ring-gray-100 sm:px-5"
			>
				<p class="text-sm text-muted-foreground">
					No money has moved this month — revenue appears here once you raise an invoice.
				</p>
				<RouterLink
					v-if="session.canSee('billing')"
					to="/billing/invoice/new"
					class="shrink-0 text-sm font-semibold text-brand-700 hover:underline"
				>
					New invoice →
				</RouterLink>
			</div>

			<div v-else class="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4" :class="hasProfit && 'xl:grid-cols-5'">
				<StatCard :value="fmtMoney(data.revenue_mtd)" label="Invoiced this month" />
				<StatCard :value="fmtMoney(data.collected_mtd)" label="Collected this month" />
				<StatCard :value="fmtMoney(data.outstanding_total)" label="Outstanding · ">
					<template #meta>
						<span class="font-medium text-red-600">{{ data.overdue_count }} overdue</span>
					</template>
				</StatCard>
				<StatCard :value="fmtMoney(data.cod_unreconciled)" label="COD awaiting reconciliation" />
				<!-- Profit — present only when the server says so -->
				<StatCard
					v-if="hasProfit"
					tone="dark"
					value=""
					label="Gross this month "
					class="col-span-2 lg:col-span-4 xl:col-span-1"
				>
					<template #value>
						<span :class="(data.profit_mtd || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'">
							{{ (data.profit_mtd || 0) >= 0 ? "+" : "" }}{{ fmtMoney(data.profit_mtd) }}
						</span>
					</template>
					<template #meta>
						<span class="text-white/35">(inv {{ fmtMoney(data.revenue_mtd) }} − pur {{ fmtMoney(data.spent_mtd) }})</span>
					</template>
				</StatCard>
			</div>

			<!-- ── Operations row ────────────────────────────────────────── -->
			<div class="mt-3 grid grid-cols-2 gap-3 sm:mt-4 sm:gap-4 lg:grid-cols-4">
				<StatCard :value="data.containers_active" label="Active containers · " to="/containers">
					<template #meta>
						<span class="text-sky-700">{{ data.containers_import }} in</span> /
						<span class="text-violet-700">{{ data.containers_export }} out</span>
					</template>
				</StatCard>
				<StatCard :value="data.shipments_active" label="Active shipments · " to="/shipments">
					<template #meta>
						<span class="text-sky-700">{{ data.shipments_import }} in</span> /
						<span class="text-violet-700">{{ data.shipments_export }} out</span>
					</template>
				</StatCard>
				<!-- Pipeline -->
				<div class="col-span-2 rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-5">
					<div class="label-caps mb-3">Shipment pipeline ({{ pipelineTotal }})</div>
					<div class="space-y-2">
						<div v-for="p in data.pipeline.slice(0, 4)" :key="p.status" class="flex items-center gap-3">
							<div class="w-24 shrink-0 sm:w-32"><StatusBadge :status="p.status" /></div>
							<div class="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-gray-100">
								<div class="h-full rounded-full bg-brand-500" :style="{ width: `${Math.max(3, (p.count / Math.max(pipelineTotal, 1)) * 100)}%` }"></div>
							</div>
							<span class="w-8 shrink-0 text-right text-sm tabular-nums">{{ p.count }}</span>
						</div>
					</div>
				</div>
			</div>

			<!-- ── Charts ────────────────────────────────────────────────── -->
			<!-- An empty axis is not information; the cards simply don't render
			     until a bar would have height. -->
			<div
				v-if="hasRevenue || hasShipmentHistory"
				class="mt-3 grid grid-cols-1 gap-3 sm:mt-4 sm:gap-4"
				:class="hasRevenue && hasShipmentHistory && 'lg:grid-cols-2'"
			>
				<div v-if="hasRevenue" class="min-w-0 rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6">
					<h2 class="mb-4 text-[15px] font-semibold tracking-tight">Revenue — invoiced vs collected (12m)</h2>
					<BarChart :groups="revenueGroups" series-a="Invoiced" series-b="Collected" :height="180" />
				</div>
				<div v-if="hasShipmentHistory" class="min-w-0 rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6">
					<h2 class="mb-4 text-[15px] font-semibold tracking-tight">Shipments — imports vs exports (12m)</h2>
					<BarChart :groups="shipmentGroups" series-a="Imports" series-b="Exports" :height="180" />
				</div>
			</div>

			<!-- ── Lists ─────────────────────────────────────────────────── -->
			<!-- Three cards each saying "nothing" say it once instead. -->
			<div v-if="quietWeek" class="mt-3 rounded-2xl bg-white px-4 py-3.5 ring-1 ring-gray-100 sm:mt-4 sm:px-5">
				<p class="text-sm text-muted-foreground">
					Nothing arriving, invoiced or paid this week yet.
				</p>
			</div>

			<div v-else class="mt-3 grid grid-cols-1 gap-3 sm:mt-4 sm:gap-4 lg:grid-cols-3">
				<!-- Arriving this week -->
				<div v-if="data.arriving_week.length" class="rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6">
					<h2 class="mb-3 text-[15px] font-semibold tracking-tight">Arriving this week</h2>
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
				<div v-if="data.top_customers.length" class="rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6">
					<h2 class="mb-3 text-[15px] font-semibold tracking-tight">Top customers (this month)</h2>
					<div v-for="(c, i) in data.top_customers" :key="c.customer" class="flex items-center gap-3 border-t border-gray-100 py-2.5 text-sm first:border-0">
						<span class="w-4 shrink-0 text-right text-xs tabular-nums text-muted-foreground">{{ i + 1 }}</span>
						<span class="min-w-0 flex-1 truncate">{{ c.customer }}</span>
						<span class="shrink-0 font-medium tabular-nums">{{ fmtMoney(c.total) }}</span>
					</div>
				</div>

				<!-- Recent payments -->
				<div v-if="data.recent_payments.length" class="rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6">
					<h2 class="mb-3 text-[15px] font-semibold tracking-tight">Recent payments</h2>
					<div v-for="p in data.recent_payments" :key="p.name" class="flex items-center justify-between gap-2 border-t border-gray-100 py-2.5 text-sm first:border-0">
						<div class="min-w-0">
							<div class="truncate font-medium">{{ p.party_name }}</div>
							<div class="text-xs text-muted-foreground">{{ fmtDate(p.posting_date) }} · {{ p.mode_of_payment || "—" }}</div>
						</div>
						<span class="shrink-0 font-semibold tabular-nums text-emerald-700">+{{ fmtMoney(p.paid_amount) }}</span>
					</div>
				</div>

				<!-- Stock on hand (trading) -->
				<div v-if="data.stock_on_hand?.products?.length" class="rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6">
					<div class="mb-3 flex items-center justify-between">
						<h2 class="text-[15px] font-semibold tracking-tight">Stock on hand</h2>
						<RouterLink v-if="session.canSee('stock')" to="/stock" class="text-xs font-medium text-brand-700 hover:underline">Stock →</RouterLink>
					</div>
					<div v-for="p in data.stock_on_hand.products" :key="p.product + p.unit" class="flex items-center justify-between gap-2 border-t border-gray-100 py-2.5 text-sm first:border-0">
						<span class="min-w-0 flex-1 truncate">{{ p.product }}</span>
						<span class="shrink-0 font-semibold tabular-nums">{{ p.remaining.toLocaleString() }} <span class="text-xs font-normal text-muted-foreground">{{ p.unit.toLowerCase() }}</span></span>
					</div>
				</div>
			</div>

			<!-- ── Activity ──────────────────────────────────────────────── -->
			<div v-if="data.recent_events.length" class="mt-3 rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:mt-4 sm:p-6">
				<h2 class="mb-3 text-[15px] font-semibold tracking-tight">Latest milestones</h2>
				<ul class="divide-y divide-gray-100">
					<li v-for="e in data.recent_events" :key="e.name" class="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 py-2.5 sm:flex-nowrap">
						<span class="order-2 shrink-0 text-xs tabular-nums text-muted-foreground sm:order-none sm:w-28">{{ fmtDateTime(e.event_datetime) }}</span>
						<span class="order-1 min-w-0 flex-[1_0_100%] truncate text-sm sm:order-none sm:flex-1">
							<span class="font-medium">{{ e.milestone }}</span>
							<span v-if="e.location" class="text-muted-foreground"> · {{ e.location }}</span>
						</span>
						<RouterLink v-if="e.shipment" :to="`/shipments/${e.shipment}`" class="order-3 shrink-0 text-xs font-medium text-brand-700 hover:underline sm:order-none">{{ e.shipment }}</RouterLink>
						<RouterLink v-else-if="e.container" :to="`/containers/${e.container}`" class="order-3 shrink-0 text-xs font-medium text-brand-700 hover:underline sm:order-none">{{ e.container }}</RouterLink>
					</li>
				</ul>
			</div>
		</template>
	</div>
</template>
