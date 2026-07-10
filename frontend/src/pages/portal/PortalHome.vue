<script setup lang="ts">
import { computed } from "vue";
import { Package, ReceiptText, Search, ArrowRight } from "lucide-vue-next";
import { RouterLink } from "vue-router";
import { useSessionStore } from "@/stores/session";

// Customer portal landing. P0 renders the layout; P1 wires "my shipments"
// and the public track endpoint.
const session = useSessionStore();
const firstName = computed(
	() => (session.user?.full_name || session.user?.first_name || "").split(/\s+/)[0] || "there",
);
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
			<div class="mt-3 flex flex-col gap-2 sm:flex-row">
				<div class="relative flex-1">
					<Search class="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-white/40" />
					<input
						type="text"
						placeholder="Enter your tracking number"
						disabled
						class="h-11 w-full rounded-xl border border-white/15 bg-white/[0.06] pl-10 pr-3 text-sm text-white placeholder:text-white/40 focus:outline-none"
					/>
				</div>
				<button
					type="button"
					disabled
					class="h-11 rounded-xl bg-brand-500 px-6 text-sm font-semibold text-coal-900 opacity-60"
				>
					Track
				</button>
			</div>
			<p class="mt-2 text-xs text-white/45">Live tracking arrives with the next release.</p>
		</div>

		<!-- Quick links -->
		<div class="mt-4 grid gap-4 sm:grid-cols-2">
			<RouterLink
				to="/portal/shipments"
				class="group flex items-center gap-4 rounded-3xl bg-white p-6 ring-1 ring-gray-100 transition-shadow hover:shadow-pop"
			>
				<span class="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand-600/10 text-brand-700 transition-transform group-hover:scale-105">
					<Package class="h-5 w-5" />
				</span>
				<span class="min-w-0 flex-1">
					<span class="block font-semibold">My shipments</span>
					<span class="block text-[13px] text-muted-foreground">Milestone timelines & documents</span>
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
					<span class="block font-semibold">Invoices & payments</span>
					<span class="block text-[13px] text-muted-foreground">View and pay online</span>
				</span>
				<ArrowRight class="h-4 w-4 shrink-0 text-gray-300 transition-colors group-hover:text-brand-600" />
			</RouterLink>
		</div>
	</div>
</template>
