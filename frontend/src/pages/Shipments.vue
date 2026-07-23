<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Plus, Search, Package, Trash2 } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtMoney } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import { useBranchStore } from "@/stores/branch";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Select from "@/components/ui/Select.vue";
import SearchCombo from "@/components/ui/SearchCombo.vue";
import Textarea from "@/components/ui/Textarea.vue";
import Dialog from "@/components/ui/Dialog.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import DirectionBadge from "@/components/DirectionBadge.vue";

const router = useRouter();
const toast = useToast();
const session = useSessionStore();
const branch = useBranchStore();

// ── list ────────────────────────────────────────────────────────────────────
const rows = ref<Record<string, unknown>[]>([]);
const total = ref(0);
const loading = ref(false);
const search = ref("");
const statusFilter = ref("");
const directionFilter = ref("");
const PAGE = 25;

async function load(append = false) {
	loading.value = true;
	try {
		const res = await call<{ rows: Record<string, unknown>[]; total: number }>(
			"bwm_logistics.api.shipments.list_shipments",
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
watch(directionFilter, () => load());
onMounted(load);

const columns: Column[] = [
	{ key: "name", label: "Tracking No" },
	{ key: "customer_name", label: "Customer" },
	{ key: "direction", label: "Direction" },
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
	unit: string;
	weight_kg: number | null;
	declared_value: number | null;
}
const UNITS = ["PIECES", "CARTONS", "BOXES", "BAGS", "PALLETS", "KG", "UNITS"];
interface ChargeRow {
	charge_type: string;
	amount: number | null;
}
const form = reactive({
	shipment_type: "Customer Cargo",
	customer: "" as string | null,
	container: "" as string | null,
	direction: "Import",
	consignee_name: "",
	consignee_phone: "",
	destination: "",
	delivery_address: "",
	packages: [{ description: "", qty: 1, unit: "PIECES", weight_kg: null, declared_value: null }] as PkgRow[],
	charges: [] as ChargeRow[],
});

// Server-searched link fields (SearchCombo fetchers).
interface CustomerHit extends Record<string, unknown> {
	name: string;
	customer_name: string;
	mobile_no?: string;
}
interface ContainerHit extends Record<string, unknown> {
	name: string;
	label: string;
	sub: string;
}
const customerDisplay = ref<string | null>(null);
const containerDisplay = ref<string | null>(null);

async function fetchCustomers(q: string): Promise<CustomerHit[]> {
	const res = await call<{ rows: CustomerHit[] }>("bwm_logistics.api.customers.list_customers", {
		search: q || null,
		limit: 20,
	});
	return res.rows;
}
async function fetchContainers(q: string): Promise<ContainerHit[]> {
	const res = await call<{ rows: Array<{ name: string; container_no?: string; direction: string; vessel?: string; eta?: string }> }>(
		"bwm_logistics.api.containers.list_containers",
		{ status: "Active", search: q || null, limit: 20 },
	);
	return res.rows.map((c) => ({
		name: c.name,
		label: c.container_no || c.name,
		sub: [c.direction, c.vessel, c.eta ? `ETA ${c.eta}` : null].filter(Boolean).join(" · "),
	}));
}

function openDialog() {
	dialogOpen.value = true;
	customerDisplay.value = null;
	containerDisplay.value = null;
}

function addPackage() {
	form.packages.push({ description: "", qty: 1, unit: "PIECES", weight_kg: null, declared_value: null });
}
function addCharge() {
	form.charges.push({ charge_type: "", amount: null });
}

const isTrading = computed(() => form.shipment_type === "Own Goods (Trading)");

async function save() {
	if (!isTrading.value && !form.customer) {
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
				customer: isTrading.value ? null : form.customer,
				container: form.container || null,
				branch: branch.filter,
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

		<!-- Direction — the primary lens (Import vs Export) -->
		<div class="mb-4 flex gap-1.5">
			<button
				v-for="d in ['', 'Import', 'Export']"
				:key="d"
				type="button"
				class="rounded-full px-4 py-2 text-sm font-semibold transition-colors"
				:class="
					directionFilter === d
						? 'bg-coal-900 text-white'
						: 'bg-white text-gray-600 ring-1 ring-gray-200 hover:bg-gray-50'
				"
				@click="directionFilter = d"
			>
				{{ d === "Import" ? "⬇ Imports" : d === "Export" ? "⬆ Exports" : "All" }}
			</button>
		</div>

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
			<template #cell-customer_name="{ row }">
				<span v-if="row.shipment_type === 'Own Goods (Trading)'" class="inline-flex items-center rounded-full bg-brand-600/10 px-2.5 py-0.5 text-[11.5px] font-semibold text-brand-700">
					Own goods
				</span>
				<template v-else>{{ row.customer_name || "—" }}</template>
			</template>
			<template #cell-direction="{ value }"><DirectionBadge :direction="String(value)" /></template>
			<template #cell-status="{ value, row }">
				<span class="inline-flex items-center gap-1.5">
					<StatusBadge :status="String(value)" />
					<span
						v-if="row.current_milestone === 'Delayed'"
						class="inline-flex items-center rounded-full bg-red-50 px-2 py-0.5 text-[10.5px] font-semibold text-red-700 ring-1 ring-red-200"
					>Delayed</span>
				</span>
			</template>
			<template #cell-container="{ value }">
				<span :class="!value && 'text-gray-400'">{{ value || "loose cargo" }}</span>
			</template>
			<template #cell-total_charges="{ value }">{{ fmtMoney(value as number) }}</template>
		</DataTable>

		<!-- ── New shipment ──────────────────────────────────────────────── -->
		<Dialog v-model:open="dialogOpen" title="New shipment" size="xl">
			<!-- Type toggle -->
			<div class="mb-4 flex gap-2">
				<button
					v-for="t in ['Customer Cargo', 'Own Goods (Trading)']"
					:key="t"
					type="button"
					class="flex-1 rounded-xl border px-4 py-3 text-left transition-colors"
					:class="form.shipment_type === t ? 'border-brand-400 bg-brand-50' : 'border-gray-200 hover:bg-gray-50'"
					@click="form.shipment_type = t"
				>
					<span class="block text-sm font-semibold">{{ t }}</span>
					<span class="block text-xs text-muted-foreground">
						{{ t === "Customer Cargo" ? "A customer's goods — they get tracked & notified" : "Your own goods to sell — carries costs & sales for a P&L" }}
					</span>
				</button>
			</div>

			<div class="grid gap-4 sm:grid-cols-2">
				<div v-if="!isTrading" class="space-y-1.5">
					<Label required>Customer</Label>
					<SearchCombo
						v-model="form.customer"
						v-model:display-value="customerDisplay"
						:fetcher="fetchCustomers"
						value-key="name"
						label-key="customer_name"
						sublabel-key="mobile_no"
						placeholder="Search customer…"
					/>
				</div>
				<div class="space-y-1.5">
					<Label>Container (tag for notifications)</Label>
					<SearchCombo
						v-model="form.container"
						v-model:display-value="containerDisplay"
						:fetcher="fetchContainers"
						value-key="name"
						label-key="label"
						sublabel-key="sub"
						placeholder="Search container… (leave empty for loose cargo)"
					/>
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
						<Input v-model="p.description" placeholder="Description (e.g. US Hen Leg Quarter)" class="flex-1" />
						<Input v-model.number="p.qty" type="number" min="1" placeholder="Qty" class="w-20" />
						<div class="w-28 shrink-0"><Select v-model="p.unit" :options="UNITS" /></div>
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
