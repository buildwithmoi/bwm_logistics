<script setup lang="ts">
import { computed } from "vue";

// Status → tinted pill. Semantic colors are separate from the gold accent.
const props = defineProps<{ status?: string | null }>();

const TONES: Record<string, string> = {
	// containers
	Active: "bg-blue-50 text-blue-700 ring-blue-200",
	Completed: "bg-emerald-50 text-emerald-700 ring-emerald-200",
	Cancelled: "bg-gray-100 text-gray-500 ring-gray-200",
	// shipments
	Open: "bg-gray-100 text-gray-600 ring-gray-200",
	"In Transit": "bg-blue-50 text-blue-700 ring-blue-200",
	Arrived: "bg-cyan-50 text-cyan-700 ring-cyan-200",
	"Ready for Delivery": "bg-amber-50 text-amber-700 ring-amber-200",
	Delivered: "bg-emerald-50 text-emerald-700 ring-emerald-200",
	// invoices / notifications
	Paid: "bg-emerald-50 text-emerald-700 ring-emerald-200",
	Unpaid: "bg-amber-50 text-amber-700 ring-amber-200",
	Overdue: "bg-red-50 text-red-700 ring-red-200",
	"Partly Paid": "bg-amber-50 text-amber-700 ring-amber-200",
	Sent: "bg-emerald-50 text-emerald-700 ring-emerald-200",
	Failed: "bg-red-50 text-red-700 ring-red-200",
	Skipped: "bg-gray-100 text-gray-500 ring-gray-200",
	Queued: "bg-blue-50 text-blue-700 ring-blue-200",
};

const cls = computed(
	() => TONES[props.status || ""] || "bg-gray-100 text-gray-600 ring-gray-200",
);
</script>

<template>
	<span
		v-if="status"
		class="inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-[11.5px] font-semibold ring-1"
		:class="cls"
	>
		{{ status }}
	</span>
	<span v-else class="text-gray-400">—</span>
</template>
