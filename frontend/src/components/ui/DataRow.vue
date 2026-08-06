<script setup lang="ts">
// One label/value pair inside <DataList>. Empty renders an em-dash rather than
// collapsing, so a half-filled record still reads as a form you can complete.
defineProps<{ label: string; value?: string | number | null; wide?: boolean }>();
</script>

<template>
	<div
		class="flex items-baseline justify-between gap-4 py-2.5 sm:block sm:border-b sm:border-gray-100 sm:py-3"
		:class="wide && 'sm:col-span-2'"
	>
		<dt class="shrink-0 text-[13px] text-muted-foreground sm:label-caps sm:mb-1 sm:block">{{ label }}</dt>
		<dd class="min-w-0 text-right text-sm sm:text-left">
			<slot>
				<span v-if="value === null || value === undefined || value === ''" class="text-gray-400">—</span>
				<span v-else>{{ value }}</span>
			</slot>
		</dd>
	</div>
</template>
