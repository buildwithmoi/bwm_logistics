<script setup lang="ts">
// Label/value pairs for a record screen.
//
// Detail pages were each rolling their own two-column grid of `label-caps` +
// value, which drifted: different gaps, different em-dashes for empty, some
// wrapping badly on a phone. One <dl> instead — stacked rows on a phone (label
// left, value right, like a native settings list), two columns from sm up.
defineProps<{ columns?: 1 | 2 }>();
</script>

<template>
	<dl
		class="divide-y divide-gray-100 sm:grid sm:gap-x-6 sm:gap-y-0 sm:divide-y-0"
		:class="columns === 1 ? 'sm:grid-cols-1' : 'sm:grid-cols-2'"
	>
		<slot />
	</dl>
</template>
