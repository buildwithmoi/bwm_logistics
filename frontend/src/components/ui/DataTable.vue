<script setup lang="ts">
import { computed } from "vue";

// Lean list primitive in the house style.
//
// Two renderings of the same rows and the same `#cell-<key>` slots:
//   ≥ md  — a table: label-caps header row, hoverable rows
//   < md  — one stacked card per row, so a phone never scrolls sideways
//
// Columns say how they behave on the small layout:
//   primary      the card's headline (defaults to the first column)
//   trailing     pinned top-right of the card — status, amount, an action
//   mobileHidden dropped from the card entirely (noise on a phone)
// Everything else becomes a "Label   value" line.
export interface Column {
	key: string;
	label: string;
	class?: string;
	numeric?: boolean;
	primary?: boolean;
	trailing?: boolean;
	mobileHidden?: boolean;
	/** Keep the cell on one line in the table view (dates, ids, amounts). */
	nowrap?: boolean;
}

const props = defineProps<{
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

const primaryCol = computed(() => props.columns.find((c) => c.primary) || props.columns[0]);
const trailingCols = computed(() => props.columns.filter((c) => c.trailing && !c.mobileHidden));
const detailCols = computed(() =>
	props.columns.filter((c) => c !== primaryCol.value && !c.trailing && !c.mobileHidden && c.label),
);
const rowId = (row: Record<string, unknown>) => String(row[props.rowKey || "name"]);
</script>

<template>
	<div class="overflow-hidden rounded-xl border border-border bg-white shadow-card">
		<!-- ── Table (tablet and up) ───────────────────────────────────────── -->
		<div class="hidden overflow-x-auto md:block">
			<table class="w-full border-collapse text-sm">
				<thead>
					<tr class="bg-gray-50/60">
						<th
							v-for="c in columns"
							:key="c.key"
							scope="col"
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
						:key="rowId(row)"
						class="border-b border-border/60 transition-colors last:border-0 hover:bg-gray-50/80"
						:class="clickable && 'cursor-pointer'"
						@click="clickable && emit('row-click', row)"
					>
						<td
							v-for="c in columns"
							:key="c.key"
							class="px-4 py-3 align-middle"
							:class="[c.class, c.numeric && 'whitespace-nowrap text-right tabular-nums', c.nowrap && 'whitespace-nowrap']"
						>
							<slot :name="`cell-${c.key}`" :row="row" :value="row[c.key]">
								{{ row[c.key] ?? "—" }}
							</slot>
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<!-- ── Cards (phone) ───────────────────────────────────────────────── -->
		<div class="md:hidden">
			<div v-if="loading && !rows.length" class="px-4 py-10 text-center text-sm text-muted-foreground">
				Loading…
			</div>
			<div v-else-if="!rows.length" class="px-4 py-10 text-center text-sm text-muted-foreground">
				{{ emptyText || "Nothing here yet." }}
			</div>
			<component
				:is="clickable ? 'button' : 'div'"
				v-for="row in rows"
				v-else
				:key="rowId(row)"
				:type="clickable ? 'button' : undefined"
				class="block w-full border-b border-border/60 px-4 py-3.5 text-left last:border-0"
				:class="clickable && 'touch-manipulation transition-colors active:bg-gray-50'"
				@click="clickable && emit('row-click', row)"
			>
				<div class="flex items-start justify-between gap-3">
					<div class="min-w-0 flex-1 text-sm font-medium">
						<slot :name="`cell-${primaryCol.key}`" :row="row" :value="row[primaryCol.key]">
							{{ row[primaryCol.key] ?? "—" }}
						</slot>
					</div>
					<div v-if="trailingCols.length" class="flex shrink-0 flex-col items-end gap-1 text-sm">
						<div v-for="c in trailingCols" :key="c.key" :class="c.numeric && 'tabular-nums'">
							<slot :name="`cell-${c.key}`" :row="row" :value="row[c.key]">
								{{ row[c.key] ?? "—" }}
							</slot>
						</div>
					</div>
				</div>

				<dl v-if="detailCols.length" class="mt-2 space-y-1">
					<div v-for="c in detailCols" :key="c.key" class="flex items-baseline gap-3 text-[13px]">
						<dt class="w-24 shrink-0 truncate text-muted-foreground">{{ c.label }}</dt>
						<dd class="min-w-0 flex-1 truncate" :class="c.numeric && 'tabular-nums'">
							<slot :name="`cell-${c.key}`" :row="row" :value="row[c.key]">
								{{ row[c.key] ?? "—" }}
							</slot>
						</dd>
					</div>
				</dl>
			</component>
		</div>

		<div
			v-if="total !== undefined && rows.length < total"
			class="border-t border-border bg-gray-50/40 px-4 py-2.5 text-center"
		>
			<button
				type="button"
				class="touch-manipulation text-[13px] font-medium text-brand-700 hover:text-brand-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 disabled:opacity-50"
				:disabled="loading"
				@click="emit('load-more')"
			>
				{{ loading ? "Loading…" : `Load more (${rows.length} of ${total})` }}
			</button>
		</div>
	</div>
</template>
