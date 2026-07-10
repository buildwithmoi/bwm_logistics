<script setup lang="ts">
defineProps<{ for?: string; required?: boolean }>();
</script>

<template>
	<label
		:for="$props.for"
		class="text-[13px] font-medium leading-none text-gray-600 peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
	>
		<slot />
		<span v-if="required" class="text-red-500">*</span>
	</label>
</template>
