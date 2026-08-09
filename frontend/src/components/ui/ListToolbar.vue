<script setup lang="ts">
import Input from "./Input.vue";
import Select from "./Select.vue";
import { Search } from "lucide-vue-next";

// One filter bar per list.
//
// The lists used to stack two competing pill rows — direction above, status
// below — each starting with a button labelled "All", so the screen showed the
// same word twice meaning two different things and pushed the data three rows
// down. Search and the secondary lens now share one line; the status pills are
// the only pill row on the screen.
defineProps<{
	search: string;
	searchLabel: string;
	searchPlaceholder: string;
	/** Secondary lens (direction, channel…). Omit for lists that have none. */
	lens?: string;
	lensLabel?: string;
	lensOptions?: Array<{ value: string; label: string }>;
	/** The one pill row. `""` is always "All". */
	statuses?: string[];
	status?: string;
	statusLabel?: string;
}>();
const emit = defineEmits<{
	(e: "update:search", v: string): void;
	(e: "update:lens", v: string): void;
	(e: "update:status", v: string): void;
}>();
</script>

<template>
	<div class="mb-4 space-y-3">
		<div class="flex flex-col gap-2 sm:flex-row sm:items-center">
			<div class="relative min-w-0 flex-1 sm:max-w-xs">
				<Search
					class="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400"
					aria-hidden="true"
				/>
				<Input
					:model-value="search"
					type="search"
					:aria-label="searchLabel"
					:placeholder="searchPlaceholder"
					class="pl-9"
					@update:model-value="emit('update:search', $event)"
				/>
			</div>
			<Select
				v-if="lensOptions?.length"
				:model-value="lens"
				:options="lensOptions"
				:aria-label="lensLabel"
				class="sm:w-44"
				@update:model-value="emit('update:lens', String($event))"
			/>
		</div>

		<div v-if="statuses?.length" class="chip-row" role="group" :aria-label="statusLabel || 'Status'">
			<button
				v-for="s in statuses"
				:key="s"
				type="button"
				class="chip"
				:class="status === s ? 'chip-on' : 'chip-off'"
				:aria-pressed="status === s"
				@click="emit('update:status', s)"
			>
				{{ s || "All" }}
			</button>
		</div>
	</div>
</template>
