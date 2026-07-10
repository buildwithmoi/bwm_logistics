<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Package, ReceiptText, Search, ArrowRight } from "lucide-vue-next";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { useSessionStore } from "@/stores/session";
import { call } from "@/lib/frappe";
import { useToast } from "@/composables/useToast";
import StatusBadge from "@/components/StatusBadge.vue";
import Timeline, { type TimelineEvent } from "@/components/Timeline.vue";

// Customer portal landing — live overview + the track box (uses the same
// guest endpoint as the public site, so any tracking number can be checked).
const session = useSessionStore();
const route = useRoute();
const router = useRouter();
const toast = useToast();

const firstName = computed(
	() => (session.user?.full_name || session.user?.first_name || "").split(/\s+/)[0] || "there",
);

interface Overview {
	active_count: number;
	unpaid_invoices: number;
	recent: Array<{ name: string; status: string; current_milestone?: string; destination?: string }>;
}
const data = ref<Overview | null>(null);
onMounted(async () => {
	try {
		data.value = await call<Overview>("bwm_logistics.api.portal.overview");
	} catch {
		/* customer without link sees empty state */
	}
	// Deep link from notification emails: /portal?track=BWM-000001
	const t = route.query.track;
	if (typeof t === "string" && t) {
		trackNo.value = t;
		doTrack();
		router.replace({ query: {} });
	}
});

// ── track box ───────────────────────────────────────────────────────────────
interface TrackResult {
	found: boolean;
	tracking_no?: string;
	status?: string;
	current_milestone?: string;
	destination?: string;
	eta?: string;
	timeline?: TimelineEvent[];
}
const trackNo = ref("");
const tracking = ref(false);
const trackResult = ref<TrackResult | null>(null);

async function doTrack() {
	if (!trackNo.value.trim()) return;
	tracking.value = true;
	trackResult.value = null;
	try {
		trackResult.value = await call<TrackResult>("bwm_logistics.api.track.track", {
			tracking_no: trackNo.value.trim(),
		});
		if (!trackResult.value.found) toast.warning("No shipment found for that number");
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not track right now");
	} finally {
		tracking.value = false;
	}
}
</script>

<template>
	<div class="mx-auto max-w-4xl">
		<header class="mb-6">
			<h1 class="text-2xl font-semibold tracking-tight sm:text-3xl">Hello, {{ firstName }} 👋</h1>
			<p class="mt-1 text-sm text-muted-foreground">
				Track your shipments, download documents, and pay invoices — all in one place.
			</p>
		</header>

		<!-- Track box -->
		<div class="rounded-3xl bg-coal-900 p-7 text-white">
			<div class="label-caps !text-brand-400">Track a shipment</div>
			<form class="mt-3 flex flex-col gap-2 sm:flex-row" @submit.prevent="doTrack">
				<div class="relative flex-1">
					<Search class="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" />
					<input
						v-model="trackNo"
						type="text"
						placeholder="Enter your tracking number (e.g. BWM-000001)"
						class="h-11 w-full rounded-xl border border-white/15 bg-white/[0.06] pl-10 pr-3 text-sm text-white placeholder:text-white/40 focus:border-brand-400 focus:outline-none"
					/>
				</div>
				<button
					type="submit"
					:disabled="tracking"
					class="h-11 rounded-xl bg-brand-500 px-6 text-sm font-semibold text-coal-900 transition-colors hover:bg-brand-400 disabled:opacity-60"
				>
					{{ tracking ? "Tracking…" : "Track" }}
				</button>
			</form>

			<!-- Inline result -->
			<div v-if="trackResult?.found" class="mt-5 rounded-2xl bg-white p-5 text-gray-900">
				<div class="mb-3 flex flex-wrap items-center gap-2">
					<span class="font-semibold">{{ trackResult.tracking_no }}</span>
					<StatusBadge :status="trackResult.status" />
					<span v-if="trackResult.destination" class="text-sm text-muted-foreground">→ {{ trackResult.destination }}</span>
				</div>
				<Timeline :events="trackResult.timeline || []" />
			</div>
		</div>

		<!-- KPI cards -->
		<div class="mt-4 grid gap-4 sm:grid-cols-2">
			<RouterLink
				to="/portal/shipments"
				class="group flex items-center gap-4 rounded-3xl bg-white p-6 ring-1 ring-gray-100 transition-shadow hover:shadow-pop"
			>
				<span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-600/10 text-brand-700 transition-transform group-hover:scale-105">
					<Package class="h-5 w-5" />
				</span>
				<span class="min-w-0 flex-1">
					<span class="block text-2xl font-semibold tabular-nums">{{ data?.active_count ?? "…" }}</span>
					<span class="block text-[13px] text-muted-foreground">Active shipments</span>
				</span>
				<ArrowRight class="h-4 w-4 shrink-0 text-gray-300 transition-colors group-hover:text-brand-600" />
			</RouterLink>
			<RouterLink
				to="/portal/invoices"
				class="group flex items-center gap-4 rounded-3xl bg-white p-6 ring-1 ring-gray-100 transition-shadow hover:shadow-pop"
			>
				<span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-600/10 text-brand-700 transition-transform group-hover:scale-105">
					<ReceiptText class="h-5 w-5" />
				</span>
				<span class="min-w-0 flex-1">
					<span class="block text-2xl font-semibold tabular-nums">{{ data?.unpaid_invoices ?? "…" }}</span>
					<span class="block text-[13px] text-muted-foreground">Invoices awaiting payment</span>
				</span>
				<ArrowRight class="h-4 w-4 shrink-0 text-gray-300 transition-colors group-hover:text-brand-600" />
			</RouterLink>
		</div>

		<!-- Recent shipments -->
		<div v-if="data?.recent?.length" class="mt-4 rounded-3xl bg-white p-6 ring-1 ring-gray-100">
			<h2 class="label-caps mb-3">Recent shipments</h2>
			<ul class="divide-y divide-gray-100">
				<li v-for="s in data.recent" :key="s.name">
					<RouterLink
						:to="`/portal/shipments/${s.name}`"
						class="flex items-center gap-3 py-3 transition-colors hover:bg-gray-50/60"
					>
						<span class="min-w-0 flex-1">
							<span class="block font-medium text-brand-700">{{ s.name }}</span>
							<span class="block text-xs text-muted-foreground">
								{{ s.current_milestone || "No updates yet" }}
								<template v-if="s.destination"> · {{ s.destination }}</template>
							</span>
						</span>
						<StatusBadge :status="s.status" />
					</RouterLink>
				</li>
			</ul>
		</div>
	</div>
</template>
