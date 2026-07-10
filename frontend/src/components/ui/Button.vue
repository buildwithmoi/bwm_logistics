<script setup lang="ts">
import { computed } from "vue";
import { cn } from "@/lib/utils";

type Variant = "default" | "secondary" | "outline" | "ghost" | "destructive" | "link";
type Size = "default" | "sm" | "lg" | "icon";

const props = withDefaults(
	defineProps<{
		variant?: Variant;
		size?: Size;
		type?: "button" | "submit" | "reset";
		disabled?: boolean;
		loading?: boolean;
	}>(),
	{ variant: "default", size: "default", type: "button" },
);

const variants: Record<Variant, string> = {
	default:
		"bg-brand-600 text-white shadow-xs hover:bg-brand-700 active:bg-brand-800",
	secondary:
		"bg-secondary text-secondary-foreground shadow-xs hover:bg-gray-200/70",
	outline:
		"border border-input bg-white text-gray-700 shadow-xs hover:bg-gray-50 hover:text-gray-900",
	ghost: "text-gray-600 hover:bg-gray-100 hover:text-gray-900",
	destructive: "bg-destructive text-white shadow-xs hover:bg-red-700",
	link: "text-brand-700 underline-offset-4 hover:underline",
};
const sizes: Record<Size, string> = {
	default: "h-9 px-4 text-sm",
	sm: "h-8 px-3 text-[13px]",
	lg: "h-11 px-6 text-[15px]",
	icon: "h-9 w-9",
};

const classes = computed(() =>
	cn(
		"inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/60 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
		variants[props.variant],
		sizes[props.size],
	),
);
</script>

<template>
	<button :type="type" :class="classes" :disabled="disabled || loading">
		<svg
			v-if="loading"
			class="h-3 w-3 animate-spin"
			viewBox="0 0 24 24"
			fill="none"
			stroke="currentColor"
			stroke-width="3"
		>
			<circle cx="12" cy="12" r="10" stroke-opacity="0.25" />
			<path d="M22 12a10 10 0 0 0-10-10" stroke-linecap="round" />
		</svg>
		<slot />
	</button>
</template>
