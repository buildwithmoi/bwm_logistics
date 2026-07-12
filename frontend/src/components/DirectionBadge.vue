<script setup lang="ts">
import { computed } from "vue";
import { ArrowDownToLine, ArrowUpFromLine } from "lucide-vue-next";

// Import vs Export at a glance (P7 feedback: the difference wasn't clear).
// Import = sky + inbound arrow; Export = violet + outbound arrow.
const props = defineProps<{ direction?: string | null; size?: "sm" | "md" }>();

const isImport = computed(() => props.direction === "Import");
const isExport = computed(() => props.direction === "Export");
</script>

<template>
	<span
		v-if="isImport || isExport"
		class="inline-flex items-center gap-1 whitespace-nowrap rounded-full font-semibold ring-1"
		:class="[
			size === 'md' ? 'px-3 py-1 text-[12.5px]' : 'px-2.5 py-0.5 text-[11.5px]',
			isImport ? 'bg-sky-50 text-sky-700 ring-sky-200' : 'bg-violet-50 text-violet-700 ring-violet-200',
		]"
	>
		<ArrowDownToLine v-if="isImport" class="h-3 w-3" />
		<ArrowUpFromLine v-else class="h-3 w-3" />
		{{ direction }}
	</span>
	<span v-else class="text-gray-400">—</span>
</template>
