<script setup lang="ts">
// Empty-state stub for pages whose real implementation lands in a later
// phase (P1/P2 per the PRD roadmap). Keeps every nav destination renderable
// so the shell, access gating, and routing can be exercised end-to-end.
defineProps<{
	title: string;
	description: string;
	phase?: string;
}>();
</script>

<template>
	<div class="mx-auto max-w-3xl">
		<header class="mb-6">
			<h1 class="text-2xl font-semibold tracking-tight">{{ title }}</h1>
		</header>
		<div class="flex flex-col items-center rounded-3xl bg-white p-14 text-center ring-1 ring-gray-100">
			<div class="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-600/10 text-brand-700">
				<slot name="icon" />
			</div>
			<p class="max-w-md text-sm text-muted-foreground">{{ description }}</p>
			<span
				v-if="phase"
				class="mt-5 inline-flex items-center rounded-full bg-gray-100 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-gray-500"
			>
				Coming in {{ phase }}
			</span>
		</div>
	</div>
</template>
