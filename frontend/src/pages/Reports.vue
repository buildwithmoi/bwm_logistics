<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { BarChart3, Users, PieChart } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtMoney } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import BarChart, { type BarGroup } from "@/components/BarChart.vue";
import StatusBadge from "@/components/StatusBadge.vue";

const toast = useToast();

interface Reports {
	months: Array<{ month: string; label: string; invoiced: number; collected: number }>;
	top_customers: Array<{ customer: string; count: number; charges: number }>;
	status_breakdown: Array<{ status: string; count: number }>;
}
const data = ref<Reports | null>(null);
const loading = ref(true);
const monthsBack = ref(6);

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

const groups = computed<BarGroup[]>(
	() => data.value?.months.map((m) => ({ label: m.label, a: m.invoiced, b: m.collected })) || [],
);
const totalShipments = computed(
	() => data.value?.status_breakdown.reduce((n, s) => n + s.count, 0) || 0,
);
</script>

<template>
	<div class="mx-auto max-w-6xl">
		<header class="mb-5 flex flex-wrap items-center gap-3">
			<div class="min-w-0 flex-1">
				<h1 class="text-2xl font-semibold tracking-tight">Reports</h1>
				<p class="mt-1 text-sm text-muted-foreground">Revenue, customers, and shipment health at a glance.</p>
			</div>
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
		</header>

		<div v-if="loading && !data" class="py-16 text-center text-sm text-muted-foreground">Loading…</div>
		<template v-else-if="data">
			<!-- Revenue chart -->
			<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
				<div class="mb-4 flex items-center gap-2">
					<BarChart3 class="h-4 w-4 text-brand-700" />
					<h2 class="text-[15px] font-semibold tracking-tight">Invoiced vs collected by month</h2>
				</div>
				<BarChart :groups="groups" />
			</div>

			<div class="mt-4 grid gap-4 lg:grid-cols-2">
				<!-- Top customers -->
				<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
					<div class="mb-4 flex items-center gap-2">
						<Users class="h-4 w-4 text-brand-700" />
						<h2 class="text-[15px] font-semibold tracking-tight">Top customers</h2>
					</div>
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

				<!-- Status breakdown -->
				<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
					<div class="mb-4 flex items-center gap-2">
						<PieChart class="h-4 w-4 text-brand-700" />
						<h2 class="text-[15px] font-semibold tracking-tight">Shipments by status ({{ totalShipments }})</h2>
					</div>
					<div class="space-y-2.5">
						<div v-for="s in data.status_breakdown" :key="s.status" class="flex items-center gap-3">
							<div class="w-36 shrink-0"><StatusBadge :status="s.status" /></div>
							<div class="h-2.5 min-w-0 flex-1 overflow-hidden rounded-full bg-gray-100">
								<div
									class="h-full rounded-full bg-brand-500"
									:style="{ width: `${Math.max(3, (s.count / Math.max(totalShipments, 1)) * 100)}%` }"
								></div>
							</div>
							<span class="w-10 shrink-0 text-right text-sm tabular-nums">{{ s.count }}</span>
						</div>
					</div>
				</div>
			</div>
		</template>
	</div>
</template>
