<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, RouterLink } from "vue-router";
import { ArrowLeft, Printer } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { useToast } from "@/composables/useToast";
import Button from "@/components/ui/Button.vue";
import Input from "@/components/ui/Input.vue";
import StatementView, { type StatementData } from "@/components/StatementView.vue";

const route = useRoute();
const toast = useToast();
const customer = computed(() => String(route.params.name));

const data = ref<StatementData | null>(null);
const loading = ref(true);
const fromDate = ref("");
const toDate = ref("");

function printStatement() {
	window.print();
}

async function load() {
	loading.value = true;
	try {
		data.value = await call<StatementData>("bwm_logistics.api.billing.customer_statement", {
			customer: customer.value,
			from_date: fromDate.value || null,
			to_date: toDate.value || null,
		});
		fromDate.value = data.value.from_date;
		toDate.value = data.value.to_date;
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load the statement");
	} finally {
		loading.value = false;
	}
}
onMounted(load);
</script>

<template>
	<div class="mx-auto max-w-3xl">
		<header class="mb-5 flex flex-wrap items-center gap-3 print:hidden">
			<RouterLink
				to="/customers"
				class="flex h-9 w-9 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
			>
				<ArrowLeft class="h-4 w-4" />
			</RouterLink>
			<h1 class="min-w-0 flex-1 text-2xl font-semibold tracking-tight">Statement</h1>
			<Input v-model="fromDate" type="date" class="w-40" />
			<Input v-model="toDate" type="date" class="w-40" />
			<Button variant="outline" @click="load">Update</Button>
			<Button @click="printStatement"><Printer class="h-4 w-4" /> Print</Button>
		</header>

		<div v-if="loading" class="py-16 text-center text-sm text-muted-foreground">Loading…</div>
		<StatementView v-else-if="data" :data="data" />
	</div>
</template>
