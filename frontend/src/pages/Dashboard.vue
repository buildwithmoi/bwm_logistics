<script setup lang="ts">
import { computed } from "vue";
import { Container, Package, ReceiptText, Truck, ArrowRight } from "lucide-vue-next";
import { RouterLink } from "vue-router";
import { useSessionStore } from "@/stores/session";

// Operator landing — bento-grid dashboard (ex_beauty pattern). P0 renders the
// layout with empty KPIs; P1 wires them to api/dashboard aggregates.
const session = useSessionStore();

const firstName = computed(
	() => (session.user?.full_name || session.user?.first_name || "").split(/\s+/)[0] || "there",
);
const today = new Date().toLocaleDateString(undefined, {
	weekday: "long",
	month: "long",
	day: "numeric",
});

const tiles = [
	{ label: "Containers in transit", value: 0, icon: Container, accent: "#b8860b", to: "/containers" },
	{ label: "Active shipments", value: 0, icon: Package, accent: "#0891b2", to: "/shipments" },
	{ label: "Unpaid invoices", value: 0, icon: ReceiptText, accent: "#a855f7", to: "/billing" },
	{ label: "Deliveries today", value: 0, icon: Truck, accent: "#10b981", to: "/dispatch" },
];
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

		<!-- Getting-started ribbon (P0: the operational pages arrive with P1) -->
		<div class="mt-4 flex flex-wrap items-center gap-6 rounded-3xl bg-gray-900 p-7 text-white">
			<div class="min-w-0 flex-1">
				<h2 class="text-lg font-semibold tracking-tight text-white">Foundation is live</h2>
				<p class="mt-1 max-w-xl text-sm text-white/60">
					Roles, access control, the public site, and this shell are in place.
					Containers, shipments, customer tagging, and notifications arrive with
					the MVP phase.
				</p>
			</div>
			<RouterLink
				to="/settings"
				class="inline-flex items-center gap-2 rounded-full bg-brand-500 px-5 py-2.5 text-sm font-semibold text-coal-900 transition-colors hover:bg-brand-400"
			>
				Review settings <ArrowRight class="h-4 w-4" />
			</RouterLink>
		</div>
	</div>
</template>
