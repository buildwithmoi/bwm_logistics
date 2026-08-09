<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { Trash2 } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { useToast } from "@/composables/useToast";
import { useBranchStore } from "@/stores/branch";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Select from "@/components/ui/Select.vue";
import SearchCombo from "@/components/ui/SearchCombo.vue";
import FormPage from "@/components/ui/FormPage.vue";
import FormSection from "@/components/ui/FormSection.vue";

// New container — the voyage paperwork, grouped the way it arrives: what it is,
// which ship it's on, which ports, and the demurrage clock.
const router = useRouter();
const toast = useToast();
const branch = useBranchStore();

const saving = ref(false);

// ── the manifest ────────────────────────────────────────────────────────────
// What is in the box, and whose it is. `customer` empty means the goods are
// ours; set, it names the customer whose cargo is riding in a consolidated box,
// which is what lets a milestone notification say "your 200 cartons".
interface ContentRow {
	item: string | null;
	label: string | null;
	qty: number | null;
	unit: string;
	customer: string | null;
	customerLabel: string | null;
}
function blankLine(): ContentRow {
	return { item: null, label: null, qty: null, unit: "Nos", customer: null, customerLabel: null };
}

interface ItemHit extends Record<string, unknown> {
	name: string;
	item_name: string;
	stock_uom: string;
}
/** Only the goods this direction can carry — an export box never offers
 *  the frozen chicken you only ever import. */
async function fetchItems(q: string): Promise<ItemHit[]> {
	return call<ItemHit[]>("bwm_logistics.api.items.list_items", {
		search: q || null,
		direction: form.direction,
	});
}
async function createItem(name: string, row: ContentRow) {
	if (!name) return;
	try {
		const res = await call<{ name: string; item_name: string; stock_uom: string }>(
			"bwm_logistics.api.items.save_item",
			{ payload: { item_name: name, direction: form.direction } },
		);
		row.item = res.name;
		row.label = res.item_name;
		row.unit = res.stock_uom || row.unit;
		toast.success(`“${res.item_name}” added to the catalogue`);
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not add item");
	}
}

interface CustomerHit extends Record<string, unknown> {
	name: string;
	customer_name: string;
}
async function fetchCustomers(q: string): Promise<CustomerHit[]> {
	const res = await call<{ rows: CustomerHit[] }>("bwm_logistics.api.customers.list_customers", {
		search: q || null,
		limit: 20,
	});
	return res.rows;
}

const form = reactive({
	direction: "Import",
	container_no: "",
	container_type: "",
	shipping_line: "" as string | null,
	vessel: "",
	bl_no: "",
	booking_no: "",
	port_of_loading: "" as string | null,
	port_of_discharge: "" as string | null,
	etd: "",
	eta: "",
	free_days: "",
	contents: [blankLine()] as ContentRow[],
});

interface Masters {
	shipping_lines: string[];
	ports: string[];
	container_types: string[];
}
const masters = ref<Masters>({ shipping_lines: [], ports: [], container_types: [] });
onMounted(async () => {
	try {
		masters.value = await call<Masters>("bwm_logistics.api.containers.get_masters");
	} catch {
		/* dropdowns degrade to free entry */
	}
});

// Link-field fetchers: client-side filter over the masters list, with an
// inline "create" action so unknown lines/ports never block the flow.
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
				contents: form.contents
					.filter((c) => c.item)
					.map((c) => ({
						item: c.item,
						description: c.label,
						qty: c.qty || 0,
						unit: c.unit,
						customer: c.customer || null,
					})),
			},
		});
		toast.success("Container created");
		router.push(`/containers/${res.name}`);
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not save container");
	} finally {
		saving.value = false;
	}
}
</script>

<template>
	<FormPage
		title="New container"
		subtitle="Only Direction is required — the rest can be filled in as the paperwork arrives."
		back-to="/containers"
		back-label="Containers"
	>
		<FormSection title="Container">
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
				<div class="space-y-1.5">
					<Label for="c-direction" required>Direction</Label>
					<Select id="c-direction" v-model="form.direction" :options="['Import', 'Export']" />
				</div>
				<div class="space-y-1.5">
					<Label for="c-no">Container No</Label>
					<Input id="c-no" v-model="form.container_no" placeholder="MSCU1234567" spellcheck="false" />
				</div>
				<div class="space-y-1.5">
					<Label for="c-type">Type</Label>
					<Select id="c-type" v-model="form.container_type" :options="masters.container_types" placeholder="Select type" />
				</div>
				<div class="space-y-1.5">
					<Label for="c-bl">Master BL No</Label>
					<Input id="c-bl" v-model="form.bl_no" spellcheck="false" />
				</div>
				<div class="space-y-1.5">
					<Label for="c-booking">Booking No</Label>
					<Input id="c-booking" v-model="form.booking_no" spellcheck="false" />
				</div>
			</div>
		</FormSection>

		<FormSection title="Voyage">
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
					<Label for="c-vessel">Vessel</Label>
					<Input id="c-vessel" v-model="form.vessel" placeholder="Vessel name" />
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
		</FormSection>

		<FormSection
			title="Contents"
			hint="What's in the box. Leave Customer empty for your own goods; name a customer for cargo you're carrying for them."
		>
			<template #action>
				<button
					type="button"
					class="shrink-0 text-xs font-medium text-brand-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
					@click="form.contents.push(blankLine())"
				>
					+ Add line
				</button>
			</template>
			<div class="space-y-3">
				<div
					v-for="(c, i) in form.contents"
					:key="i"
					class="rounded-xl border border-border p-3 sm:flex sm:items-end sm:gap-2 sm:border-0 sm:p-0"
				>
					<div class="space-y-1.5 sm:min-w-0 sm:flex-1">
						<Label>Item</Label>
						<SearchCombo
							v-model="c.item"
							v-model:display-value="c.label"
							:fetcher="fetchItems"
							value-key="name"
							label-key="item_name"
							sublabel-key="stock_uom"
							placeholder="Search goods…"
							create-label="Add item"
							@create="(q) => createItem(q, c)"
						/>
					</div>
					<div class="mt-2 grid grid-cols-2 gap-2 sm:mt-0 sm:flex sm:items-end">
						<div class="space-y-1.5 sm:w-24">
							<Label :for="`ct-qty-${i}`">Qty</Label>
							<Input :id="`ct-qty-${i}`" v-model.number="c.qty" type="number" min="0" inputmode="decimal" />
						</div>
						<div class="space-y-1.5 sm:w-24">
							<Label :for="`ct-unit-${i}`">Unit</Label>
							<Input :id="`ct-unit-${i}`" v-model="c.unit" />
						</div>
					</div>
					<div class="mt-2 space-y-1.5 sm:mt-0 sm:w-52">
						<Label>Customer</Label>
						<SearchCombo
							v-model="c.customer"
							v-model:display-value="c.customerLabel"
							:fetcher="fetchCustomers"
							value-key="name"
							label-key="customer_name"
							placeholder="Own goods"
						/>
					</div>
					<button
						type="button"
						class="mt-2 flex h-9 w-full shrink-0 items-center justify-center gap-1.5 rounded-lg text-[13px] text-gray-500 hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-40 sm:mt-0 sm:w-9 sm:text-transparent"
						:disabled="form.contents.length === 1"
						:aria-label="`Remove line ${i + 1}`"
						@click="form.contents.splice(i, 1)"
					>
						<Trash2 class="h-4 w-4 text-gray-400" aria-hidden="true" />
						<span class="sm:hidden">Remove</span>
					</button>
				</div>
			</div>
		</FormSection>

		<FormSection title="Dates" hint="Free days start the demurrage clock once the box lands.">
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
				<div class="space-y-1.5">
					<Label for="c-etd">ETD</Label>
					<Input id="c-etd" v-model="form.etd" type="date" />
				</div>
				<div class="space-y-1.5">
					<Label for="c-eta">ETA</Label>
					<Input id="c-eta" v-model="form.eta" type="date" />
				</div>
				<div class="space-y-1.5">
					<Label for="c-free">Free days</Label>
					<Input id="c-free" v-model="form.free_days" type="number" min="0" inputmode="numeric" />
				</div>
			</div>
		</FormSection>

		<template #actions>
			<Button variant="outline" @click="router.push('/containers')">Cancel</Button>
			<Button :loading="saving" @click="save">Create container</Button>
		</template>
	</FormPage>
</template>
