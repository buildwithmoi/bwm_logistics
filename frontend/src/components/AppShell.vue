<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { onClickOutside } from "@vueuse/core";
import {
	LayoutDashboard,
	Container,
	Package,
	Truck,
	Users,
	ReceiptText,
	BellRing,
	Settings,
	LogOut,
	Menu,
	X,
	MapPin,
	UserRound,
	BarChart3,
	Boxes,
	PackageSearch,
} from "lucide-vue-next";
import { useSessionStore } from "@/stores/session";
import BrandLogo from "@/components/BrandLogo.vue";
import PortalBell from "@/components/PortalBell.vue";
import BranchPicker from "@/components/BranchPicker.vue";
import { useBranchStore } from "@/stores/branch";
import { call } from "@/lib/frappe";
import { logout as apiLogout } from "@/lib/auth";

// One shell, two route trees. The layout is deliberately spare:
//   left    — the menu button (every breakpoint); it opens the full nav
//   centre  — the handful of everyday tabs (desktop only)
//   right   — the business logo
// Everything else — the long tail of pages plus Log out — lives in the drawer,
// so there is exactly one place to look for "where else can I go?".

interface NavItem {
	key: string;
	label: string;
	icon: unknown;
	to: string;
}

// Operator tabs shown in the bar. Kept short on purpose — Stock, Reports,
// Notifications and Settings are drawer-only.
const operatorPrimary: NavItem[] = [
	{ key: "dashboard", label: "Dashboard", icon: LayoutDashboard, to: "/" },
	{ key: "containers", label: "Containers", icon: Container, to: "/containers" },
	{ key: "shipments", label: "Shipments", icon: Package, to: "/shipments" },
	{ key: "dispatch", label: "Dispatch", icon: MapPin, to: "/dispatch" },
	{ key: "customers", label: "Customers", icon: Users, to: "/customers" },
	{ key: "billing", label: "Billing", icon: ReceiptText, to: "/billing" },
];

// Customer portal tabs — the whole portal nav.
const portalPrimary: NavItem[] = [
	{ key: "portal", label: "My Portal", icon: LayoutDashboard, to: "/portal" },
	{ key: "portal-shipments", label: "Shipments", icon: Package, to: "/portal/shipments" },
	{ key: "portal-pickups", label: "Pickups", icon: Truck, to: "/portal/pickups" },
	{ key: "portal-invoices", label: "Invoices", icon: ReceiptText, to: "/portal/invoices" },
	{ key: "portal-profile", label: "Profile", icon: UserRound, to: "/portal/profile" },
];

const session = useSessionStore();
const route = useRoute();

// Customers (portal-only users) always see the portal nav; staff see the
// operator nav, switching to portal tabs only while browsing /portal/*.
const portalMode = computed(
	() => route.path.startsWith("/portal") || (!session.isStaff && session.isCustomer),
);
const primary = computed(() =>
	(portalMode.value ? portalPrimary : operatorPrimary).filter((i) => session.canSee(i.key)),
);

const fullName = computed(() => session.user?.full_name || session.user?.first_name || "Account");
const userEmail = computed(() => session.user?.email || "");

const isActive = (to: string) => {
	if (to === "/") return route.path === "/";
	if (to === "/portal") return route.path === "/portal";
	return route.path.startsWith(to);
};

async function logout() {
	// POST + CSRF via the auth helper (the endpoint is POST-only); then leave
	// the app for the public site.
	try {
		await apiLogout();
	} finally {
		window.location.href = "/home";
	}
}

// ── Nav drawer ──────────────────────────────────────────────────────────────
// The single source of "everywhere you can go", at every breakpoint. The bar
// tabs are a shortcut to its first few entries, not a separate menu.
const operatorAll: NavItem[] = [
	...operatorPrimary,
	{ key: "stock", label: "Stock", icon: Boxes, to: "/stock" },
	{ key: "items", label: "Items", icon: PackageSearch, to: "/items" },
	{ key: "reports", label: "Reports", icon: BarChart3, to: "/reports" },
	{ key: "notifications", label: "Notifications", icon: BellRing, to: "/notifications" },
	{ key: "settings", label: "Settings", icon: Settings, to: "/settings" },
];
const navOpen = ref(false);
const drawerRef = ref<HTMLElement | null>(null);
onClickOutside(drawerRef, () => (navOpen.value = false));
const drawerNav = computed(() =>
	(portalMode.value ? portalPrimary : operatorAll).filter((i) => session.canSee(i.key)),
);
// Close the drawer whenever the route changes, and lock the page behind it.
watch(() => route.path, () => (navOpen.value = false));
watch(navOpen, (open) => {
	document.documentElement.style.overflow = open ? "hidden" : "";
});
function onEscape(e: KeyboardEvent) {
	if (e.key === "Escape") navOpen.value = false;
}

// Bottom tab bar (mobile / PWA): the same everyday tabs, capped at four. No
// overflow "More" — the menu button in the top bar already covers the rest.
const bottomNav = computed(() => primary.value.slice(0, 4));

// Business name + logo come from Logistics Settings (tenant branding).
const businessName = ref("BWM Logistics");
const logo = ref<string | null>(null);

const branchStore = useBranchStore();

onMounted(async () => {
	session.loadAccess();
	if (session.isStaff) branchStore.load();
	try {
		const b = await call<{ business_name: string; logo?: string }>(
			"bwm_logistics.api.settings.get_branding",
		);
		if (b?.business_name) businessName.value = b.business_name;
		logo.value = b?.logo || null;
	} catch {
		/* branding falls back to default */
	}
});
</script>

<template>
	<div class="flex h-dvh flex-col overflow-hidden bg-gray-50 text-gray-900" @keydown="onEscape">
		<!-- ── Top bar ─────────────────────────────────────────────────────── -->
		<header class="relative z-40 flex h-14 shrink-0 items-center gap-1 bg-coal-900 px-2 text-white sm:px-3">
			<!-- Menu — the one way into the full nav, at every width -->
			<button
				type="button"
				class="flex h-10 w-10 shrink-0 touch-manipulation items-center justify-center rounded-lg text-white/80 transition-colors hover:bg-white/[0.08] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
				aria-label="Open menu"
				:aria-expanded="navOpen"
				@click="navOpen = true"
			>
				<Menu class="h-5 w-5" aria-hidden="true" />
			</button>

			<!-- Primary tabs (desktop) -->
			<nav class="ml-1 hidden min-w-0 flex-1 items-center gap-0.5 overflow-x-auto md:flex" aria-label="Primary">
				<RouterLink
					v-for="item in primary"
					:key="item.key"
					:to="item.to"
					class="shrink-0 touch-manipulation rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
					:class="
						isActive(item.to)
							? 'bg-white/[0.14] text-white'
							: 'text-white/65 hover:bg-white/[0.07] hover:text-white'
					"
					:aria-current="isActive(item.to) ? 'page' : undefined"
				>
					{{ item.label }}
				</RouterLink>
			</nav>

			<!-- Right cluster — branch filter, portal bell, then the logo -->
			<div class="ml-auto flex shrink-0 items-center gap-1.5">
				<BranchPicker v-if="!portalMode" />
				<PortalBell v-if="portalMode" />

				<RouterLink
					:to="portalMode ? '/portal' : '/'"
					class="flex shrink-0 touch-manipulation items-center gap-2.5 rounded-lg pl-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
					:aria-label="`${businessName} — home`"
				>
					<span class="hidden text-sm font-semibold tracking-tight text-white/90 lg:inline">
						{{ businessName }}
					</span>
					<span
						class="flex h-9 w-9 items-center justify-center overflow-hidden rounded-lg shadow-sm shadow-black/20"
						:class="logo ? 'bg-white' : 'bg-gradient-to-br from-brand-400 to-brand-600 text-coal-900'"
					>
						<img v-if="logo" :src="logo" alt="" width="36" height="36" class="h-full w-full object-contain" />
						<BrandLogo v-else :size="22" />
					</span>
				</RouterLink>
			</div>
		</header>

		<!-- ── Nav drawer ──────────────────────────────────────────────────── -->
		<Transition
			enter-active-class="transition-opacity duration-200"
			enter-from-class="opacity-0"
			enter-to-class="opacity-100"
			leave-active-class="transition-opacity duration-150"
			leave-from-class="opacity-100"
			leave-to-class="opacity-0"
		>
			<div v-if="navOpen" class="fixed inset-0 z-50 bg-black/40" @click="navOpen = false" />
		</Transition>
		<Transition
			enter-active-class="transition-transform duration-200 ease-out"
			enter-from-class="-translate-x-full"
			enter-to-class="translate-x-0"
			leave-active-class="transition-transform duration-150 ease-in"
			leave-from-class="translate-x-0"
			leave-to-class="-translate-x-full"
		>
			<aside
				v-if="navOpen"
				ref="drawerRef"
				class="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[82vw] flex-col overscroll-contain bg-coal-900 text-white"
				aria-label="All pages"
			>
				<div class="flex h-14 shrink-0 items-center justify-between gap-2 px-3">
					<span class="truncate pl-1 text-sm font-semibold tracking-tight">{{ businessName }}</span>
					<button
						type="button"
						class="flex h-9 w-9 shrink-0 touch-manipulation items-center justify-center rounded-lg text-white/70 transition-colors hover:bg-white/[0.08] hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
						aria-label="Close menu"
						@click="navOpen = false"
					>
						<X class="h-4 w-4" aria-hidden="true" />
					</button>
				</div>
				<nav class="min-h-0 flex-1 space-y-0.5 overflow-y-auto overscroll-contain p-2.5">
					<RouterLink
						v-for="item in drawerNav"
						:key="item.key"
						:to="item.to"
						class="flex touch-manipulation items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
						:class="
							isActive(item.to)
								? 'bg-white/[0.14] text-white'
								: 'text-white/70 hover:bg-white/[0.07] hover:text-white'
						"
						:aria-current="isActive(item.to) ? 'page' : undefined"
					>
						<component :is="item.icon" class="h-[18px] w-[18px] shrink-0" aria-hidden="true" />
						{{ item.label }}
					</RouterLink>
				</nav>
				<div class="shrink-0 border-t border-white/10 p-2.5">
					<div class="px-3 pb-2 pt-1">
						<div class="truncate text-sm font-medium">{{ fullName }}</div>
						<div class="truncate text-xs text-white/50">{{ userEmail }}</div>
					</div>
					<button
						type="button"
						class="flex w-full touch-manipulation items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-red-300 transition-colors hover:bg-white/[0.07] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
						@click="logout"
					>
						<LogOut class="h-[18px] w-[18px]" aria-hidden="true" /> Log out
					</button>
				</div>
			</aside>
		</Transition>

		<!-- ── Main area ───────────────────────────────────────────────────── -->
		<main class="min-w-0 flex-1 overflow-y-auto p-4 pb-24 sm:p-6 md:pb-6">
			<slot />
		</main>

		<!-- ── Mobile bottom tab bar ───────────────────────────────────────── -->
		<nav
			v-if="bottomNav.length > 1"
			class="fixed inset-x-0 bottom-0 z-40 flex items-stretch justify-around border-t border-gray-200 bg-white pb-[env(safe-area-inset-bottom)] md:hidden print:hidden"
			aria-label="Sections"
		>
			<RouterLink
				v-for="item in bottomNav"
				:key="item.key"
				:to="item.to"
				class="flex min-w-0 flex-1 touch-manipulation flex-col items-center gap-1 py-2.5 text-[11px] font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-brand-500"
				:class="isActive(item.to) ? 'text-brand-700' : 'text-gray-500'"
				:aria-current="isActive(item.to) ? 'page' : undefined"
			>
				<component :is="item.icon" class="h-5 w-5" aria-hidden="true" />
				<span class="max-w-full truncate">{{ item.label }}</span>
			</RouterLink>
		</nav>
	</div>
</template>
