<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Plus, Search, Package, Trash2 } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtMoney } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Select from "@/components/ui/Select.vue";
import Textarea from "@/components/ui/Textarea.vue";
import Dialog from "@/components/ui/Dialog.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
import StatusBadge from "@/components/StatusBadge.vue";

const router = useRouter();
const toast = useToast();
const session = useSessionStore();

// ── list ────────────────────────────────────────────────────────────────────
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
			"bwm_logistics.api.shipments.list_shipments",
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
onMounted(load);

const columns: Column[] = [
	{ key: "name", label: "Tracking No" },
	{ key: "customer_name", label: "Customer" },
	{ key: "status", label: "Status" },
	{ key: "container", label: "Container" },
	{ key: "destination", label: "Destination" },
	{ key: "total_charges", label: "Charges", numeric: true },
];
const STATUSES = ["", "Open", "In Transit", "Arrived", "Ready for Delivery", "Delivered"];

// ── new shipment dialog ─────────────────────────────────────────────────────
const dialogOpen = ref(false);
const saving = ref(false);
const canCreate = computed(() => session.can("shipments", "create"));

interface PkgRow {
	description: string;
	qty: number;
	weight_kg: number | null;
	declared_value: number | null;
}
interface ChargeRow {
	charge_type: string;
	amount: number | null;
}
const form = reactive({
	customer: "",
	container: "",
	direction: "Import",
	consignee_name: "",
	consignee_phone: "",
	destination: "",
	delivery_address: "",
	packages: [{ description: "", qty: 1, weight_kg: null, declared_value: null }] as PkgRow[],
	charges: [] as ChargeRow[],
});

const customerOptions = ref<Array<{ value: string; label: string }>>([]);
const containerOptions = ref<Array<{ value: string; label: string }>>([]);
async function openDialog() {
	dialogOpen.value = true;
	try {
		const [cust, cont] = await Promise.all([
			call<{ rows: Array<{ name: string; customer_name: string }> }>(
				"bwm_logistics.api.customers.list_customers",
				{ limit: 100 },
			),
			call<{ rows: Array<{ name: string; container_no?: string; direction: string }> }>(
				"bwm_logistics.api.containers.list_containers",
				{ status: "Active", limit: 100 },
			),
		]);
		customerOptions.value = cust.rows.map((c) => ({ value: c.name, label: c.customer_name }));
		containerOptions.value = cont.rows.map((c) => ({
			value: c.name,
			label: `${c.container_no || c.name} (${c.direction})`,
		}));
	} catch {
		/* selects degrade */
	}
}

function addPackage() {
	form.packages.push({ description: "", qty: 1, weight_kg: null, declared_value: null });
}
function addCharge() {
	form.charges.push({ charge_type: "", amount: null });
}

async function save() {
	if (!form.customer) {
		toast.warning("Pick a customer");
		return;
	}
	if (!form.packages.some((p) => p.description)) {
		toast.warning("Add at least one package");
		return;
	}
	saving.value = true;
	try {
		const res = await call<{ name: string }>("bwm_logistics.api.shipments.save_shipment", {
			payload: {
				...form,
				container: form.container || null,
				packages: form.packages.filter((p) => p.description),
				charges: form.charges.filter((c) => c.charge_type),
			},
		});
		toast.success(`Shipment ${res.name} created`);
		dialogOpen.value = false;
		router.push(`/shipments/${res.name}`);
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not save shipment");
	} finally {
		saving.value = false;
	}
}
</script>

<template>
	<div class="mx-auto max-w-6xl">
		<header class="mb-5 flex flex-wrap items-center gap-3">
			<h1 class="min-w-0 flex-1 text-2xl font-semibold tracking-tight">Shipments</h1>
			<Button v-if="canCreate" @click="openDialog"><Plus class="h-4 w-4" /> New shipment</Button>
		</header>

		<div class="mb-4 flex flex-wrap items-center gap-2">
			<div class="relative min-w-56 flex-1 sm:max-w-xs">
				<Search class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
				<Input v-model="search" placeholder="Search tracking no, customer…" class="pl-9" />
			</div>
			<div class="flex flex-wrap gap-1.5">
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
		</div>

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
				<span class="inline-flex items-center gap-2 font-medium text-brand-700">
					<Package class="h-4 w-4" /> {{ row.name }}
				</span>
			</template>
			<template #cell-status="{ value }"><StatusBadge :status="String(value)" /></template>
			<template #cell-container="{ value }">
				<span :class="!value && 'text-gray-400'">{{ value || "loose cargo" }}</span>
			</template>
			<template #cell-total_charges="{ value }">{{ fmtMoney(value as number) }}</template>
		</DataTable>

		<!-- ── New shipment ──────────────────────────────────────────────── -->
		<Dialog v-model:open="dialogOpen" title="New shipment" size="xl">
			<div class="grid gap-4 sm:grid-cols-2">
				<div class="space-y-1.5">
					<Label required>Customer</Label>
					<Select v-model="form.customer" :options="customerOptions" placeholder="Select customer" />
				</div>
				<div class="space-y-1.5">
					<Label>Container (tag for notifications)</Label>
					<Select v-model="form.container" :options="containerOptions" placeholder="None — loose cargo" />
				</div>
				<div class="space-y-1.5">
					<Label required>Direction</Label>
					<Select v-model="form.direction" :options="['Import', 'Export']" />
				</div>
				<div class="space-y-1.5">
					<Label>Destination</Label>
					<Input v-model="form.destination" placeholder="e.g. Accra" />
				</div>
				<div class="space-y-1.5">
					<Label>Consignee (receiver)</Label>
					<Input v-model="form.consignee_name" placeholder="Receiver name" />
				</div>
				<div class="space-y-1.5">
					<Label>Consignee phone</Label>
					<Input v-model="form.consignee_phone" placeholder="+233…" />
				</div>
				<div class="space-y-1.5 sm:col-span-2">
					<Label>Delivery address</Label>
					<Textarea v-model="form.delivery_address" :rows="2" />
				</div>
			</div>

			<!-- Packages -->
			<div class="mt-6">
				<div class="mb-2 flex items-center justify-between">
					<Label required>Packages</Label>
					<button type="button" class="text-xs font-medium text-brand-700 hover:underline" @click="addPackage">+ Add package</button>
				</div>
				<div class="space-y-2">
					<div v-for="(p, i) in form.packages" :key="i" class="flex items-center gap-2">
						<Input v-model="p.description" placeholder="Description (e.g. Barrel — household goods)" class="flex-1" />
						<Input v-model.number="p.qty" type="number" min="1" placeholder="Qty" class="w-20" />
						<Input v-model.number="p.weight_kg" type="number" min="0" placeholder="kg" class="w-24" />
						<Input v-model.number="p.declared_value" type="number" min="0" placeholder="Value" class="w-28" />
						<button
							type="button"
							class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-gray-400 hover:bg-red-50 hover:text-red-600"
							:disabled="form.packages.length === 1"
							@click="form.packages.splice(i, 1)"
						>
							<Trash2 class="h-4 w-4" />
						</button>
					</div>
				</div>
			</div>

			<!-- Charges -->
			<div class="mt-6">
				<div class="mb-2 flex items-center justify-between">
					<Label>Charges (invoiced later from Billing)</Label>
					<button type="button" class="text-xs font-medium text-brand-700 hover:underline" @click="addCharge">+ Add charge</button>
				</div>
				<div v-if="!form.charges.length" class="rounded-lg bg-gray-50 px-3 py-2.5 text-xs text-muted-foreground">
					No charges yet — you can add them now or later on the shipment page.
				</div>
				<div class="space-y-2">
					<div v-for="(c, i) in form.charges" :key="i" class="flex items-center gap-2">
						<Input v-model="c.charge_type" placeholder="Charge (e.g. Freight)" class="flex-1" />
						<Input v-model.number="c.amount" type="number" min="0" placeholder="Amount" class="w-32" />
						<button
							type="button"
							class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-gray-400 hover:bg-red-50 hover:text-red-600"
							@click="form.charges.splice(i, 1)"
						>
							<Trash2 class="h-4 w-4" />
						</button>
					</div>
				</div>
			</div>

			<template #footer>
				<div class="flex justify-end gap-2">
					<Button variant="outline" @click="dialogOpen = false">Cancel</Button>
					<Button :loading="saving" @click="save">Create shipment</Button>
				</div>
			</template>
		</Dialog>
	</div>
</template>
