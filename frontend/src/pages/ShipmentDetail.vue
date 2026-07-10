<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter, RouterLink } from "vue-router";
import { ArrowLeft, Package, Flag, ReceiptText, Printer } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtMoney, fmtWeight, fmtDate } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Textarea from "@/components/ui/Textarea.vue";
import Dialog from "@/components/ui/Dialog.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import Timeline, { type TimelineEvent } from "@/components/Timeline.vue";

const route = useRoute();
const router = useRouter();
const toast = useToast();
const session = useSessionStore();

interface ShipmentData extends Record<string, unknown> {
	name: string;
	customer_name?: string;
	status?: string;
	direction?: string;
	current_milestone?: string;
	container?: string;
	timeline: TimelineEvent[];
	packages?: Array<Record<string, unknown>>;
	charges?: Array<Record<string, unknown>>;
	invoice?: { name: string; status: string; grand_total: number; outstanding_amount: number; currency: string };
	container_info?: { name: string; container_no?: string; eta?: string; vessel?: string; current_milestone?: string };
}
const data = ref<ShipmentData | null>(null);
const loading = ref(true);
const name = computed(() => String(route.params.name));

async function load() {
	loading.value = true;
	try {
		data.value = await call<ShipmentData>("bwm_logistics.api.shipments.get_shipment", { name: name.value });
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load shipment");
		router.push("/shipments");
	} finally {
		loading.value = false;
	}
}
onMounted(load);

const canEdit = computed(() => session.can("shipments", "edit"));
const canBill = computed(() => session.canSee("billing") || session.hasRole("Logistics Manager", "System Manager"));

// ── record shipment event ───────────────────────────────────────────────────
const eventOpen = ref(false);
const saving = ref(false);
const form = reactive({ milestone: "", location: "", remarks: "", notify: true });

async function recordEvent() {
	if (!form.milestone) {
		toast.warning("Enter a milestone");
		return;
	}
	saving.value = true;
	try {
		await call("bwm_logistics.api.shipments.record_event", {
			shipment: name.value,
			milestone: form.milestone,
			location: form.location || null,
			remarks: form.remarks || null,
			notify: form.notify ? 1 : 0,
		});
		toast.success("Event recorded");
		eventOpen.value = false;
		form.milestone = "";
		form.location = "";
		form.remarks = "";
		await load();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not record event");
	} finally {
		saving.value = false;
	}
}

// ── invoice ─────────────────────────────────────────────────────────────────
const invoicing = ref(false);
async function makeInvoice() {
	invoicing.value = true;
	try {
		const res = await call<{ sales_invoice: string }>("bwm_logistics.api.shipments.make_invoice", {
			shipment: name.value,
		});
		toast.success(`Invoice ${res.sales_invoice} created`);
		await load();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not create invoice");
	} finally {
		invoicing.value = false;
	}
}
</script>

<template>
	<div class="mx-auto max-w-6xl">
		<div v-if="loading" class="py-16 text-center text-sm text-muted-foreground">Loading…</div>
		<template v-else-if="data">
			<header class="mb-6 flex flex-wrap items-center gap-3">
				<RouterLink
					to="/shipments"
					class="flex h-9 w-9 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
				>
					<ArrowLeft class="h-4 w-4" />
				</RouterLink>
				<span class="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600/10 text-brand-700">
					<Package class="h-5 w-5" />
				</span>
				<div class="min-w-0 flex-1">
					<div class="flex flex-wrap items-center gap-2">
						<h1 class="text-2xl font-semibold tracking-tight">{{ data.name }}</h1>
						<StatusBadge :status="data.status" />
						<span class="rounded-full bg-gray-100 px-2.5 py-0.5 text-[11.5px] font-semibold text-gray-600">{{ data.direction }}</span>
					</div>
					<p class="text-sm text-muted-foreground">
						{{ data.customer_name }} · {{ data.destination || "destination not set" }}
						<span v-if="data.current_milestone"> · {{ data.current_milestone }}</span>
					</p>
				</div>
				<Button variant="outline" @click="router.push(`/shipments/${name}/label`)">
					<Printer class="h-4 w-4" /> Labels
				</Button>
				<Button v-if="canEdit" variant="outline" @click="eventOpen = true">
					<Flag class="h-4 w-4" /> Record event
				</Button>
				<Button
					v-if="canBill && !data.invoice && (data.charges || []).length"
					:loading="invoicing"
					@click="makeInvoice"
				>
					<ReceiptText class="h-4 w-4" /> Create invoice
				</Button>
			</header>

			<div class="grid gap-4 lg:grid-cols-12">
				<div class="space-y-4 lg:col-span-5">
					<!-- Container card -->
					<div v-if="data.container_info" class="rounded-3xl bg-coal-900 p-6 text-white">
						<div class="label-caps !text-brand-400">In container</div>
						<RouterLink
							:to="`/containers/${data.container_info.name}`"
							class="mt-1 block text-lg font-semibold hover:text-brand-300"
						>
							{{ data.container_info.container_no || data.container_info.name }}
						</RouterLink>
						<div class="mt-1 text-sm text-white/60">
							{{ data.container_info.vessel || "vessel TBD" }} ·
							ETA {{ fmtDate(data.container_info.eta) }}
						</div>
					</div>

					<!-- Parties -->
					<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
						<h2 class="label-caps mb-4">Consignee & route</h2>
						<dl class="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
							<div><dt class="label-caps !text-[10px]">Receiver</dt><dd class="mt-0.5">{{ data.consignee_name || "—" }}</dd></div>
							<div><dt class="label-caps !text-[10px]">Phone</dt><dd class="mt-0.5">{{ data.consignee_phone || "—" }}</dd></div>
							<div><dt class="label-caps !text-[10px]">Origin</dt><dd class="mt-0.5">{{ data.origin || "—" }}</dd></div>
							<div><dt class="label-caps !text-[10px]">Destination</dt><dd class="mt-0.5">{{ data.destination || "—" }}</dd></div>
							<div class="col-span-2"><dt class="label-caps !text-[10px]">Delivery address</dt><dd class="mt-0.5">{{ data.delivery_address || "—" }}</dd></div>
						</dl>
					</div>

					<!-- Packages -->
					<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
						<h2 class="label-caps mb-4">Packages ({{ data.total_packages || 0 }})</h2>
						<ul class="divide-y divide-gray-100 text-sm">
							<li v-for="(p, i) in data.packages" :key="i" class="flex items-baseline justify-between gap-3 py-2">
								<span class="min-w-0 flex-1">{{ p.description }} <span class="text-muted-foreground">× {{ p.qty }}</span></span>
								<span class="shrink-0 tabular-nums text-muted-foreground">{{ fmtWeight(p.weight_kg as number) }}</span>
							</li>
						</ul>
						<div class="mt-3 flex justify-between border-t border-gray-100 pt-3 text-sm">
							<span class="text-muted-foreground">Total weight</span>
							<span class="font-medium tabular-nums">{{ fmtWeight(data.total_weight_kg as number) }}</span>
						</div>
					</div>

					<!-- Billing -->
					<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100">
						<h2 class="label-caps mb-4">Charges & billing</h2>
						<ul v-if="(data.charges || []).length" class="divide-y divide-gray-100 text-sm">
							<li v-for="(c, i) in data.charges" :key="i" class="flex justify-between py-2">
								<span>{{ c.charge_type }}</span>
								<span class="tabular-nums">{{ fmtMoney(c.amount as number) }}</span>
							</li>
							<li class="flex justify-between py-2 font-semibold">
								<span>Total</span>
								<span class="tabular-nums">{{ fmtMoney(data.total_charges as number) }}</span>
							</li>
						</ul>
						<p v-else class="text-sm text-muted-foreground">No charges added.</p>
						<div v-if="data.invoice" class="mt-3 flex items-center justify-between rounded-xl bg-gray-50 px-4 py-3 text-sm">
							<div>
								<div class="font-medium">{{ data.invoice.name }}</div>
								<div class="text-xs text-muted-foreground">
									Outstanding {{ fmtMoney(data.invoice.outstanding_amount, data.invoice.currency) }}
								</div>
							</div>
							<StatusBadge :status="data.invoice.status" />
						</div>
					</div>
				</div>

				<!-- Timeline -->
				<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100 lg:col-span-7">
					<h2 class="label-caps mb-4">Tracking timeline</h2>
					<Timeline :events="data.timeline" />
				</div>
			</div>

			<!-- ── Record event dialog ───────────────────────────────────────── -->
			<Dialog v-model:open="eventOpen" title="Record shipment event">
				<div class="space-y-4">
					<p class="rounded-xl bg-gray-50 px-4 py-3 text-xs text-muted-foreground">
						This event applies to <b>this shipment only</b> (e.g. "Received at warehouse",
						"Out for delivery"). Container-wide milestones are recorded on the container.
					</p>
					<div class="space-y-1.5">
						<Label required>Milestone</Label>
						<Input v-model="form.milestone" placeholder="e.g. Out for Delivery" />
					</div>
					<div class="space-y-1.5">
						<Label>Location</Label>
						<Input v-model="form.location" />
					</div>
					<div class="space-y-1.5">
						<Label>Remarks</Label>
						<Textarea v-model="form.remarks" :rows="2" />
					</div>
					<label class="flex cursor-pointer items-center gap-2.5 rounded-xl bg-brand-50 px-4 py-3">
						<input v-model="form.notify" type="checkbox" class="h-4 w-4 rounded accent-[#b8860b]" />
						<span class="text-sm font-medium">Notify this customer</span>
					</label>
				</div>
				<template #footer>
					<div class="flex justify-end gap-2">
						<Button variant="outline" @click="eventOpen = false">Cancel</Button>
						<Button :loading="saving" @click="recordEvent">Record</Button>
					</div>
				</template>
			</Dialog>
		</template>
	</div>
</template>
