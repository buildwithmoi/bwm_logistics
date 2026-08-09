<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { Trash2 } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtMoney } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import { useBranchStore } from "@/stores/branch";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Select from "@/components/ui/Select.vue";
import SearchCombo from "@/components/ui/SearchCombo.vue";
import Textarea from "@/components/ui/Textarea.vue";
import FormPage from "@/components/ui/FormPage.vue";
import FormSection from "@/components/ui/FormSection.vue";

// New shipment. The old dialog had five inputs on one line, which a phone could
// not show — here each package/charge is its own block on small screens and
// collapses to a single row from sm up.
const router = useRouter();
const toast = useToast();
const branch = useBranchStore();

const saving = ref(false);

interface ChargeRow {
	charge_type: string;
	amount: number | null;
}
const form = reactive({
	shipment_type: "Own Goods (Trading)",
	customer: "" as string | null,
	supplier: "" as string | null,
	// A booking can ride in several boxes; what's *in* each box is recorded on
	// the container itself, because a consolidated box carries several people's
	// goods and only the container knows whose is whose.
	containers: [] as Array<{ container: string; label: string }>,
	direction: "Import",
	// The voyage. Typed once here and written down to every container on the
	// booking — the sailing is the same for all of them, so asking per box was
	// asking for the same answer several times.
	shipping_line: "" as string | null,
	vessel: "",
	voyage_no: "",
	booking_no: "",
	port_of_loading: "" as string | null,
	port_of_discharge: "" as string | null,
	etd: "",
	eta: "",
	date_received: "",
	consignee_name: "",
	consignee_phone: "",
	destination: "",
	delivery_address: "",
	charges: [] as ChargeRow[],
});

// Shipping lines and ports come from the masters list, filtered client-side,
// with an inline create so an unknown one never blocks the booking.
interface Masters {
	shipping_lines: string[];
	ports: string[];
}
const masters = ref<Masters>({ shipping_lines: [], ports: [] });
onMounted(async () => {
	try {
		masters.value = await call<Masters>("bwm_logistics.api.containers.get_masters");
	} catch {
		/* dropdowns degrade to free entry */
	}
});

type MasterHit = Record<string, unknown> & { name: string };
function masterFetcher(list: () => string[]) {
	return async (q: string): Promise<MasterHit[]> =>
		list()
			.filter((n) => n.toLowerCase().includes(q.toLowerCase()))
			.slice(0, 20)
			.map((n) => ({ name: n }));
}
const fetchLines = masterFetcher(() => masters.value.shipping_lines);
const fetchPorts = masterFetcher(() => masters.value.ports);

async function quickAdd(
	doctype: "Shipping Line" | "Port",
	field: "shipping_line" | "port_of_loading" | "port_of_discharge",
	value: string,
) {
	if (!value) return;
	try {
		const res = await call<{ name: string }>("bwm_logistics.api.containers.quick_add_master", { doctype, value });
		if (doctype === "Shipping Line" && !masters.value.shipping_lines.includes(res.name)) {
			masters.value.shipping_lines.push(res.name);
		} else if (doctype === "Port" && !masters.value.ports.includes(res.name)) {
			masters.value.ports.push(res.name);
		}
		form[field] = res.name;
		toast.success(`${doctype} “${res.name}” added`);
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not add");
	}
}

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
const supplierDisplay = ref<string | null>(null);
// The picker clears itself after each pick so several boxes can be added in a row.
const containerPick = ref<string | null>(null);
const containerPickLabel = ref<string | null>(null);

async function fetchCustomers(q: string): Promise<CustomerHit[]> {
	const res = await call<{ rows: CustomerHit[] }>("bwm_logistics.api.customers.list_customers", {
		search: q || null,
		limit: 20,
	});
	return res.rows;
}
interface SupplierHit extends Record<string, unknown> {
	name: string;
	supplier_name: string;
}
async function fetchSuppliers(q: string): Promise<SupplierHit[]> {
	return call<SupplierHit[]>("bwm_logistics.api.purchasing.list_suppliers", { search: q || null });
}
async function createSupplier(name: string) {
	if (!name) return;
	try {
		const res = await call<{ name: string }>("bwm_logistics.api.purchasing.create_supplier", {
			supplier_name: name,
		});
		form.supplier = res.name;
		supplierDisplay.value = name;
		toast.success(`Supplier “${name}” added`);
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not add supplier");
	}
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

function addContainer(name: string | null) {
	if (!name || form.containers.some((c) => c.container === name)) return;
	form.containers.push({ container: name, label: containerPickLabel.value || name });
	containerPick.value = null;
	containerPickLabel.value = null;
}
function addCharge() {
	form.charges.push({ charge_type: "", amount: null });
}

const isTrading = computed(() => form.shipment_type === "Own Goods (Trading)");
const chargesTotal = computed(() => form.charges.reduce((n, c) => n + (c.amount || 0), 0));

async function save() {
	if (!isTrading.value && !form.customer) {
		toast.warning("Pick a customer");
		return;
	}
	saving.value = true;
	try {
		const res = await call<{ name: string }>("bwm_logistics.api.shipments.save_shipment", {
			payload: {
				...form,
				customer: isTrading.value ? null : form.customer,
				supplier: form.supplier || null,
				// Empty date inputs are "", which a Date field must not be handed.
				etd: form.etd || null,
				eta: form.eta || null,
				date_received: form.date_received || null,
				shipping_line: form.shipping_line || null,
				port_of_loading: form.port_of_loading || null,
				port_of_discharge: form.port_of_discharge || null,
				containers: form.containers.map((c) => c.container),
				branch: branch.filter,
				charges: form.charges.filter((c) => c.charge_type),
			},
		});
		toast.success(`Shipment ${res.name} created`);
		router.push(`/shipments/${res.name}`);
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not save shipment");
	} finally {
		saving.value = false;
	}
}
</script>

<template>
	<FormPage title="New shipment" back-to="/shipments" back-label="Shipments">
		<FormSection title="Type">
			<div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
				<button
					v-for="t in ['Own Goods (Trading)', 'Customer Cargo']"
					:key="t"
					type="button"
					class="rounded-xl border px-4 py-3 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
					:class="form.shipment_type === t ? 'border-brand-400 bg-brand-50' : 'border-gray-200 hover:bg-gray-50'"
					:aria-pressed="form.shipment_type === t"
					@click="form.shipment_type = t"
				>
					<span class="block text-sm font-semibold">{{ t }}</span>
					<span class="block text-pretty text-xs text-muted-foreground">
						{{ t === "Customer Cargo" ? "A customer's goods — they get tracked & notified" : "Your own goods to sell — carries costs & sales for a P&L" }}
					</span>
				</button>
			</div>
		</FormSection>

		<FormSection title="Details">
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
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
					<Label>Supplier</Label>
					<SearchCombo
						v-model="form.supplier"
						v-model:display-value="supplierDisplay"
						:fetcher="fetchSuppliers"
						value-key="name"
						label-key="supplier_name"
						placeholder="Search supplier…"
						create-label="Add supplier"
						@create="createSupplier"
					/>
				</div>
				<div class="space-y-1.5">
					<Label for="s-direction" required>Direction</Label>
					<Select id="s-direction" v-model="form.direction" :options="['Import', 'Export']" />
				</div>
				<div class="space-y-1.5">
					<Label for="s-destination">Destination</Label>
					<Input id="s-destination" v-model="form.destination" placeholder="e.g. Accra" />
				</div>
				<!-- Own goods are consigned to us, so there is nobody to name. -->
				<div v-if="!isTrading" class="space-y-1.5">
					<Label for="s-consignee">Consignee (who receives it)</Label>
					<Input id="s-consignee" v-model="form.consignee_name" placeholder="Defaults to the customer" />
				</div>
				<div v-if="!isTrading" class="space-y-1.5">
					<Label for="s-phone">Consignee phone</Label>
					<Input id="s-phone" v-model="form.consignee_phone" type="tel" inputmode="tel" placeholder="+233…" />
				</div>
				<div class="space-y-1.5 sm:col-span-2">
					<Label for="s-address">Delivery address</Label>
					<Textarea id="s-address" v-model="form.delivery_address" :rows="2" />
				</div>
			</div>
		</FormSection>

		<FormSection
			title="Containers"
			hint="Every box this booking rides in. What's inside each one — and whose it is — is recorded on the container."
		>
			<div class="space-y-3">
				<div v-if="form.containers.length" class="space-y-1.5">
					<div
						v-for="(c, i) in form.containers"
						:key="c.container"
						class="flex items-center gap-3 rounded-xl border border-gray-200 px-3.5 py-2.5"
					>
						<span class="min-w-0 flex-1 truncate text-sm font-medium">{{ c.label }}</span>
						<button
							type="button"
							class="shrink-0 rounded-lg px-2 py-1 text-[13px] text-gray-500 hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
							:aria-label="`Remove ${c.label}`"
							@click="form.containers.splice(i, 1)"
						>
							Remove
						</button>
					</div>
				</div>
				<div class="space-y-1.5">
					<Label>Add a container</Label>
					<SearchCombo
						v-model="containerPick"
						v-model:display-value="containerPickLabel"
						:fetcher="fetchContainers"
						value-key="name"
						label-key="label"
						sublabel-key="sub"
						placeholder="Search container… (leave empty for loose cargo)"
						@update:model-value="(v) => addContainer(v as string | null)"
					/>
				</div>
			</div>
		</FormSection>

		<FormSection
			title="Voyage &amp; dates"
			hint="Entered once here and applied to every container on this booking — they all sail together."
		>
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
				<div class="space-y-1.5">
					<Label>Shipping line</Label>
					<SearchCombo
						v-model="form.shipping_line"
						:fetcher="fetchLines"
						value-key="name"
						label-key="name"
						placeholder="Search shipping line…"
						create-label="Add line"
						@create="(q) => quickAdd('Shipping Line', 'shipping_line', q)"
					/>
				</div>
				<div class="space-y-1.5">
					<Label for="s-vessel">Vessel</Label>
					<Input id="s-vessel" v-model="form.vessel" placeholder="Vessel name" />
				</div>
				<div class="space-y-1.5">
					<Label for="s-voyage">Voyage no</Label>
					<Input id="s-voyage" v-model="form.voyage_no" spellcheck="false" />
				</div>
				<div class="space-y-1.5">
					<Label for="s-booking">Booking no</Label>
					<Input id="s-booking" v-model="form.booking_no" spellcheck="false" />
				</div>
				<div class="space-y-1.5">
					<Label>Port of loading</Label>
					<SearchCombo
						v-model="form.port_of_loading"
						:fetcher="fetchPorts"
						value-key="name"
						label-key="name"
						placeholder="Search port…"
						create-label="Add port"
						@create="(q) => quickAdd('Port', 'port_of_loading', q)"
					/>
				</div>
				<div class="space-y-1.5">
					<Label>Port of discharge</Label>
					<SearchCombo
						v-model="form.port_of_discharge"
						:fetcher="fetchPorts"
						value-key="name"
						label-key="name"
						placeholder="Search port…"
						create-label="Add port"
						@create="(q) => quickAdd('Port', 'port_of_discharge', q)"
					/>
				</div>
			</div>
			<div class="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
				<div class="space-y-1.5">
					<Label for="s-etd">ETD</Label>
					<Input id="s-etd" v-model="form.etd" type="date" />
				</div>
				<div class="space-y-1.5">
					<Label for="s-eta">ETA</Label>
					<Input id="s-eta" v-model="form.eta" type="date" />
				</div>
				<div class="space-y-1.5">
					<Label for="s-received">Date received</Label>
					<Input id="s-received" v-model="form.date_received" type="date" />
					<p class="text-xs text-muted-foreground">Starts the demurrage clock on each box.</p>
				</div>
			</div>
		</FormSection>

		<FormSection title="Charges" hint="Invoiced later from Billing — add them now or on the shipment page.">
			<template #action>
				<button
					type="button"
					class="shrink-0 text-xs font-medium text-brand-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
					@click="addCharge"
				>
					+ Add charge
				</button>
			</template>
			<div v-if="!form.charges.length" class="rounded-lg bg-gray-50 px-3 py-2.5 text-xs text-muted-foreground">
				No charges yet.
			</div>
			<div v-else class="space-y-3">
				<div
					v-for="(c, i) in form.charges"
					:key="i"
					class="rounded-xl border border-border p-3 sm:flex sm:items-end sm:gap-2 sm:border-0 sm:p-0"
				>
					<div class="space-y-1.5 sm:min-w-0 sm:flex-1">
						<Label :for="`chg-type-${i}`">Charge</Label>
						<Input :id="`chg-type-${i}`" v-model="c.charge_type" placeholder="e.g. Freight" />
					</div>
					<div class="mt-2 space-y-1.5 sm:mt-0 sm:w-36">
						<Label :for="`chg-amt-${i}`">Amount</Label>
						<Input :id="`chg-amt-${i}`" v-model.number="c.amount" type="number" min="0" inputmode="decimal" />
					</div>
					<button
						type="button"
						class="mt-2 flex h-9 w-full shrink-0 items-center justify-center gap-1.5 rounded-lg text-[13px] text-gray-500 hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 sm:mt-0 sm:w-9 sm:text-transparent"
						:aria-label="`Remove charge ${i + 1}`"
						@click="form.charges.splice(i, 1)"
					>
						<Trash2 class="h-4 w-4 text-gray-400" aria-hidden="true" />
						<span class="sm:hidden">Remove</span>
					</button>
				</div>
				<div class="flex justify-end border-t border-gray-100 pt-3 text-sm font-semibold tabular-nums">
					Total: {{ fmtMoney(chargesTotal) }}
				</div>
			</div>
		</FormSection>

		<template #actions>
			<Button variant="outline" @click="router.push('/shipments')">Cancel</Button>
			<Button :loading="saving" @click="save">Create shipment</Button>
		</template>
	</FormPage>
</template>
