<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { call } from "@/lib/frappe";
import { fmtDate } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import { useBranchStore } from "@/stores/branch";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import SearchCombo from "@/components/ui/SearchCombo.vue";
import FormPage from "@/components/ui/FormPage.vue";
import FormSection from "@/components/ui/FormSection.vue";

// New delivery run. Picking stops is a browsing job — a page gives the two
// lists room and lets the whole thing scroll normally on a phone, instead of
// two 16rem panes nested inside a dialog.
const router = useRouter();
const toast = useToast();
const branch = useBranchStore();

const saving = ref(false);
const form = reactive({
	driver: "" as string | null,
	vehicle: "" as string | null,
	run_date: new Date().toISOString().slice(0, 10),
	shipments: new Set<string>(),
	pickups: new Set<string>(),
});
const driverDisplay = ref<string | null>(null);

interface Assignable {
	shipments: Array<{ name: string; customer_name: string; destination?: string; delivery_address?: string; total_packages: number }>;
	pickups: Array<{ name: string; customer_name: string; pickup_address: string; preferred_date?: string; time_window?: string }>;
	drivers: Array<{ name: string; full_name: string }>;
	vehicles: Array<{ name: string }>;
}
const assignable = ref<Assignable>({ shipments: [], pickups: [], drivers: [], vehicles: [] });
const loading = ref(true);
onMounted(async () => {
	try {
		assignable.value = await call<Assignable>("bwm_logistics.api.dispatch.assignable");
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load assignable stops");
	} finally {
		loading.value = false;
	}
});

// Link-field fetchers — client-side filter over the assignable pools.
type DriverHit = Record<string, unknown> & { name: string; full_name: string; cell_number?: string };
async function fetchDrivers(q: string): Promise<DriverHit[]> {
	return assignable.value.drivers
		.filter((d) => d.full_name.toLowerCase().includes(q.toLowerCase()))
		.slice(0, 20) as DriverHit[];
}
type VehicleHit = Record<string, unknown> & { name: string };
async function fetchVehicles(q: string): Promise<VehicleHit[]> {
	return assignable.value.vehicles.filter((v) => v.name.toLowerCase().includes(q.toLowerCase())).slice(0, 20);
}
function toggle(set: Set<string>, name: string) {
	set.has(name) ? set.delete(name) : set.add(name);
}

const stopCount = computed(() => form.shipments.size + form.pickups.size);

async function saveRun() {
	if (!form.driver) {
		toast.warning("Pick a driver");
		return;
	}
	if (!stopCount.value) {
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
		router.push(`/dispatch/${res.name}`);
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not save run");
	} finally {
		saving.value = false;
	}
}
</script>

<template>
	<FormPage title="New delivery run" back-to="/dispatch" back-label="Dispatch">
		<FormSection title="Assignment">
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
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
					<Label for="run-date" required>Date</Label>
					<Input id="run-date" v-model="form.run_date" type="date" />
				</div>
			</div>
		</FormSection>

		<FormSection title="Deliveries — ready shipments">
			<div v-if="loading" class="px-3 py-4 text-center text-xs text-muted-foreground">Loading…</div>
			<div v-else-if="!assignable.shipments.length" class="rounded-lg bg-gray-50 px-3 py-4 text-center text-xs text-muted-foreground">
				No shipments in “Arrived” or “Ready for Delivery”.
			</div>
			<div v-else class="space-y-1.5">
				<label
					v-for="s in assignable.shipments"
					:key="s.name"
					class="flex cursor-pointer items-start gap-2.5 rounded-xl border px-3 py-2.5 transition-colors"
					:class="form.shipments.has(s.name) ? 'border-brand-400 bg-brand-50' : 'border-gray-150 hover:bg-gray-50'"
				>
					<input
						type="checkbox"
						class="mt-0.5 h-4 w-4 shrink-0 rounded accent-[#b8860b]"
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
		</FormSection>

		<FormSection title="Pickups — open requests">
			<div v-if="loading" class="px-3 py-4 text-center text-xs text-muted-foreground">Loading…</div>
			<div v-else-if="!assignable.pickups.length" class="rounded-lg bg-gray-50 px-3 py-4 text-center text-xs text-muted-foreground">
				No open pickup requests.
			</div>
			<div v-else class="space-y-1.5">
				<label
					v-for="p in assignable.pickups"
					:key="p.name"
					class="flex cursor-pointer items-start gap-2.5 rounded-xl border px-3 py-2.5 transition-colors"
					:class="form.pickups.has(p.name) ? 'border-brand-400 bg-brand-50' : 'border-gray-150 hover:bg-gray-50'"
				>
					<input
						type="checkbox"
						class="mt-0.5 h-4 w-4 shrink-0 rounded accent-[#b8860b]"
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
		</FormSection>

		<template #actions>
			<span class="self-center text-xs text-muted-foreground sm:mr-auto" aria-live="polite">
				{{ stopCount }} stop(s) selected
			</span>
			<Button variant="outline" @click="router.push('/dispatch')">Cancel</Button>
			<Button :loading="saving" @click="saveRun">Schedule run</Button>
		</template>
	</FormPage>
</template>
