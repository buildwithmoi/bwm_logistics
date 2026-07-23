<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { Boxes, Ship } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtDate } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import StatusBadge from "@/components/StatusBadge.vue";

// Stock (P8) — the client's Excel "Stock Tracker" + reconciliation, live:
// what's on hand per product, per trading shipment, and what's still on the
// water. Quantities only — money lives in Billing.
const toast = useToast();

interface StockRow {
	shipment: string;
	status: string;
	current_milestone?: string;
	container?: string;
	container_no?: string;
	eta?: string | null;
	received: number;
	distributed: number;
	remaining: number;
}
interface ProductRow {
	product: string;
	unit: string;
	received: number;
	distributed: number;
	remaining: number;
}
const data = ref<{ incoming: StockRow[]; shipments: StockRow[]; products: ProductRow[] } | null>(null);
const loading = ref(true);

onMounted(async () => {
	try {
		data.value = await call("bwm_logistics.api.stock.stock_overview");
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load stock");
	} finally {
		loading.value = false;
	}
});

const fmtQty = (v: number) => (v || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
const onHand = computed(() => data.value?.products.filter((p) => p.remaining > 0) || []);
const soldOut = computed(() => data.value?.products.filter((p) => p.remaining <= 0) || []);
</script>

<template>
	<div class="mx-auto max-w-6xl">
		<header class="mb-5 flex flex-wrap items-center gap-3">
			<span class="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600/10 text-brand-700">
				<Boxes class="h-5 w-5" />
			</span>
			<div class="min-w-0 flex-1">
				<h1 class="text-2xl font-semibold tracking-tight">Stock</h1>
				<p class="text-sm text-muted-foreground">
					Own-goods containers: received, distributed, and what's left.
				</p>
			</div>
			<RouterLink
				to="/shipments"
				class="text-sm font-medium text-brand-700 hover:underline"
			>New trading shipment →</RouterLink>
		</header>

		<div v-if="loading" class="py-16 text-center text-sm text-muted-foreground">Loading…</div>
		<template v-else-if="data">
			<div
				v-if="!data.shipments.length && !data.incoming.length"
				class="rounded-3xl bg-white px-6 py-16 text-center ring-1 ring-gray-100"
			>
				<Boxes class="mx-auto mb-3 h-10 w-10 text-gray-300" />
				<p class="font-medium">No trading shipments yet</p>
				<p class="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
					Create a shipment with type <b>Own Goods (Trading)</b> and its items appear
					here with received / distributed / on-hand balances.
				</p>
			</div>

			<template v-else>
				<!-- On hand by product -->
				<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
					<h2 class="mb-4 text-[15px] font-semibold tracking-tight">On hand by product</h2>
					<div v-if="!onHand.length" class="rounded-xl bg-gray-50 px-4 py-6 text-center text-sm text-muted-foreground">
						Everything received has been distributed. 🎉
					</div>
					<div v-else class="space-y-3">
						<div v-for="p in onHand" :key="p.product + p.unit" class="flex items-center gap-4">
							<div class="w-56 min-w-0 shrink-0 sm:w-72">
								<div class="truncate text-sm font-medium">{{ p.product }}</div>
								<div class="text-xs text-muted-foreground">
									{{ fmtQty(p.distributed) }} of {{ fmtQty(p.received) }} {{ p.unit.toLowerCase() }} distributed
								</div>
							</div>
							<div class="h-2.5 min-w-0 flex-1 overflow-hidden rounded-full bg-gray-100">
								<div
									class="h-full rounded-full bg-brand-500"
									:style="{ width: `${Math.min(100, (p.distributed / Math.max(p.received, 1)) * 100)}%` }"
								></div>
							</div>
							<div class="w-28 shrink-0 text-right">
								<span class="font-semibold tabular-nums">{{ fmtQty(p.remaining) }}</span>
								<span class="text-xs text-muted-foreground"> {{ p.unit.toLowerCase() }}</span>
							</div>
						</div>
					</div>
					<p v-if="soldOut.length" class="mt-4 border-t border-gray-100 pt-3 text-xs text-muted-foreground">
						Fully distributed: {{ soldOut.map((p) => p.product).join(", ") }}
					</p>
				</div>

				<!-- Arrived trading shipments -->
				<div class="mt-4 rounded-3xl bg-white p-6 ring-1 ring-gray-100">
					<h2 class="mb-3 text-[15px] font-semibold tracking-tight">Containers in stock ({{ data.shipments.length }})</h2>
					<div v-if="!data.shipments.length" class="rounded-xl bg-gray-50 px-4 py-6 text-center text-sm text-muted-foreground">
						Nothing arrived yet.
					</div>
					<div v-else class="overflow-x-auto">
						<table class="w-full min-w-[640px] text-sm">
							<thead>
								<tr class="text-left">
									<th class="label-caps pb-2 pr-4">Shipment</th>
									<th class="label-caps pb-2 pr-4">Container</th>
									<th class="label-caps pb-2 pr-4">Status</th>
									<th class="label-caps pb-2 pr-4 text-right">Received</th>
									<th class="label-caps pb-2 pr-4 text-right">Distributed</th>
									<th class="label-caps pb-2 text-right">Remaining</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="s in data.shipments" :key="s.shipment" class="border-t border-gray-100">
									<td class="py-2.5 pr-4">
										<RouterLink :to="`/shipments/${s.shipment}`" class="font-medium text-brand-700 hover:underline">
											{{ s.shipment }}
										</RouterLink>
										<span
											v-if="s.current_milestone === 'Delayed'"
											class="ml-1.5 rounded-full bg-red-50 px-2 py-0.5 text-[10.5px] font-semibold text-red-700 ring-1 ring-red-200"
										>Delayed</span>
									</td>
									<td class="py-2.5 pr-4 text-muted-foreground">{{ s.container_no || s.container || "—" }}</td>
									<td class="py-2.5 pr-4"><StatusBadge :status="s.status" /></td>
									<td class="py-2.5 pr-4 text-right tabular-nums">{{ fmtQty(s.received) }}</td>
									<td class="py-2.5 pr-4 text-right tabular-nums">{{ fmtQty(s.distributed) }}</td>
									<td class="py-2.5 text-right font-semibold tabular-nums" :class="s.remaining > 0 ? 'text-brand-800' : 'text-gray-400'">
										{{ fmtQty(s.remaining) }}
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>

				<!-- Incoming -->
				<div class="mt-4 rounded-3xl bg-white p-6 ring-1 ring-gray-100">
					<div class="mb-3 flex items-center gap-2">
						<Ship class="h-4 w-4 text-brand-700" />
						<h2 class="text-[15px] font-semibold tracking-tight">Incoming ({{ data.incoming.length }})</h2>
					</div>
					<div v-if="!data.incoming.length" class="rounded-xl bg-gray-50 px-4 py-6 text-center text-sm text-muted-foreground">
						Nothing on the water.
					</div>
					<div
						v-for="s in data.incoming"
						:key="s.shipment"
						class="flex flex-wrap items-center justify-between gap-2 border-t border-gray-100 py-2.5 text-sm first:border-0"
					>
						<div class="min-w-0">
							<RouterLink :to="`/shipments/${s.shipment}`" class="font-medium text-brand-700 hover:underline">
								{{ s.shipment }}
							</RouterLink>
							<span class="text-muted-foreground"> · {{ s.container_no || s.container || "no container" }}</span>
							<span
								v-if="s.current_milestone === 'Delayed'"
								class="ml-1.5 rounded-full bg-red-50 px-2 py-0.5 text-[10.5px] font-semibold text-red-700 ring-1 ring-red-200"
							>Delayed</span>
						</div>
						<div class="flex shrink-0 items-center gap-3">
							<StatusBadge :status="s.status" />
							<span class="text-xs tabular-nums text-muted-foreground">
								{{ s.eta ? `ETA ${fmtDate(s.eta)}` : "no ETA" }} · {{ fmtQty(s.received) }} expected
							</span>
						</div>
					</div>
				</div>
			</template>
		</template>
	</div>
</template>
