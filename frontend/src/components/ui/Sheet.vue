<script setup lang="ts">
import { DialogRoot, DialogPortal, DialogOverlay, DialogContent, DialogTitle, DialogDescription } from "reka-ui";
import { X } from "lucide-vue-next";
import { cn } from "@/lib/utils";

// A bottom sheet on phones, a centred dialog from `sm` up.
//
// The PWA is used one-handed on a phone, where a sheet that rises from the
// bottom puts its controls under the thumb and reads as native. The same
// component becomes an ordinary modal on a desktop, so a flow written once
// feels right in both places.
withDefaults(
	defineProps<{ open: boolean; title: string; description?: string; size?: "default" | "wide" }>(),
	{ size: "default" },
);
const emit = defineEmits<{ (e: "update:open", v: boolean): void }>();
</script>

<template>
	<DialogRoot :open="open" @update:open="emit('update:open', $event)">
		<DialogPortal>
			<DialogOverlay
				class="fixed inset-0 z-[80] bg-coal-900/50 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=closed]:animate-out data-[state=closed]:fade-out-0"
			/>
			<DialogContent
				:class="
					cn(
						'fixed z-[90] flex flex-col overflow-hidden bg-white outline-none',
						// phone: full-width sheet anchored to the bottom edge
						'inset-x-0 bottom-0 max-h-[88vh] rounded-t-2xl pb-[env(safe-area-inset-bottom)]',
						'data-[state=open]:animate-in data-[state=open]:slide-in-from-bottom data-[state=closed]:animate-out data-[state=closed]:slide-out-to-bottom',
						// sm and up: a centred card again
						'sm:inset-x-auto sm:bottom-auto sm:left-1/2 sm:top-1/2 sm:w-[calc(100vw-3rem)] sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-xl sm:border sm:border-border sm:pb-0 sm:shadow-modal',
						'sm:data-[state=open]:slide-in-from-bottom-0 sm:data-[state=closed]:slide-out-to-bottom-0',
						size === 'wide' ? 'sm:max-w-2xl' : 'sm:max-w-md',
					)
				"
			>
				<!-- Grab handle: the affordance that says "drag/dismiss me" on a phone -->
				<div class="flex shrink-0 justify-center pt-2.5 sm:hidden" aria-hidden="true">
					<span class="h-1 w-9 rounded-full bg-gray-300" />
				</div>

				<div class="flex shrink-0 items-start justify-between gap-3 px-5 pb-3 pt-3 sm:border-b sm:border-border sm:px-6 sm:py-4">
					<div class="min-w-0">
						<DialogTitle class="text-[17px] font-semibold tracking-tight">{{ title }}</DialogTitle>
						<DialogDescription v-if="description" class="mt-0.5 text-[13px] text-muted-foreground">
							{{ description }}
						</DialogDescription>
					</div>
					<button
						type="button"
						class="-mr-1 flex h-9 w-9 shrink-0 touch-manipulation items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
						aria-label="Close"
						@click="emit('update:open', false)"
					>
						<X class="h-4 w-4" aria-hidden="true" />
					</button>
				</div>

				<div class="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pb-5 sm:px-6 sm:pb-6">
					<slot />
				</div>

				<div
					v-if="$slots.footer"
					class="shrink-0 border-t border-border bg-gray-50/60 px-5 py-3.5 sm:px-6 sm:py-4"
				>
					<slot name="footer" />
				</div>
			</DialogContent>
		</DialogPortal>
	</DialogRoot>
</template>
