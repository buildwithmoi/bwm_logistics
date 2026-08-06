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

// New (free-form) invoice. `?shipment=BWM-000001` pre-tags it, which is how the
// shipment page hands off — the URL carries the context a dialog used to hold
// in memory.
const route = useRoute();
const router = useRouter();
const toast = useToast();

interface SaleLine {
	description: string;
	qty: number;
	rate: number | null;
}
const saving = ref(false);
const form = reactive({
	customer: "" as string | null,
	shipment: (route.query.shipment as string) || ("" as string | null),
	due_date: "",
	lines: [{ description: "", qty: 1, rate: null }] as SaleLine[],
});
const customerDisplay = ref<string | null>(null);

interface CustomerHit extends Record<string, unknown> {
	name: string;
	customer_name: string;
	mobile_no?: string;
}
async function fetchCustomers(q: string): Promise<CustomerHit[]> {
	const res = await call<{ rows: CustomerHit[] }>("bwm_logistics.api.customers.list_customers", {
		search: q || null,
		limit: 20,
	});
	return res.rows;
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

const total = computed(() => form.lines.reduce((n, l) => n + (l.qty && l.rate ? l.qty * l.rate : 0), 0));

async function save() {
	if (!form.customer) {
		toast.warning("Pick a customer");
		return;
	}
	if (!form.lines.some((l) => l.description && l.rate)) {
		toast.warning("Add at least one line with a rate");
		return;
	}
	saving.value = true;
	try {
		const res = await call<{ sales_invoice: string; grand_total: number }>(
			"bwm_logistics.api.billing.new_invoice",
			{
				payload: {
					customer: form.customer,
					shipment: form.shipment || null,
					due_date: form.due_date || null,
					lines: form.lines.filter((l) => l.description && l.rate),
				},
			},
		);
		toast.success(`Invoice ${res.sales_invoice} — ${fmtMoney(res.grand_total)}`);
		router.push("/billing?tab=sales");
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not create invoice");
	} finally {
		saving.value = false;
	}
}
</script>

<template>
	<FormPage title="New invoice" back-to="/billing?tab=sales" back-label="Billing">
		<FormSection title="Invoice">
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
				<div class="space-y-1.5">
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
					<Label for="inv-due">Due date</Label>
					<Input id="inv-due" v-model="form.due_date" type="date" />
				</div>
			</div>
		</FormSection>

		<FormSection title="Lines">
			<template #action>
				<button
					type="button"
					class="shrink-0 text-xs font-medium text-brand-700 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
					@click="form.lines.push({ description: '', qty: 1, rate: null })"
				>
					+ Add line
				</button>
			</template>
			<div class="space-y-3">
				<div
					v-for="(l, i) in form.lines"
					:key="i"
					class="rounded-xl border border-border p-3 sm:flex sm:items-end sm:gap-2 sm:border-0 sm:p-0"
				>
					<div class="space-y-1.5 sm:min-w-0 sm:flex-1">
						<Label :for="`inv-desc-${i}`">Description</Label>
						<Input :id="`inv-desc-${i}`" v-model="l.description" placeholder="e.g. Chicken wings — carton" />
					</div>
					<div class="mt-2 grid grid-cols-2 gap-2 sm:mt-0 sm:flex sm:items-end">
						<div class="space-y-1.5 sm:w-24">
							<Label :for="`inv-qty-${i}`">Qty</Label>
							<Input :id="`inv-qty-${i}`" v-model.number="l.qty" type="number" min="0.01" step="0.01" inputmode="decimal" />
						</div>
						<div class="space-y-1.5 sm:w-28">
							<Label :for="`inv-rate-${i}`">Rate</Label>
							<Input :id="`inv-rate-${i}`" v-model.number="l.rate" type="number" min="0" step="0.01" inputmode="decimal" />
						</div>
					</div>
					<div class="mt-2 flex items-center justify-between gap-2 sm:mt-0 sm:block">
						<span class="text-sm tabular-nums text-muted-foreground sm:block sm:w-28 sm:pb-2 sm:text-right">
							{{ l.qty && l.rate ? fmtMoney(l.qty * l.rate) : "—" }}
						</span>
						<button
							type="button"
							class="flex h-9 shrink-0 items-center justify-center gap-1.5 rounded-lg px-2 text-[13px] text-gray-500 hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-40 sm:hidden"
							:disabled="form.lines.length === 1"
							:aria-label="`Remove line ${i + 1}`"
							@click="form.lines.splice(i, 1)"
						>
							<Trash2 class="h-4 w-4 text-gray-400" aria-hidden="true" /> Remove
						</button>
					</div>
					<button
						type="button"
						class="hidden h-9 w-9 shrink-0 items-center justify-center rounded-lg text-gray-400 hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-40 sm:flex"
						:disabled="form.lines.length === 1"
						:aria-label="`Remove line ${i + 1}`"
						@click="form.lines.splice(i, 1)"
					>
						<Trash2 class="h-4 w-4" aria-hidden="true" />
					</button>
				</div>
				<div class="flex justify-end border-t border-gray-100 pt-3 text-sm font-semibold tabular-nums">
					Total: {{ fmtMoney(total) }}
				</div>
			</div>
		</FormSection>

		<template #actions>
			<Button variant="outline" @click="router.push('/billing?tab=sales')">Cancel</Button>
			<Button :loading="saving" @click="save">Create invoice</Button>
		</template>
	</FormPage>
</template>
