<script setup lang="ts">
// Lean list table in the house style: label-caps header row, hoverable rows,
// server-driven "Load more" footer. Cell rendering can be overridden per
// column with a #cell-<key> slot. (Selection/sort arrive when a page needs
// them — keep the primitive small.)
export interface Column {
	key: string;
	label: string;
	class?: string;
	numeric?: boolean;
}

defineProps<{
	columns: Column[];
	rows: Record<string, unknown>[];
	loading?: boolean;
	emptyText?: string;
	total?: number;
	rowKey?: string;
	clickable?: boolean;
}>();
const emit = defineEmits<{
	(e: "row-click", row: Record<string, unknown>): void;
	(e: "load-more"): void;
}>();
</script>

<template>
	<div class="overflow-hidden rounded-xl border border-border bg-white shadow-card">
		<div class="overflow-x-auto">
			<table class="w-full min-w-[640px] border-collapse text-sm">
				<thead>
					<tr class="bg-gray-50/60">
						<th
							v-for="c in columns"
							:key="c.key"
							class="label-caps border-b border-border px-4 py-3 text-left"
							:class="[c.class, c.numeric && 'text-right']"
						>
							{{ c.label }}
						</th>
					</tr>
				</thead>
				<tbody>
					<tr v-if="loading && !rows.length">
						<td :colspan="columns.length" class="px-4 py-10 text-center text-sm text-muted-foreground">
							Loading…
						</td>
					</tr>
					<tr v-else-if="!rows.length">
						<td :colspan="columns.length" class="px-4 py-10 text-center text-sm text-muted-foreground">
							{{ emptyText || "Nothing here yet." }}
						</td>
					</tr>
					<tr
						v-for="row in rows"
						:key="String(row[rowKey || 'name'])"
						class="border-b border-border/60 transition-colors last:border-0 hover:bg-gray-50/80"
						:class="clickable && 'cursor-pointer'"
						@click="clickable && emit('row-click', row)"
					>
						<td
							v-for="c in columns"
							:key="c.key"
							class="px-4 py-3 align-middle"
							:class="[c.class, c.numeric && 'text-right tabular-nums']"
						>
							<slot :name="`cell-${c.key}`" :row="row" :value="row[c.key]">
								{{ row[c.key] ?? "—" }}
							</slot>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div
			v-if="total !== undefined && rows.length < total"
			class="border-t border-border bg-gray-50/40 px-4 py-2.5 text-center"
		>
			<button
				type="button"
				class="text-[13px] font-medium text-brand-700 hover:text-brand-800 disabled:opacity-50"
				:disabled="loading"
				@click="emit('load-more')"
			>
				{{ loading ? "Loading…" : `Load more (${rows.length} of ${total})` }}
			</button>
		</div>
	</div>
</template>
