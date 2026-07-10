<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter, RouterLink } from "vue-router";
import {
	ArrowLeft,
	MapPin,
	Navigation,
	Package,
	Truck,
	Play,
	Flag,
	HandCoins,
	Camera,
	CheckCircle2,
	XCircle,
} from "lucide-vue-next";
import { call, uploadFile } from "@/lib/frappe";
import { fmtDate, fmtMoney, fmtDateTime } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import { useSessionStore } from "@/stores/session";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import Label from "@/components/ui/Label.vue";
import Textarea from "@/components/ui/Textarea.vue";
import Dialog from "@/components/ui/Dialog.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import SignaturePad from "@/components/SignaturePad.vue";

const route = useRoute();
const router = useRouter();
const toast = useToast();
const session = useSessionStore();

interface Stop extends Record<string, unknown> {
	name: string;
	stop_type: "Delivery" | "Pickup";
	shipment?: string;
	pickup_request?: string;
	status: string;
	address?: string;
	contact_name?: string;
	contact_phone?: string;
	cod_due?: number;
	cod_collected?: number;
	pod_receiver?: string;
	pod_time?: string;
	pod_photo?: string;
	pod_signature?: string;
	failure_reason?: string;
	shipment_info?: { customer_name?: string; total_packages?: number };
}
interface Run extends Record<string, unknown> {
	name: string;
	run_date: string;
	status: string;
	driver_name?: string;
	vehicle?: string;
	stops: Stop[];
	cod_due_total?: number;
	cod_collected_total?: number;
	cod_reconciled?: number;
}
const run = ref<Run | null>(null);
const loading = ref(true);
const name = computed(() => String(route.params.name));

const isDispatcher = computed(() =>
	session.hasRole("Logistics Manager", "Logistics Operations", "System Manager", "Administrator"),
);
const canReconcile = computed(() =>
	session.hasRole("Logistics Manager", "Logistics Accounts", "System Manager", "Administrator"),
);

async function load() {
	loading.value = true;
	try {
		run.value = await call<Run>("bwm_logistics.api.dispatch.get_run", { name: name.value });
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load run");
		router.push("/dispatch");
	} finally {
		loading.value = false;
	}
}
onMounted(load);

const openStops = computed(() => (run.value?.stops || []).filter((s) => ["Pending", "Arrived"].includes(s.status)));
const busy = ref<string | null>(null);

async function act(method: string, args: Record<string, unknown>, okMsg: string) {
	busy.value = String(args.stop || method);
	try {
		await call(`bwm_logistics.api.dispatch.${method}`, { name: name.value, ...args });
		toast.success(okMsg);
		await load();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Action failed");
	} finally {
		busy.value = null;
	}
}
const startRun = () => act("start_run", {}, "Run started — customers notified");
const finishRun = () => act("finish_run", {}, "Run completed");
const reconcile = () => act("reconcile_cod", {}, "Cash reconciled — payments posted");
const arrived = (s: Stop) =>
	call("bwm_logistics.api.dispatch.stop_arrived", { run: name.value, stop: s.name })
		.then(() => load())
		.catch((e) => toast.error(e?.message || "Failed"));

function mapsUrl(address?: string): string {
	return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(address || "")}`;
}

// ── POD dialog ──────────────────────────────────────────────────────────────
const podFor = ref<Stop | null>(null);
const podSaving = ref(false);
const sigPad = ref<InstanceType<typeof SignaturePad> | null>(null);
const pod = reactive({ receiver: "", cod: 0, photoFile: null as File | null });

function openPod(s: Stop) {
	podFor.value = s;
	pod.receiver = "";
	pod.cod = s.cod_due || 0;
	pod.photoFile = null;
}
function onPhoto(e: Event) {
	pod.photoFile = (e.target as HTMLInputElement).files?.[0] || null;
}

async function completePod() {
	if (!podFor.value) return;
	podSaving.value = true;
	try {
		let signature: string | null = null;
		const blob = await sigPad.value?.toBlob();
		if (blob) {
			signature = await uploadFile(new File([blob], `sig-${podFor.value.name}.png`, { type: "image/png" }));
		}
		let photo: string | null = null;
		if (pod.photoFile) photo = await uploadFile(pod.photoFile);

		let geo: string | null = null;
		try {
			geo = await new Promise<string | null>((resolve) => {
				if (!navigator.geolocation) return resolve(null);
				navigator.geolocation.getCurrentPosition(
					(p) => resolve(`${p.coords.latitude.toFixed(5)},${p.coords.longitude.toFixed(5)}`),
					() => resolve(null),
					{ timeout: 3000 },
				);
			});
		} catch {
			/* geo optional */
		}

		await call("bwm_logistics.api.dispatch.stop_complete", {
			run: name.value,
			stop: podFor.value.name,
			receiver: pod.receiver || null,
			signature,
			photo,
			cod_collected: pod.cod || 0,
			geo,
		});
		toast.success(podFor.value.stop_type === "Delivery" ? "Delivered — customer notified" : "Pickup completed");
		podFor.value = null;
		await load();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not complete stop");
	} finally {
		podSaving.value = false;
	}
}

// ── fail dialog ─────────────────────────────────────────────────────────────
const failFor = ref<Stop | null>(null);
const failReason = ref("");
const failing = ref(false);
async function confirmFail() {
	if (!failFor.value) return;
	failing.value = true;
	try {
		await call("bwm_logistics.api.dispatch.stop_fail", {
			run: name.value,
			stop: failFor.value.name,
			reason: failReason.value || null,
		});
		toast.info("Stop marked failed");
		failFor.value = null;
		failReason.value = "";
		await load();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Failed");
	} finally {
		failing.value = false;
	}
}
</script>

<template>
	<div class="mx-auto max-w-3xl">
		<div v-if="loading" class="py-16 text-center text-sm text-muted-foreground">Loading…</div>
		<template v-else-if="run">
			<!-- Header -->
			<header class="mb-5 flex flex-wrap items-center gap-3">
				<RouterLink
					to="/dispatch"
					class="flex h-9 w-9 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
				>
					<ArrowLeft class="h-4 w-4" />
				</RouterLink>
				<span class="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600/10 text-brand-700">
					<MapPin class="h-5 w-5" />
				</span>
				<div class="min-w-0 flex-1">
					<div class="flex flex-wrap items-center gap-2">
						<h1 class="text-xl font-semibold tracking-tight sm:text-2xl">{{ run.name }}</h1>
						<StatusBadge :status="run.status" />
					</div>
					<p class="text-sm text-muted-foreground">
						{{ fmtDate(run.run_date) }} · {{ run.driver_name }}
						<template v-if="run.vehicle"> · <Truck class="inline h-3.5 w-3.5" /> {{ run.vehicle }}</template>
					</p>
				</div>
				<Button v-if="['Draft', 'Scheduled'].includes(run.status)" @click="startRun">
					<Play class="h-4 w-4" /> Start run
				</Button>
				<Button v-else-if="run.status === 'In Transit' && !openStops.length" @click="finishRun">
					<Flag class="h-4 w-4" /> Finish run
				</Button>
				<Button
					v-else-if="run.status === 'Completed' && !run.cod_reconciled && canReconcile && (run.cod_collected_total || 0) > 0"
					@click="reconcile"
				>
					<HandCoins class="h-4 w-4" /> Reconcile {{ fmtMoney(run.cod_collected_total) }}
				</Button>
			</header>

			<!-- COD summary -->
			<div
				v-if="(run.cod_due_total || 0) > 0"
				class="mb-4 flex flex-wrap items-center gap-x-6 gap-y-1 rounded-2xl bg-coal-900 px-5 py-3.5 text-sm text-white"
			>
				<span class="text-white/60">Cash to collect: <b class="text-white tabular-nums">{{ fmtMoney(run.cod_due_total) }}</b></span>
				<span class="text-white/60">Collected: <b class="text-brand-400 tabular-nums">{{ fmtMoney(run.cod_collected_total) }}</b></span>
				<span v-if="run.cod_reconciled" class="inline-flex items-center gap-1 text-emerald-400">
					<CheckCircle2 class="h-4 w-4" /> Reconciled
				</span>
			</div>

			<!-- Stops -->
			<div class="space-y-3">
				<div
					v-for="(s, i) in run.stops"
					:key="s.name"
					class="rounded-2xl bg-white p-5 ring-1 ring-gray-100"
					:class="s.status === 'Completed' && 'opacity-75'"
				>
					<div class="flex flex-wrap items-start gap-3">
						<span
							class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-sm font-bold"
							:class="s.stop_type === 'Delivery' ? 'bg-brand-600/10 text-brand-700' : 'bg-cyan-50 text-cyan-700'"
						>
							{{ i + 1 }}
						</span>
						<div class="min-w-0 flex-1">
							<div class="flex flex-wrap items-center gap-2">
								<span class="text-[11px] font-bold uppercase tracking-wider" :class="s.stop_type === 'Delivery' ? 'text-brand-700' : 'text-cyan-700'">
									{{ s.stop_type }}
								</span>
								<RouterLink
									v-if="s.shipment"
									:to="`/shipments/${s.shipment}`"
									class="inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline"
								>
									<Package class="h-3.5 w-3.5" /> {{ s.shipment }}
								</RouterLink>
								<span v-else-if="s.pickup_request" class="text-sm font-medium">{{ s.pickup_request }}</span>
								<StatusBadge :status="s.status" />
							</div>
							<div class="mt-1 text-sm">
								{{ s.contact_name || s.shipment_info?.customer_name || "—" }}
								<a v-if="s.contact_phone" :href="`tel:${s.contact_phone}`" class="text-brand-700">· {{ s.contact_phone }}</a>
							</div>
							<div class="text-[13px] text-muted-foreground">{{ s.address || "no address" }}</div>
							<div v-if="(s.cod_due || 0) > 0" class="mt-1 text-[13px]">
								<span class="rounded-full bg-amber-50 px-2 py-0.5 font-semibold text-amber-700 ring-1 ring-amber-200 tabular-nums">
									COD {{ fmtMoney(s.cod_due) }}
								</span>
							</div>
							<!-- POD summary once done -->
							<div v-if="s.status === 'Completed'" class="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
								<span v-if="s.pod_receiver">Received by <b>{{ s.pod_receiver }}</b></span>
								<span v-if="s.pod_time">{{ fmtDateTime(s.pod_time) }}</span>
								<a v-if="s.pod_photo" :href="s.pod_photo" target="_blank" class="text-brand-700 hover:underline">photo</a>
								<a v-if="s.pod_signature" :href="s.pod_signature" target="_blank" class="text-brand-700 hover:underline">signature</a>
								<span v-if="(s.cod_collected || 0) > 0" class="tabular-nums">cash {{ fmtMoney(s.cod_collected) }}</span>
							</div>
							<div v-else-if="s.status === 'Failed'" class="mt-2 text-xs text-red-600">
								<XCircle class="inline h-3.5 w-3.5" /> {{ s.failure_reason || "Failed" }}
							</div>
						</div>
					</div>

					<!-- Driver actions -->
					<div v-if="run.status === 'In Transit' && ['Pending', 'Arrived'].includes(s.status)" class="mt-4 flex flex-wrap gap-2">
						<a
							:href="mapsUrl(s.address)"
							target="_blank"
							rel="noopener"
							class="inline-flex h-10 items-center gap-2 rounded-lg border border-input bg-white px-4 text-sm font-medium text-gray-700 shadow-xs hover:bg-gray-50"
						>
							<Navigation class="h-4 w-4" /> Navigate
						</a>
						<Button v-if="s.status === 'Pending'" variant="secondary" @click="arrived(s)">Arrived</Button>
						<Button @click="openPod(s)">
							<CheckCircle2 class="h-4 w-4" /> Complete
						</Button>
						<Button variant="ghost" class="text-red-600 hover:bg-red-50" @click="failFor = s">
							Can't deliver
						</Button>
					</div>
				</div>
			</div>

			<!-- ── POD dialog ─────────────────────────────────────────────── -->
			<Dialog
				:open="!!podFor"
				:title="podFor?.stop_type === 'Delivery' ? 'Proof of delivery' : 'Complete pickup'"
				@update:open="podFor = null"
			>
				<div class="space-y-4">
					<div class="space-y-1.5">
						<Label :required="podFor?.stop_type === 'Delivery'">
							{{ podFor?.stop_type === "Delivery" ? "Received by" : "Handed over by" }}
						</Label>
						<Input v-model="pod.receiver" placeholder="Name of the person" />
					</div>
					<div v-if="podFor?.stop_type === 'Delivery'" class="space-y-1.5">
						<Label>Signature</Label>
						<SignaturePad ref="sigPad" />
					</div>
					<div class="space-y-1.5">
						<Label>Photo</Label>
						<label class="flex cursor-pointer items-center gap-2.5 rounded-xl border border-dashed border-gray-300 px-4 py-3 text-sm text-gray-600 hover:bg-gray-50">
							<Camera class="h-4 w-4 text-gray-400" />
							{{ pod.photoFile ? pod.photoFile.name : "Take or choose a photo" }}
							<input type="file" accept="image/*" capture="environment" class="hidden" @change="onPhoto" />
						</label>
					</div>
					<div v-if="(podFor?.cod_due || 0) > 0" class="space-y-1.5">
						<Label required>Cash collected</Label>
						<Input v-model.number="pod.cod" type="number" min="0" step="0.01" />
						<p class="text-xs text-muted-foreground">Due: {{ fmtMoney(podFor?.cod_due) }}</p>
					</div>
				</div>
				<template #footer>
					<div class="flex justify-end gap-2">
						<Button variant="outline" @click="podFor = null">Cancel</Button>
						<Button :loading="podSaving" @click="completePod">
							{{ podFor?.stop_type === "Delivery" ? "Confirm delivery" : "Confirm pickup" }}
						</Button>
					</div>
				</template>
			</Dialog>

			<!-- ── Fail dialog ────────────────────────────────────────────── -->
			<Dialog :open="!!failFor" title="Can't deliver" @update:open="failFor = null">
				<div class="space-y-4">
					<p class="text-sm text-muted-foreground">
						The customer will be notified that delivery was attempted. Tell us why:
					</p>
					<Textarea v-model="failReason" :rows="2" placeholder="e.g. Nobody home, phone off" />
				</div>
				<template #footer>
					<div class="flex justify-end gap-2">
						<Button variant="outline" @click="failFor = null">Back</Button>
						<Button variant="destructive" :loading="failing" @click="confirmFail">Mark failed</Button>
					</div>
				</template>
			</Dialog>
		</template>
	</div>
</template>
