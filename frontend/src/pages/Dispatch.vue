<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Plus, UserPlus, HandCoins } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtDate, fmtMoney } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import { useBranchStore } from "@/stores/branch";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Dialog from "@/components/ui/Dialog.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
import PageHeader from "@/components/ui/PageHeader.vue";
import StatusBadge from "@/components/StatusBadge.vue";

const router = useRouter();
const toast = useToast();
const session = useSessionStore();
const branch = useBranchStore();

// Dispatchers manage runs; a driver-only user gets the same list, scoped
// server-side to their runs, with none of the management chrome.
const isDispatcher = computed(() =>
	session.hasRole("Logistics Manager", "Logistics Operations", "System Manager", "Administrator"),
);

// ── runs list ───────────────────────────────────────────────────────────────
const rows = ref<Record<string, unknown>[]>([]);
const total = ref(0);
const loading = ref(false);
const statusFilter = ref("");
const PAGE = 25;

async function load(append = false) {
	loading.value = true;
	try {
		const res = await call<{ rows: Record<string, unknown>[]; total: number }>(
			"bwm_logistics.api.dispatch.list_runs",
			{
				status: statusFilter.value || null,
				branch: branch.filter,
				start: append ? rows.value.length : 0,
				limit: PAGE,
			},
		);
		rows.value = append ? [...rows.value, ...res.rows] : res.rows;
		total.value = res.total;
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load runs");
	} finally {
		loading.value = false;
	}
}
watch(statusFilter, () => load());
onMounted(() => {
	load();
	if (isDispatcher.value) loadAssignable();
});

const columns: Column[] = [
	{ key: "name", label: "Run", primary: true },
	{ key: "run_date", label: "Date", nowrap: true },
	{ key: "driver_name", label: "Driver" },
	{ key: "status", label: "Status", trailing: true },
	{ key: "stops", label: "Stops", numeric: true },
	{ key: "cod", label: "COD", numeric: true },
];
const STATUSES = ["", "Scheduled", "In Transit", "Completed"];

// ── assignable pool (dispatcher) ────────────────────────────────────────────
interface Assignable {
	shipments: Array<{ name: string; customer_name: string; destination?: string; delivery_address?: string; total_packages: number }>;
	pickups: Array<{ name: string; customer_name: string; pickup_address: string; preferred_date?: string; time_window?: string }>;
	drivers: Array<{ name: string; full_name: string }>;
	vehicles: Array<{ name: string }>;
}
const assignable = ref<Assignable>({ shipments: [], pickups: [], drivers: [], vehicles: [] });
async function loadAssignable() {
	try {
		assignable.value = await call<Assignable>("bwm_logistics.api.dispatch.assignable");
	} catch {
		/* panel degrades */
	}
}

// Scheduling a run is a page (/dispatch/new), not a dialog — picking stops is
// a browsing job that needs the room. The strip above still shows how many
// are waiting.

// ── new driver dialog ───────────────────────────────────────────────────────
const driverOpen = ref(false);
const savingDriver = ref(false);
const driverForm = reactive({ full_name: "", cell_number: "", email: "" });
async function saveDriver() {
	if (!driverForm.full_name) {
		toast.warning("Driver name is required");
		return;
	}
	savingDriver.value = true;
	try {
		await call("bwm_logistics.api.dispatch.save_driver", { payload: { ...driverForm } });
		toast.success(
			driverForm.email ? "Driver created — set-password email sent" : "Driver created",
		);
		driverOpen.value = false;
		driverForm.full_name = "";
		driverForm.cell_number = "";
		driverForm.email = "";
		await loadAssignable();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not save driver");
	} finally {
		savingDriver.value = false;
	}
}

</script>

<template>
	<div class="mx-auto max-w-6xl">
		<PageHeader title="Dispatch" :subtitle="isDispatcher ? undefined : 'Your delivery runs — tap one to work it.'">
			<template v-if="isDispatcher" #actions>
				<Button variant="outline" @click="driverOpen = true"><UserPlus class="h-4 w-4" aria-hidden="true" /> New driver</Button>
				<Button @click="router.push('/dispatch/new')"><Plus class="h-4 w-4" aria-hidden="true" /> New run</Button>
			</template>
		</PageHeader>

		<!-- Ready-to-assign strip (dispatcher only) -->
		<div
			v-if="isDispatcher && (assignable.shipments.length || assignable.pickups.length)"
			class="mb-4 flex flex-wrap gap-2"
		>
			<div class="rounded-xl bg-brand-50 px-4 py-2.5 text-sm ring-1 ring-brand-200">
				<b>{{ assignable.shipments.length }}</b> shipment(s) ready for delivery
			</div>
			<div class="rounded-xl bg-brand-50 px-4 py-2.5 text-sm ring-1 ring-brand-200">
				<b>{{ assignable.pickups.length }}</b> pickup request(s) waiting
			</div>
		</div>

		<div class="chip-row mb-4" role="group" aria-label="Status">
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

		<DataTable
			:columns="columns"
			:rows="rows"
			:loading="loading"
			:total="total"
			clickable
			empty-text="No runs yet."
			@row-click="(r) => router.push(`/dispatch/${r.name}`)"
			@load-more="load(true)"
		>
			<template #cell-name="{ row }">
				<span class="font-medium text-brand-700">{{ row.name }}</span>
			</template>
			<template #cell-run_date="{ value }">{{ fmtDate(value as string) }}</template>
			<template #cell-status="{ value }"><StatusBadge :status="String(value)" /></template>
			<template #cell-stops="{ row }">
				<span class="tabular-nums">{{ row.completed_stops }}/{{ row.total_stops }}</span>
			</template>
			<template #cell-cod="{ row }">
				<span class="inline-flex items-center gap-1.5 tabular-nums">
					{{ fmtMoney(row.cod_collected_total as number) }}
					<HandCoins v-if="row.cod_reconciled" class="h-3.5 w-3.5 text-emerald-600" />
				</span>
			</template>
		</DataTable>

		<!-- ── New run ───────────────────────────────────────────────────── -->

		<!-- ── New driver ────────────────────────────────────────────────── -->
		<Dialog v-model:open="driverOpen" title="New driver">
			<div class="space-y-4">
				<div class="space-y-1.5">
					<Label required>Full name</Label>
					<Input v-model="driverForm.full_name" placeholder="e.g. Yaw Mensah" />
				</div>
				<div class="space-y-1.5">
					<Label>Phone</Label>
					<Input v-model="driverForm.cell_number" placeholder="+233…" />
				</div>
				<div class="space-y-1.5">
					<Label>Email (gives app access)</Label>
					<Input v-model="driverForm.email" type="email" placeholder="driver@example.com" />
					<p class="text-xs text-muted-foreground">
						With an email, the driver gets a login (set-password link by email) and can
						work their runs from a phone.
					</p>
				</div>
			</div>
			<template #footer>
				<div class="flex justify-end gap-2">
					<Button variant="outline" @click="driverOpen = false">Cancel</Button>
					<Button :loading="savingDriver" @click="saveDriver">Create driver</Button>
				</div>
			</template>
		</Dialog>
	</div>
</template>
