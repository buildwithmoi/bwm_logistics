<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Container, Package, ReceiptText, CalendarClock, ArrowRight, Activity, AlertTriangle } from "lucide-vue-next";
import { RouterLink } from "vue-router";
import { useSessionStore } from "@/stores/session";
import { call } from "@/lib/frappe";
import { fmtDateTime } from "@/lib/format";

// Operator landing — bento dashboard wired to api/dashboard.get_overview.
const session = useSessionStore();

const firstName = computed(
	() => (session.user?.full_name || session.user?.first_name || "").split(/\s+/)[0] || "there",
);
const today = new Date().toLocaleDateString(undefined, {
	weekday: "long",
	month: "long",
	day: "numeric",
});

interface Overview {
	containers_active: number;
	arriving_soon: number;
	active_shipments: number;
	unpaid_invoices: number;
	demurrage_risk: Array<{ name: string; container_no?: string; demurrage_start_date: string; days_left: number }>;
	recent_events: Array<{
		name: string;
		event_datetime: string;
		milestone: string;
		location?: string;
		container?: string;
		shipment?: string;
	}>;
}
const data = ref<Overview | null>(null);
const loading = ref(true);

onMounted(async () => {
	try {
		data.value = await call<Overview>("bwm_logistics.api.dashboard.get_overview");
	} finally {
		loading.value = false;
	}
});

const tiles = computed(() => [
	{ label: "Containers active", value: data.value?.containers_active ?? "…", icon: Container, accent: "#b8860b", to: "/containers" },
	{ label: "Arriving in 7 days", value: data.value?.arriving_soon ?? "…", icon: CalendarClock, accent: "#0891b2", to: "/containers" },
	{ label: "Active shipments", value: data.value?.active_shipments ?? "…", icon: Package, accent: "#a855f7", to: "/shipments" },
	{ label: "Unpaid invoices", value: data.value?.unpaid_invoices ?? "…", icon: ReceiptText, accent: "#10b981", to: "/billing" },
]);
</script>

<template>
	<div class="mx-auto max-w-6xl">
		<!-- Greeting header -->
		<header class="mb-6 flex flex-wrap items-center gap-4">
			<div
				class="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-400 to-brand-600 text-lg font-bold text-coal-900"
			>
				{{ firstName[0]?.toUpperCase() || "B" }}
			</div>
			<div class="min-w-0 flex-1">
				<h1 class="text-2xl font-semibold tracking-tight sm:text-3xl">
					Good day, {{ firstName }} 👋
				</h1>
			</div>
			<span class="rounded-full bg-gray-100 px-4 py-1.5 text-sm text-gray-600">{{ today }}</span>
		</header>

		<!-- Demurrage risk banner -->
		<div
			v-if="data?.demurrage_risk?.length"
			class="mb-4 flex flex-wrap items-center gap-3 rounded-2xl bg-red-50 px-5 py-3.5 ring-1 ring-red-200"
		>
			<AlertTriangle class="h-5 w-5 shrink-0 text-red-600" />
			<span class="min-w-0 flex-1 text-sm text-red-800">
				<b>{{ data.demurrage_risk.length }}</b> container(s) at demurrage risk:
				<template v-for="(c, i) in data.demurrage_risk.slice(0, 3)" :key="c.name">
					<RouterLink :to="`/containers/${c.name}`" class="font-semibold underline underline-offset-2">
						{{ c.container_no || c.name }}</RouterLink>
					<span v-if="c.days_left > 0"> (in {{ c.days_left }}d)</span><span v-else> (running)</span
					><span v-if="i < Math.min(data.demurrage_risk.length, 3) - 1">, </span>
				</template>
				<span v-if="data.demurrage_risk.length > 3">…</span>
			</span>
			<RouterLink to="/containers" class="shrink-0 text-sm font-semibold text-red-700 hover:underline">
				Review →
			</RouterLink>
		</div>

		<!-- KPI strip -->
		<div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
			<RouterLink
				v-for="t in tiles"
				:key="t.label"
				:to="t.to"
				class="group rounded-3xl bg-white p-5 ring-1 ring-gray-100 transition-shadow hover:shadow-pop"
			>
				<span
					class="mb-4 flex h-10 w-10 items-center justify-center rounded-xl transition-transform group-hover:scale-105"
					:style="{ backgroundColor: t.accent + '1f', color: t.accent }"
				>
					<component :is="t.icon" class="h-5 w-5" />
				</span>
				<div class="text-3xl font-semibold tracking-tight tabular-nums">{{ t.value }}</div>
				<div class="mt-1 text-[13px] text-muted-foreground">{{ t.label }}</div>
			</RouterLink>
		</div>

		<!-- Activity feed -->
		<div class="mt-4 grid gap-4 lg:grid-cols-12">
			<div class="rounded-3xl bg-white p-6 ring-1 ring-gray-100 lg:col-span-7">
				<div class="mb-4 flex items-center gap-2">
					<Activity class="h-4 w-4 text-brand-600" />
					<h2 class="text-[15px] font-semibold tracking-tight">Latest milestones</h2>
				</div>
				<div v-if="loading" class="py-8 text-center text-sm text-muted-foreground">Loading…</div>
				<div v-else-if="!data?.recent_events?.length" class="rounded-xl bg-gray-50 px-4 py-8 text-center text-sm text-muted-foreground">
					No activity yet — create a container and record its first milestone.
				</div>
				<ul v-else class="divide-y divide-gray-100">
					<li v-for="e in data.recent_events" :key="e.name" class="flex items-baseline gap-3 py-2.5">
						<span class="w-32 shrink-0 text-xs tabular-nums text-muted-foreground">{{ fmtDateTime(e.event_datetime) }}</span>
						<span class="min-w-0 flex-1 truncate">
							<span class="font-medium">{{ e.milestone }}</span>
							<span v-if="e.location" class="text-muted-foreground"> · {{ e.location }}</span>
						</span>
						<RouterLink
							v-if="e.shipment"
							:to="`/shipments/${e.shipment}`"
							class="shrink-0 text-xs font-medium text-brand-700 hover:underline"
						>{{ e.shipment }}</RouterLink>
						<RouterLink
							v-else-if="e.container"
							:to="`/containers/${e.container}`"
							class="shrink-0 text-xs font-medium text-brand-700 hover:underline"
						>{{ e.container }}</RouterLink>
					</li>
				</ul>
			</div>

			<!-- Quick actions ribbon -->
			<div class="flex flex-col justify-between gap-6 rounded-3xl bg-gray-900 p-7 text-white lg:col-span-5">
				<div>
					<h2 class="text-lg font-semibold tracking-tight text-white">Move something today</h2>
					<p class="mt-1 text-sm text-white/60">
						Create a container, tag your customers' shipments to it, and every
						milestone you record notifies them automatically.
					</p>
				</div>
				<div class="flex flex-wrap gap-2">
					<RouterLink
						to="/containers"
						class="inline-flex items-center gap-2 rounded-full bg-brand-500 px-5 py-2.5 text-sm font-semibold text-coal-900 transition-colors hover:bg-brand-400"
					>
						New container <ArrowRight class="h-4 w-4" />
					</RouterLink>
					<RouterLink
						to="/shipments"
						class="inline-flex items-center gap-2 rounded-full border border-white/25 px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:border-brand-400 hover:text-brand-300"
					>
						New shipment
					</RouterLink>
				</div>
			</div>
		</div>
	</div>
</template>
