<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter, RouterLink } from "vue-router";
import { ArrowLeft, Printer, CheckCircle2 } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtDate, fmtMoney } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import Button from "@/components/ui/Button.vue";

// Branded payment receipt — printed/handed to the customer after a payment
// is recorded (or reprinted any time from Billing).
const route = useRoute();
const router = useRouter();
const toast = useToast();
const name = computed(() => String(route.params.name));

interface Receipt {
	name: string;
	posting_date: string;
	party_name?: string;
	party?: string;
	paid_amount: number;
	mode_of_payment?: string;
	reference_no?: string;
	paid_to_account_currency?: string;
	in_words?: string;
	business_name: string;
	contact_phone?: string;
	contact_email?: string;
	invoices: Array<{ invoice: string; allocated: number; outstanding: number }>;
}
const data = ref<Receipt | null>(null);

function printReceipt() {
	window.print();
}

onMounted(async () => {
	try {
		data.value = await call<Receipt>("bwm_logistics.api.billing.get_receipt", {
			payment_entry: name.value,
		});
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Receipt not found");
		router.push("/billing");
	}
});
</script>

<template>
	<div class="mx-auto max-w-lg">
		<header class="mb-5 flex items-center gap-3 print:hidden">
			<RouterLink
				to="/billing"
				class="flex h-9 w-9 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
			>
				<ArrowLeft class="h-4 w-4" />
			</RouterLink>
			<h1 class="min-w-0 flex-1 text-2xl font-semibold tracking-tight">Receipt</h1>
			<Button @click="printReceipt"><Printer class="h-4 w-4" /> Print</Button>
		</header>

		<div v-if="data" class="rounded-3xl bg-white p-8 ring-1 ring-gray-100 print:rounded-none print:ring-0">
			<!-- Letterhead -->
			<div class="mb-6 border-b-2 border-gray-900 pb-4 text-center">
				<div class="text-lg font-extrabold tracking-tight">{{ data.business_name }}</div>
				<div class="label-caps mt-1">Payment Receipt</div>
				<div v-if="data.contact_phone || data.contact_email" class="mt-1 text-xs text-muted-foreground">
					{{ [data.contact_phone, data.contact_email].filter(Boolean).join(" · ") }}
				</div>
			</div>

			<div class="mb-5 flex items-center justify-center gap-2 text-emerald-700">
				<CheckCircle2 class="h-5 w-5" />
				<span class="text-2xl font-bold tabular-nums">
					{{ fmtMoney(data.paid_amount, data.paid_to_account_currency) }}
				</span>
			</div>
			<p v-if="data.in_words" class="mb-6 text-center text-xs italic text-muted-foreground">{{ data.in_words }}</p>

			<dl class="space-y-2.5 text-sm">
				<div class="flex justify-between"><dt class="text-muted-foreground">Receipt No</dt><dd class="font-medium">{{ data.name }}</dd></div>
				<div class="flex justify-between"><dt class="text-muted-foreground">Date</dt><dd class="tabular-nums">{{ fmtDate(data.posting_date) }}</dd></div>
				<div class="flex justify-between"><dt class="text-muted-foreground">Received from</dt><dd class="font-medium">{{ data.party_name || data.party }}</dd></div>
				<div class="flex justify-between"><dt class="text-muted-foreground">Mode</dt><dd>{{ data.mode_of_payment || "—" }}</dd></div>
				<div v-if="data.reference_no" class="flex justify-between"><dt class="text-muted-foreground">Reference</dt><dd>{{ data.reference_no }}</dd></div>
			</dl>

			<div v-if="data.invoices.length" class="mt-5 border-t border-dashed border-gray-300 pt-4">
				<div class="label-caps mb-2">Applied to</div>
				<div v-for="inv in data.invoices" :key="inv.invoice" class="flex justify-between text-sm">
					<span>{{ inv.invoice }}</span>
					<span class="tabular-nums">
						{{ fmtMoney(inv.allocated) }}
						<span class="text-xs text-muted-foreground">
							({{ inv.outstanding > 0 ? fmtMoney(inv.outstanding) + " still due" : "settled" }})
						</span>
					</span>
				</div>
			</div>

			<p class="mt-8 text-center text-[11px] text-muted-foreground">
				Thank you for your business. Keep this receipt for your records.
			</p>
		</div>
	</div>
</template>

<style>
@media print {
	header, nav, aside, .print\:hidden { display: none !important; }
	main { overflow: visible !important; padding: 0 !important; }
	body { background: white !important; }
}
</style>
