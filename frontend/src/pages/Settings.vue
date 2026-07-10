<script setup lang="ts">
import { Settings } from "lucide-vue-next";
import PagePlaceholder from "@/components/PagePlaceholder.vue";
</script>

<template>
	<PagePlaceholder
		title="Settings"
		description="Company branding, milestone templates, rate cards, notification templates, payment gateways, and staff access."
		phase="MVP (P1)"
	>
		<template #icon><Settings class="h-7 w-7" /></template>
	</PagePlaceholder>
</template>
