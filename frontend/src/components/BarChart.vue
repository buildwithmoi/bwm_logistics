<script setup lang="ts">
import { computed } from "vue";

// Minimal grouped-bar SVG chart (no deps): two series per category with a
// faint baseline grid, value labels on hover via <title>, gold + slate marks.
export interface BarGroup {
	label: string;
	a: number;
	b: number;
}
const props = withDefaults(
	defineProps<{
		groups: BarGroup[];
		seriesA?: string;
		seriesB?: string;
		height?: number;
	}>(),
	{ seriesA: "Invoiced", seriesB: "Collected", height: 200 },
);

const PAD = { top: 12, right: 8, bottom: 24, left: 8 };
const width = 640;

const maxValue = computed(() => Math.max(1, ...props.groups.flatMap((g) => [g.a, g.b])));
const innerW = computed(() => width - PAD.left - PAD.right);
const innerH = computed(() => props.height - PAD.top - PAD.bottom);
const slot = computed(() => innerW.value / Math.max(props.groups.length, 1));
const barW = computed(() => Math.min(26, slot.value / 3));

function y(v: number): number {
	return PAD.top + innerH.value * (1 - v / maxValue.value);
}
function h(v: number): number {
	return Math.max(v > 0 ? 2 : 0, innerH.value * (v / maxValue.value));
}
function fmt(v: number): string {
	return v.toLocaleString(undefined, { maximumFractionDigits: 0 });
}
</script>

<template>
	<div>
		<div class="mb-3 flex gap-4 text-xs text-muted-foreground">
			<span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-sm bg-[#b8860b]"></span> {{ seriesA }}</span>
			<span class="inline-flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-sm bg-slate-400"></span> {{ seriesB }}</span>
		</div>
		<div class="overflow-x-auto">
			<svg :viewBox="`0 0 ${width} ${height}`" class="w-full min-w-[480px]" role="img" aria-label="Monthly totals">
				<!-- baseline grid -->
				<line
					v-for="frac in [0, 0.5, 1]"
					:key="frac"
					:x1="PAD.left"
					:x2="width - PAD.right"
					:y1="PAD.top + innerH * frac"
					:y2="PAD.top + innerH * frac"
					stroke="#e7e1d5"
					stroke-width="1"
					:stroke-dasharray="frac === 1 ? '' : '3 4'"
				/>
				<g v-for="(g, i) in groups" :key="g.label">
					<rect
						:x="PAD.left + slot * i + slot / 2 - barW - 2"
						:y="y(g.a)"
						:width="barW"
						:height="h(g.a)"
						rx="3"
						fill="#b8860b"
					>
						<title>{{ g.label }} — {{ seriesA }}: {{ fmt(g.a) }}</title>
					</rect>
					<rect
						:x="PAD.left + slot * i + slot / 2 + 2"
						:y="y(g.b)"
						:width="barW"
						:height="h(g.b)"
						rx="3"
						fill="#94a3b8"
					>
						<title>{{ g.label }} — {{ seriesB }}: {{ fmt(g.b) }}</title>
					</rect>
					<text
						:x="PAD.left + slot * i + slot / 2"
						:y="height - 6"
						text-anchor="middle"
						class="fill-gray-500"
						font-size="11"
					>
						{{ g.label }}
					</text>
				</g>
			</svg>
		</div>
	</div>
</template>
