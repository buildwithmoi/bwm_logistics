<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter, RouterLink } from "vue-router";
import { RefreshCw } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtDate, fmtMoney } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Textarea from "@/components/ui/Textarea.vue";
import Sheet from "@/components/ui/Sheet.vue";
import Badge from "@/components/ui/Badge.vue";
import DetailHeader from "@/components/ui/DetailHeader.vue";
import DataTable from "@/components/ui/DataTable.vue";
import DataList from "@/components/ui/DataList.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import DirectionBadge from "@/components/DirectionBadge.vue";
import Timeline, { type TimelineEvent } from "@/components/Timeline.vue";

const route = useRoute();
const router = useRouter();
const toast = useToast();
const session = useSessionStore();

interface ContentRow extends Record<string, unknown> {
	item: string;
	description: string;
	qty: number;
	unit?: string;
	customer?: string | null;
	customer_name?: string | null;
}
interface ContainerData {
	doc: Record<string, unknown>;
	contents: ContentRow[];
	shipments: Array<Record<string, unknown>>;
	timeline: TimelineEvent[];
	milestone_options: Array<{ milestone: string; notify_customer: number }>;
	tracking_provider?: string | null;
}
const data = ref<ContainerData | null>(null);
const loading = ref(true);
const name = computed(() => String(route.params.name));

async function load() {
	loading.value = true;
	try {
		data.value = await call<ContainerData>("bwm_logistics.api.containers.get_container", {
			name: name.value,
		});
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load container");
		router.push("/containers");
	} finally {
		loading.value = false;
	}
}
onMounted(load);

const doc = computed(() => (data.value?.doc || {}) as Record<string, string | number | null>);
const canEdit = computed(() => session.can("containers", "edit"));

// Carrier-API sync (visible when a provider is configured in Settings).
const syncing = ref(false);
async function syncTracking() {
	syncing.value = true;
	try {
		const res = await call<{ new_events: number; updated: string[] }>(
			"bwm_logistics.api.containers.sync_tracking",
			{ name: name.value },
		);
		toast.success(
			res.new_events
				? `${res.new_events} new event(s) from ${data.value?.tracking_provider}`
				: "Already up to date",
		);
		if (res.new_events || res.updated.length) await load();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Sync failed");
	} finally {
		syncing.value = false;
	}
}

// ── record milestone ────────────────────────────────────────────────────────
const milestoneOpen = ref(false);
const saving = ref(false);
const form = reactive({ milestone: "", location: "", remarks: "", notify: true });

const milestoneOptions = computed(() => {
	const opts = (data.value?.milestone_options || []).map((m) => m.milestone);
	// Free-form fallback when no template is linked.
	return opts;
});

async function recordMilestone() {
	if (!form.milestone) {
		toast.warning("Pick a milestone");
		return;
	}
	saving.value = true;
	try {
		await call("bwm_logistics.api.containers.record_milestone", {
			container: name.value,
			milestone: form.milestone,
			location: form.location || null,
			remarks: form.remarks || null,
			notify: form.notify ? 1 : 0,
		});
		toast.success(
			form.notify ? "Milestone recorded — customers are being notified" : "Milestone recorded",
		);
		milestoneOpen.value = false;
		form.milestone = "";
		form.location = "";
		form.remarks = "";
		await load();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not record milestone");
	} finally {
		saving.value = false;
	}
}

/** "estimated / actual" — but only the halves that exist, so a container with
 *  an ETA and no ATA reads "May 31" rather than "May 31 / —". */
function pair(estimated?: string | null, actual?: string | null): string | null {
	const parts = [estimated, actual].filter(Boolean).map((d) => fmtDate(d as string));
	return parts.length ? parts.join(" → ") : null;
}

// Two sections rather than one twelve-row table: what the voyage is, and what
// the clock is doing. DataList drops the rows nobody has filled in and
// collapses a section that is entirely empty.
const voyageRows = computed(() => [
	{ label: "Shipping line", value: doc.value.shipping_line },
	{ label: "Vessel / Voyage", value: [doc.value.vessel, doc.value.voyage_no].filter(Boolean).join(" / ") },
	{ label: "Master BL", value: doc.value.bl_no },
	{ label: "Booking No", value: doc.value.booking_no },
	{ label: "Seal No", value: doc.value.seal_no },
	{ label: "Loading port", value: doc.value.port_of_loading },
	{ label: "Discharge port", value: doc.value.port_of_discharge },
	{ label: "Departure", value: pair(doc.value.etd as string, doc.value.atd as string) },
	{ label: "Arrival", value: pair(doc.value.eta as string, doc.value.ata as string) },
]);
// The tagged list gets the same card-on-a-phone treatment as every other list
// rather than a 560px table nobody can read on a handset.
const shipmentColumns = [
	{ key: "name", label: "Tracking No", primary: true, nowrap: true },
	{ key: "status", label: "Status", trailing: true },
	{ key: "customer_name", label: "Customer" },
	{ key: "total_packages", label: "Packages", numeric: true },
	{ key: "total_charges", label: "Charges", numeric: true },
];

// The manifest, and who is in the box. An untagged line is ours.
const contentColumns = [
	{ key: "description", label: "Item", primary: true },
	{ key: "customer_name", label: "Customer", trailing: true },
	{ key: "qty", label: "Qty", numeric: true },
];
const contents = computed<ContentRow[]>(() => data.value?.contents || []);
const contentCustomers = computed(() => {
	const seen = new Map<string, string>();
	for (const row of contents.value) {
		if (row.customer) seen.set(row.customer, row.customer_name || row.customer);
	}
	return [...seen.values()];
});

const customsRows = computed(() => [
	{ label: "Customs", value: doc.value.customs_status },
	{ label: "Free days", value: doc.value.free_days },
	{ label: "Demurrage from", value: fmtDate(doc.value.demurrage_start_date as string) },
]);
</script>

<template>
	<div class="mx-auto max-w-6xl">
		<div v-if="loading" class="py-16 text-center text-sm text-muted-foreground">Loading…</div>
		<template v-else-if="data">
			<DetailHeader
				:title="String(doc.container_no || name)"
				back-to="/containers"
				back-label="Containers"
				:subtitle="`${name}${doc.container_type ? ' · ' + doc.container_type : ''}${doc.current_milestone ? ' · ' + doc.current_milestone : ''}`"
				status-action-label="Update status"
				@status-click="canEdit && (milestoneOpen = true)"
			>
				<!-- The badge is the control: tapping it opens the status sheet.
				     No separate Status button, no Current status card. -->
				<template v-if="canEdit" #statusAction />
				<template #badges>
					<StatusBadge :status="String(doc.status)" />
					<DirectionBadge :direction="String(doc.direction)" />
					<Badge v-if="doc.current_milestone === 'Delayed'" tone="danger" dot>Delayed</Badge>
				</template>
				<template #actions>
					<Button
						v-if="canEdit && data.tracking_provider && doc.container_no"
						variant="outline"
						size="icon"
						title="Sync tracking"
						aria-label="Sync tracking"
						:loading="syncing"
						@click="syncTracking"
					>
						<RefreshCw class="h-4 w-4" aria-hidden="true" />
					</Button>
					<Button v-if="canEdit" variant="outline" size="sm" @click="router.push(`/containers/${name}/edit`)">
						Edit
					</Button>
				</template>
			</DetailHeader>

			<div class="grid grid-cols-1 gap-4 lg:grid-cols-12">
				<!-- Info card -->
				<div class="space-y-4 lg:col-span-5">
					<div class="rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6">
						<h2 class="label-caps mb-2 sm:mb-4">Voyage</h2>
						<DataList :items="voyageRows" empty-text="No voyage details recorded yet.">
							<template #empty-action>
								<Button v-if="canEdit" size="sm" variant="outline" @click="milestoneOpen = true">
									Add details
								</Button>
							</template>
						</DataList>
					</div>
					<div class="rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6">
						<h2 class="label-caps mb-2 sm:mb-4">Customs &amp; demurrage</h2>
						<DataList :items="customsRows" :columns="1" empty-text="Nothing cleared or clocked yet." />
					</div>
				</div>

				<!-- Timeline -->
				<div class="rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6 lg:col-span-7">
					<h2 class="label-caps mb-4">Milestone timeline</h2>
					<Timeline :events="data.timeline" />
				</div>
			</div>

			<!-- What's in the box -->
			<div class="mt-4">
				<div class="mb-3 flex flex-wrap items-baseline justify-between gap-2">
					<h2 class="label-caps">Contents ({{ contents.length }})</h2>
					<p v-if="contentCustomers.length" class="text-xs text-muted-foreground">
						Carrying goods for {{ contentCustomers.join(", ") }}
					</p>
				</div>
				<DataTable
					:columns="contentColumns"
					:rows="contents"
					row-key="description"
					empty-text="Nothing recorded in this box yet."
				>
					<template #cell-description="{ row }">
						<span class="font-medium">{{ row.description }}</span>
					</template>
					<template #cell-customer_name="{ row }">
						<Badge v-if="row.customer" tone="info">{{ row.customer_name || row.customer }}</Badge>
						<Badge v-else tone="brand">Own goods</Badge>
					</template>
					<template #cell-qty="{ row }">
						{{ Number(row.qty || 0).toLocaleString() }}
						<span class="text-xs text-muted-foreground">{{ String(row.unit || "").toLowerCase() }}</span>
					</template>
				</DataTable>
			</div>

			<!-- Tagged shipments -->
			<div class="mt-4 rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6">
				<div class="mb-4 flex items-center justify-between">
					<h2 class="label-caps">Tagged shipments ({{ data.shipments.length }})</h2>
					<RouterLink to="/shipments" class="text-xs font-medium text-brand-700 hover:underline">
						New shipment →
					</RouterLink>
				</div>
				<DataTable
					:columns="shipmentColumns"
					:rows="data.shipments"
					clickable
					empty-text="No shipments tagged yet — tag one so its customer gets every milestone."
					@row-click="(r) => router.push(`/shipments/${r.name}`)"
				>
					<template #cell-name="{ row }">
						<span class="font-medium text-brand-700">{{ row.name }}</span>
					</template>
					<template #cell-customer_name="{ row }">
						<Badge v-if="!row.customer" tone="brand">Own goods</Badge>
						<template v-else>{{ row.customer_name || row.customer }}</template>
					</template>
					<template #cell-status="{ value }"><StatusBadge :status="String(value)" /></template>
					<template #cell-total_charges="{ value }">{{ fmtMoney(value as number) }}</template>
				</DataTable>
			</div>

			<!-- ── Record milestone dialog ───────────────────────────────────── -->
			<Sheet
				v-model:open="milestoneOpen"
				title="Update status"
				:description="`${doc.container_no || name} is currently ${doc.current_milestone || 'not started'}.`"
			>
				<div class="space-y-4">
					<fieldset v-if="milestoneOptions.length">
						<legend class="label-caps mb-2">Move to</legend>
						<div class="space-y-1.5">
							<label
								v-for="m in milestoneOptions"
								:key="m"
								class="flex cursor-pointer items-center gap-3 rounded-xl border px-3.5 py-3 transition-colors"
								:class="[
									form.milestone === m ? 'border-brand-400 bg-brand-50' : 'border-gray-200 hover:bg-gray-50',
									// Where it already is, so you can see what you're moving from.
									m === doc.current_milestone && form.milestone !== m && 'border-gray-300 bg-gray-50',
								]"
							>
								<input
									v-model="form.milestone"
									type="radio"
									name="container-milestone"
									:value="m"
									class="h-4 w-4 shrink-0 accent-[#b8860b]"
								/>
								<span class="min-w-0 flex-1 text-sm font-medium">
									{{ m }}
									<span v-if="m === doc.current_milestone" class="ml-1.5 text-xs font-normal text-muted-foreground">
										· current
									</span>
								</span>
							</label>
						</div>
					</fieldset>
					<div v-else class="space-y-1.5">
						<Label for="ms-free" required>Milestone</Label>
						<Input id="ms-free" v-model="form.milestone" placeholder="e.g. Vessel Departed" />
						<p class="text-xs text-muted-foreground">
							No milestone template on this container — type the milestone instead.
						</p>
					</div>

					<div class="space-y-1.5">
						<Label for="ms-location">Location <span class="font-normal text-muted-foreground">(optional)</span></Label>
						<Input id="ms-location" v-model="form.location" placeholder="e.g. Tema Port" />
					</div>
					<div class="space-y-1.5">
						<Label for="ms-remarks">Remarks <span class="font-normal text-muted-foreground">(optional)</span></Label>
						<Textarea id="ms-remarks" v-model="form.remarks" :rows="2" placeholder="Optional internal note" />
					</div>
					<label class="flex cursor-pointer items-center gap-2.5 rounded-xl bg-brand-50 px-4 py-3">
						<input v-model="form.notify" type="checkbox" class="h-4 w-4 shrink-0 rounded accent-[#b8860b]" />
						<span class="text-sm">
							<span class="font-medium">Notify tagged customers</span>
							<span class="block text-xs text-muted-foreground">
								Email/SMS every customer with a shipment in this container
							</span>
						</span>
					</label>
				</div>
				<template #footer>
					<div class="flex justify-end gap-2">
						<Button variant="outline" @click="milestoneOpen = false">Cancel</Button>
						<Button :loading="saving" :disabled="!form.milestone" @click="recordMilestone">Update status</Button>
					</div>
				</template>
			</Sheet>
		</template>
	</div>
</template>
