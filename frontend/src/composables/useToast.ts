import { reactive } from "vue";

// Minimal toast queue — no deps. <ToastViewport /> in App.vue renders the
// stack; components push messages with `useToast().show(...)`. Auto-dismiss
// after 3s unless `sticky: true`.

export type ToastTone = "success" | "error" | "info" | "warning";

export interface Toast {
	id: number;
	message: string;
	tone: ToastTone;
	sticky?: boolean;
}

const state = reactive<{ items: Toast[] }>({ items: [] });
let nextId = 1;

export function useToast() {
	function show(message: string, tone: ToastTone = "info", opts?: { sticky?: boolean }) {
		const t: Toast = { id: nextId++, message, tone, sticky: opts?.sticky };
		state.items.push(t);
		if (!t.sticky) {
			setTimeout(() => dismiss(t.id), 3000);
		}
	}
	function dismiss(id: number) {
		const i = state.items.findIndex((t) => t.id === id);
		if (i >= 0) state.items.splice(i, 1);
	}
	return {
		items: state.items,
		show,
		success: (m: string) => show(m, "success"),
		error: (m: string) => show(m, "error"),
		info: (m: string) => show(m, "info"),
		warning: (m: string) => show(m, "warning"),
		dismiss,
	};
}
