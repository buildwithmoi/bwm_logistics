<script setup lang="ts">
import { Package } from "lucide-vue-next";
import PagePlaceholder from "@/components/PagePlaceholder.vue";
</script>

<template>
	<PagePlaceholder
		title="My Shipments"
		description="Every shipment tagged to you — its milestone timeline, packages, and documents — updated automatically as your goods move."
		phase="MVP (P1)"
	>
		<template #icon><Package class="h-7 w-7" /></template>
	</PagePlaceholder>
</template>
