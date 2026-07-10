<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter, RouterLink } from "vue-router";
import { ArrowLeft, Printer } from "lucide-vue-next";
import qrcode from "qrcode-generator";
import { call } from "@/lib/frappe";
import { useToast } from "@/composables/useToast";
import Button from "@/components/ui/Button.vue";

// Printable package labels (FR-CON-5): one label per package with a QR of
// the tracking number. Browser print → thermal/A4; @media print CSS strips
// the app chrome so only labels render.
const route = useRoute();
const router = useRouter();
const toast = useToast();

interface ShipmentData extends Record<string, unknown> {
	name: string;
	customer_name?: string;
	destination?: string;
	consignee_name?: string;
	consignee_phone?: string;
	packages?: Array<{ description: string; qty: number }>;
}
const data = ref<ShipmentData | null>(null);
const name = computed(() => String(route.params.name));

// One label per physical package (qty expands: 2× barrels → 2 labels).
const labels = computed(() => {
	const out: Array<{ description: string; index: number; total: number }> = [];
	const pkgs = data.value?.packages || [];
	const total = pkgs.reduce((n, p) => n + (p.qty || 1), 0);
	let i = 0;
	for (const p of pkgs) {
		for (let q = 0; q < (p.qty || 1); q++) {
			i += 1;
			out.push({ description: p.description, index: i, total });
		}
	}
	return out;
});

const qrSvg = computed(() => {
	if (!data.value) return "";
	const qr = qrcode(0, "M");
	qr.addData(data.value.name);
	qr.make();
	return qr.createSvgTag({ cellSize: 3, margin: 0, scalable: true });
});

function printLabels() {
	window.print();
}

onMounted(async () => {
	try {
		data.value = await call<ShipmentData>("bwm_logistics.api.shipments.get_shipment", {
			name: name.value,
		});
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load shipment");
		router.push("/shipments");
	}
});
</script>

<template>
	<div class="mx-auto max-w-3xl">
		<header class="mb-5 flex items-center gap-3 print:hidden">
			<RouterLink
				:to="`/shipments/${name}`"
				class="flex h-9 w-9 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
			>
				<ArrowLeft class="h-4 w-4" />
			</RouterLink>
			<h1 class="min-w-0 flex-1 text-2xl font-semibold tracking-tight">Labels — {{ name }}</h1>
			<Button @click="printLabels"><Printer class="h-4 w-4" /> Print</Button>
		</header>

		<div v-if="data" class="grid gap-4 sm:grid-cols-2 print:block">
			<div
				v-for="l in labels"
				:key="l.index"
				class="bwm-label rounded-xl border-2 border-gray-900 bg-white p-4 print:mb-3 print:break-inside-avoid print:rounded-none"
			>
				<div class="flex items-start justify-between gap-3">
					<div class="min-w-0">
						<div class="text-[10px] font-bold uppercase tracking-[0.18em]">BWM Logistics</div>
						<div class="mt-1 text-xl font-extrabold tracking-tight">{{ data.name }}</div>
						<div class="mt-1 truncate text-sm font-medium">{{ data.consignee_name || data.customer_name }}</div>
						<div class="truncate text-xs text-gray-600">{{ data.destination }}</div>
						<div v-if="data.consignee_phone" class="text-xs text-gray-600">{{ data.consignee_phone }}</div>
					</div>
					<div class="h-24 w-24 shrink-0 [&_svg]:h-full [&_svg]:w-full" v-html="qrSvg"></div>
				</div>
				<div class="mt-3 flex items-end justify-between border-t border-dashed border-gray-400 pt-2">
					<span class="min-w-0 flex-1 truncate text-xs">{{ l.description }}</span>
					<span class="shrink-0 text-sm font-bold tabular-nums">{{ l.index }} / {{ l.total }}</span>
				</div>
			</div>
		</div>
	</div>
</template>

<style>
@media print {
	/* Only the labels leave the printer. */
	header, nav, aside, .print\:hidden { display: none !important; }
	main { overflow: visible !important; padding: 0 !important; }
	body { background: white !important; }
	.bwm-label { width: 90mm; border-width: 1.5px; }
}
</style>
