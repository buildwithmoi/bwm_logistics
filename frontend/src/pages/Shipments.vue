<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Plus, Search } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtMoney } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import { useBranchStore } from "@/stores/branch";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
import PageHeader from "@/components/ui/PageHeader.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import DirectionBadge from "@/components/DirectionBadge.vue";

const router = useRouter();
const toast = useToast();
const session = useSessionStore();
const branch = useBranchStore();

// ── list ────────────────────────────────────────────────────────────────────
const rows = ref<Record<string, unknown>[]>([]);
const total = ref(0);
const loading = ref(false);
const search = ref("");
const statusFilter = ref("");
const directionFilter = ref("");
const PAGE = 25;

async function load(append = false) {
	loading.value = true;
	try {
		const res = await call<{ rows: Record<string, unknown>[]; total: number }>(
			"bwm_logistics.api.shipments.list_shipments",
			{
				status: statusFilter.value || null,
				direction: directionFilter.value || null,
				branch: branch.filter,
				search: search.value || null,
				start: append ? rows.value.length : 0,
				limit: PAGE,
			},
		);
		rows.value = append ? [...rows.value, ...res.rows] : res.rows;
		total.value = res.total;
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load shipments");
	} finally {
		loading.value = false;
	}
}
let searchTimer: ReturnType<typeof setTimeout>;
watch(search, () => {
	clearTimeout(searchTimer);
	searchTimer = setTimeout(() => load(), 300);
});
watch(statusFilter, () => load());
watch(directionFilter, () => load());
onMounted(load);

const columns: Column[] = [
	{ key: "name", label: "Tracking No", primary: true, nowrap: true },
	{ key: "customer_name", label: "Customer" },
	{ key: "direction", label: "Direction" },
	{ key: "status", label: "Status", trailing: true },
	{ key: "container", label: "Container" },
	{ key: "destination", label: "Destination" },
	{ key: "total_charges", label: "Charges", numeric: true },
];
const STATUSES = ["", "Open", "In Transit", "Arrived", "Ready for Delivery", "Delivered"];

// Creating a shipment is a page (/shipments/new), not a dialog — packages and
// charges are repeating tables that need the room.
const canCreate = computed(() => session.can("shipments", "create"));
</script>

<template>
	<div class="mx-auto max-w-6xl">
		<PageHeader title="Shipments">
			<template v-if="canCreate" #actions>
				<Button @click="router.push('/shipments/new')">
					<Plus class="h-4 w-4" aria-hidden="true" /> New shipment
				</Button>
			</template>
		</PageHeader>

		<!-- Direction — the primary lens (Import vs Export) -->
		<div class="chip-row mb-3" role="group" aria-label="Direction">
			<button
				v-for="d in ['', 'Import', 'Export']"
				:key="d"
				type="button"
				class="chip !px-4 !py-2 !text-sm !font-semibold"
				:class="directionFilter === d ? 'chip-seg-on' : 'chip-off'"
				:aria-pressed="directionFilter === d"
				@click="directionFilter = d"
			>
				{{ d === "Import" ? "Imports" : d === "Export" ? "Exports" : "All" }}
			</button>
		</div>

		<div class="mb-4 space-y-3">
			<div class="relative sm:max-w-xs">
				<Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" aria-hidden="true" />
				<Input v-model="search" type="search" aria-label="Search shipments" placeholder="Search tracking no, customer…" class="pl-9" />
			</div>
			<div class="chip-row" role="group" aria-label="Status">
				<button
					v-for="s in STATUSES"
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
			:columns="columns"
			:rows="rows"
			:loading="loading"
			:total="total"
			clickable
			empty-text="No shipments yet."
			@row-click="(r) => router.push(`/shipments/${r.name}`)"
			@load-more="load(true)"
		>
			<template #cell-name="{ row }">
				<span class="font-medium text-brand-700">{{ row.name }}</span>
			</template>
			<template #cell-customer_name="{ row }">
				<span v-if="row.shipment_type === 'Own Goods (Trading)'" class="inline-flex items-center rounded-full bg-brand-600/10 px-2.5 py-0.5 text-[11.5px] font-semibold text-brand-700">
					Own goods
				</span>
				<template v-else>{{ row.customer_name || "—" }}</template>
			</template>
			<template #cell-direction="{ value }"><DirectionBadge :direction="String(value)" /></template>
			<template #cell-status="{ value, row }">
				<span class="inline-flex items-center gap-1.5">
					<StatusBadge :status="String(value)" />
					<span
						v-if="row.current_milestone === 'Delayed'"
						class="inline-flex items-center rounded-full bg-red-50 px-2 py-0.5 text-[10.5px] font-semibold text-red-700 ring-1 ring-red-200"
					>Delayed</span>
				</span>
			</template>
			<template #cell-container="{ value }">
				<span :class="!value && 'text-gray-400'">{{ value || "loose cargo" }}</span>
			</template>
			<template #cell-total_charges="{ value }">{{ fmtMoney(value as number) }}</template>
		</DataTable>
	</div>
</template>
