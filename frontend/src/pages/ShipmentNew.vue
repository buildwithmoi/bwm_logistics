<script setup lang="ts">
import { computed, reactive, ref } from "vue";
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
	shipment_type: "Own Goods (Trading)",
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

function addPackage() {
	form.packages.push({ description: "", qty: 1, unit: "PIECES", weight_kg: null, declared_value: null });
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
					<Label for="s-direction" required>Direction</Label>
					<Select id="s-direction" v-model="form.direction" :options="['Import', 'Export']" />
				</div>
				<div class="space-y-1.5">
					<Label for="s-destination">Destination</Label>
					<Input id="s-destination" v-model="form.destination" placeholder="e.g. Accra" />
				</div>
				<div class="space-y-1.5">
					<Label for="s-consignee">Consignee (receiver)</Label>
					<Input id="s-consignee" v-model="form.consignee_name" placeholder="Receiver name" />
				</div>
				<div class="space-y-1.5">
					<Label for="s-phone">Consignee phone</Label>
					<Input id="s-phone" v-model="form.consignee_phone" type="tel" inputmode="tel" placeholder="+233…" />
				</div>
				<div class="space-y-1.5 sm:col-span-2">
					<Label for="s-address">Delivery address</Label>
					<Textarea id="s-address" v-model="form.delivery_address" :rows="2" />
				</div>
			</div>
		</FormSection>

		<FormSection title="Packages">
			<template #action>
				<button
					type="button"
					class="shrink-0 text-xs font-medium text-brand-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
					@click="addPackage"
				>
					+ Add package
				</button>
			</template>
			<div class="space-y-3">
				<div
					v-for="(p, i) in form.packages"
					:key="i"
					class="rounded-xl border border-border p-3 sm:flex sm:items-end sm:gap-2 sm:border-0 sm:p-0"
				>
					<div class="space-y-1.5 sm:min-w-0 sm:flex-1">
						<Label :for="`pkg-desc-${i}`">Description</Label>
						<Input :id="`pkg-desc-${i}`" v-model="p.description" placeholder="e.g. US Hen Leg Quarter" />
					</div>
					<div class="mt-2 grid grid-cols-2 gap-2 sm:mt-0 sm:flex sm:items-end">
						<div class="space-y-1.5 sm:w-20">
							<Label :for="`pkg-qty-${i}`">Qty</Label>
							<Input :id="`pkg-qty-${i}`" v-model.number="p.qty" type="number" min="1" inputmode="numeric" />
						</div>
						<div class="space-y-1.5 sm:w-32">
							<Label :for="`pkg-unit-${i}`">Unit</Label>
							<Select :id="`pkg-unit-${i}`" v-model="p.unit" :options="UNITS" />
						</div>
						<div class="space-y-1.5 sm:w-24">
							<Label :for="`pkg-kg-${i}`">Weight kg</Label>
							<Input :id="`pkg-kg-${i}`" v-model.number="p.weight_kg" type="number" min="0" inputmode="decimal" />
						</div>
						<div class="space-y-1.5 sm:w-28">
							<Label :for="`pkg-val-${i}`">Value</Label>
							<Input :id="`pkg-val-${i}`" v-model.number="p.declared_value" type="number" min="0" inputmode="decimal" />
						</div>
					</div>
					<button
						type="button"
						class="mt-2 flex h-9 w-full shrink-0 items-center justify-center gap-1.5 rounded-lg text-[13px] text-gray-500 hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-40 sm:mt-0 sm:w-9 sm:text-transparent"
						:disabled="form.packages.length === 1"
						:aria-label="`Remove package ${i + 1}`"
						@click="form.packages.splice(i, 1)"
					>
						<Trash2 class="h-4 w-4 text-gray-400" aria-hidden="true" />
						<span class="sm:hidden">Remove</span>
					</button>
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
