<script setup lang="ts">
import { ReceiptText } from "lucide-vue-next";
import PagePlaceholder from "@/components/PagePlaceholder.vue";
</script>

<template>
	<PagePlaceholder
		title="Billing"
		description="Rate cards, one-click Sales Invoices from shipment charges, and online payments via card or mobile money."
		phase="MVP (P1)"
	>
		<template #icon><ReceiptText class="h-7 w-7" /></template>
	</PagePlaceholder>
</template>
