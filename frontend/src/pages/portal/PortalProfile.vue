<script setup lang="ts">
import { UserRound } from "lucide-vue-next";
import PagePlaceholder from "@/components/PagePlaceholder.vue";
</script>

<template>
	<PagePlaceholder
		title="Profile"
		description="Your contact details, delivery addresses, and notification preferences — choose how you want to hear from us."
		phase="MVP (P1)"
	>
		<template #icon><UserRound class="h-7 w-7" /></template>
	</PagePlaceholder>
</template>
