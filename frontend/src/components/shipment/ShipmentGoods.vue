<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import { call } from "@/lib/frappe";
import { fmtMoney, fmtDate } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Select from "@/components/ui/Select.vue";
import Textarea from "@/components/ui/Textarea.vue";
import Dialog from "@/components/ui/Dialog.vue";
import DataTable, { type Column } from "@/components/ui/DataTable.vue";
import SearchCombo from "@/components/ui/SearchCombo.vue";

// Stock & distribution for an own-goods booking: what came in, what has gone
// out, and to whom. Own goods only — somebody else's cargo is delivered
// through Dispatch, not distributed out of our stock.
//
// It owns its own data because nothing else on the shipment page reads it, and
// tells the parent only when money moved (an entry became an invoice), which
// is the one thing the P&L card cares about.
const props = defineProps<{ shipment: string; canBill?: boolean }>();
const emit = defineEmits<{ (e: "invoiced"): void }>();

const toast = useToast();
const session = useSessionStore();
const canDistribute = computed(() => session.can("stock", "create") || session.can("shipments", "edit"));
const fmtQty = (v?: number) => (v || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });

interface BalanceLine {
	item?: string | null;
	product: string;
	unit: string;
	received: number;
	distributed: number;
	remaining: number;
	/** Distributed but no longer on the manifest — surfaced, never dropped. */
	off_manifest?: boolean;
}
interface Balances {
	lines: BalanceLine[];
	received_total: number;
	distributed_total: number;
	remaining_total: number;
}
interface DistRow extends Record<string, unknown> {
	name: string;
	product: string;
	qty: number;
	unit?: string;
	recipient: string;
	customer?: string | null;
	destination?: string;
	unit_price?: number;
	amount?: number;
	delivery_date?: string;
	sales_invoice?: string | null;
}

const balances = ref<Balances | null>(null);
const distributions = ref<DistRow[]>([]);

async function loadStock() {
	try {
		const [bal, list] = await Promise.all([
			call<Balances>("bwm_logistics.api.stock.shipment_stock_balance", { shipment: props.shipment }),
			call<{ rows: DistRow[] }>("bwm_logistics.api.stock.list_distributions", {
				shipment: props.shipment,
				limit: 100,
			}),
		]);
		balances.value = bal;
		distributions.value = list.rows;
	} catch {
		/* section hidden on error */
	}
}
onMounted(loadStock);

// ── record a distribution ───────────────────────────────────────────────────
const distOpen = ref(false);
const distSaving = ref(false);
const distForm = reactive({
	product: "",
	qty: null as number | null,
	recipient: "",
	customer: "" as string | null,
	destination: "",
	unit_price: null as number | null,
	delivery_date: new Date().toISOString().slice(0, 10),
	notes: "",
});
const distCustomerDisplay = ref<string | null>(null);

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

const productOptions = computed(() =>
	(balances.value?.lines || []).map((l) => ({
		value: l.product,
		label: `${l.product} — ${fmtQty(l.remaining)} ${l.unit.toLowerCase()} left`,
	})),
);
const selectedLine = computed(() => balances.value?.lines.find((l) => l.product === distForm.product));

function openDist() {
	const firstOpen = balances.value?.lines.find((l) => l.remaining > 0) || balances.value?.lines[0];
	distForm.product = firstOpen?.product || "";
	distForm.qty = null;
	distForm.recipient = "";
	distForm.customer = "";
	distCustomerDisplay.value = null;
	distForm.destination = "";
	distForm.unit_price = null;
	distForm.notes = "";
	distOpen.value = true;
}

async function saveDistribution() {
	if (!distForm.product || !distForm.qty || !distForm.recipient.trim()) {
		toast.warning("Product, quantity and recipient are required");
		return;
	}
	distSaving.value = true;
	try {
		await call("bwm_logistics.api.stock.record_distribution", {
			payload: {
				shipment: props.shipment,
				item: selectedLine.value?.item || null,
				product: distForm.product,
				qty: distForm.qty,
				recipient: distForm.recipient,
				customer: distForm.customer || null,
				destination: distForm.destination || null,
				unit_price: distForm.unit_price || null,
				delivery_date: distForm.delivery_date || null,
				notes: distForm.notes || null,
			},
		});
		toast.success("Distribution recorded");
		distOpen.value = false;
		await loadStock();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not record distribution");
	} finally {
		distSaving.value = false;
	}
}

async function deleteDistribution(row: DistRow) {
	try {
		await call("bwm_logistics.api.stock.delete_distribution", { name: row.name });
		toast.info("Entry removed");
		await loadStock();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not delete entry");
	}
}

const invoicingDist = ref("");
async function invoiceDistribution(row: DistRow) {
	invoicingDist.value = row.name;
	try {
		const res = await call<{ sales_invoice: string }>("bwm_logistics.api.stock.invoice_distribution", {
			name: row.name,
		});
		toast.success(`Invoice ${res.sales_invoice} created`);
		await loadStock();
		emit("invoiced");
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not invoice entry");
	} finally {
		invoicingDist.value = "";
	}
}

const columns: Column[] = [
	{ key: "recipient", label: "Recipient", primary: true },
	{ key: "qty", label: "Qty", numeric: true, trailing: true, nowrap: true },
	{ key: "product", label: "Product" },
	{ key: "delivery_date", label: "Date", nowrap: true },
	{ key: "destination", label: "Destination", hideWhenEmpty: true },
	// An entry with no price isn't a sale — a zero amount is nothing to report.
	{ key: "amount", label: "Amount", numeric: true, nowrap: true, hideWhenEmpty: (r) => !r.amount },
	{ key: "actions", label: "", class: "text-right" },
];
</script>

<template>
	<div v-if="balances" class="mt-4 rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6">
		<!-- The heading and the running total each want a full line on a phone;
		     side by side they squeeze the label to two words per row. -->
		<div class="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center">
			<div class="min-w-0 flex-1">
				<h2 class="label-caps">Stock &amp; distribution</h2>
				<p class="mt-0.5 text-sm tabular-nums text-muted-foreground">
					{{ fmtQty(balances.distributed_total) }} of {{ fmtQty(balances.received_total) }} distributed ·
					<b class="text-gray-900">{{ fmtQty(balances.remaining_total) }} left</b>
				</p>
			</div>
			<div v-if="canDistribute" class="flex justify-end">
				<Button size="sm" @click="openDist">Record distribution</Button>
			</div>
		</div>

		<!-- Per-product balance bars -->
		<!-- On a phone the bar gets its own line: squeezed between a product name
		     and a figure it shrinks to a stub that reads nothing. -->
		<div v-if="balances.lines.length" class="mb-5 space-y-3">
			<div v-for="l in balances.lines" :key="l.item || l.product" class="sm:flex sm:items-center sm:gap-3">
				<div class="flex min-w-0 items-baseline justify-between gap-3 sm:block sm:w-64 sm:shrink-0">
					<div class="min-w-0 truncate text-sm font-medium">
						{{ l.product }}
						<span v-if="l.off_manifest" class="font-normal text-red-600">· not on the manifest</span>
					</div>
					<span
						class="shrink-0 text-sm font-semibold tabular-nums sm:hidden"
						:class="l.remaining < 0 ? 'text-red-600' : l.remaining > 0 ? 'text-brand-800' : 'text-gray-400'"
					>
						{{ fmtQty(l.remaining) }} left
					</span>
					<div class="hidden text-xs text-muted-foreground sm:block">
						{{ fmtQty(l.received) }} {{ l.unit.toLowerCase() }} received
					</div>
				</div>
				<div class="mt-1.5 h-2.5 min-w-0 flex-1 overflow-hidden rounded-full bg-gray-100 sm:mt-0">
					<div
						class="h-full rounded-full bg-brand-500"
						:style="{ width: `${Math.min(100, (l.distributed / Math.max(l.received, 1)) * 100)}%` }"
					></div>
				</div>
				<div class="mt-1 text-xs text-muted-foreground sm:hidden">
					{{ fmtQty(l.distributed) }} of {{ fmtQty(l.received) }} {{ l.unit.toLowerCase() }} distributed
				</div>
				<span
					class="hidden w-28 shrink-0 text-right text-sm font-semibold tabular-nums sm:inline"
					:class="l.remaining < 0 ? 'text-red-600' : l.remaining > 0 ? 'text-brand-800' : 'text-gray-400'"
				>
					{{ fmtQty(l.remaining) }} left
				</span>
			</div>
		</div>
		<div v-else class="mb-5 rounded-xl bg-gray-50 px-4 py-6 text-center text-sm text-muted-foreground">
			No goods on this booking's containers yet — add contents to the container to track what arrived.
		</div>

		<DataTable
			:columns="columns"
			:rows="distributions"
			row-key="name"
			empty-text="Nothing distributed yet — record where the goods go (a truck, a buyer, or storage)."
		>
			<template #cell-qty="{ row }">
				<span class="tabular-nums">{{ fmtQty(row.qty as number) }} {{ ((row.unit as string) || "").toLowerCase() }}</span>
			</template>
			<template #cell-delivery_date="{ row }">
				<span class="tabular-nums text-muted-foreground">{{ fmtDate(row.delivery_date as string) }}</span>
			</template>
			<template #cell-amount="{ row }">
				<span v-if="row.amount" class="tabular-nums">{{ fmtMoney(row.amount as number) }}</span>
				<span v-else />
			</template>
			<template #cell-actions="{ row }">
				<span class="inline-flex items-center gap-2">
					<RouterLink
						v-if="row.sales_invoice"
						:to="`/billing?tab=sales`"
						class="text-xs font-medium text-emerald-700 hover:underline"
					>{{ row.sales_invoice }}</RouterLink>
					<Button
						v-else-if="canBill && row.customer && ((row.unit_price as number) || 0) > 0"
						size="sm"
						variant="outline"
						:loading="invoicingDist === row.name"
						@click="invoiceDistribution(row as DistRow)"
					>Invoice</Button>
					<button
						v-if="canDistribute && !row.sales_invoice"
						type="button"
						class="text-xs font-medium text-gray-400 hover:text-red-600"
						@click="deleteDistribution(row as DistRow)"
					>Remove</button>
				</span>
			</template>
		</DataTable>
	</div>

	<!-- ── Record distribution dialog ────────────────────────────────────── -->
	<Dialog v-model:open="distOpen" title="Record distribution" size="wide">
		<div class="space-y-4">
			<div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
				<div class="space-y-1.5">
					<Label required>Product</Label>
					<Select v-model="distForm.product" :options="productOptions" />
				</div>
				<div class="space-y-1.5">
					<Label required>Quantity</Label>
					<Input v-model.number="distForm.qty" type="number" min="0" :placeholder="selectedLine ? `${fmtQty(selectedLine.remaining)} remaining` : 'Qty'" />
					<p v-if="selectedLine && (distForm.qty || 0) > selectedLine.remaining" class="text-xs font-medium text-red-600">
						Only {{ fmtQty(selectedLine.remaining) }} {{ selectedLine.unit.toLowerCase() }} left on this line.
					</p>
				</div>
				<div class="space-y-1.5">
					<Label required>Recipient</Label>
					<Input v-model="distForm.recipient" placeholder='e.g. "Truck 1", "Ella", "Storage"' />
				</div>
				<div class="space-y-1.5">
					<Label>Destination</Label>
					<Input v-model="distForm.destination" placeholder="Where it's headed (optional)" />
				</div>
				<div class="space-y-1.5">
					<Label>Delivery date</Label>
					<Input v-model="distForm.delivery_date" type="date" />
				</div>
				<div class="space-y-1.5">
					<Label>Unit price (optional)</Label>
					<Input v-model.number="distForm.unit_price" type="number" min="0" placeholder="For invoicing later" />
				</div>
			</div>
			<div class="space-y-1.5">
				<Label>Customer (optional — enables invoicing)</Label>
				<SearchCombo
					v-model="distForm.customer"
					v-model:display-value="distCustomerDisplay"
					:fetcher="fetchCustomers"
					value-key="name"
					label-key="customer_name"
					sublabel-key="mobile_no"
					placeholder="Search customer… (leave empty for trucks/storage)"
				/>
			</div>
			<div class="space-y-1.5">
				<Label>Notes</Label>
				<Textarea v-model="distForm.notes" :rows="2" placeholder="Optional note" />
			</div>
		</div>
		<template #footer>
			<div class="flex justify-end gap-2">
				<Button variant="outline" @click="distOpen = false">Cancel</Button>
				<Button :loading="distSaving" @click="saveDistribution">Record</Button>
			</div>
		</template>
	</Dialog>
</template>
