<script setup lang="ts">
import { DialogRoot, DialogPortal, DialogOverlay, DialogContent, DialogTitle } from "reka-ui";
import { X } from "lucide-vue-next";
import { cn } from "@/lib/utils";

// reka-ui dialog in the house style: dimmed blurred overlay, centered white
// card, pinned header, scrollable body (ex_beauty pattern).
const props = withDefaults(
	defineProps<{
		open: boolean;
		title: string;
		size?: "default" | "wide" | "xl";
	}>(),
	{ size: "default" },
);
const emit = defineEmits<{ (e: "update:open", v: boolean): void }>();

const widths: Record<string, string> = {
	default: "max-w-md",
	wide: "max-w-2xl",
	xl: "max-w-5xl",
};
</script>

<template>
	<DialogRoot :open="open" @update:open="emit('update:open', $event)">
		<DialogPortal>
			<DialogOverlay
				class="fixed inset-0 z-[80] bg-coal-900/40 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in-0"
			/>
			<DialogContent
				:class="
					cn(
						'fixed left-1/2 top-1/2 z-[90] flex max-h-[90vh] w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col overflow-hidden border border-border bg-white shadow-modal outline-none sm:rounded-xl',
						widths[size],
					)
				"
			>
				<div class="flex shrink-0 items-center justify-between border-b border-border px-6 py-4">
					<DialogTitle class="text-[17px] font-semibold tracking-tight">{{ title }}</DialogTitle>
					<button
						type="button"
						class="flex h-8 w-8 items-center justify-center rounded-md text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
						aria-label="Close"
						@click="emit('update:open', false)"
					>
						<X class="h-4 w-4" />
					</button>
				</div>
				<div class="min-h-0 flex-1 overflow-y-auto p-6">
					<slot />
				</div>
				<div v-if="$slots.footer" class="shrink-0 border-t border-border bg-gray-50/60 px-6 py-4">
					<slot name="footer" />
				</div>
			</DialogContent>
		</DialogPortal>
	</DialogRoot>
</template>
