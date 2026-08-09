<script setup lang="ts">
import { computed } from "vue";
import { isBlank } from "@/lib/format";
import DataRow from "./DataRow.vue";

// Label/value pairs for a record screen.
//
// A detail view answers a question; it is not a rendering of the table schema.
// So a field with no value is *omitted*, and a section where nothing has been
// filled in collapses to one line offering to fill it — rather than eleven rows
// of em-dashes the reader has to scan past to find the three that say
// something. Forms are the exception and pass `show-empty`, because there the
// blank row IS the affordance.
export interface DataItem {
	label: string;
	value?: string | number | null;
	/** Span both columns on wide screens (addresses, notes). */
	wide?: boolean;
}

const props = withDefaults(
	defineProps<{
		items?: DataItem[];
		columns?: 1 | 2;
		/** Shown when every item is blank. Name what's missing, not "no data". */
		emptyText?: string;
		/** Forms want the blanks: they're the fields still to fill. */
		showEmpty?: boolean;
	}>(),
	{ columns: 2 },
);

const visible = computed(() => (props.items || []).filter((i) => props.showEmpty || !isBlank(i.value)));
const allBlank = computed(() => !!props.items && visible.value.length === 0);
</script>

<template>
	<!-- Nothing recorded in this whole section -->
	<div v-if="allBlank" class="flex flex-wrap items-center justify-between gap-3 py-1">
		<p class="text-[13px] text-muted-foreground">{{ emptyText || "Nothing recorded yet." }}</p>
		<slot name="empty-action" />
	</div>

	<dl
		v-else
		class="divide-y divide-gray-100 sm:grid sm:gap-x-6 sm:gap-y-0 sm:divide-y-0"
		:class="columns === 1 ? 'sm:grid-cols-1' : 'sm:grid-cols-2'"
	>
		<DataRow
			v-for="i in visible"
			:key="i.label"
			:label="i.label"
			:value="i.value"
			:wide="i.wide"
			show-empty
		/>
		<!-- Rows that need custom markup (a badge, a link) stay slot-driven. -->
		<slot />
	</dl>
</template>
