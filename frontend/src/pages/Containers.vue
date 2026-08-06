<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Plus, Search } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtDate } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import { useBranchStore } from "@/stores/branch";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
import PageHeader from "@/components/ui/PageHeader.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import Badge from "@/components/ui/Badge.vue";
import DirectionBadge from "@/components/DirectionBadge.vue";

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

const columns: Column[] = [
	{ key: "container_no", label: "Container", primary: true },
	// Route earns its place over a Direction badge, which mostly restates the
	// Imports/Exports tab you already picked.
	{ key: "route", label: "Route" },
	// Two trailing cells rather than one: DataTable stacks them on a phone, so
	// the container number keeps its width instead of truncating behind badges.
	{ key: "risk", label: "", trailing: true },
	{ key: "status", label: "Status", trailing: true },
	{ key: "current_milestone", label: "Milestone" },
	{ key: "eta", label: "ETA", nowrap: true },
	{ key: "shipment_count", label: "Shipments", numeric: true },
];

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

		<!-- Filters -->
		<div class="mb-4 space-y-3">
			<div class="relative sm:max-w-xs">
				<Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" aria-hidden="true" />
				<Input v-model="search" type="search" aria-label="Search containers" placeholder="Search container, BL, vessel…" class="pl-9" />
			</div>
			<div class="chip-row" role="group" aria-label="Status">
				<button
					v-for="s in ['', 'Active', 'Completed', 'Cancelled']"
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
			:row-tone="(r) => ((r as Row).at_risk ? 'danger' : null)"
			empty-text="No containers yet — create the first one."
			@row-click="(r) => router.push(`/containers/${r.name}`)"
			@load-more="load(true)"
		>
			<template #cell-container_no="{ row }">
				<div class="min-w-0 font-medium">
					<div class="truncate">{{ row.container_no || "(not allocated)" }}</div>
					<div class="text-xs font-normal text-muted-foreground">{{ row.name }}</div>
				</div>
			</template>
			<template #cell-route="{ row }">
				<span v-if="route(row as Row)" class="truncate">{{ route(row as Row) }}</span>
				<DirectionBadge v-else :direction="String(row.direction)" />
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
