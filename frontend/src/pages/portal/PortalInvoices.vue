<script setup lang="ts">
import { ReceiptText } from "lucide-vue-next";
import PagePlaceholder from "@/components/PagePlaceholder.vue";
</script>

<template>
	<PagePlaceholder
		title="Invoices & Payments"
		description="Your invoices with live payment status — pay by card or mobile money and your goods release faster."
		phase="MVP (P1)"
	>
		<template #icon><ReceiptText class="h-7 w-7" /></template>
	</PagePlaceholder>
</template>
