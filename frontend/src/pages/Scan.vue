<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { ScanLine, Package, Warehouse, ArrowRight, Keyboard } from "lucide-vue-next";
import { Html5Qrcode } from "html5-qrcode";
import { call } from "@/lib/frappe";
import { useToast } from "@/composables/useToast";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import StatusBadge from "@/components/StatusBadge.vue";

// Warehouse scan station (FR-CON-6): point the camera at a package label's
// QR → shipment card → one-tap "Received at warehouse". Falls back to typing
// the tracking number when there's no camera.
const router = useRouter();
const toast = useToast();

const READER_ID = "bwm-qr-reader";
let scanner: Html5Qrcode | null = null;
const scanning = ref(false);
const cameraError = ref("");
const manual = ref("");

interface ShipmentHit extends Record<string, unknown> {
	name: string;
	customer_name?: string;
	status?: string;
	current_milestone?: string;
	destination?: string;
	total_packages?: number;
}
const hit = ref<ShipmentHit | null>(null);
const marking = ref(false);

async function lookup(code: string) {
	const tracking = code.trim().toUpperCase();
	if (!tracking) return;
	try {
		hit.value = await call<ShipmentHit>("bwm_logistics.api.shipments.get_shipment", { name: tracking });
		// Pause between hits so one QR doesn't fire twenty lookups.
		await pauseScanner();
	} catch {
		toast.warning(`No shipment found for ${tracking}`);
	}
}

async function markReceived() {
	if (!hit.value) return;
	marking.value = true;
	try {
		await call("bwm_logistics.api.shipments.record_event", {
			shipment: hit.value.name,
			milestone: "Received at Warehouse",
			notify: 1,
		});
		toast.success(`${hit.value.name} received — customer notified`);
		hit.value = null;
		await resumeScanner();
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not record receipt");
	} finally {
		marking.value = false;
	}
}

async function nextScan() {
	hit.value = null;
	await resumeScanner();
}

async function startScanner() {
	try {
		scanner = new Html5Qrcode(READER_ID);
		await scanner.start(
			{ facingMode: "environment" },
			{ fps: 8, qrbox: { width: 220, height: 220 } },
			(text) => lookup(text),
			() => undefined, // per-frame decode misses are normal
		);
		scanning.value = true;
	} catch (e: unknown) {
		cameraError.value =
			(e as { message?: string })?.message ||
			"Camera unavailable — type the tracking number instead.";
	}
}
async function pauseScanner() {
	try {
		scanner?.pause(true);
	} catch {
		/* not started */
	}
}
async function resumeScanner() {
	try {
		scanner?.resume();
	} catch {
		/* not started */
	}
}

onMounted(startScanner);
onBeforeUnmount(async () => {
	try {
		if (scanner && scanning.value) await scanner.stop();
	} catch {
		/* already stopped */
	}
});
</script>

<template>
	<div class="mx-auto max-w-xl">
		<header class="mb-5">
			<h1 class="text-2xl font-semibold tracking-tight">Scan</h1>
			<p class="mt-1 text-sm text-muted-foreground">
				Scan a package label to receive it at the warehouse or open the shipment.
			</p>
		</header>

		<!-- Camera -->
		<div class="overflow-hidden rounded-3xl bg-coal-900 ring-1 ring-gray-100">
			<div :id="READER_ID" class="mx-auto w-full [&_video]:!w-full"></div>
			<div v-if="cameraError" class="p-8 text-center text-sm text-white/60">
				<ScanLine class="mx-auto mb-3 h-8 w-8 text-white/30" />
				{{ cameraError }}
			</div>
		</div>

		<!-- Manual entry -->
		<form class="mt-4 flex gap-2" @submit.prevent="lookup(manual)">
			<div class="relative flex-1">
				<Keyboard class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
				<Input v-model="manual" placeholder="Or type a tracking number…" class="pl-9" />
			</div>
			<Button type="submit" variant="outline">Find</Button>
		</form>

		<!-- Hit card -->
		<div v-if="hit" class="mt-4 rounded-3xl bg-white p-6 ring-1 ring-brand-300">
			<div class="flex items-start gap-3">
				<span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-600/10 text-brand-700">
					<Package class="h-5 w-5" />
				</span>
				<div class="min-w-0 flex-1">
					<div class="flex flex-wrap items-center gap-2">
						<span class="text-lg font-semibold">{{ hit.name }}</span>
						<StatusBadge :status="hit.status" />
					</div>
					<div class="text-sm text-muted-foreground">
						{{ hit.customer_name }} · {{ hit.total_packages || 0 }} pkg
						<template v-if="hit.destination"> · → {{ hit.destination }}</template>
					</div>
					<div v-if="hit.current_milestone" class="text-xs text-muted-foreground">
						Latest: {{ hit.current_milestone }}
					</div>
				</div>
			</div>
			<div class="mt-4 flex flex-wrap gap-2">
				<Button :loading="marking" @click="markReceived">
					<Warehouse class="h-4 w-4" /> Received at warehouse
				</Button>
				<Button variant="outline" @click="router.push(`/shipments/${hit.name}`)">
					Open shipment <ArrowRight class="h-4 w-4" />
				</Button>
				<Button variant="ghost" @click="nextScan">Scan next</Button>
			</div>
		</div>
	</div>
</template>
