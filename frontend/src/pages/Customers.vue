<script setup lang="ts">
import { Users } from "lucide-vue-next";
import PagePlaceholder from "@/components/PagePlaceholder.vue";
</script>

<template>
	<PagePlaceholder
		title="Customers"
		description="Customer profiles, portal access, notification preferences, and each customer's shipment history — staff create accounts and Frappe emails the set-password link."
		phase="MVP (P1)"
	>
		<template #icon><Users class="h-7 w-7" /></template>
	</PagePlaceholder>
</template>
