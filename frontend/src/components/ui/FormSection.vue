<script setup lang="ts">
// One titled block of a form page. Optional `#action` for a section-level
// control (the "+ Add line" of a repeating table).
defineProps<{ title: string; hint?: string }>();
</script>

<template>
	<section class="rounded-2xl bg-white p-4 ring-1 ring-gray-100 sm:p-5">
		<div class="mb-3 flex items-baseline justify-between gap-3">
			<div class="min-w-0">
				<h2 class="label-caps">{{ title }}</h2>
				<p v-if="hint" class="mt-1 text-pretty text-xs text-muted-foreground">{{ hint }}</p>
			</div>
			<slot name="action" />
		</div>
		<slot />
	</section>
</template>
