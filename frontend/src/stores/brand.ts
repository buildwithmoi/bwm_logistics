import { defineStore } from "pinia";
import { ref } from "vue";
import { call } from "@/lib/frappe";

// Who this installation says it is. Fetched once and shared, because the name
// and mark appear on the login screen, the shell, the printed label and the
// report header — and every one of those used to spell it out in the source,
// so a client site called itself by our name.
//
// get_branding is guest-allowed: the login screen has to be branded before
// anyone has signed in.
export const useBrandStore = defineStore("brand", () => {
	const name = ref("Logistics");
	const logo = ref<string | null>(null);
	const monogram = ref("L");
	const loaded = ref(false);

	async function load(force = false) {
		if (loaded.value && !force) return;
		try {
			const b = await call<{ business_name: string; logo?: string | null; monogram?: string }>(
				"bwm_logistics.api.settings.get_branding",
			);
			if (b?.business_name) name.value = b.business_name;
			logo.value = b?.logo || null;
			monogram.value = b?.monogram || name.value.trim().charAt(0).toUpperCase() || "?";
			loaded.value = true;
		} catch {
			/* keep the neutral default rather than showing somebody else's name */
		}
	}

	return { name, logo, monogram, loaded, load };
});
