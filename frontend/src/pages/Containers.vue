<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Plus, Search, Container as ContainerIcon } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtDate } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import { useBranchStore } from "@/stores/branch";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Select from "@/components/ui/Select.vue";
import Dialog from "@/components/ui/Dialog.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
import StatusBadge from "@/components/StatusBadge.vue";

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
}
const rows = ref<Row[]>([]);
const total = ref(0);
const loading = ref(false);
const search = ref("");
const statusFilter = ref<string>("");
const PAGE = 25;

async function load(append = false) {
	loading.value = true;
	try {
		const res = await call<{ rows: Row[]; total: number }>(
			"bwm_logistics.api.containers.list_containers",
			{
				status: statusFilter.value || null,
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
onMounted(load);

const columns: Column[] = [
	{ key: "container_no", label: "Container" },
	{ key: "direction", label: "Direction" },
	{ key: "status", label: "Status" },
	{ key: "current_milestone", label: "Milestone" },
	{ key: "eta", label: "ETA" },
	{ key: "shipment_count", label: "Shipments", numeric: true },
];

// ── new container dialog ───────────────────────────────────────────────────
const dialogOpen = ref(false);
const saving = ref(false);
const canCreate = computed(() => session.can("containers", "create"));
const form = reactive({
	direction: "Import",
	container_no: "",
	container_type: "",
	shipping_line: "",
	vessel: "",
	bl_no: "",
	booking_no: "",
	port_of_loading: "",
	port_of_discharge: "",
	etd: "",
	eta: "",
	free_days: "",
});

interface Masters {
	shipping_lines: string[];
	ports: string[];
	container_types: string[];
}
const masters = ref<Masters>({ shipping_lines: [], ports: [], container_types: [] });
async function openDialog() {
	dialogOpen.value = true;
	try {
		masters.value = await call<Masters>("bwm_logistics.api.containers.get_masters");
	} catch {
		/* dropdowns degrade to free entry */
	}
}

// Inline quick-add for Shipping Line / Port (FR: masters shouldn't block flow).
async function quickAdd(doctype: "Shipping Line" | "Port", field: "shipping_line" | "port_of_loading" | "port_of_discharge") {
	const value = prompt(`New ${doctype} name`);
	if (!value) return;
	try {
		const res = await call<{ name: string }>("bwm_logistics.api.containers.quick_add_master", { doctype, value });
		if (doctype === "Shipping Line") masters.value.shipping_lines.push(res.name);
		else masters.value.ports.push(res.name);
		form[field] = res.name;
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not add");
	}
}

async function save() {
	if (!form.direction) {
		toast.warning("Direction is required");
		return;
	}
	saving.value = true;
	try {
		const res = await call<{ name: string }>("bwm_logistics.api.containers.save_container", {
			payload: {
				...form,
				free_days: form.free_days ? Number(form.free_days) : null,
				branch: branch.filter,
			},
		});
		toast.success("Container created");
		dialogOpen.value = false;
		router.push(`/containers/${res.name}`);
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not save container");
	} finally {
		saving.value = false;
	}
}
</script>

<template>
	<div class="mx-auto max-w-6xl">
		<header class="mb-5 flex flex-wrap items-center gap-3">
			<h1 class="min-w-0 flex-1 text-2xl font-semibold tracking-tight">Containers</h1>
			<Button v-if="canCreate" @click="openDialog"><Plus class="h-4 w-4" /> New container</Button>
		</header>

		<!-- Filters -->
		<div class="mb-4 flex flex-wrap items-center gap-2">
			<div class="relative min-w-56 flex-1 sm:max-w-xs">
				<Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
				<Input v-model="search" placeholder="Search container, BL, vessel…" class="pl-9" />
			</div>
			<div class="flex gap-1.5">
				<button
					v-for="s in ['', 'Active', 'Completed', 'Cancelled']"
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
			clickable
			empty-text="No containers yet — create the first one."
			@row-click="(r) => router.push(`/containers/${r.name}`)"
			@load-more="load(true)"
		>
			<template #cell-container_no="{ row }">
				<div class="flex items-center gap-2.5 font-medium">
					<span class="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600/10 text-brand-700">
						<ContainerIcon class="h-4 w-4" />
					</span>
					<div>
						<div>{{ row.container_no || "(not allocated)" }}</div>
						<div class="text-xs font-normal text-muted-foreground">{{ row.name }}</div>
					</div>
				</div>
			</template>
			<template #cell-status="{ value }"><StatusBadge :status="String(value)" /></template>
			<template #cell-current_milestone="{ value }">
				<span :class="!value && 'text-gray-400'">{{ value || "No milestones yet" }}</span>
			</template>
			<template #cell-eta="{ value }">{{ fmtDate(value as string) }}</template>
		</DataTable>

		<!-- ── New container ─────────────────────────────────────────────── -->
		<Dialog v-model:open="dialogOpen" title="New container" size="wide">
			<div class="grid gap-4 sm:grid-cols-2">
				<div class="space-y-1.5">
					<Label required>Direction</Label>
					<Select v-model="form.direction" :options="['Import', 'Export']" />
				</div>
				<div class="space-y-1.5">
					<Label>Container No</Label>
					<Input v-model="form.container_no" placeholder="MSCU1234567" />
				</div>
				<div class="space-y-1.5">
					<Label>Type</Label>
					<Select v-model="form.container_type" :options="masters.container_types" placeholder="Select type" />
				</div>
				<div class="space-y-1.5">
					<div class="flex items-center justify-between">
						<Label>Shipping line</Label>
						<button type="button" class="text-xs font-medium text-brand-700 hover:underline" @click="quickAdd('Shipping Line', 'shipping_line')">+ Add</button>
					</div>
					<Select v-model="form.shipping_line" :options="masters.shipping_lines" placeholder="Select line" />
				</div>
				<div class="space-y-1.5">
					<Label>Vessel</Label>
					<Input v-model="form.vessel" placeholder="Vessel name" />
				</div>
				<div class="space-y-1.5">
					<Label>Master BL No</Label>
					<Input v-model="form.bl_no" />
				</div>
				<div class="space-y-1.5">
					<div class="flex items-center justify-between">
						<Label>Port of loading</Label>
						<button type="button" class="text-xs font-medium text-brand-700 hover:underline" @click="quickAdd('Port', 'port_of_loading')">+ Add</button>
					</div>
					<Select v-model="form.port_of_loading" :options="masters.ports" placeholder="Select port" />
				</div>
				<div class="space-y-1.5">
					<div class="flex items-center justify-between">
						<Label>Port of discharge</Label>
						<button type="button" class="text-xs font-medium text-brand-700 hover:underline" @click="quickAdd('Port', 'port_of_discharge')">+ Add</button>
					</div>
					<Select v-model="form.port_of_discharge" :options="masters.ports" placeholder="Select port" />
				</div>
				<div class="space-y-1.5">
					<Label>ETD</Label>
					<Input v-model="form.etd" type="date" />
				</div>
				<div class="space-y-1.5">
					<Label>ETA</Label>
					<Input v-model="form.eta" type="date" />
				</div>
				<div class="space-y-1.5">
					<Label>Free days</Label>
					<Input v-model="form.free_days" type="number" min="0" />
				</div>
			</div>
			<template #footer>
				<div class="flex justify-end gap-2">
					<Button variant="outline" @click="dialogOpen = false">Cancel</Button>
					<Button :loading="saving" @click="save">Create container</Button>
				</div>
			</template>
		</Dialog>
	</div>
</template>
