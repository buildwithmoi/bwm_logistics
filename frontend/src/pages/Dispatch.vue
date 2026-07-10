<script setup lang="ts">
import { MapPin } from "lucide-vue-next";
import PagePlaceholder from "@/components/PagePlaceholder.vue";
</script>

<template>
	<PagePlaceholder
		title="Dispatch"
		description="Pickups, delivery runs, driver assignment, and proof of delivery — the courier side of the operation."
		phase="V1 (P2)"
	>
		<template #icon><MapPin class="h-7 w-7" /></template>
	</PagePlaceholder>
</template>
