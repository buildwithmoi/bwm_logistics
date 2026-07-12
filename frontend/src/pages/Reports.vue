<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { Download, Printer } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtDate, fmtMoney } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import BarChart, { type BarGroup } from "@/components/BarChart.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import DirectionBadge from "@/components/DirectionBadge.vue";
import Select from "@/components/ui/Select.vue";
import Input from "@/components/ui/Input.vue";

// Reports (P7 — advanced): left-rail section list, custom date range +
// branch/direction filters, receivables aging and per-shipment profitability
// (the server omits the profitability section for non-billing roles).
const toast = useToast();

interface Reports {
	window: { from: string; to: string };
	months: Array<{ month: string; label: string; invoiced: number; collected: number }>;
	shipment_months: Array<{ month: string; label: string; imports: number; exports: number }>;
	collection: { invoiced: number; collected: number; rate_pct: number | null };
	aging: {
		buckets: { current: number; b1_30: number; b31_60: number; b61_90: number; b90_plus: number };
		total: number;
		worst: Array<{ invoice: string; customer: string; due_date: string; overdue_days: number; outstanding: number }>;
	};
	top_customers: Array<{ customer: string; count: number; charges: number }>;
	status_breakdown: Array<{ status: string; count: number }>;
	containers: {
		by_status: Array<{ status: string; count: number }>;
		by_direction: Array<{ direction: string; count: number }>;
		arriving: Array<{ name: string; container_no?: string; eta?: string; port_of_discharge?: string; vessel?: string; direction?: string }>;
		demurrage_risk: Array<{ name: string; container_no?: string; demurrage_start_date: string; days_left: number }>;
	};
	deliveries: {
		runs_total: number;
		runs_completed: number;
		stops_completed: number;
		stops_failed: number;
		cod_collected: number;
		cod_unreconciled: number;
		pickups: Array<{ status: string; count: number }>;
	};
	messaging: {
		total: number;
		delivered_pct: number;
		channels: Array<{ channel: string; sent: number; failed: number; skipped: number; queued: number }>;
	};
	profitability?: {
		rows: Array<{ shipment: string; type: string; customer?: string; direction?: string; status: string; revenue: number; cost: number; profit: number; margin_pct: number | null }>;
		totals: { revenue: number; cost: number; profit: number };
	};
}
const data = ref<Reports | null>(null);
const loading = ref(true);

// ── filters ─────────────────────────────────────────────────────────────────
const monthsBack = ref(6);
const customRange = ref(false);
const fromDate = ref("");
const toDate = ref("");
const branch = ref("");
const direction = ref("");
const branches = ref<string[]>([]);

const BASE_SECTIONS = [
	{ key: "revenue", label: "Revenue" },
	{ key: "aging", label: "Receivables aging" },
	{ key: "profitability", label: "Profitability" },
	{ key: "shipments", label: "Shipments" },
	{ key: "customers", label: "Customers" },
	{ key: "containers", label: "Containers" },
	{ key: "deliveries", label: "Deliveries" },
	{ key: "messaging", label: "Messaging" },
] as const;
type SectionKey = (typeof BASE_SECTIONS)[number]["key"];
const section = ref<SectionKey>("revenue");
// Profitability disappears from the rail when the server withheld the section.
const sections = computed(() =>
	BASE_SECTIONS.filter((s) => s.key !== "profitability" || data.value?.profitability !== undefined),
);

async function load() {
	loading.value = true;
	try {
		data.value = await call<Reports>("bwm_logistics.api.reports.get_reports", {
			months: monthsBack.value,
			from_date: customRange.value && fromDate.value ? fromDate.value : null,
			to_date: customRange.value && toDate.value ? toDate.value : null,
			branch: branch.value || null,
			direction: direction.value || null,
		});
		if (section.value === "profitability" && data.value?.profitability === undefined) {
			section.value = "revenue";
		}
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load reports");
	} finally {
		loading.value = false;
	}
}
onMounted(async () => {
	load();
	try {
		branches.value = await call<string[]>("bwm_logistics.api.settings.list_branches");
	} catch {
		branches.value = [];
	}
});

function setMonths(m: number) {
	customRange.value = false;
	monthsBack.value = m;
	load();
}
function applyRange() {
	if (!fromDate.value || !toDate.value) {
		toast.warning("Pick both dates");
		return;
	}
	customRange.value = true;
	load();
}

const revenueGroups = computed<BarGroup[]>(
	() => data.value?.months.map((m) => ({ label: m.label, a: m.invoiced, b: m.collected })) || [],
);
const shipmentGroups = computed<BarGroup[]>(
	() => data.value?.shipment_months.map((m) => ({ label: m.label, a: m.imports, b: m.exports })) || [],
);
const totalShipments = computed(
	() => data.value?.status_breakdown.reduce((n, s) => n + s.count, 0) || 0,
);
const agingBars = computed(() => {
	const b = data.value?.aging.buckets;
	if (!b) return [];
	return [
		{ label: "Not yet due", amount: b.current, tone: "bg-emerald-500" },
		{ label: "1–30 days", amount: b.b1_30, tone: "bg-amber-400" },
		{ label: "31–60 days", amount: b.b31_60, tone: "bg-amber-500" },
		{ label: "61–90 days", amount: b.b61_90, tone: "bg-orange-500" },
		{ label: "90+ days", amount: b.b90_plus, tone: "bg-red-500" },
	];
});
const agingMax = computed(() => Math.max(...agingBars.value.map((b) => b.amount), 1));
const activeLabel = computed(() => sections.value.find((s) => s.key === section.value)?.label || "");

// Vue templates can't reach window — wrap print in a method.
function printSection() {
	window.print();
}

// ── CSV export of the active section ────────────────────────────────────────
function exportCsv() {
	if (!data.value) return;
	const d = data.value;
	let rows: (string | number)[][] = [];
	if (section.value === "revenue") {
		rows = [["Month", "Invoiced", "Collected"], ...d.months.map((m) => [m.month, m.invoiced, m.collected])];
	} else if (section.value === "aging") {
		rows = [
			["Bucket", "Outstanding"],
			...agingBars.value.map((b) => [b.label, b.amount]),
			[],
			["Invoice", "Customer", "Due date", "Days overdue", "Outstanding"],
			...d.aging.worst.map((w) => [w.invoice, w.customer, w.due_date, w.overdue_days, w.outstanding]),
		];
	} else if (section.value === "profitability" && d.profitability) {
		rows = [
			["Shipment", "Type", "Customer", "Revenue", "Cost", "Profit", "Margin %"],
			...d.profitability.rows.map((r) => [r.shipment, r.type, r.customer || "", r.revenue, r.cost, r.profit, r.margin_pct ?? ""]),
		];
	} else if (section.value === "shipments") {
		rows = [
			["Month", "Imports", "Exports"],
			...d.shipment_months.map((m) => [m.month, m.imports, m.exports]),
			[],
			["Status", "Count"],
			...d.status_breakdown.map((s) => [s.status, s.count]),
		];
	} else if (section.value === "customers") {
		rows = [["Customer", "Shipments", "Charges"], ...d.top_customers.map((c) => [c.customer, c.count, c.charges])];
	} else if (section.value === "containers") {
		rows = [
			["Container", "ETA", "Port", "Vessel"],
			...d.containers.arriving.map((c) => [c.container_no || c.name, c.eta || "", c.port_of_discharge || "", c.vessel || ""]),
		];
	} else if (section.value === "deliveries") {
		rows = [
			["Metric", "Value"],
			["Runs", d.deliveries.runs_total],
			["Runs completed", d.deliveries.runs_completed],
			["Stops completed", d.deliveries.stops_completed],
			["Stops failed", d.deliveries.stops_failed],
			["COD collected", d.deliveries.cod_collected],
			["COD awaiting reconciliation", d.deliveries.cod_unreconciled],
		];
	} else {
		rows = [
			["Channel", "Sent", "Failed", "Skipped"],
			...d.messaging.channels.map((c) => [c.channel, c.sent, c.failed, c.skipped]),
		];
	}
	const csv = rows.map((r) => r.map((v) => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\n");
	const a = document.createElement("a");
	a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
	a.download = `bwm-report-${section.value}.csv`;
	a.click();
	URL.revokeObjectURL(a.href);
}
</script>

<template>
	<div class="mx-auto max-w-6xl">
		<header class="report-no-print mb-5 flex flex-wrap items-center gap-3">
			<h1 class="min-w-0 flex-1 text-2xl font-semibold tracking-tight">Reports</h1>
			<button
				type="button"
				class="inline-flex h-9 items-center gap-2 rounded-lg border border-input bg-white px-4 text-sm font-medium text-gray-700 shadow-xs hover:bg-gray-50"
				@click="printSection"
			>
				<Printer class="h-4 w-4" /> Print / PDF
			</button>
			<button
				type="button"
				class="inline-flex h-9 items-center gap-2 rounded-lg border border-input bg-white px-4 text-sm font-medium text-gray-700 shadow-xs hover:bg-gray-50"
				@click="exportCsv"
			>
				<Download class="h-4 w-4" /> Export CSV
			</button>
		</header>

		<!-- Filter bar -->
		<div class="report-no-print mb-5 flex flex-wrap items-end gap-3 rounded-2xl bg-white px-4 py-3 ring-1 ring-gray-100">
			<div class="flex gap-1.5">
				<button
					v-for="m in [6, 12]"
					:key="m"
					type="button"
					class="rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors"
					:class="!customRange && monthsBack === m ? 'bg-brand-600 text-white' : 'bg-gray-50 text-gray-600 ring-1 ring-gray-200 hover:bg-gray-100'"
					@click="setMonths(m)"
				>
					{{ m }} months
				</button>
			</div>
			<div class="h-8 w-px bg-gray-200"></div>
			<div class="flex items-end gap-2">
				<div class="w-36">
					<label class="label-caps mb-1 block">From</label>
					<Input v-model="fromDate" type="date" />
				</div>
				<div class="w-36">
					<label class="label-caps mb-1 block">To</label>
					<Input v-model="toDate" type="date" />
				</div>
				<button
					type="button"
					class="h-9 rounded-lg px-3.5 text-[13px] font-medium transition-colors"
					:class="customRange ? 'bg-brand-600 text-white' : 'bg-gray-50 text-gray-600 ring-1 ring-gray-200 hover:bg-gray-100'"
					@click="applyRange"
				>
					Apply
				</button>
			</div>
			<div class="h-8 w-px bg-gray-200"></div>
			<div class="w-40">
				<label class="label-caps mb-1 block">Branch</label>
				<Select v-model="branch" :options="[{ value: '', label: 'All branches' }, ...branches]" @update:model-value="load" />
			</div>
			<div class="w-40">
				<label class="label-caps mb-1 block">Direction</label>
				<Select v-model="direction" :options="[{ value: '', label: 'All directions' }, 'Import', 'Export']" @update:model-value="load" />
			</div>
		</div>

		<div class="flex flex-col gap-6 lg:flex-row">
			<!-- Left rail (SubNav pattern) -->
			<nav class="report-no-print flex shrink-0 gap-1 overflow-x-auto lg:w-52 lg:flex-col">
				<button
					v-for="s in sections"
					:key="s.key"
					type="button"
					class="shrink-0 rounded-lg px-3.5 py-2 text-left text-sm font-medium transition-colors"
					:class="section === s.key ? 'bg-brand-50 text-brand-800' : 'text-gray-600 hover:bg-gray-50'"
					@click="section = s.key"
				>
					{{ s.label }}
				</button>
			</nav>

			<!-- Panel -->
			<div class="report-print-area min-w-0 flex-1">
				<div v-if="loading && !data" class="py-16 text-center text-sm text-muted-foreground">Loading…</div>
				<template v-else-if="data">
					<!-- Print-only header (hidden on screen) -->
					<div class="report-print-header hidden">
						<h1 class="text-xl font-bold">BWM Logistics — {{ activeLabel }}</h1>
						<p class="text-sm text-gray-600">
							{{ fmtDate(data.window.from) }} – {{ fmtDate(data.window.to) }}
							<span v-if="branch"> · {{ branch }}</span>
							<span v-if="direction"> · {{ direction }}s</span>
						</p>
					</div>

					<!-- Revenue -->
					<div v-if="section === 'revenue'" class="space-y-4">
						<div class="grid grid-cols-3 gap-4">
							<div class="rounded-2xl bg-white p-4 ring-1 ring-gray-100">
								<div class="label-caps">Invoiced</div>
								<div class="mt-1 text-xl font-semibold tabular-nums">{{ fmtMoney(data.collection.invoiced) }}</div>
							</div>
							<div class="rounded-2xl bg-white p-4 ring-1 ring-gray-100">
								<div class="label-caps">Collected</div>
								<div class="mt-1 text-xl font-semibold tabular-nums">{{ fmtMoney(data.collection.collected) }}</div>
							</div>
							<div class="rounded-2xl bg-white p-4 ring-1 ring-gray-100">
								<div class="label-caps">Collection rate</div>
								<div class="mt-1 text-xl font-semibold tabular-nums" :class="(data.collection.rate_pct ?? 100) >= 80 ? 'text-emerald-700' : 'text-amber-600'">
									{{ data.collection.rate_pct !== null ? `${data.collection.rate_pct}%` : "—" }}
								</div>
							</div>
						</div>
						<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
							<h2 class="mb-4 text-[15px] font-semibold tracking-tight">Invoiced vs collected by month</h2>
							<BarChart :groups="revenueGroups" series-a="Invoiced" series-b="Collected" />
						</div>
					</div>

					<!-- Receivables aging -->
					<div v-else-if="section === 'aging'" class="space-y-4">
						<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
							<div class="mb-4 flex items-baseline justify-between">
								<h2 class="text-[15px] font-semibold tracking-tight">Receivables aging</h2>
								<span class="text-sm tabular-nums text-muted-foreground">Total outstanding: <b class="text-gray-900">{{ fmtMoney(data.aging.total) }}</b></span>
							</div>
							<div class="space-y-2.5">
								<div v-for="b in agingBars" :key="b.label" class="flex items-center gap-3">
									<span class="w-28 shrink-0 text-sm text-gray-600">{{ b.label }}</span>
									<div class="h-3 min-w-0 flex-1 overflow-hidden rounded-full bg-gray-100">
										<div class="h-full rounded-full" :class="b.tone" :style="{ width: `${Math.max(b.amount ? 3 : 0, (b.amount / agingMax) * 100)}%` }"></div>
									</div>
									<span class="w-28 shrink-0 text-right text-sm font-medium tabular-nums">{{ fmtMoney(b.amount) }}</span>
								</div>
							</div>
						</div>
						<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
							<h2 class="mb-3 text-[15px] font-semibold tracking-tight">Most overdue invoices</h2>
							<div v-if="!data.aging.worst.length" class="rounded-xl bg-gray-50 px-4 py-8 text-center text-sm text-muted-foreground">
								Nothing outstanding — every invoice is settled. 🎉
							</div>
							<div v-else class="overflow-x-auto">
								<table class="w-full min-w-[560px] text-sm">
									<thead>
										<tr class="text-left">
											<th class="label-caps pb-2 pr-4">Invoice</th>
											<th class="label-caps pb-2 pr-4">Customer</th>
											<th class="label-caps pb-2 pr-4">Due</th>
											<th class="label-caps pb-2 pr-4 text-right">Days overdue</th>
											<th class="label-caps pb-2 text-right">Outstanding</th>
										</tr>
									</thead>
									<tbody>
										<tr v-for="w in data.aging.worst" :key="w.invoice" class="border-t border-gray-100">
											<td class="py-2 pr-4 font-medium">{{ w.invoice }}</td>
											<td class="py-2 pr-4">{{ w.customer }}</td>
											<td class="py-2 pr-4 tabular-nums">{{ fmtDate(w.due_date) }}</td>
											<td class="py-2 pr-4 text-right tabular-nums" :class="w.overdue_days > 30 ? 'font-semibold text-red-600' : w.overdue_days > 0 ? 'text-amber-600' : 'text-gray-500'">
												{{ w.overdue_days || "—" }}
											</td>
											<td class="py-2 text-right font-medium tabular-nums">{{ fmtMoney(w.outstanding) }}</td>
										</tr>
									</tbody>
								</table>
							</div>
						</div>
					</div>

					<!-- Profitability (server-gated) -->
					<div v-else-if="section === 'profitability' && data.profitability" class="space-y-4">
						<div class="grid grid-cols-3 gap-4">
							<div class="rounded-2xl bg-white p-4 ring-1 ring-gray-100">
								<div class="label-caps">Revenue (tagged)</div>
								<div class="mt-1 text-xl font-semibold tabular-nums">{{ fmtMoney(data.profitability.totals.revenue) }}</div>
							</div>
							<div class="rounded-2xl bg-white p-4 ring-1 ring-gray-100">
								<div class="label-caps">Cost (tagged)</div>
								<div class="mt-1 text-xl font-semibold tabular-nums">{{ fmtMoney(data.profitability.totals.cost) }}</div>
							</div>
							<div class="rounded-2xl bg-coal-900 p-4 text-white">
								<div class="label-caps !text-white/50">Gross profit</div>
								<div class="mt-1 text-xl font-bold tabular-nums" :class="data.profitability.totals.profit >= 0 ? 'text-emerald-400' : 'text-red-400'">
									{{ data.profitability.totals.profit >= 0 ? "+" : "" }}{{ fmtMoney(data.profitability.totals.profit) }}
								</div>
							</div>
						</div>
						<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
							<h2 class="mb-3 text-[15px] font-semibold tracking-tight">Per-shipment P&amp;L</h2>
							<div v-if="!data.profitability.rows.length" class="rounded-xl bg-gray-50 px-4 py-8 text-center text-sm text-muted-foreground">
								No shipments have tagged invoices or purchases yet. Tag a shipment when
								raising invoices or recording purchases in Billing.
							</div>
							<div v-else class="overflow-x-auto">
								<table class="w-full min-w-[640px] text-sm">
									<thead>
										<tr class="text-left">
											<th class="label-caps pb-2 pr-4">Shipment</th>
											<th class="label-caps pb-2 pr-4">Customer</th>
											<th class="label-caps pb-2 pr-4 text-right">Revenue</th>
											<th class="label-caps pb-2 pr-4 text-right">Cost</th>
											<th class="label-caps pb-2 pr-4 text-right">Profit</th>
											<th class="label-caps pb-2 text-right">Margin</th>
										</tr>
									</thead>
									<tbody>
										<tr v-for="r in data.profitability.rows" :key="r.shipment" class="border-t border-gray-100">
											<td class="py-2 pr-4">
												<RouterLink :to="`/shipments/${r.shipment}`" class="font-medium text-brand-700 hover:underline">{{ r.shipment }}</RouterLink>
												<span v-if="r.type !== 'Customer Cargo'" class="ml-1.5 rounded-full bg-brand-600/10 px-2 py-0.5 text-[10px] font-semibold text-brand-700">Own goods</span>
											</td>
											<td class="py-2 pr-4">{{ r.customer || "—" }}</td>
											<td class="py-2 pr-4 text-right tabular-nums">{{ fmtMoney(r.revenue) }}</td>
											<td class="py-2 pr-4 text-right tabular-nums">{{ fmtMoney(r.cost) }}</td>
											<td class="py-2 pr-4 text-right font-semibold tabular-nums" :class="r.profit >= 0 ? 'text-emerald-700' : 'text-red-600'">
												{{ r.profit >= 0 ? "+" : "" }}{{ fmtMoney(r.profit) }}
											</td>
											<td class="py-2 text-right tabular-nums">{{ r.margin_pct !== null ? `${r.margin_pct}%` : "—" }}</td>
										</tr>
									</tbody>
								</table>
							</div>
						</div>
					</div>

					<!-- Shipments -->
					<div v-else-if="section === 'shipments'" class="space-y-4">
						<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
							<h2 class="mb-4 text-[15px] font-semibold tracking-tight">New shipments by month</h2>
							<BarChart :groups="shipmentGroups" series-a="Imports" series-b="Exports" />
						</div>
						<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
							<h2 class="mb-4 text-[15px] font-semibold tracking-tight">By status ({{ totalShipments }})</h2>
							<div class="space-y-2.5">
								<div v-for="s in data.status_breakdown" :key="s.status" class="flex items-center gap-3">
									<div class="w-36 shrink-0"><StatusBadge :status="s.status" /></div>
									<div class="h-2.5 min-w-0 flex-1 overflow-hidden rounded-full bg-gray-100">
										<div class="h-full rounded-full bg-brand-500" :style="{ width: `${Math.max(3, (s.count / Math.max(totalShipments, 1)) * 100)}%` }"></div>
									</div>
									<span class="w-10 shrink-0 text-right text-sm tabular-nums">{{ s.count }}</span>
								</div>
							</div>
						</div>
					</div>

					<!-- Customers -->
					<div v-else-if="section === 'customers'" class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
						<h2 class="mb-4 text-[15px] font-semibold tracking-tight">Top customers</h2>
						<div v-if="!data.top_customers.length" class="rounded-xl bg-gray-50 px-4 py-8 text-center text-sm text-muted-foreground">
							No shipments yet.
						</div>
						<table v-else class="w-full text-sm">
							<thead>
								<tr class="text-left">
									<th class="label-caps pb-2">Customer</th>
									<th class="label-caps pb-2 text-right">Shipments</th>
									<th class="label-caps pb-2 text-right">Charges</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="c in data.top_customers" :key="c.customer" class="border-t border-gray-100">
									<td class="py-2">{{ c.customer }}</td>
									<td class="py-2 text-right tabular-nums">{{ c.count }}</td>
									<td class="py-2 text-right tabular-nums">{{ fmtMoney(c.charges) }}</td>
								</tr>
							</tbody>
						</table>
					</div>

					<!-- Containers -->
					<div v-else-if="section === 'containers'" class="space-y-4">
						<div class="grid grid-cols-2 gap-4 sm:grid-cols-4">
							<div v-for="s in data.containers.by_status" :key="s.status" class="rounded-2xl bg-white p-4 ring-1 ring-gray-100">
								<div class="text-2xl font-semibold tabular-nums">{{ s.count }}</div>
								<div class="text-[12px] text-muted-foreground">{{ s.status }}</div>
							</div>
							<div v-for="d2 in data.containers.by_direction" :key="d2.direction" class="rounded-2xl bg-white p-4 ring-1 ring-gray-100">
								<div class="text-2xl font-semibold tabular-nums">{{ d2.count }}</div>
								<div class="text-[12px] text-muted-foreground">{{ d2.direction }}s</div>
							</div>
						</div>
						<div v-if="data.containers.demurrage_risk.length" class="rounded-3xl bg-red-50 p-6 ring-1 ring-red-200">
							<h2 class="mb-3 text-[15px] font-semibold tracking-tight text-red-800">Demurrage risk</h2>
							<div v-for="c in data.containers.demurrage_risk" :key="c.name" class="flex justify-between border-t border-red-100 py-2 text-sm first:border-0">
								<RouterLink :to="`/containers/${c.name}`" class="font-medium text-red-800 underline underline-offset-2">
									{{ c.container_no || c.name }}
								</RouterLink>
								<span class="tabular-nums text-red-700">{{ c.days_left > 0 ? `in ${c.days_left}d` : "running" }}</span>
							</div>
						</div>
						<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
							<h2 class="mb-3 text-[15px] font-semibold tracking-tight">Arriving next</h2>
							<div v-if="!data.containers.arriving.length" class="rounded-xl bg-gray-50 px-4 py-6 text-center text-sm text-muted-foreground">
								Nothing scheduled.
							</div>
							<div v-for="c in data.containers.arriving" :key="c.name" class="flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 py-2 text-sm first:border-0">
								<span class="inline-flex items-center gap-2">
									<RouterLink :to="`/containers/${c.name}`" class="font-medium text-brand-700 hover:underline">
										{{ c.container_no || c.name }}
									</RouterLink>
									<DirectionBadge :direction="c.direction" size="sm" />
								</span>
								<span class="text-muted-foreground">{{ c.vessel }} → {{ c.port_of_discharge }} · {{ fmtDate(c.eta) }}</span>
							</div>
						</div>
					</div>

					<!-- Deliveries -->
					<div v-else-if="section === 'deliveries'" class="space-y-4">
						<div class="grid grid-cols-2 gap-4 sm:grid-cols-3">
							<div class="rounded-2xl bg-white p-4 ring-1 ring-gray-100">
								<div class="text-2xl font-semibold tabular-nums">{{ data.deliveries.runs_completed }}/{{ data.deliveries.runs_total }}</div>
								<div class="text-[12px] text-muted-foreground">Runs completed</div>
							</div>
							<div class="rounded-2xl bg-white p-4 ring-1 ring-gray-100">
								<div class="text-2xl font-semibold tabular-nums">{{ data.deliveries.stops_completed }}</div>
								<div class="text-[12px] text-muted-foreground">Stops delivered</div>
							</div>
							<div class="rounded-2xl bg-white p-4 ring-1 ring-gray-100">
								<div class="text-2xl font-semibold tabular-nums text-red-600">{{ data.deliveries.stops_failed }}</div>
								<div class="text-[12px] text-muted-foreground">Failed attempts</div>
							</div>
							<div class="rounded-2xl bg-white p-4 ring-1 ring-gray-100">
								<div class="text-2xl font-semibold tabular-nums">{{ fmtMoney(data.deliveries.cod_collected) }}</div>
								<div class="text-[12px] text-muted-foreground">COD collected</div>
							</div>
							<div class="rounded-2xl bg-white p-4 ring-1 ring-gray-100">
								<div class="text-2xl font-semibold tabular-nums text-amber-600">{{ fmtMoney(data.deliveries.cod_unreconciled) }}</div>
								<div class="text-[12px] text-muted-foreground">COD awaiting reconciliation</div>
							</div>
						</div>
						<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
							<h2 class="mb-3 text-[15px] font-semibold tracking-tight">Pickup requests</h2>
							<div v-for="p in data.deliveries.pickups" :key="p.status" class="flex justify-between border-t border-gray-100 py-2 text-sm first:border-0">
								<StatusBadge :status="p.status" />
								<span class="tabular-nums">{{ p.count }}</span>
							</div>
						</div>
					</div>

					<!-- Messaging -->
					<div v-else class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
						<div class="mb-4 flex items-baseline justify-between">
							<h2 class="text-[15px] font-semibold tracking-tight">Messaging</h2>
							<span class="text-sm text-muted-foreground tabular-nums">
								{{ data.messaging.delivered_pct }}% delivered · {{ data.messaging.total }} sent
							</span>
						</div>
						<div v-if="!data.messaging.channels.length" class="rounded-xl bg-gray-50 px-4 py-8 text-center text-sm text-muted-foreground">
							No notifications in this period.
						</div>
						<div v-for="c in data.messaging.channels" :key="c.channel" class="flex flex-wrap items-baseline justify-between gap-2 border-t border-gray-100 py-3 first:border-0">
							<span class="font-medium">{{ c.channel }}</span>
							<span class="text-sm tabular-nums">
								<b class="text-emerald-700">{{ c.sent }} sent</b>
								<span v-if="c.failed" class="text-red-600"> · {{ c.failed }} failed</span>
								<span v-if="c.skipped" class="text-muted-foreground"> · {{ c.skipped }} skipped</span>
							</span>
						</div>
					</div>
				</template>
			</div>
		</div>
	</div>
</template>

<style>
/* Print: only the active report panel, with its print-only header. */
@media print {
	.report-no-print,
	header,
	nav,
	aside {
		display: none !important;
	}
	/* AppShell locks the viewport (h-screen + overflow-hidden) — unlock it so
	   the report flows across pages instead of clipping to one. */
	.h-screen {
		height: auto !important;
		overflow: visible !important;
	}
	main {
		overflow: visible !important;
		padding: 0 !important;
	}
	.report-print-header {
		display: block !important;
		margin-bottom: 16px;
		border-bottom: 3px solid #b8860b;
		padding-bottom: 10px;
	}
	.report-print-area {
		width: 100% !important;
	}
	.report-print-area .rounded-3xl,
	.report-print-area .rounded-2xl {
		box-shadow: none !important;
		border: 1px solid #e5e7eb;
		break-inside: avoid;
	}
	body {
		background: #fff !important;
		-webkit-print-color-adjust: exact;
		print-color-adjust: exact;
	}
}
</style>
