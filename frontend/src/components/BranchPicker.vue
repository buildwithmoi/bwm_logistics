<script setup lang="ts">
import { ref } from "vue";
import { onClickOutside } from "@vueuse/core";
import { Building2, Check, ChevronDown, Plus } from "lucide-vue-next";
import { useBranchStore } from "@/stores/branch";
import { useSessionStore } from "@/stores/session";
import { useToast } from "@/composables/useToast";

// Top-bar branch filter. Hidden entirely until the first branch exists, so
// single-location operators never see it.
const branch = useBranchStore();
const session = useSessionStore();
const toast = useToast();

const open = ref(false);
const rootRef = ref<HTMLElement | null>(null);
onClickOutside(rootRef, () => (open.value = false));

const canManage = session.hasRole("Logistics Manager", "System Manager", "Administrator");

async function addBranch() {
	const name = prompt("New branch name");
	if (!name) return;
	try {
		const created = await branch.addBranch(name);
		branch.setActive(created);
		toast.success(`Branch ${created} added`);
		open.value = false;
	} catch (e: unknown) {
		toast.error((e as { message?: string })?.message || "Could not add branch");
	}
}

function pick(name: string) {
	branch.setActive(name);
	open.value = false;
	// List pages re-query on branch change via watching the store; a reload
	// keeps it dead simple and correct everywhere.
	window.location.reload();
}
</script>

<template>
	<div v-if="branch.hasBranches || canManage" ref="rootRef" class="relative hidden md:block">
		<button
			type="button"
			class="flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-colors"
			:class="open ? 'bg-white/[0.14] text-white' : 'text-white/75 hover:bg-white/[0.08] hover:text-white'"
			@click="open = !open"
		>
			<Building2 class="h-4 w-4" />
			<span class="hidden max-w-28 truncate lg:inline">{{ branch.active || "All branches" }}</span>
			<ChevronDown class="h-3 w-3 text-white/50" />
		</button>

		<transition
			enter-active-class="transition duration-100 ease-out"
			enter-from-class="opacity-0 -translate-y-1"
			enter-to-class="opacity-100 translate-y-0"
			leave-active-class="transition duration-75 ease-in"
			leave-from-class="opacity-100"
			leave-to-class="opacity-0"
		>
			<div
				v-if="open"
				class="absolute right-0 top-full z-50 mt-1.5 w-56 overflow-hidden rounded-xl border border-black/5 bg-white p-1.5 text-gray-900 shadow-pop"
			>
				<button
					type="button"
					class="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition-colors hover:bg-gray-100"
					@click="pick('')"
				>
					<Check class="h-4 w-4" :class="!branch.active ? 'text-brand-600' : 'text-transparent'" />
					All branches
				</button>
				<button
					v-for="b in branch.branches"
					:key="b"
					type="button"
					class="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition-colors hover:bg-gray-100"
					@click="pick(b)"
				>
					<Check class="h-4 w-4" :class="branch.active === b ? 'text-brand-600' : 'text-transparent'" />
					<span class="truncate">{{ b }}</span>
				</button>
				<button
					v-if="canManage"
					type="button"
					class="mt-1 flex w-full items-center gap-2.5 rounded-lg border-t border-gray-100 px-3 py-2 pt-2.5 text-left text-sm font-medium text-brand-700 transition-colors hover:bg-brand-50"
					@click="addBranch"
				>
					<Plus class="h-4 w-4" /> Add branch
				</button>
			</div>
		</transition>
	</div>
</template>
