<script setup lang="ts">
// A figure and what it means. No icon — a wallet glyph beside a cash number
// tells an operator nothing the label doesn't, and eight of them in a row is
// what made the dashboard feel busy. Colour is reserved for the one card that
// earns it (`tone="dark"` for the P&L) and for emphasis passed via `#meta`.
defineProps<{
	value: string | number;
	label: string;
	tone?: "default" | "dark";
	to?: string;
}>();
</script>

<template>
	<component
		:is="to ? 'router-link' : 'div'"
		:to="to"
		class="flex h-full flex-col justify-center rounded-2xl p-4 sm:p-5"
		:class="
			tone === 'dark'
				? 'bg-coal-900 text-white'
				: [
						'bg-white ring-1 ring-gray-100',
						to && 'touch-manipulation transition-shadow hover:shadow-card focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500',
					]
		"
	>
		<div class="text-xl font-semibold tabular-nums sm:text-2xl" :class="tone === 'dark' && 'text-brand-400'">
			<slot name="value">{{ value }}</slot>
		</div>
		<div class="mt-1 text-pretty text-[13px]" :class="tone === 'dark' ? 'text-white/55' : 'text-muted-foreground'">
			{{ label }}<slot name="meta" />
		</div>
	</component>
</template>
