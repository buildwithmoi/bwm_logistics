<script setup lang="ts">
import { computed } from "vue";
import { cn } from "@/lib/utils";

// The one pill in the system. StatusBadge/DirectionBadge render through this so
// every tinted label in the app has identical geometry — pages should never
// hand-roll a `rounded-full px-2 …` span again.
type Tone = "neutral" | "brand" | "info" | "success" | "warning" | "danger" | "violet" | "outline";

const props = withDefaults(defineProps<{ tone?: Tone; size?: "sm" | "md"; dot?: boolean }>(), {
	tone: "neutral",
	size: "sm",
});

const TONES: Record<Tone, string> = {
	neutral: "bg-gray-100 text-gray-600 ring-gray-200",
	brand: "bg-brand-600/10 text-brand-800 ring-brand-600/20",
	info: "bg-blue-50 text-blue-700 ring-blue-200",
	success: "bg-emerald-50 text-emerald-700 ring-emerald-200",
	warning: "bg-amber-50 text-amber-800 ring-amber-200",
	danger: "bg-red-50 text-red-700 ring-red-200",
	violet: "bg-violet-50 text-violet-700 ring-violet-200",
	outline: "bg-white text-gray-600 ring-gray-200",
};
const DOTS: Record<Tone, string> = {
	neutral: "bg-gray-400",
	brand: "bg-brand-600",
	info: "bg-blue-500",
	success: "bg-emerald-500",
	warning: "bg-amber-500",
	danger: "bg-red-500",
	violet: "bg-violet-500",
	outline: "bg-gray-400",
};

const classes = computed(() =>
	cn(
		"inline-flex items-center gap-1.5 whitespace-nowrap rounded-full font-semibold ring-1",
		props.size === "md" ? "px-3 py-1 text-[12.5px]" : "px-2.5 py-0.5 text-[11.5px]",
		TONES[props.tone],
	),
);
</script>

<template>
	<span :class="classes">
		<span v-if="dot" class="h-1.5 w-1.5 shrink-0 rounded-full" :class="DOTS[tone]" aria-hidden="true" />
		<slot />
	</span>
</template>
