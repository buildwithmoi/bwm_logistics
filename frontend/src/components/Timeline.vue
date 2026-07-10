<script setup lang="ts">
import { CheckCircle2, Circle } from "lucide-vue-next";

// Milestone timeline — newest first, gold dot on the latest event. Shared by
// operator detail pages, the portal, and (visually) the public tracker.
export interface TimelineEvent {
	name?: string;
	event_datetime: string;
	milestone: string;
	location?: string | null;
	remarks?: string | null;
}

defineProps<{ events: TimelineEvent[] }>();

function fmt(dt: string): string {
	try {
		return new Date(dt.replace(" ", "T")).toLocaleString(undefined, {
			day: "numeric",
			month: "short",
			year: "numeric",
			hour: "2-digit",
			minute: "2-digit",
		});
	} catch {
		return dt;
	}
}
</script>

<template>
	<div v-if="!events.length" class="rounded-xl bg-gray-50 px-4 py-8 text-center text-sm text-muted-foreground">
		No milestones recorded yet.
	</div>
	<ol v-else class="relative space-y-0">
		<li v-for="(e, i) in events" :key="e.name || i" class="relative flex gap-3 pb-6 last:pb-0">
			<!-- rail -->
			<div class="flex flex-col items-center">
				<component
					:is="i === 0 ? CheckCircle2 : Circle"
					class="h-5 w-5 shrink-0"
					:class="i === 0 ? 'text-brand-600' : 'text-gray-300'"
				/>
				<div v-if="i < events.length - 1" class="mt-1 w-px flex-1 bg-gray-200"></div>
			</div>
			<div class="min-w-0 flex-1 -mt-0.5">
				<div class="flex flex-wrap items-baseline gap-x-3">
					<span class="text-sm font-semibold" :class="i === 0 ? 'text-gray-900' : 'text-gray-700'">
						{{ e.milestone }}
					</span>
					<span class="text-xs tabular-nums text-muted-foreground">{{ fmt(e.event_datetime) }}</span>
				</div>
				<div v-if="e.location" class="mt-0.5 text-[13px] text-muted-foreground">{{ e.location }}</div>
				<div v-if="e.remarks" class="mt-0.5 text-[13px] text-gray-500">{{ e.remarks }}</div>
			</div>
		</li>
	</ol>
</template>
