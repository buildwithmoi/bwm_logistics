<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { Search } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtDateTime } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import Input from "@/components/ui/Input.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
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
	{ key: "creation", label: "When" },
	{ key: "channel", label: "Channel" },
	{ key: "recipient", label: "Recipient" },
	{ key: "milestone", label: "Milestone" },
	{ key: "shipment", label: "Shipment" },
	{ key: "status", label: "Status" },
];
</script>

<template>
	<div class="mx-auto max-w-6xl">
		<header class="mb-5">
			<h1 class="text-2xl font-semibold tracking-tight">Notifications</h1>
			<p class="mt-1 text-sm text-muted-foreground">Every email and SMS sent to customers — and why any failed.</p>
		</header>

		<div class="mb-4 flex flex-wrap items-center gap-2">
			<div class="relative min-w-56 flex-1 sm:max-w-xs">
				<Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
				<Input v-model="search" placeholder="Search recipient, shipment…" class="pl-9" />
			</div>
			<div class="flex gap-1.5">
				<button
					v-for="s in ['', 'Sent', 'Failed', 'Skipped']"
					:key="s"
					type="button"
					class="rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors"
					:class="
						statusFilter === s
							? 'bg-brand-600 text-white'
							: 'bg-white text-gray-600 ring-1 ring-gray-200 hover:bg-gray-50'
					"
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
