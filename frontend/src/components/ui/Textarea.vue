<script setup lang="ts">
defineProps<{
	modelValue?: string | null;
	placeholder?: string;
	rows?: number;
	disabled?: boolean;
	id?: string;
}>();
const emit = defineEmits<{ (e: "update:modelValue", value: string): void }>();
</script>

<template>
	<textarea
		:id="id"
		:value="modelValue ?? ''"
		:placeholder="placeholder"
		:rows="rows || 3"
		:disabled="disabled"
		class="flex w-full rounded-lg border border-input bg-white px-3 py-2 text-sm text-gray-900 shadow-xs transition-colors placeholder:text-gray-400 focus-visible:border-brand-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-100 disabled:cursor-not-allowed disabled:bg-gray-50"
		@input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
	></textarea>
</template>
