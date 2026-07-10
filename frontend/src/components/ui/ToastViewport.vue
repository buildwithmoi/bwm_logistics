<script setup lang="ts">
import { useToast, type ToastTone } from "@/composables/useToast";

const { items, dismiss } = useToast();

const toneClasses: Record<ToastTone, string> = {
	success: "border-emerald-200 bg-emerald-50 text-emerald-900",
	error: "border-red-200 bg-red-50 text-red-900",
	info: "border-blue-200 bg-blue-50 text-blue-900",
	warning: "border-amber-200 bg-amber-50 text-amber-900",
};
</script>

<template>
	<div class="pointer-events-none fixed bottom-6 right-6 z-[100] flex w-80 flex-col gap-2">
		<div
			v-for="t in items"
			:key="t.id"
			class="pointer-events-auto flex items-start gap-3 rounded-xl border px-4 py-3 shadow-pop"
			:class="toneClasses[t.tone]"
		>
			<div class="flex-1 text-sm">{{ t.message }}</div>
			<button
				class="text-xs opacity-60 hover:opacity-100"
				aria-label="Dismiss"
				@click="dismiss(t.id)"
			>
				✕
			</button>
		</div>
	</div>
</template>
