<script setup lang="ts">
import { Container } from "lucide-vue-next";
import PagePlaceholder from "@/components/PagePlaceholder.vue";
</script>

<template>
	<PagePlaceholder
		title="Containers"
		description="Track every import and export container milestone-by-milestone — vessel, ports, ETA, customs, and demurrage risk — with customers tagged for automatic notifications."
		phase="MVP (P1)"
	>
		<template #icon><Container class="h-7 w-7" /></template>
	</PagePlaceholder>
</template>
