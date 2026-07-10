<script setup lang="ts">
import { BellRing } from "lucide-vue-next";
import PagePlaceholder from "@/components/PagePlaceholder.vue";
</script>

<template>
	<PagePlaceholder
		title="Notifications"
		description="Every email and SMS the system sends — who was told what, when, and whether it delivered — with templates you can edit."
		phase="MVP (P1)"
	>
		<template #icon><BellRing class="h-7 w-7" /></template>
	</PagePlaceholder>
</template>
