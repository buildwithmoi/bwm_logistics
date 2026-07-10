<script setup lang="ts">
import { computed } from "vue";
import { cn } from "@/lib/utils";

const props = withDefaults(
	defineProps<{
		modelValue?: string | number | null;
		type?: string;
		placeholder?: string;
		disabled?: boolean;
		invalid?: boolean;
		step?: string | number;
		min?: string | number;
		max?: string | number;
		id?: string;
	}>(),
	{ type: "text" },
);

const emit = defineEmits<{
	(e: "update:modelValue", value: string): void;
}>();

const classes = computed(() =>
	cn(
		"flex h-9 w-full rounded-lg border bg-white px-3 py-1 text-sm text-gray-900 shadow-xs transition-colors placeholder:text-gray-400 focus-visible:border-brand-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-100 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-500",
		props.invalid ? "border-red-400 focus-visible:border-red-400 focus-visible:ring-red-100" : "border-input",
	),
);
</script>

<template>
	<input
		:id="id"
		:type="type"
		:value="modelValue ?? ''"
		:placeholder="placeholder"
		:disabled="disabled"
		:step="step"
		:min="min"
		:max="max"
		:class="classes"
		@input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
	/>
</template>
