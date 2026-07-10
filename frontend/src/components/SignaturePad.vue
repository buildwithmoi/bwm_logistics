<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

// Minimal canvas signature pad — pointer events (works for touch + mouse),
// no dependencies. Parent calls toBlob() to upload the drawn signature.
const canvasRef = ref<HTMLCanvasElement | null>(null);
const empty = ref(true);
let ctx: CanvasRenderingContext2D | null = null;
let drawing = false;

function resize() {
	const canvas = canvasRef.value;
	if (!canvas) return;
	// Preserve drawing on resize is overkill for a signature — just clear.
	const ratio = window.devicePixelRatio || 1;
	const rect = canvas.getBoundingClientRect();
	canvas.width = rect.width * ratio;
	canvas.height = rect.height * ratio;
	ctx = canvas.getContext("2d");
	if (ctx) {
		ctx.scale(ratio, ratio);
		ctx.lineWidth = 2.2;
		ctx.lineCap = "round";
		ctx.lineJoin = "round";
		ctx.strokeStyle = "#17150f";
	}
	empty.value = true;
}

function pos(e: PointerEvent) {
	const rect = canvasRef.value!.getBoundingClientRect();
	return { x: e.clientX - rect.left, y: e.clientY - rect.top };
}
function down(e: PointerEvent) {
	if (!ctx) return;
	drawing = true;
	canvasRef.value?.setPointerCapture(e.pointerId);
	const p = pos(e);
	ctx.beginPath();
	ctx.moveTo(p.x, p.y);
}
function move(e: PointerEvent) {
	if (!drawing || !ctx) return;
	const p = pos(e);
	ctx.lineTo(p.x, p.y);
	ctx.stroke();
	empty.value = false;
}
function up() {
	drawing = false;
}

function clear() {
	const canvas = canvasRef.value;
	if (canvas && ctx) {
		ctx.clearRect(0, 0, canvas.width, canvas.height);
		empty.value = true;
	}
}

function isEmpty(): boolean {
	return empty.value;
}

function toBlob(): Promise<Blob | null> {
	return new Promise((resolve) => {
		const canvas = canvasRef.value;
		if (!canvas || empty.value) return resolve(null);
		canvas.toBlob((b) => resolve(b), "image/png");
	});
}

defineExpose({ clear, toBlob, isEmpty });

onMounted(() => {
	resize();
	window.addEventListener("resize", resize);
});
onBeforeUnmount(() => window.removeEventListener("resize", resize));
</script>

<template>
	<div>
		<div class="relative overflow-hidden rounded-xl border border-dashed border-gray-300 bg-white">
			<canvas
				ref="canvasRef"
				class="block h-36 w-full touch-none"
				@pointerdown="down"
				@pointermove="move"
				@pointerup="up"
				@pointerleave="up"
			></canvas>
			<span
				v-if="empty"
				class="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-gray-300"
			>
				Sign here
			</span>
		</div>
		<button
			type="button"
			class="mt-1.5 text-xs font-medium text-muted-foreground hover:text-gray-700"
			@click="clear"
		>
			Clear signature
		</button>
	</div>
</template>
