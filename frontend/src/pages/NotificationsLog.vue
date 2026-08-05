<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { Search } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtDateTime } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import Input from "@/components/ui/Input.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
import PageHeader from "@/components/ui/PageHeader.vue";
import StatusBadge from "@/components/StatusBadge.vue";

// "Who was told what, when" — the notification send log (FR-NOT-4).
const toast = useToast();
const rows = ref<Record<string, unknown>[]>([]);
const total = ref(0);
const loading = ref(false);
const search = ref("");
const statusFilter = ref("");
const PAGE = 25;

async function load(append = false) {
	loading.value = true;
	try {
		const res = await call<{ rows: Record<string, unknown>[]; total: number }>(
			"bwm_logistics.api.notifications.list_log",
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
		toast.error((e as { message?: string })?.message || "Could not load the log");
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
onMounted(load);

const columns: Column[] = [
	{ key: "creation", label: "When", nowrap: true },
	{ key: "channel", label: "Channel" },
	{ key: "recipient", label: "Recipient" },
	{ key: "milestone", label: "Milestone", primary: true },
	{ key: "shipment", label: "Shipment" },
	{ key: "status", label: "Status", trailing: true },
];
</script>

<template>
	<div class="mx-auto max-w-6xl">
		<PageHeader title="Notifications" subtitle="Every email and SMS sent to customers — and why any failed." />

		<div class="mb-4 space-y-3">
			<div class="relative sm:max-w-xs">
				<Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" aria-hidden="true" />
				<Input v-model="search" type="search" aria-label="Search notifications" placeholder="Search recipient, shipment…" class="pl-9" />
			</div>
			<div class="chip-row" role="group" aria-label="Status">
				<button
					v-for="s in ['', 'Sent', 'Failed', 'Skipped']"
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
			empty-text="No notifications sent yet — record a milestone with notify on."
			@load-more="load(true)"
		>
			<template #cell-creation="{ value }">
				<span class="tabular-nums text-muted-foreground">{{ fmtDateTime(value as string) }}</span>
			</template>
			<template #cell-status="{ row }">
				<div>
					<StatusBadge :status="String(row.status)" />
					<div v-if="row.error" class="mt-1 max-w-56 truncate text-xs text-red-600" :title="String(row.error)">
						{{ row.error }}
					</div>
				</div>
			</template>
		</DataTable>
	</div>
</template>
