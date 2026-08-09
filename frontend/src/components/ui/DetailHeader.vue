<script setup lang="ts">
import { ChevronLeft, ChevronDown } from "lucide-vue-next";
import { useRouter } from "vue-router";

// The header every record screen wears.
//
// On a phone this is a real app bar: a full-height, labelled Back control on
// the left (44px target, not a bare arrow floating in the margin), the record
// id as the title, and actions pinned to the right. Meta — status pills, the
// one-line summary — sits on its own row underneath so nothing has to compete
// for the same line. From `sm` up it relaxes into a page heading with the
// actions on the right of the title row.
//
// Back is a real navigation: router.back() when there's history to pop (so the
// list keeps its scroll position and filters), else the canonical parent URL,
// which is what a reloaded deep link needs.
const props = defineProps<{
	title: string;
	subtitle?: string;
	backTo: string;
	backLabel?: string;
	/** Accessible name for the badge-as-button, when `#statusAction` is used. */
	statusActionLabel?: string;
}>();
const emit = defineEmits<{ (e: "status-click"): void }>();

const router = useRouter();
function goBack() {
	if (window.history.state?.back) router.back();
	else router.push(props.backTo);
}
</script>

<template>
	<header class="mb-4">
		<!-- Row 1: back · title · actions -->
		<div class="flex items-center gap-2">
			<button
				type="button"
				class="-ml-2 flex h-10 shrink-0 touch-manipulation items-center gap-1 rounded-lg pl-1.5 pr-2.5 text-[13px] font-medium text-gray-600 transition-colors hover:bg-gray-100 hover:text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
				@click="goBack"
			>
				<ChevronLeft class="h-5 w-5" aria-hidden="true" />
				<span>{{ backLabel || "Back" }}</span>
			</button>

			<div class="ml-auto flex shrink-0 items-center gap-2">
				<slot name="actions" />
			</div>
		</div>

		<!-- Row 2: the record itself. The status badge beside the title IS the
		     control that changes it — one status, one place, one action. -->
		<div class="mt-2 flex flex-wrap items-center gap-x-3 gap-y-2">
			<h1 class="min-w-0 truncate text-xl font-semibold tracking-tight sm:text-2xl">{{ title }}</h1>
			<component
				:is="$slots.statusAction ? 'button' : 'div'"
				v-if="$slots.badges"
				:type="$slots.statusAction ? 'button' : undefined"
				class="flex flex-wrap items-center gap-1.5 rounded-full"
				:class="
					$slots.statusAction &&
					'touch-manipulation px-1 py-0.5 -mx-1 transition-colors hover:bg-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500'
				"
				:aria-label="$slots.statusAction ? statusActionLabel || 'Update status' : undefined"
				@click="$slots.statusAction && emit('status-click')"
			>
				<slot name="badges" />
				<ChevronDown v-if="$slots.statusAction" class="h-3.5 w-3.5 text-gray-400" aria-hidden="true" />
			</component>
		</div>
		<p v-if="subtitle" class="mt-1 text-pretty text-[13px] text-muted-foreground">{{ subtitle }}</p>
	</header>
</template>
