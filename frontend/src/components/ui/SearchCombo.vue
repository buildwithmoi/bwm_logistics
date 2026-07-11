<script setup lang="ts" generic="T extends Record<string, unknown>">
import { ref, watch, computed } from "vue";
import { Search, ChevronDown, Check, Plus } from "lucide-vue-next";

// Async-search combobox (ex_beauty pattern) — the house link-field. Parent
// supplies a `fetcher` that takes a query string and returns an array of
// items; this widget handles debouncing, the dropdown, keyboard navigation,
// and selection.
//
// `valueKey` + `labelKey` tell us how to read the id and the display string
// off each item; `sublabelKey` renders secondary info under each option.

interface Props<R> {
	modelValue: string | null;
	displayValue?: string | null;
	placeholder?: string;
	fetcher: (q: string) => Promise<R[]>;
	valueKey: keyof R & string;
	labelKey: keyof R & string;
	sublabelKey?: keyof R & string;
	disabled?: boolean;
	id?: string;
	createLabel?: string;
}

const props = defineProps<Props<T>>();
const emit = defineEmits<{
	(e: "update:modelValue", v: string | null): void;
	(e: "update:displayValue", v: string | null): void;
	(e: "select", item: T): void;
	(e: "create", q: string): void;
}>();

function emitCreate() {
	emit("create", query.value.trim());
	open.value = false;
	query.value = "";
}

const query = ref("");
const items = ref<T[]>([]);
const open = ref(false);
const loading = ref(false);
const highlight = ref(0);
const inputRef = ref<HTMLInputElement | null>(null);

const selectedLabel = computed(() => props.displayValue || props.modelValue || "");

watch(open, async (isOpen) => {
	if (isOpen) await runFetch();
});

let timer: number | undefined;
watch(query, () => {
	if (timer) window.clearTimeout(timer);
	timer = window.setTimeout(runFetch, 200);
});

async function runFetch() {
	loading.value = true;
	try {
		items.value = await props.fetcher(query.value);
		highlight.value = 0;
	} finally {
		loading.value = false;
	}
}

function select(item: T) {
	emit("update:modelValue", String(item[props.valueKey]));
	emit("update:displayValue", String(item[props.labelKey]));
	emit("select", item);
	open.value = false;
	query.value = "";
}

function clear() {
	emit("update:modelValue", null);
	emit("update:displayValue", null);
	query.value = "";
	open.value = true;
	inputRef.value?.focus();
}

function onKey(e: KeyboardEvent) {
	if (!open.value) return;
	if (e.key === "ArrowDown") {
		highlight.value = Math.min(items.value.length - 1, highlight.value + 1);
		e.preventDefault();
	} else if (e.key === "ArrowUp") {
		highlight.value = Math.max(0, highlight.value - 1);
		e.preventDefault();
	} else if (e.key === "Enter") {
		const item = items.value[highlight.value];
		if (item) {
			select(item as T);
			e.preventDefault();
		}
	} else if (e.key === "Escape") {
		open.value = false;
	}
}

function openMenu() {
	if (props.disabled) return;
	open.value = true;
	setTimeout(() => inputRef.value?.focus(), 50);
}

function onBlur() {
	// Delay so a click on a result registers before the dropdown closes.
	setTimeout(() => (open.value = false), 150);
}
</script>

<template>
	<div class="relative">
		<button
			:id="id"
			type="button"
			class="flex h-9 w-full items-center gap-2 rounded-lg border border-input bg-white px-3 text-left text-sm shadow-xs transition-colors hover:border-gray-300 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100"
			:disabled="disabled"
			@click="openMenu"
		>
			<span v-if="modelValue" class="flex-1 truncate text-gray-900">{{ selectedLabel }}</span>
			<span v-else class="flex-1 truncate text-gray-400">{{ placeholder || "Select…" }}</span>
			<button
				v-if="modelValue"
				type="button"
				class="text-xs text-gray-400 hover:text-gray-700"
				@click.stop="clear"
			>
				clear
			</button>
			<ChevronDown class="h-3.5 w-3.5 text-gray-400" />
		</button>

		<Transition
			enter-active-class="transition duration-150 ease-out"
			enter-from-class="opacity-0 -translate-y-1"
			enter-to-class="opacity-100 translate-y-0"
			leave-active-class="transition duration-100 ease-in"
			leave-from-class="opacity-100 translate-y-0"
			leave-to-class="opacity-0 -translate-y-1"
		>
			<div
				v-if="open"
				class="absolute left-0 right-0 z-50 mt-1.5 overflow-hidden rounded-xl border border-border bg-white shadow-pop"
			>
				<div class="relative border-b border-gray-100">
					<Search class="absolute left-3 top-2.5 h-4 w-4 text-gray-400" />
					<input
						ref="inputRef"
						v-model="query"
						type="text"
						:placeholder="placeholder || 'Search…'"
						class="h-9 w-full bg-transparent pl-9 pr-3 text-sm outline-none"
						@keydown="onKey"
						@blur="onBlur"
					/>
				</div>
				<div class="max-h-72 overflow-y-auto">
					<div v-if="loading" class="px-3 py-2 text-xs text-gray-400">
						Loading…
					</div>
					<div v-else-if="!items.length && !createLabel" class="px-3 py-4 text-center text-xs text-gray-400">
						Nothing here.
					</div>
					<button
						v-for="(item, i) in items"
						:key="String(item[valueKey])"
						type="button"
						class="flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors"
						:class="i === highlight ? 'bg-brand-50' : 'hover:bg-gray-50'"
						@mousedown.prevent="select(item as T)"
						@mouseenter="highlight = i"
					>
						<div class="min-w-0 flex-1">
							<div class="truncate text-sm font-medium text-gray-900">
								{{ item[labelKey] }}
							</div>
							<div
								v-if="sublabelKey && item[sublabelKey]"
								class="truncate text-xs text-gray-500"
							>
								{{ item[sublabelKey] }}
							</div>
						</div>
						<Check
							v-if="String(item[valueKey]) === modelValue"
							class="h-3.5 w-3.5 text-brand-600"
						/>
					</button>

					<!-- Create-new footer action — always the last item -->
					<button
						v-if="createLabel"
						type="button"
						class="flex w-full items-center gap-2 border-t border-gray-100 px-3 py-2.5 text-left text-sm font-medium text-brand-700 transition-colors hover:bg-brand-50"
						@mousedown.prevent="emitCreate"
					>
						<Plus class="h-4 w-4" />
						<span class="truncate">{{ createLabel }}<span v-if="query.trim()" class="font-normal text-brand-600"> “{{ query.trim() }}”</span></span>
					</button>
				</div>
			</div>
		</Transition>
	</div>
</template>
