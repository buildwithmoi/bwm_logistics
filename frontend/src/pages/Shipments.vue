<script setup lang="ts">
import { Package } from "lucide-vue-next";
import PagePlaceholder from "@/components/PagePlaceholder.vue";
</script>

<template>
	<PagePlaceholder
		title="Shipments"
		description="Each customer's consignment — packages, weights, values, and its own tracking number — consolidated into containers and tracked door to door."
		phase="MVP (P1)"
	>
		<template #icon><Package class="h-7 w-7" /></template>
	</PagePlaceholder>
</template>
