<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter, RouterLink } from "vue-router";
import { ArrowLeft, Package, ReceiptText, CheckCircle2 } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtDate, fmtDateTime, fmtMoney, fmtWeight } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import StatusBadge from "@/components/StatusBadge.vue";
import Timeline, { type TimelineEvent } from "@/components/Timeline.vue";

const route = useRoute();
const router = useRouter();
const toast = useToast();

interface Detail extends Record<string, unknown> {
	name: string;
	status?: string;
	direction?: string;
	destination?: string;
	eta?: string;
	timeline: TimelineEvent[];
	packages: Array<Record<string, unknown>>;
	invoice?: { name: string; status: string; grand_total: number; outstanding_amount: number; currency: string };
	pod?: { pod_receiver?: string; pod_time?: string; pod_photo?: string; pod_signature?: string };
}
const data = ref<Detail | null>(null);
const loading = ref(true);
const name = computed(() => String(route.params.name));

onMounted(async () => {
	try {
		data.value = await call<Detail>("bwm_logistics.api.portal.shipment_detail", { name: name.value });
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Shipment not found");
		router.push("/portal/shipments");
	} finally {
		loading.value = false;
	}
});
</script>

<template>
	<div class="mx-auto max-w-4xl">
		<div v-if="loading" class="py-16 text-center text-sm text-muted-foreground">Loading…</div>
		<template v-else-if="data">
			<header class="mb-6 flex flex-wrap items-center gap-3">
				<RouterLink
					to="/portal/shipments"
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
					</div>
					<p class="text-sm text-muted-foreground">
						{{ data.direction }} · {{ data.destination || "—" }}
						<template v-if="data.eta"> · ETA {{ fmtDate(data.eta as string) }}</template>
					</p>
				</div>
			</header>

			<!-- Invoice banner -->
			<div
				v-if="data.invoice && data.invoice.outstanding_amount > 0"
				class="mb-4 flex flex-wrap items-center gap-4 rounded-3xl bg-brand-50 p-5 ring-1 ring-brand-200"
			>
				<span class="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-600 text-white">
					<ReceiptText class="h-5 w-5" />
				</span>
				<div class="min-w-0 flex-1">
					<div class="font-semibold">
						{{ fmtMoney(data.invoice.outstanding_amount, data.invoice.currency) }} outstanding
					</div>
					<div class="text-xs text-muted-foreground">Invoice {{ data.invoice.name }}</div>
				</div>
				<RouterLink
					to="/portal/invoices"
					class="rounded-full bg-brand-600 px-5 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-700"
				>
					Pay now
				</RouterLink>
			</div>

			<!-- Proof of delivery -->
			<div
				v-if="data.pod"
				class="mb-4 rounded-3xl bg-emerald-50 p-5 ring-1 ring-emerald-200"
			>
				<div class="flex items-center gap-2 font-semibold text-emerald-800">
					<CheckCircle2 class="h-5 w-5" /> Delivered
					<span v-if="data.pod.pod_time" class="font-normal text-emerald-700">· {{ fmtDateTime(data.pod.pod_time) }}</span>
				</div>
				<div class="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-emerald-800">
					<span v-if="data.pod.pod_receiver">Received by <b>{{ data.pod.pod_receiver }}</b></span>
					<a v-if="data.pod.pod_photo" :href="data.pod.pod_photo" target="_blank" rel="noopener" class="font-medium underline underline-offset-2">View photo</a>
					<a v-if="data.pod.pod_signature" :href="data.pod.pod_signature" target="_blank" rel="noopener" class="font-medium underline underline-offset-2">View signature</a>
				</div>
			</div>

			<div class="grid gap-4 sm:grid-cols-5">
				<!-- Timeline -->
				<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100 sm:col-span-3">
					<h2 class="label-caps mb-4">Tracking timeline</h2>
					<Timeline :events="data.timeline" />
				</div>

				<!-- Packages -->
				<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100 sm:col-span-2">
					<h2 class="label-caps mb-4">Your packages</h2>
					<ul class="divide-y divide-gray-100 text-sm">
						<li v-for="(p, i) in data.packages" :key="i" class="py-2">
							<div class="font-medium">{{ p.description }}</div>
							<div class="text-xs text-muted-foreground">
								× {{ p.qty }} · {{ fmtWeight(p.weight_kg as number) }}
							</div>
						</li>
					</ul>
					<div class="mt-3 border-t border-gray-100 pt-3 text-sm">
						<div class="flex justify-between">
							<span class="text-muted-foreground">Total weight</span>
							<span class="font-medium tabular-nums">{{ fmtWeight(data.total_weight_kg as number) }}</span>
						</div>
					</div>
				</div>
			</div>
		</template>
	</div>
</template>
