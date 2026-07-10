import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { call } from "@/lib/frappe";

// Mirrors the bootinfo shape Frappe injects into the page. We only read the
// bits we care about; everything else is left untyped to avoid drift.
export interface BootUser {
	name: string;
	email: string;
	full_name?: string;
	first_name?: string;
	roles: string[];
	user_image?: string;
}

interface BootInfo {
	user?: BootUser;
	sysdefaults?: Record<string, unknown>;
}

declare global {
	interface Window {
		frappe?: { boot?: BootInfo };
	}
}

const STAFF_ROLES = [
	"Logistics Driver",
	"Logistics Accounts",
	"Logistics Operations",
	"Logistics Manager",
	"System Manager",
	"Administrator",
];

export const useSessionStore = defineStore("session", () => {
	const boot = window.frappe?.boot;
	const user = ref<BootUser | null>(boot?.user && boot.user.name !== "Guest" ? boot.user : null);
	// `false` until bootstrap() resolves the first time. App.vue uses this to
	// render a thin loading state instead of flashing the Login page for a
	// fraction of a second when a logged-in dev session needs an API round-trip.
	const ready = ref(!!boot?.user);

	const isLoggedIn = computed(() => !!user.value && user.value.name !== "Guest");
	const roles = computed<Set<string>>(() => new Set(user.value?.roles ?? []));
	// Staff → operator route tree; customer-only → portal route tree.
	const isStaff = computed(() => STAFF_ROLES.some((r) => roles.value.has(r)));
	const isCustomer = computed(() => roles.value.has("Logistics Customer"));

	function hasRole(...names: string[]): boolean {
		return names.some((n) => roles.value.has(n));
	}

	/** Detect the current session without a page reload.
	 *
	 * In production (loaded via /logistics on the Frappe site), bootinfo is
	 * already injected and this is a no-op.
	 *
	 * In dev (loaded via Vite at :8080), there's no server-rendered bootinfo —
	 * we ask Frappe who we are. `frappe.auth.get_logged_user` is
	 * allow_guest=True so the call works either way; if the response is
	 * "Guest" we leave `user` null and the SPA renders the Login page.
	 */
	async function bootstrap() {
		if (ready.value) return;
		try {
			const who = await call<string>("frappe.auth.get_logged_user");
			if (!who || who === "Guest") {
				user.value = null;
				return;
			}
			const profile = await call<{
				name: string;
				email: string;
				full_name: string;
				first_name: string;
				roles: { role: string }[];
				user_image: string | null;
			}>("frappe.client.get", {
				doctype: "User",
				name: who,
			});
			user.value = {
				name: profile.name,
				email: profile.email,
				full_name: profile.full_name,
				first_name: profile.first_name,
				roles: (profile.roles || []).map((r) => r.role).filter(Boolean),
				user_image: profile.user_image || undefined,
			};
		} catch {
			// Network or auth error — treat as logged out.
			user.value = null;
		} finally {
			ready.value = true;
		}
	}

	// ── Page-level access ─────────────────────────────────────────────────────
	// null until loaded — treated as "allow" so nav doesn't flicker-hide on
	// first paint. Once loaded it's the allow-list of page keys.
	const allowedPages = ref<Set<string> | null>(null);
	// Per-page permissions: { page: { scope, create, read, edit, delete } }.
	interface PagePerm {
		scope: string;
		create: number;
		read: number;
		edit: number;
		delete: number;
	}
	const permissions = ref<Record<string, PagePerm> | null>(null);
	// Dedupe concurrent loads (the route guard + AppShell both trigger it) so
	// the guard can reliably await a single in-flight request.
	let accessInFlight: Promise<void> | null = null;
	async function loadAccess() {
		if (accessInFlight) return accessInFlight;
		accessInFlight = (async () => {
			try {
				const perms = await call<Record<string, PagePerm>>(
					"bwm_logistics.api.access.my_permissions",
				);
				permissions.value = perms;
				allowedPages.value = new Set(Object.keys(perms));
			} catch {
				allowedPages.value = null;
				permissions.value = null;
				accessInFlight = null; // allow a retry once logged in
			}
		})();
		return accessInFlight;
	}
	function canSee(key: string): boolean {
		if (!allowedPages.value) return true;
		return allowedPages.value.has(key);
	}
	// Can the user do `action` on `page`? Defaults to true until perms load (UX
	// only — the backend enforces the real check).
	function can(page: string, action: "create" | "read" | "edit" | "delete"): boolean {
		if (!permissions.value) return true;
		const p = permissions.value[page];
		if (!p) return false;
		if (action === "read") return true;
		return !!p[action];
	}

	return {
		user, ready, isLoggedIn, roles, isStaff, isCustomer, hasRole, bootstrap,
		allowedPages, permissions, loadAccess, canSee, can,
	};
});
