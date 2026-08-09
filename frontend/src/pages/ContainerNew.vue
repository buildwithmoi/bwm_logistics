<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
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

// The container form, for both creating one and correcting it afterwards —
// /containers/new and /containers/:name/edit are the same page. A record you
// can create but never fix is a record you have to get right first time.
const route = useRoute();
const router = useRouter();
const toast = useToast();
const branch = useBranchStore();

const editing = computed(() => (route.params.name ? String(route.params.name) : null));
const saving = ref(false);
const loading = ref(false);

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
	bl_no: "",
	free_days: "",
	contents: [blankLine()] as ContentRow[],
});

interface Masters {
	container_types: string[];
}
const masters = ref<Masters>({ container_types: [] });

interface ContainerDoc extends Record<string, unknown> {
	doc: Record<string, unknown>;
	contents?: Array<Record<string, unknown>>;
}
async function load(name: string) {
	loading.value = true;
	try {
		const data = await call<ContainerDoc>("bwm_logistics.api.containers.get_container", { name });
		const doc = data.doc || (data as Record<string, unknown>);
		form.direction = (doc.direction as string) || "Import";
		form.container_no = (doc.container_no as string) || "";
		form.container_type = (doc.container_type as string) || "";
		form.bl_no = (doc.bl_no as string) || "";
		form.free_days = doc.free_days == null ? "" : String(doc.free_days);
		const lines = (data.contents || []) as Array<Record<string, unknown>>;
		form.contents = lines.length
			? lines.map((c) => ({
					item: (c.item as string) ?? null,
					label: (c.description as string) ?? null,
					qty: (c.qty as number) ?? null,
					unit: (c.unit as string) || "Nos",
					customer: (c.customer as string) ?? null,
					customerLabel: (c.customer_name as string) ?? null,
				}))
			: [blankLine()];
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load container");
		router.push("/containers");
	} finally {
		loading.value = false;
	}
}

onMounted(async () => {
	try {
		masters.value = await call<Masters>("bwm_logistics.api.containers.get_masters");
	} catch {
		/* dropdowns degrade to free entry */
	}
	if (editing.value) await load(editing.value);
});

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
				name: editing.value,
				free_days: form.free_days ? Number(form.free_days) : null,
				// Branch is set when the box is created; an edit must not
				// silently move it to whatever the current filter happens to be.
				branch: editing.value ? undefined : branch.filter,
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
		toast.success(editing.value ? "Container saved" : "Container created");
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
		:title="editing ? 'Edit container' : 'New container'"
		:subtitle="editing ? undefined : 'Only Direction is required — the rest can be filled in as the paperwork arrives.'"
		:back-to="editing ? `/containers/${editing}` : '/containers'"
		:back-label="editing ? 'Container' : 'Containers'"
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
			</div>
		</FormSection>

		<!-- Voyage and dates are not asked for here. The sailing is the same for
		     every box on a booking, so they are typed once on the shipment and
		     written down from there — see Shipment.apply_voyage_to_containers(). -->

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

		<FormSection
			title="Demurrage"
			hint="Free days run from the day this box lands — the arrival date is entered on its shipment."
		>
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
				<div class="space-y-1.5">
					<Label for="c-free">Free days</Label>
					<Input id="c-free" v-model="form.free_days" type="number" min="0" inputmode="numeric" />
				</div>
			</div>
		</FormSection>

		<template #actions>
			<Button variant="outline" @click="router.push(editing ? `/containers/${editing}` : '/containers')">Cancel</Button>
			<Button :loading="saving" :disabled="loading" @click="save">
				{{ editing ? "Save changes" : "Create container" }}
			</Button>
		</template>
	</FormPage>
</template>
