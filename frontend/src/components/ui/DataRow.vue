<script setup lang="ts">
import { computed, useSlots } from "vue";
import { isBlank } from "@/lib/format";

// One label/value pair inside <DataList>.
//
// Blank rows are dropped by default: on a detail screen an unrecorded field is
// noise, and eleven of them bury the three that matter. `show-empty` brings the
// em-dash back for surfaces that are genuinely a form being filled in — the
// exception stays visible at the call site.
const props = defineProps<{
	label: string;
	value?: string | number | null;
	wide?: boolean;
	showEmpty?: boolean;
}>();

const slots = useSlots();
// A slot could render anything, so never hide a row that has one.
const show = computed(() => props.showEmpty || !!slots.default || !isBlank(props.value));
</script>

<template>
	<div
		v-if="show"
		class="flex items-baseline justify-between gap-4 py-2.5 sm:block sm:border-b sm:border-gray-100 sm:py-3"
		:class="wide && 'sm:col-span-2'"
	>
		<dt class="shrink-0 text-[13px] text-muted-foreground sm:label-caps sm:mb-1 sm:block">{{ label }}</dt>
		<dd class="min-w-0 text-right text-sm sm:text-left">
			<slot>
				<span v-if="isBlank(value)" class="text-gray-400">—</span>
				<span v-else>{{ value }}</span>
			</slot>
		</dd>
	</div>
</template>
