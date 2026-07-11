<script setup lang="ts">
import { fmtDate, fmtMoney } from "@/lib/format";

// Shared branded statement body — used by the operator page and the portal
// page; @media print strips the app chrome.
export interface StatementData {
	customer_name?: string;
	business_name: string;
	from_date: string;
	to_date: string;
	opening_balance: number;
	rows: Array<{ date: string; ref: string; type: string; debit: number; credit: number; balance: number }>;
	total_invoiced: number;
	total_paid: number;
	closing_balance: number;
}
defineProps<{ data: StatementData }>();
</script>

<template>
	<div class="bwm-statement rounded-3xl bg-white p-8 ring-1 ring-gray-100 print:rounded-none print:p-0 print:ring-0">
		<!-- Letterhead -->
		<div class="mb-6 flex items-start justify-between border-b-2 border-gray-900 pb-4">
			<div>
				<div class="text-lg font-extrabold tracking-tight">{{ data.business_name }}</div>
				<div class="label-caps mt-1">Statement of Account</div>
			</div>
			<div class="text-right text-sm">
				<div class="font-semibold">{{ data.customer_name }}</div>
				<div class="text-muted-foreground tabular-nums">
					{{ fmtDate(data.from_date) }} — {{ fmtDate(data.to_date) }}
				</div>
			</div>
		</div>

		<!-- Rows -->
		<table class="w-full text-sm">
			<thead>
				<tr class="text-left">
					<th class="label-caps pb-2">Date</th>
					<th class="label-caps pb-2">Reference</th>
					<th class="label-caps pb-2">Type</th>
					<th class="label-caps pb-2 text-right">Charges</th>
					<th class="label-caps pb-2 text-right">Payments</th>
					<th class="label-caps pb-2 text-right">Balance</th>
				</tr>
			</thead>
			<tbody>
				<tr class="border-t border-gray-100">
					<td class="py-2 text-muted-foreground" colspan="5">Opening balance</td>
					<td class="py-2 text-right font-medium tabular-nums">{{ fmtMoney(data.opening_balance) }}</td>
				</tr>
				<tr v-for="r in data.rows" :key="r.ref" class="border-t border-gray-100">
					<td class="py-2 tabular-nums">{{ fmtDate(r.date) }}</td>
					<td class="py-2">{{ r.ref }}</td>
					<td class="py-2">{{ r.type }}</td>
					<td class="py-2 text-right tabular-nums">{{ r.debit ? fmtMoney(r.debit) : "—" }}</td>
					<td class="py-2 text-right tabular-nums">{{ r.credit ? fmtMoney(r.credit) : "—" }}</td>
					<td class="py-2 text-right tabular-nums">{{ fmtMoney(r.balance) }}</td>
				</tr>
			</tbody>
			<tfoot>
				<tr class="border-t-2 border-gray-900 font-semibold">
					<td class="py-2.5" colspan="3">Totals for period</td>
					<td class="py-2.5 text-right tabular-nums">{{ fmtMoney(data.total_invoiced) }}</td>
					<td class="py-2.5 text-right tabular-nums">{{ fmtMoney(data.total_paid) }}</td>
					<td class="py-2.5 text-right tabular-nums">{{ fmtMoney(data.closing_balance) }}</td>
				</tr>
			</tfoot>
		</table>

		<p class="mt-6 text-xs text-muted-foreground">
			Balance due: <b class="text-gray-900 tabular-nums">{{ fmtMoney(data.closing_balance) }}</b>
			<span v-if="data.closing_balance <= 0"> — account fully settled, thank you.</span>
		</p>
	</div>
</template>

<style>
@media print {
	header, nav, aside, .print\:hidden { display: none !important; }
	main { overflow: visible !important; padding: 0 !important; }
	body { background: white !important; }
}
</style>
