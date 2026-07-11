import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { call } from "@/lib/frappe";

// Multi-branch filter (P5). The active branch is an organizational lens the
// staff user picks in the top bar — list pages pass it to their APIs and new
// documents are stamped with it. It is NOT a security boundary (server-side
// role checks stay the gate); strict per-branch permissions can layer on later.

const STORAGE_KEY = "bwm-active-branch";

export const useBranchStore = defineStore("branch", () => {
	const branches = ref<string[]>([]);
	const loaded = ref(false);
	const active = ref<string>(localStorage.getItem(STORAGE_KEY) || "");

	const hasBranches = computed(() => branches.value.length > 0);
	// "" means All branches.
	const filter = computed(() => active.value || null);

	async function load() {
		try {
			branches.value = await call<string[]>("bwm_logistics.api.settings.list_branches");
			// Drop a stale selection if the branch was deleted.
			if (active.value && !branches.value.includes(active.value)) setActive("");
		} catch {
			branches.value = [];
		} finally {
			loaded.value = true;
		}
	}

	function setActive(name: string) {
		active.value = name;
		if (name) localStorage.setItem(STORAGE_KEY, name);
		else localStorage.removeItem(STORAGE_KEY);
	}

	async function addBranch(name: string) {
		const res = await call<{ name: string }>("bwm_logistics.api.settings.add_branch", { name });
		if (!branches.value.includes(res.name)) branches.value.push(res.name);
		return res.name;
	}

	return { branches, loaded, active, hasBranches, filter, load, setActive, addBranch };
});
