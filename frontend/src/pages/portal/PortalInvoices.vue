<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ReceiptText, ExternalLink } from "lucide-vue-next";
import { call } from "@/lib/frappe";
import { fmtDate, fmtMoney } from "@/lib/format";
import { useToast } from "@/composables/useToast";
import Button from "@/components/ui/Button.vue";
import StatusBadge from "@/components/StatusBadge.vue";

const toast = useToast();

interface Invoice {
	name: string;
	posting_date: string;
	status: string;
	grand_total: number;
	outstanding_amount: number;
	currency: string;
}
const invoices = ref<Invoice[]>([]);
const loading = ref(true);
const paying = ref<string | null>(null);

onMounted(async () => {
	try {
		invoices.value = await call<Invoice[]>("bwm_logistics.api.portal.my_invoices");
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not load invoices");
	} finally {
		loading.value = false;
	}
});

async function payNow(inv: Invoice) {
	paying.value = inv.name;
	try {
		const res = await call<{ payment_url: string }>("bwm_logistics.api.portal.payment_link", {
			invoice: inv.name,
		});
		window.location.href = res.payment_url;
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Online payment unavailable right now");
	} finally {
		paying.value = null;
	}
}

function pdfUrl(name: string): string {
	// Branded server PDF (BWM Invoice print format).
	return `/api/method/frappe.utils.print_format.download_pdf?doctype=Sales%20Invoice&name=${encodeURIComponent(name)}&format=BWM%20Invoice&no_letterhead=1`;
}
</script>

<template>
	<div class="mx-auto max-w-4xl">
		<header class="mb-5 flex flex-wrap items-end gap-3">
			<div class="min-w-0 flex-1">
				<h1 class="text-2xl font-semibold tracking-tight">Invoices & Payments</h1>
				<p class="mt-1 text-sm text-muted-foreground">Pay online and your goods release faster.</p>
			</div>
			<RouterLink
				to="/portal/statement"
				class="text-sm font-medium text-brand-700 hover:underline"
			>
				View statement →
			</RouterLink>
		</header>

		<div v-if="loading" class="py-16 text-center text-sm text-muted-foreground">Loading…</div>
		<div
			v-else-if="!invoices.length"
			class="flex flex-col items-center rounded-3xl bg-white p-14 text-center ring-1 ring-gray-100"
		>
			<span class="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-brand-600/10 text-brand-700">
				<ReceiptText class="h-6 w-6" />
			</span>
			<p class="text-sm text-muted-foreground">No invoices yet.</p>
		</div>

		<div v-else class="space-y-3">
			<div
				v-for="inv in invoices"
				:key="inv.name"
				class="flex flex-wrap items-center gap-4 rounded-2xl bg-white p-5 ring-1 ring-gray-100"
			>
				<div class="min-w-0 flex-1">
					<div class="flex flex-wrap items-center gap-2">
						<span class="font-semibold">{{ inv.name }}</span>
						<StatusBadge :status="inv.status" />
					</div>
					<div class="mt-0.5 text-xs text-muted-foreground">{{ fmtDate(inv.posting_date) }}</div>
				</div>
				<div class="text-right">
					<div class="font-semibold tabular-nums">{{ fmtMoney(inv.grand_total, inv.currency) }}</div>
					<div v-if="inv.outstanding_amount > 0" class="text-xs tabular-nums text-amber-700">
						{{ fmtMoney(inv.outstanding_amount, inv.currency) }} due
					</div>
				</div>
				<div class="flex items-center gap-2">
					<a
						:href="pdfUrl(inv.name)"
						target="_blank"
						rel="noopener"
						class="flex h-9 w-9 items-center justify-center rounded-lg text-gray-400 transition-colors hover:bg-gray-100 hover:text-gray-700"
						title="Download PDF"
					>
						<ExternalLink class="h-4 w-4" />
					</a>
					<Button
						v-if="inv.outstanding_amount > 0"
						size="sm"
						:loading="paying === inv.name"
						@click="payNow(inv)"
					>
						Pay now
					</Button>
				</div>
			</div>
		</div>
	</div>
</template>
