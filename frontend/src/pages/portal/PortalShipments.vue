<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { Package } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtMoney } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
import StatusBadge from "@/components/StatusBadge.vue";

const router = useRouter();
const toast = useToast();
const rows = ref<Record<string, unknown>[]>([]);
const total = ref(0);
const loading = ref(false);
const PAGE = 25;

async function load(append = false) {
	loading.value = true;
	try {
		const res = await call<{ rows: Record<string, unknown>[]; total: number }>(
			"bwm_logistics.api.portal.my_shipments",
			{ start: append ? rows.value.length : 0, limit: PAGE },
		);
		rows.value = append ? [...rows.value, ...res.rows] : res.rows;
		total.value = res.total;
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load your shipments");
	} finally {
		loading.value = false;
	}
}
onMounted(load);

const columns: Column[] = [
	{ key: "name", label: "Tracking No" },
	{ key: "status", label: "Status" },
	{ key: "current_milestone", label: "Latest update" },
	{ key: "destination", label: "Destination" },
	{ key: "total_charges", label: "Charges", numeric: true },
];
</script>

<template>
	<div class="mx-auto max-w-5xl">
		<header class="mb-5">
			<h1 class="text-2xl font-semibold tracking-tight">My Shipments</h1>
			<p class="mt-1 text-sm text-muted-foreground">Everything tagged to you — tap a shipment for its full timeline.</p>
		</header>

		<DataTable
			:columns="columns"
			:rows="rows"
			:loading="loading"
			:total="total"
			clickable
			empty-text="No shipments yet — they appear here as soon as we receive your goods."
			@row-click="(r) => router.push(`/portal/shipments/${r.name}`)"
			@load-more="load(true)"
		>
			<template #cell-name="{ row }">
				<span class="inline-flex items-center gap-2 font-medium text-brand-700">
					<Package class="h-4 w-4" /> {{ row.name }}
				</span>
			</template>
			<template #cell-status="{ value }"><StatusBadge :status="String(value)" /></template>
			<template #cell-current_milestone="{ value }">
				<span :class="!value && 'text-gray-400'">{{ value || "No updates yet" }}</span>
			</template>
			<template #cell-total_charges="{ value }">{{ fmtMoney(value as number) }}</template>
		</DataTable>
	</div>
</template>
