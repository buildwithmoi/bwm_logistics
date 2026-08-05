<script setup lang="ts">
// One page header for every screen: a title that stays on one line on a phone,
// an optional sub-line, and actions that sit beside it on desktop and drop onto
// their own row when there isn't room. Pages shouldn't hand-roll this — the
// titles were competing with their own buttons at 390px.
defineProps<{ title: string; subtitle?: string }>();
</script>

<template>
	<header class="mb-5 flex flex-col gap-3 sm:flex-row sm:items-start sm:gap-x-3">
		<div class="min-w-0 flex-1">
			<h1 class="truncate text-xl font-semibold tracking-tight sm:text-2xl">{{ title }}</h1>
			<p v-if="subtitle" class="mt-0.5 text-pretty text-[13px] text-muted-foreground sm:text-sm">
				{{ subtitle }}
			</p>
		</div>
		<div v-if="$slots.actions" class="flex shrink-0 flex-wrap items-center gap-2">
			<slot name="actions" />
		</div>
	</header>
</template>
