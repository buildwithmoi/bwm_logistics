<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { Download } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtDate, fmtMoney } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import BarChart, { type BarGroup } from "@/components/BarChart.vue";
import StatusBadge from "@/components/StatusBadge.vue";

// Reports with a left-rail section list (ex_beauty pattern): pick a report,
// the panel renders from one prefetched dataset. Export CSV downloads the
// active section's table.
const toast = useToast();

interface Reports {
	months: Array<{ month: string; label: string; invoiced: number; collected: number }>;
	shipment_months: Array<{ month: string; label: string; imports: number; exports: number }>;
	top_customers: Array<{ customer: string; count: number; charges: number }>;
	status_breakdown: Array<{ status: string; count: number }>;
	containers: {
		by_status: Array<{ status: string; count: number }>;
		by_direction: Array<{ direction: string; count: number }>;
		arriving: Array<{ name: string; container_no?: string; eta?: string; port_of_discharge?: string; vessel?: string }>;
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
}
const data = ref<Reports | null>(null);
const loading = ref(true);
const monthsBack = ref(6);

const SECTIONS = [
	{ key: "revenue", label: "Revenue" },
	{ key: "shipments", label: "Shipments" },
	{ key: "customers", label: "Customers" },
	{ key: "containers", label: "Containers" },
	{ key: "deliveries", label: "Deliveries" },
	{ key: "messaging", label: "Messaging" },
] as const;
type SectionKey = (typeof SECTIONS)[number]["key"];
const section = ref<SectionKey>("revenue");

async function load() {
	loading.value = true;
	try {
		data.value = await call<Reports>("bwm_logistics.api.reports.get_reports", {
			months: monthsBack.value,
		});
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load reports");
	} finally {
		loading.value = false;
	}
}
onMounted(load);

const revenueGroups = computed<BarGroup[]>(
	() => data.value?.months.map((m) => ({ label: m.label, a: m.invoiced, b: m.collected })) || [],
);
const shipmentGroups = computed<BarGroup[]>(
	() => data.value?.shipment_months.map((m) => ({ label: m.label, a: m.imports, b: m.exports })) || [],
);
const totalShipments = computed(
	() => data.value?.status_breakdown.reduce((n, s) => n + s.count, 0) || 0,
);

// ── CSV export of the active section ────────────────────────────────────────
function exportCsv() {
	if (!data.value) return;
	const d = data.value;
	let rows: (string | number)[][] = [];
	if (section.value === "revenue") {
		rows = [["Month", "Invoiced", "Collected"], ...d.months.map((m) => [m.month, m.invoiced, m.collected])];
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
		<header class="mb-5 flex flex-wrap items-center gap-3">
			<h1 class="min-w-0 flex-1 text-2xl font-semibold tracking-tight">Reports</h1>
			<div class="flex gap-1.5">
				<button
					v-for="m in [6, 12]"
					:key="m"
					type="button"
					class="rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors"
					:class="monthsBack === m ? 'bg-brand-600 text-white' : 'bg-white text-gray-600 ring-1 ring-gray-200 hover:bg-gray-50'"
					@click="monthsBack = m; load()"
				>
					{{ m }} months
				</button>
			</div>
			<button
				type="button"
				class="inline-flex h-9 items-center gap-2 rounded-lg border border-input bg-white px-4 text-sm font-medium text-gray-700 shadow-xs hover:bg-gray-50"
				@click="exportCsv"
			>
				<Download class="h-4 w-4" /> Export CSV
			</button>
		</header>

		<div class="flex flex-col gap-6 lg:flex-row">
			<!-- Left rail (SubNav pattern) -->
			<nav class="flex shrink-0 gap-1 overflow-x-auto lg:w-52 lg:flex-col">
				<button
					v-for="s in SECTIONS"
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
			<div class="min-w-0 flex-1">
				<div v-if="loading && !data" class="py-16 text-center text-sm text-muted-foreground">Loading…</div>
				<template v-else-if="data">
					<!-- Revenue -->
					<div v-if="section === 'revenue'" class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
						<h2 class="mb-4 text-[15px] font-semibold tracking-tight">Invoiced vs collected by month</h2>
						<BarChart :groups="revenueGroups" series-a="Invoiced" series-b="Collected" />
						<div class="mt-5 grid grid-cols-2 gap-4">
							<div class="rounded-xl bg-gray-50 px-4 py-3">
								<div class="label-caps">Invoiced ({{ monthsBack }}m)</div>
								<div class="mt-1 text-xl font-semibold tabular-nums">
									{{ fmtMoney(data.months.reduce((n, m) => n + m.invoiced, 0)) }}
								</div>
							</div>
							<div class="rounded-xl bg-gray-50 px-4 py-3">
								<div class="label-caps">Collected ({{ monthsBack }}m)</div>
								<div class="mt-1 text-xl font-semibold tabular-nums">
									{{ fmtMoney(data.months.reduce((n, m) => n + m.collected, 0)) }}
								</div>
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
								<div class="text-[12px] text-muted-foreground">{{ d2.direction }}</div>
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
							<div v-for="c in data.containers.arriving" :key="c.name" class="flex flex-wrap justify-between gap-2 border-t border-gray-100 py-2 text-sm first:border-0">
								<RouterLink :to="`/containers/${c.name}`" class="font-medium text-brand-700 hover:underline">
									{{ c.container_no || c.name }}
								</RouterLink>
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
