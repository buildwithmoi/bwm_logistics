<script setup lang="ts">
import { computed } from "vue";

// Stylised shipping-container mark — pure SVG so it stays crisp at any size
// and adapts to context (strokes inherit currentColor). Used in Login,
// AppShell, and anywhere we need brand identity.
const props = withDefaults(
	defineProps<{
		size?: number | string;
	}>(),
	{ size: 40 },
);

const dim = computed(() => (typeof props.size === "number" ? `${props.size}px` : props.size));
</script>

<template>
	<svg
		:width="dim"
		:height="dim"
		viewBox="0 0 40 40"
		fill="none"
		xmlns="http://www.w3.org/2000/svg"
		aria-hidden="true"
	>
		<!-- Container body -->
		<rect
			x="5" y="12" width="30" height="19" rx="2.5"
			stroke="currentColor" stroke-width="2.6"
		/>
		<!-- Corrugation ribs -->
		<path d="M12.5 12v19M20 12v19M27.5 12v19" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" opacity="0.85" />
		<!-- Top rail -->
		<path d="M5 17h30" stroke="currentColor" stroke-width="2" opacity="0.55" />
		<!-- Crane hook hint -->
		<path d="M20 12V7" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" />
		<path d="M14 7h12" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" />
	</svg>
</template>
