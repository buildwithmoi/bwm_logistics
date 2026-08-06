<script setup lang="ts">
import { ArrowLeft } from "lucide-vue-next";
import { RouterLink } from "vue-router";

// Layout for the "create a record" screens.
//
// Anything with more than a handful of fields — a container, a shipment, a
// delivery run, an invoice, a purchase — gets a page rather than a dialog: room
// to breathe, a real URL you can link to or reload, browser Back that works,
// and no nested scrolling on a phone. Dialogs stay for the small stuff (a
// customer, a driver, a payment).
//
// Sections are `<FormSection>`; actions live at the foot of the form, stacked
// full-width on a phone.
defineProps<{ title: string; subtitle?: string; backTo: string; backLabel?: string }>();
</script>

<template>
	<div class="mx-auto max-w-3xl">
		<header class="mb-5">
			<RouterLink
				:to="backTo"
				class="mb-2 inline-flex items-center gap-1.5 text-[13px] font-medium text-muted-foreground transition-colors hover:text-gray-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
			>
				<ArrowLeft class="h-4 w-4" aria-hidden="true" /> {{ backLabel || "Back" }}
			</RouterLink>
			<h1 class="truncate text-xl font-semibold tracking-tight sm:text-2xl">{{ title }}</h1>
			<p v-if="subtitle" class="mt-0.5 text-pretty text-[13px] text-muted-foreground sm:text-sm">
				{{ subtitle }}
			</p>
		</header>

		<form class="space-y-4" @submit.prevent>
			<slot />

			<!-- Actions sit bottom-right at every width. Stacking them full-width
			     on a phone reads as two equally-weighted choices and puts Cancel
			     under the thumb; a right-aligned pair keeps Save where the eye
			     finishes and matches the desktop. -->
			<div class="flex flex-wrap items-center justify-end gap-2 pt-1">
				<slot name="actions" />
			</div>
		</form>
	</div>
</template>
