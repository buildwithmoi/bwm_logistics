<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Plus } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtMoney } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import { useBranchStore } from "@/stores/branch";
import Button from "@/components/ui/Button.vue";
import DataTable from "@/components/ui/DataTable.vue";
import ListToolbar from "@/components/ui/ListToolbar.vue";
import { SHIPMENT_LIST, columnsFor } from "@/lib/views";
import PageHeader from "@/components/ui/PageHeader.vue";
import StatusBadge from "@/components/StatusBadge.vue";

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

// Columns from lib/views.ts; Status drops out once a status filter pins it.
const columns = computed(() =>
	columnsFor(SHIPMENT_LIST, { status: statusFilter.value, direction: directionFilter.value }, rows.value),
);
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

		<ListToolbar
			v-model:search="search"
			v-model:lens="directionFilter"
			v-model:status="statusFilter"
			search-label="Search shipments"
			search-placeholder="Search tracking no, customer…"
			lens-label="Direction"
			:lens-options="[
				{ value: '', label: 'All directions' },
				{ value: 'Import', label: 'Imports' },
				{ value: 'Export', label: 'Exports' },
			]"
			:statuses="STATUSES"
		/>

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
