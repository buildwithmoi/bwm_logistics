<script setup lang="ts">
import { onMounted, ref } from "vue";

import { Printer } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { useToast } from "@/composables/useToast";
import Button from "@/components/ui/Button.vue";
import DetailHeader from "@/components/ui/DetailHeader.vue";
import Input from "@/components/ui/Input.vue";
import StatementView, { type StatementData } from "@/components/StatementView.vue";

const toast = useToast();
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
		data.value = await call<StatementData>("bwm_logistics.api.portal.my_statement", {
			from_date: fromDate.value || null,
			to_date: toDate.value || null,
		});
		fromDate.value = data.value.from_date;
		toDate.value = data.value.to_date;
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load your statement");
	} finally {
		loading.value = false;
	}
}
onMounted(load);
</script>

<template>
	<div class="mx-auto max-w-3xl">
		<div class="print:hidden">
			<DetailHeader title="My Statement" back-to="/portal/invoices" back-label="Invoices">
				<template #actions>
				<Input v-model="fromDate" type="date" class="w-36 sm:w-40" aria-label="From date" />
					<Input v-model="toDate" type="date" class="w-36 sm:w-40" aria-label="To date" />
					<Button variant="outline" @click="load">Update</Button>
					<Button @click="printStatement"><Printer class="h-4 w-4" aria-hidden="true" /> Print</Button>
				</template>
			</DetailHeader>
		</div>

		<div v-if="loading" class="py-16 text-center text-sm text-muted-foreground">Loading…</div>
		<StatementView v-else-if="data" :data="data" />
	</div>
</template>
