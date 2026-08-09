<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Plus } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtDate } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import { useBranchStore } from "@/stores/branch";
import Button from "@/components/ui/Button.vue";
import DataTable from "@/components/ui/DataTable.vue";
import ListToolbar from "@/components/ui/ListToolbar.vue";
import { CONTAINER_LIST, columnsFor } from "@/lib/views";
import PageHeader from "@/components/ui/PageHeader.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import Badge from "@/components/ui/Badge.vue";

const router = useRouter();
const toast = useToast();
const session = useSessionStore();
const branch = useBranchStore();

// ── list state ──────────────────────────────────────────────────────────────
interface Row extends Record<string, unknown> {
	name: string;
	container_no?: string;
	direction: string;
	status: string;
	current_milestone?: string;
	eta?: string;
	shipment_count: number;
	port_of_loading?: string | null;
	port_of_discharge?: string | null;
	// Demurrage: at_risk when the clock starts inside the window (or has
	// started, in which case days_left goes negative).
	at_risk?: boolean;
	days_left?: number | null;
}

/** "Shanghai → Tema" when both ports are known, else whichever one is. */
function route(row: Row): string | null {
	const from = row.port_of_loading || null;
	const to = row.port_of_discharge || null;
	if (from && to) return `${from} → ${to}`;
	return to ? `→ ${to}` : from;
}
const rows = ref<Row[]>([]);
const total = ref(0);
const loading = ref(false);
const search = ref("");
const statusFilter = ref<string>("");
const directionFilter = ref<string>("");
const PAGE = 25;

async function load(append = false) {
	loading.value = true;
	try {
		const res = await call<{ rows: Row[]; total: number }>(
			"bwm_logistics.api.containers.list_containers",
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
		toast.error((e as { message?: string })?.message || "Could not load containers");
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

// Columns come from lib/views.ts and shrink as filters pin them: pick a status
// and the Status column goes (every row has it), pick Imports and Route goes
// (it would only ever read "Import"). `shipment_count` isn't here at all — it
// read "1" on every row, which makes it a detail-page fact.
const columns = computed(() =>
	columnsFor(CONTAINER_LIST, { status: statusFilter.value, direction: directionFilter.value }, rows.value),
);

// Creating a container is a page (/containers/new), not a dialog — too many
// fields to cram into a modal, and the URL is worth having.
const canCreate = computed(() => session.can("containers", "create"));
</script>

<template>
	<div class="mx-auto max-w-6xl">
		<PageHeader title="Containers">
			<template v-if="canCreate" #actions>
				<Button @click="router.push('/containers/new')">
					<Plus class="h-4 w-4" aria-hidden="true" /> New container
				</Button>
			</template>
		</PageHeader>

		<ListToolbar
			v-model:search="search"
			v-model:lens="directionFilter"
			v-model:status="statusFilter"
			search-label="Search containers"
			search-placeholder="Search container, BL, vessel…"
			lens-label="Direction"
			:lens-options="[
				{ value: '', label: 'All directions' },
				{ value: 'Import', label: 'Imports' },
				{ value: 'Export', label: 'Exports' },
			]"
			:statuses="['', 'Active', 'Completed', 'Cancelled']"
		/>

		<DataTable
			:columns="columns"
			:rows="rows"
			:loading="loading"
			:total="total"
			clickable
			:row-tone="(r) => ((r as Row).at_risk ? 'danger' : null)"
			empty-text="No containers yet — create the first one."
			@row-click="(r) => router.push(`/containers/${r.name}`)"
			@load-more="load(true)"
		>
			<!-- One identifier: the container number people quote on the phone.
			     The internal CONT-… name lives on the detail page. -->
			<template #cell-container_no="{ row }">
				<span class="font-medium">{{ row.container_no || row.name }}</span>
			</template>
			<template #cell-route="{ row }">
				<span class="truncate">{{ route(row as Row) || "—" }}</span>
			</template>
			<!-- Demurrage is the one thing worth interrupting a scan for.
			     The empty <span> matters: a scoped slot that renders only a
			     false v-if counts as empty, and DataTable would fall back to
			     printing an em-dash for every healthy container. -->
			<template #cell-risk="{ row }">
				<Badge v-if="row.at_risk" tone="danger" dot>
					{{ (row.days_left as number) > 0 ? `${row.days_left}d to demurrage` : "Demurrage running" }}
				</Badge>
				<span v-else />
			</template>
			<template #cell-status="{ row }"><StatusBadge :status="String(row.status)" /></template>
			<template #cell-current_milestone="{ value }">
				<Badge v-if="value === 'Delayed'" tone="danger">Delayed</Badge>
				<span v-else :class="!value && 'text-gray-400'">{{ value || "No milestones yet" }}</span>
			</template>
			<template #cell-eta="{ value }">{{ fmtDate(value as string) }}</template>
		</DataTable>
	</div>
</template>
