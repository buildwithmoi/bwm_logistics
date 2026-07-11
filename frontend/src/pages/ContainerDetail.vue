<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter, RouterLink } from "vue-router";
import { ArrowLeft, Flag, Ship, Package, RefreshCw } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtDate, fmtMoney } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Select from "@/components/ui/Select.vue";
import Textarea from "@/components/ui/Textarea.vue";
import Dialog from "@/components/ui/Dialog.vue";
import StatusBadge from "@/components/StatusBadge.vue";
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
			<!-- Header -->
			<header class="mb-6 flex flex-wrap items-center gap-3">
				<RouterLink
					to="/containers"
					class="flex h-9 w-9 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
				>
					<ArrowLeft class="h-4 w-4" />
				</RouterLink>
				<span class="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600/10 text-brand-700">
					<Ship class="h-5 w-5" />
				</span>
				<div class="min-w-0 flex-1">
					<div class="flex flex-wrap items-center gap-2">
						<h1 class="text-2xl font-semibold tracking-tight">
							{{ doc.container_no || name }}
						</h1>
						<StatusBadge :status="String(doc.status)" />
						<span class="rounded-full bg-gray-100 px-2.5 py-0.5 text-[11.5px] font-semibold text-gray-600">
							{{ doc.direction }}
						</span>
					</div>
					<p class="text-sm text-muted-foreground">
						{{ name }} · {{ doc.container_type || "type not set" }}
						<span v-if="doc.current_milestone"> · {{ doc.current_milestone }}</span>
					</p>
				</div>
				<Button
					v-if="canEdit && data.tracking_provider && doc.container_no"
					variant="outline"
					:loading="syncing"
					@click="syncTracking"
				>
					<RefreshCw class="h-4 w-4" /> Sync tracking
				</Button>
				<Button v-if="canEdit" @click="milestoneOpen = true">
					<Flag class="h-4 w-4" /> Record milestone
				</Button>
			</header>

			<div class="grid gap-4 lg:grid-cols-12">
				<!-- Info card -->
				<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100 lg:col-span-5">
					<h2 class="label-caps mb-4">Voyage details</h2>
					<dl class="grid grid-cols-2 gap-x-4 gap-y-3">
						<template v-for="r in infoRows" :key="r.label">
							<div>
								<dt class="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{{ r.label }}</dt>
								<dd class="mt-0.5 text-sm">{{ r.value || "—" }}</dd>
							</div>
						</template>
					</dl>
				</div>

				<!-- Timeline -->
				<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100 lg:col-span-7">
					<h2 class="label-caps mb-4">Milestone timeline</h2>
					<Timeline :events="data.timeline" />
				</div>
			</div>

			<!-- Tagged shipments -->
			<div class="mt-4 rounded-3xl bg-white p-6 ring-1 ring-gray-100">
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
								<td class="py-2.5 pr-4">{{ s.customer_name || s.customer }}</td>
								<td class="py-2.5 pr-4"><StatusBadge :status="String(s.status)" /></td>
								<td class="py-2.5 pr-4 text-right tabular-nums">{{ s.total_packages || 0 }}</td>
								<td class="py-2.5 text-right tabular-nums">{{ fmtMoney(s.total_charges as number) }}</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>

			<!-- ── Record milestone dialog ───────────────────────────────────── -->
			<Dialog v-model:open="milestoneOpen" title="Record milestone">
				<div class="space-y-4">
					<div class="space-y-1.5">
						<Label required>Milestone</Label>
						<Select
							v-if="milestoneOptions.length"
							v-model="form.milestone"
							:options="milestoneOptions"
							placeholder="Select milestone"
						/>
						<Input v-else v-model="form.milestone" placeholder="e.g. Vessel Departed" />
					</div>
					<div class="space-y-1.5">
						<Label>Location</Label>
						<Input v-model="form.location" placeholder="e.g. Tema Port" />
					</div>
					<div class="space-y-1.5">
						<Label>Remarks</Label>
						<Textarea v-model="form.remarks" :rows="2" placeholder="Optional internal note" />
					</div>
					<label class="flex cursor-pointer items-center gap-2.5 rounded-xl bg-brand-50 px-4 py-3">
						<input v-model="form.notify" type="checkbox" class="h-4 w-4 rounded accent-[#b8860b]" />
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
						<Button :loading="saving" @click="recordMilestone">Record</Button>
					</div>
				</template>
			</Dialog>
		</template>
	</div>
</template>
