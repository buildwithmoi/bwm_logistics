<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Trash2 } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtMoney } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import SearchCombo from "@/components/ui/SearchCombo.vue";
import FormPage from "@/components/ui/FormPage.vue";
import FormSection from "@/components/ui/FormSection.vue";

// Record a supplier purchase. `?shipment=BWM-000001` pre-tags it so the cost
// lands on that shipment's P&L.
const route = useRoute();
const router = useRouter();
const toast = useToast();

interface CostLine {
	description: string;
	amount: number | null;
}
const saving = ref(false);
const form = reactive({
	supplier: "" as string | null,
	shipment: (route.query.shipment as string) || ("" as string | null),
	posting_date: new Date().toISOString().slice(0, 10),
	reference: "",
	// Seeded with the two costs that land on nearly every import.
	lines: [
		{ description: "Goods", amount: null },
		{ description: "Duties & taxes", amount: null },
	] as CostLine[],
});
const supplierDisplay = ref<string | null>(null);

interface SupplierHit extends Record<string, unknown> {
	name: string;
	supplier_name: string;
}
async function fetchSuppliers(q: string): Promise<SupplierHit[]> {
	return call<SupplierHit[]>("bwm_logistics.api.purchasing.list_suppliers", { search: q || null });
}
interface ShipmentHit extends Record<string, unknown> {
	name: string;
	sub: string;
}
async function fetchShipments(q: string): Promise<ShipmentHit[]> {
	const res = await call<{ rows: Array<{ name: string; customer_name?: string; shipment_type?: string; destination?: string }> }>(
		"bwm_logistics.api.shipments.list_shipments",
		{ search: q || null, limit: 20 },
	);
	return res.rows.map((s) => ({
		name: s.name,
		sub: s.shipment_type === "Own Goods (Trading)" ? `Own goods · ${s.destination || ""}` : s.customer_name || "",
	}));
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

const total = computed(() => form.lines.reduce((n, l) => n + (l.amount || 0), 0));

async function save() {
	if (!form.supplier) {
		toast.warning("Pick a supplier");
		return;
	}
	if (!form.lines.some((l) => l.description && l.amount)) {
		toast.warning("Add at least one cost line with an amount");
		return;
	}
	saving.value = true;
	try {
		const res = await call<{ purchase_invoice: string; grand_total: number }>(
			"bwm_logistics.api.purchasing.record_purchase",
			{
				payload: {
					supplier: form.supplier,
					shipment: form.shipment || null,
					posting_date: form.posting_date,
					reference: form.reference || null,
					lines: form.lines.filter((l) => l.description && l.amount),
				},
			},
		);
		toast.success(`Purchase ${res.purchase_invoice} — ${fmtMoney(res.grand_total)}`);
		router.push("/billing?tab=purchases");
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not record purchase");
	} finally {
		saving.value = false;
	}
}
</script>

<template>
	<FormPage
		title="Record purchase"
		subtitle="Tag it to a shipment and the cost lands on that shipment's P&amp;L."
		back-to="/billing?tab=purchases"
		back-label="Billing"
	>
		<FormSection title="Purchase">
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
				<div class="space-y-1.5">
					<Label required>Supplier</Label>
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
					<Label>Tag to shipment (for P&amp;L)</Label>
					<SearchCombo
						v-model="form.shipment"
						:fetcher="fetchShipments"
						value-key="name"
						label-key="name"
						sublabel-key="sub"
						placeholder="Optional — search shipment…"
					/>
				</div>
				<div class="space-y-1.5">
					<Label for="pur-date" required>Date</Label>
					<Input id="pur-date" v-model="form.posting_date" type="date" />
				</div>
				<div class="space-y-1.5">
					<Label for="pur-ref">Supplier bill no</Label>
					<Input id="pur-ref" v-model="form.reference" placeholder="Their invoice/reference" spellcheck="false" />
				</div>
			</div>
		</FormSection>

		<FormSection title="Cost lines">
			<template #action>
				<button
					type="button"
					class="shrink-0 text-xs font-medium text-brand-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
					@click="form.lines.push({ description: '', amount: null })"
				>
					+ Add cost
				</button>
			</template>
			<div class="space-y-3">
				<div
					v-for="(l, i) in form.lines"
					:key="i"
					class="rounded-xl border border-border p-3 sm:flex sm:items-end sm:gap-2 sm:border-0 sm:p-0"
				>
					<div class="space-y-1.5 sm:min-w-0 sm:flex-1">
						<Label :for="`pur-desc-${i}`">Cost</Label>
						<Input :id="`pur-desc-${i}`" v-model="l.description" placeholder="e.g. Import duty, Clearing, Goods" />
					</div>
					<div class="mt-2 space-y-1.5 sm:mt-0 sm:w-40">
						<Label :for="`pur-amt-${i}`">Amount</Label>
						<Input :id="`pur-amt-${i}`" v-model.number="l.amount" type="number" min="0" step="0.01" inputmode="decimal" />
					</div>
					<button
						type="button"
						class="mt-2 flex h-9 w-full shrink-0 items-center justify-center gap-1.5 rounded-lg text-[13px] text-gray-500 hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-40 sm:mt-0 sm:w-9 sm:text-transparent"
						:disabled="form.lines.length === 1"
						:aria-label="`Remove cost ${i + 1}`"
						@click="form.lines.splice(i, 1)"
					>
						<Trash2 class="h-4 w-4 text-gray-400" aria-hidden="true" />
						<span class="sm:hidden">Remove</span>
					</button>
				</div>
				<div class="flex justify-end border-t border-gray-100 pt-3 text-sm font-semibold tabular-nums">
					Total: {{ fmtMoney(total) }}
				</div>
			</div>
		</FormSection>

		<template #actions>
			<Button variant="outline" @click="router.push('/billing?tab=purchases')">Cancel</Button>
			<Button :loading="saving" @click="save">Record purchase</Button>
		</template>
	</FormPage>
</template>
