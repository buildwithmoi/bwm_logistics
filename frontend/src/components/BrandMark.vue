<script setup lang="ts">
import { computed } from "vue";
import { useBrandStore } from "@/stores/brand";

// The tenant's mark: their uploaded logo, or the first letter of the business
// name when there isn't one. A site that has never uploaded anything still gets
// something deliberate rather than a placeholder belonging to another company.
const props = withDefaults(
	defineProps<{
		/** Box size in px. */
		size?: number;
		/** Tone of the monogram tile when no logo is set. */
		tone?: "brand" | "light";
	}>(),
	{ size: 36, tone: "brand" },
);

const brand = useBrandStore();
const box = computed(() => `${props.size}px`);
// The letter shouldn't fill the tile edge to edge.
const letter = computed(() => `${Math.round(props.size * 0.46)}px`);
</script>

<template>
	<span
		class="flex shrink-0 items-center justify-center overflow-hidden rounded-lg"
		:class="
			brand.logo
				? 'bg-white'
				: tone === 'light'
					? 'bg-white/10 text-white'
					: 'bg-gradient-to-br from-brand-400 to-brand-600 text-coal-900'
		"
		:style="{ width: box, height: box }"
	>
		<img
			v-if="brand.logo"
			:src="brand.logo"
			:alt="brand.name"
			class="h-full w-full object-contain"
		/>
		<span
			v-else
			class="font-bold leading-none tracking-tight"
			:style="{ fontSize: letter }"
			aria-hidden="true"
		>{{ brand.monogram }}</span>
	</span>
</template>
