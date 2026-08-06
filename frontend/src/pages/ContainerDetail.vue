<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter, RouterLink } from "vue-router";
import { Flag, Package, RefreshCw } from "lucide-vue-next";
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
import DataList from "@/components/ui/DataList.vue";
import DataRow from "@/components/ui/DataRow.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import DirectionBadge from "@/components/DirectionBadge.vue";
import Timeline, { type TimelineEvent } from "@/components/Timeline.vue";

const route = useRoute();
const router = useRouter();
const toast = useToast();
const session = useSessionStore();

interface ContainerData {
	doc: Record<string, unknown>;
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

const infoRows = computed(() => [
	{ label: "Shipping line", value: doc.value.shipping_line },
	{ label: "Vessel / Voyage", value: [doc.value.vessel, doc.value.voyage_no].filter(Boolean).join(" / ") },
	{ label: "Master BL", value: doc.value.bl_no },
	{ label: "Booking No", value: doc.value.booking_no },
	{ label: "Loading port", value: doc.value.port_of_loading },
	{ label: "Discharge port", value: doc.value.port_of_discharge },
	{ label: "ETD / ATD", value: [fmtDate(doc.value.etd as string), fmtDate(doc.value.atd as string)].join(" / ") },
	{ label: "ETA / ATA", value: [fmtDate(doc.value.eta as string), fmtDate(doc.value.ata as string)].join(" / ") },
	{ label: "Customs", value: doc.value.customs_status },
	{ label: "Free days", value: doc.value.free_days },
	{ label: "Demurrage from", value: fmtDate(doc.value.demurrage_start_date as string) },
	{ label: "Seal No", value: doc.value.seal_no },
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
				:subtitle="`${name} · ${doc.container_type || 'type not set'}`"
			>
				<template #badges>
					<StatusBadge :status="String(doc.status)" />
					<DirectionBadge :direction="String(doc.direction)" />
					<Badge v-if="doc.current_milestone === 'Delayed'" tone="danger" dot>Delayed</Badge>
				</template>
				<template #actions>
					<Button v-if="canEdit" @click="milestoneOpen = true">
						<Flag class="h-4 w-4" aria-hidden="true" />
						<span class="hidden sm:inline">Update status</span>
						<span class="sm:hidden">Status</span>
					</Button>
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
				</template>
			</DetailHeader>

			<!-- Where it is now, and the one tap that moves it on. -->
			<div class="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-white p-4 ring-1 ring-gray-100">
				<div class="min-w-0">
					<div class="label-caps">Current status</div>
					<div class="mt-1 flex flex-wrap items-center gap-2">
						<span class="text-lg font-semibold tracking-tight">{{ doc.current_milestone || "No milestones yet" }}</span>
						<!-- Only when it adds something: "Active / Active" is noise. -->
						<StatusBadge v-if="doc.status !== doc.current_milestone" :status="String(doc.status)" />
					</div>
				</div>
				<Button v-if="canEdit" variant="outline" class="shrink-0" @click="milestoneOpen = true">Update</Button>
			</div>

			<div class="grid grid-cols-1 gap-4 lg:grid-cols-12">
				<!-- Info card -->
				<div class="rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6 lg:col-span-5">
					<h2 class="label-caps mb-2 sm:mb-4">Voyage details</h2>
					<DataList>
						<DataRow v-for="r in infoRows" :key="r.label" :label="r.label" :value="r.value" />
					</DataList>
				</div>

				<!-- Timeline -->
				<div class="rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6 lg:col-span-7">
					<h2 class="label-caps mb-4">Milestone timeline</h2>
					<Timeline :events="data.timeline" />
				</div>
			</div>

			<!-- Tagged shipments -->
			<div class="mt-4 rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-6">
				<div class="mb-4 flex items-center justify-between">
					<h2 class="label-caps">Tagged shipments ({{ data.shipments.length }})</h2>
					<RouterLink to="/shipments" class="text-xs font-medium text-brand-700 hover:underline">
						New shipment →
					</RouterLink>
				</div>
				<div v-if="!data.shipments.length" class="rounded-xl bg-gray-50 px-4 py-8 text-center text-sm text-muted-foreground">
					No shipments tagged yet. Tag customers' shipments to this container so they
					get notified on every milestone.
				</div>
				<div v-else class="overflow-x-auto">
					<table class="w-full min-w-[560px] text-sm">
						<thead>
							<tr class="text-left">
								<th class="label-caps pb-2 pr-4">Tracking No</th>
								<th class="label-caps pb-2 pr-4">Customer</th>
								<th class="label-caps pb-2 pr-4">Status</th>
								<th class="label-caps pb-2 pr-4 text-right">Packages</th>
								<th class="label-caps pb-2 text-right">Charges</th>
							</tr>
						</thead>
						<tbody>
							<tr
								v-for="s in data.shipments"
								:key="String(s.name)"
								class="cursor-pointer border-t border-gray-100 transition-colors hover:bg-gray-50/80"
								@click="router.push(`/shipments/${s.name}`)"
							>
								<td class="py-2.5 pr-4 font-medium text-brand-700">
									<span class="inline-flex items-center gap-1.5"><Package class="h-3.5 w-3.5" /> {{ s.name }}</span>
								</td>
								<td class="py-2.5 pr-4">
									<span v-if="!s.customer" class="inline-flex items-center rounded-full bg-brand-600/10 px-2.5 py-0.5 text-[11px] font-semibold text-brand-700">Own goods</span>
									<template v-else>{{ s.customer_name || s.customer }}</template>
								</td>
								<td class="py-2.5 pr-4"><StatusBadge :status="String(s.status)" /></td>
								<td class="py-2.5 pr-4 text-right tabular-nums">{{ s.total_packages || 0 }}</td>
								<td class="py-2.5 text-right tabular-nums">{{ fmtMoney(s.total_charges as number) }}</td>
							</tr>
						</tbody>
					</table>
				</div>
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
								:class="form.milestone === m ? 'border-brand-400 bg-brand-50' : 'border-gray-200 hover:bg-gray-50'"
							>
								<input
									v-model="form.milestone"
									type="radio"
									name="container-milestone"
									:value="m"
									class="h-4 w-4 shrink-0 accent-[#b8860b]"
								/>
								<span class="min-w-0 flex-1 text-sm font-medium">{{ m }}</span>
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
