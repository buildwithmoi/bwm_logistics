<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Plus, MapPin, Package, Truck, UserPlus, HandCoins } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtDate, fmtMoney } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import { useBranchStore } from "@/stores/branch";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import SearchCombo from "@/components/ui/SearchCombo.vue";
import Dialog from "@/components/ui/Dialog.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
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
	{ key: "name", label: "Run" },
	{ key: "run_date", label: "Date" },
	{ key: "driver_name", label: "Driver" },
	{ key: "status", label: "Status" },
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

// ── new run dialog ──────────────────────────────────────────────────────────
const runOpen = ref(false);
const saving = ref(false);
const form = reactive({
	driver: "" as string | null,
	vehicle: "" as string | null,
	run_date: new Date().toISOString().slice(0, 10),
	shipments: new Set<string>(),
	pickups: new Set<string>(),
});
const driverDisplay = ref<string | null>(null);

// Link-field fetchers — client-side filter over the assignable pools.
type DriverHit = Record<string, unknown> & { name: string; full_name: string; cell_number?: string };
async function fetchDrivers(q: string): Promise<DriverHit[]> {
	return assignable.value.drivers
		.filter((d) => d.full_name.toLowerCase().includes(q.toLowerCase()))
		.slice(0, 20) as DriverHit[];
}
type VehicleHit = Record<string, unknown> & { name: string };
async function fetchVehicles(q: string): Promise<VehicleHit[]> {
	return assignable.value.vehicles
		.filter((v) => v.name.toLowerCase().includes(q.toLowerCase()))
		.slice(0, 20) as VehicleHit[];
}
function toggle(set: Set<string>, name: string) {
	set.has(name) ? set.delete(name) : set.add(name);
}

async function saveRun() {
	if (!form.driver) {
		toast.warning("Pick a driver");
		return;
	}
	if (!form.shipments.size && !form.pickups.size) {
		toast.warning("Add at least one stop");
		return;
	}
	saving.value = true;
	try {
		const stops = [
			...[...form.shipments].map((s) => ({ stop_type: "Delivery", shipment: s })),
			...[...form.pickups].map((p) => ({ stop_type: "Pickup", pickup_request: p })),
		];
		const res = await call<{ name: string }>("bwm_logistics.api.dispatch.save_run", {
			payload: {
				driver: form.driver,
				vehicle: form.vehicle || null,
				run_date: form.run_date,
				branch: branch.filter,
				stops,
			},
		});
		toast.success(`Run ${res.name} scheduled`);
		runOpen.value = false;
		form.shipments.clear();
		form.pickups.clear();
		router.push(`/dispatch/${res.name}`);
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not save run");
	} finally {
		saving.value = false;
	}
}

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
		<header class="mb-5 flex flex-wrap items-center gap-3">
			<div class="min-w-0 flex-1">
				<h1 class="text-2xl font-semibold tracking-tight">Dispatch</h1>
				<p v-if="!isDispatcher" class="mt-1 text-sm text-muted-foreground">Your delivery runs — tap one to work it.</p>
			</div>
			<template v-if="isDispatcher">
				<Button variant="outline" @click="driverOpen = true"><UserPlus class="h-4 w-4" /> New driver</Button>
				<Button @click="runOpen = true"><Plus class="h-4 w-4" /> New run</Button>
			</template>
		</header>

		<!-- Ready-to-assign strip (dispatcher only) -->
		<div
			v-if="isDispatcher && (assignable.shipments.length || assignable.pickups.length)"
			class="mb-4 flex flex-wrap gap-3"
		>
			<div class="flex items-center gap-3 rounded-2xl bg-brand-50 px-5 py-3 ring-1 ring-brand-200">
				<Package class="h-4 w-4 text-brand-700" />
				<span class="text-sm"><b>{{ assignable.shipments.length }}</b> shipment(s) ready for delivery</span>
			</div>
			<div class="flex items-center gap-3 rounded-2xl bg-brand-50 px-5 py-3 ring-1 ring-brand-200">
				<Truck class="h-4 w-4 text-brand-700" />
				<span class="text-sm"><b>{{ assignable.pickups.length }}</b> pickup request(s) waiting</span>
			</div>
		</div>

		<div class="mb-4 flex gap-1.5">
			<button
				v-for="s in STATUSES"
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
				<span class="inline-flex items-center gap-2 font-medium text-brand-700">
					<MapPin class="h-4 w-4" /> {{ row.name }}
				</span>
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
		<Dialog v-model:open="runOpen" title="New delivery run" size="xl">
			<div class="grid gap-4 sm:grid-cols-3">
				<div class="space-y-1.5">
					<Label required>Driver</Label>
					<SearchCombo
						v-model="form.driver"
						v-model:display-value="driverDisplay"
						:fetcher="fetchDrivers"
						value-key="name"
						label-key="full_name"
						sublabel-key="cell_number"
						placeholder="Search driver…"
					/>
				</div>
				<div class="space-y-1.5">
					<Label>Vehicle</Label>
					<SearchCombo
						v-model="form.vehicle"
						:fetcher="fetchVehicles"
						value-key="name"
						label-key="name"
						placeholder="Search vehicle… (optional)"
					/>
				</div>
				<div class="space-y-1.5">
					<Label required>Date</Label>
					<Input v-model="form.run_date" type="date" />
				</div>
			</div>

			<div class="mt-6 grid gap-6 lg:grid-cols-2">
				<!-- Deliveries -->
				<div>
					<div class="label-caps mb-2">Deliveries — ready shipments</div>
					<div v-if="!assignable.shipments.length" class="rounded-lg bg-gray-50 px-3 py-4 text-center text-xs text-muted-foreground">
						No shipments in "Arrived" or "Ready for Delivery".
					</div>
					<div class="max-h-64 space-y-1.5 overflow-y-auto pr-1">
						<label
							v-for="s in assignable.shipments"
							:key="s.name"
							class="flex cursor-pointer items-start gap-2.5 rounded-xl border px-3 py-2.5 transition-colors"
							:class="form.shipments.has(s.name) ? 'border-brand-400 bg-brand-50' : 'border-gray-150 hover:bg-gray-50'"
						>
							<input
								type="checkbox"
								class="mt-0.5 h-4 w-4 rounded accent-[#b8860b]"
								:checked="form.shipments.has(s.name)"
								@change="toggle(form.shipments, s.name)"
							/>
							<span class="min-w-0 text-sm">
								<span class="font-medium">{{ s.name }}</span> · {{ s.customer_name }}
								<span class="block text-xs text-muted-foreground">
									{{ s.delivery_address || s.destination || "no address" }} · {{ s.total_packages }} pkg
								</span>
							</span>
						</label>
					</div>
				</div>
				<!-- Pickups -->
				<div>
					<div class="label-caps mb-2">Pickups — open requests</div>
					<div v-if="!assignable.pickups.length" class="rounded-lg bg-gray-50 px-3 py-4 text-center text-xs text-muted-foreground">
						No open pickup requests.
					</div>
					<div class="max-h-64 space-y-1.5 overflow-y-auto pr-1">
						<label
							v-for="p in assignable.pickups"
							:key="p.name"
							class="flex cursor-pointer items-start gap-2.5 rounded-xl border px-3 py-2.5 transition-colors"
							:class="form.pickups.has(p.name) ? 'border-brand-400 bg-brand-50' : 'border-gray-150 hover:bg-gray-50'"
						>
							<input
								type="checkbox"
								class="mt-0.5 h-4 w-4 rounded accent-[#b8860b]"
								:checked="form.pickups.has(p.name)"
								@change="toggle(form.pickups, p.name)"
							/>
							<span class="min-w-0 text-sm">
								<span class="font-medium">{{ p.customer_name }}</span>
								<span class="block text-xs text-muted-foreground">
									{{ p.pickup_address }} · {{ fmtDate(p.preferred_date) }} {{ p.time_window }}
								</span>
							</span>
						</label>
					</div>
				</div>
			</div>

			<template #footer>
				<div class="flex items-center justify-between gap-2">
					<span class="text-xs text-muted-foreground">
						{{ form.shipments.size + form.pickups.size }} stop(s) selected
					</span>
					<div class="flex gap-2">
						<Button variant="outline" @click="runOpen = false">Cancel</Button>
						<Button :loading="saving" @click="saveRun">Schedule run</Button>
					</div>
				</div>
			</template>
		</Dialog>

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
