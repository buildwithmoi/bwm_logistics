<script setup lang="ts">
import { computed } from "vue";
import { cn } from "@/lib/utils";

// Styled native <select> — same visual language as Input. Options come as
// strings or {value,label}; an empty-string option renders the placeholder.
const props = defineProps<{
	modelValue?: string | null;
	options: Array<string | { value: string; label: string }>;
	placeholder?: string;
	disabled?: boolean;
	id?: string;
}>();
const emit = defineEmits<{ (e: "update:modelValue", value: string): void }>();

const normalized = computed(() =>
	props.options.map((o) => (typeof o === "string" ? { value: o, label: o } : o)),
);
</script>

<template>
	<select
		:id="id"
		:value="modelValue ?? ''"
		:disabled="disabled"
		:class="
			cn(
				'flex h-9 w-full appearance-none rounded-lg border border-input bg-white px-3 py-1 text-sm text-gray-900 shadow-xs transition-colors focus-visible:border-brand-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-100 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-500',
				!modelValue && 'text-gray-400',
			)
		"
		@change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
	>
		<option v-if="placeholder" value="" disabled hidden>{{ placeholder }}</option>
		<option v-for="o in normalized" :key="o.value" :value="o.value">{{ o.label }}</option>
	</select>
</template>
