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
	LayoutGrid,
	ChevronDown,
	LogOut,
	ExternalLink,
	Menu,
	X,
	MapPin,
	UserRound,
	ScanLine,
} from "lucide-vue-next";
import { useSessionStore } from "@/stores/session";
import BrandLogo from "@/components/BrandLogo.vue";
import AppsDrawer from "@/components/AppsDrawer.vue";
import PortalBell from "@/components/PortalBell.vue";
import { call } from "@/lib/frappe";
import { logout as apiLogout } from "@/lib/auth";

// Shell copied from the ex_beauty layout language: a near-black top bar with
// a lean set of primary tabs, an "Apps" launcher for everything else, and a
// two-line account block. Full-width content sits below; pages manage their
// own scroll. One shell serves both route trees — the tab set switches when
// the user is in the customer portal.

interface NavItem {
	key: string;
	label: string;
	icon: unknown;
	to: string;
}

// Operator primary tabs — the everyday few. Everything else lives in Apps.
const operatorPrimary: NavItem[] = [
	{ key: "dashboard", label: "Dashboard", icon: LayoutDashboard, to: "/" },
	{ key: "containers", label: "Containers", icon: Container, to: "/containers" },
	{ key: "shipments", label: "Shipments", icon: Package, to: "/shipments" },
	{ key: "dispatch", label: "Dispatch", icon: MapPin, to: "/dispatch" },
	{ key: "customers", label: "Customers", icon: Users, to: "/customers" },
	{ key: "billing", label: "Billing", icon: ReceiptText, to: "/billing" },
];

// Customer portal tabs — the whole portal nav (no Apps drawer for customers).
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

const initials = computed(() => {
	const name = session.user?.full_name || session.user?.first_name || "U";
	const parts = name.trim().split(/\s+/);
	return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "U";
});
const fullName = computed(
	() => session.user?.full_name || session.user?.first_name || "Account",
);

const isActive = (to: string) => {
	if (to === "/") return route.path === "/";
	if (to === "/portal") return route.path === "/portal";
	return route.path.startsWith(to);
};

// Apps drawer — close on outside click. Staff only.
const appsOpen = ref(false);
const appsRef = ref<HTMLElement | null>(null);
onClickOutside(appsRef, () => (appsOpen.value = false));

// Account menu — avatar + dropdown (switch to desk, logout).
const accountOpen = ref(false);
const accountRef = ref<HTMLElement | null>(null);
onClickOutside(accountRef, () => (accountOpen.value = false));
const userImage = computed(() => session.user?.user_image || null);
const userEmail = computed(() => session.user?.email || "");
const canDesk = computed(() => session.hasRole("System Manager", "Administrator"));
function switchToDesk() {
	window.location.href = "/app";
}
async function logout() {
	// POST + CSRF via the auth helper (the endpoint is POST-only); then leave
	// the app for the public site.
	try {
		await apiLogout();
	} finally {
		window.location.href = "/home";
	}
}

// Mobile sidebar — the full nav, shown via a hamburger on small screens.
const operatorMobile: NavItem[] = [
	...operatorPrimary,
	{ key: "scan", label: "Scan", icon: ScanLine, to: "/scan" },
	{ key: "notifications", label: "Notifications", icon: BellRing, to: "/notifications" },
	{ key: "settings", label: "Settings", icon: Settings, to: "/settings" },
];
const mobileNavOpen = ref(false);
const mobileNavVisible = computed(() =>
	(portalMode.value ? portalPrimary : operatorMobile).filter((i) => session.canSee(i.key)),
);
// Close the drawer whenever the route changes.
watch(() => route.path, () => (mobileNavOpen.value = false));

// Business name + logo come from Logistics Settings (tenant branding).
const businessName = ref("BWM Logistics");
const logo = ref<string | null>(null);

onMounted(async () => {
	session.loadAccess();
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
	<div class="flex h-screen flex-col overflow-hidden bg-gray-50 text-gray-900">
		<!-- ── Top bar (near-black, full-width) ────────────────────────────── -->
		<header
			class="relative z-40 flex h-14 shrink-0 items-center gap-1 bg-coal-900 px-3 text-white sm:px-4"
		>
			<!-- Mobile hamburger -->
			<button
				type="button"
				class="-ml-1 mr-1 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-white/80 transition-colors hover:bg-white/[0.08] hover:text-white md:hidden"
				title="Menu"
				@click="mobileNavOpen = true"
			>
				<Menu class="h-5 w-5" />
			</button>

			<!-- Brand -->
			<RouterLink :to="portalMode ? '/portal' : '/'" class="flex shrink-0 items-center gap-2.5 pr-3">
				<div
					class="flex h-9 w-9 items-center justify-center overflow-hidden rounded-lg shadow-sm shadow-black/20"
					:class="logo ? 'bg-white' : 'bg-gradient-to-br from-brand-400 to-brand-600 text-coal-900'"
				>
					<img v-if="logo" :src="logo" alt="" class="h-full w-full object-contain" />
					<BrandLogo v-else :size="22" />
				</div>
				<span class="hidden text-sm font-semibold tracking-tight xl:inline">
					{{ businessName }}
				</span>
			</RouterLink>

			<!-- Primary tabs (hidden on mobile — see the sidebar drawer) -->
			<nav class="hidden min-w-0 flex-1 items-center gap-0.5 overflow-x-auto md:flex">
				<RouterLink
					v-for="item in primary"
					:key="item.key"
					:to="item.to"
					class="flex shrink-0 items-center gap-2 rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors"
					:class="
						isActive(item.to)
							? 'bg-brand-500/20 text-brand-300'
							: 'text-white/70 hover:bg-white/[0.07] hover:text-white'
					"
				>
					<component :is="item.icon" class="h-4 w-4 shrink-0" />
					<span class="hidden md:inline">{{ item.label }}</span>
				</RouterLink>
			</nav>

			<!-- Right cluster (kept hard-right even when the nav is hidden on mobile) -->
			<div class="ml-auto flex shrink-0 items-center gap-1">
				<!-- Apps launcher (staff, desktop only — mobile uses the sidebar) -->
				<div v-if="!portalMode" ref="appsRef" class="relative hidden md:block">
					<button
						type="button"
						class="flex items-center gap-1.5 rounded-lg px-2.5 py-2 text-[13px] font-medium transition-colors"
						:class="appsOpen ? 'bg-white/[0.14] text-white' : 'text-white/75 hover:bg-white/[0.08] hover:text-white'"
						@click="appsOpen = !appsOpen"
					>
						<LayoutGrid class="h-4 w-4" />
						<span class="hidden lg:inline">Apps</span>
					</button>
					<AppsDrawer :open="appsOpen" @close="appsOpen = false" />
				</div>

				<!-- Notification bell (customer portal) -->
				<PortalBell v-if="portalMode" />

				<!-- Divider before account block -->
				<div class="mx-1 hidden h-6 w-px bg-white/10 lg:block" />

				<!-- Account block -->
				<div ref="accountRef" class="relative ml-0.5">
					<button
						class="flex items-center gap-2 rounded-lg py-1 pl-1 pr-2 transition-colors hover:bg-white/[0.08]"
						:class="accountOpen ? 'bg-white/[0.1]' : ''"
						@click="accountOpen = !accountOpen"
					>
						<img
							v-if="userImage"
							:src="userImage"
							:alt="fullName"
							class="h-8 w-8 rounded-full object-cover ring-1 ring-white/20"
						/>
						<div
							v-else
							class="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-brand-400 to-brand-600 text-xs font-bold text-coal-900"
						>
							{{ initials }}
						</div>
						<div class="hidden text-left leading-tight lg:block">
							<div class="max-w-[9rem] truncate text-xs font-semibold">{{ fullName }}</div>
							<div class="max-w-[9rem] truncate text-[10px] text-white/55">{{ businessName }}</div>
						</div>
						<ChevronDown
							class="hidden h-3.5 w-3.5 text-white/50 transition-transform lg:block"
							:class="accountOpen ? 'rotate-180' : ''"
						/>
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
							v-if="accountOpen"
							class="absolute right-0 top-full z-50 mt-1.5 w-60 overflow-hidden rounded-xl border border-black/5 bg-white text-gray-900 shadow-pop"
						>
							<div class="flex items-center gap-3 border-b border-gray-100 px-3.5 py-3">
								<img
									v-if="userImage"
									:src="userImage"
									:alt="fullName"
									class="h-9 w-9 rounded-full object-cover"
								/>
								<div
									v-else
									class="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-brand-400 to-brand-600 text-xs font-bold text-coal-900"
								>
									{{ initials }}
								</div>
								<div class="min-w-0">
									<div class="truncate text-sm font-semibold">{{ fullName }}</div>
									<div class="truncate text-xs text-gray-500">{{ userEmail }}</div>
								</div>
							</div>
							<div class="p-1.5">
								<button
									v-if="canDesk"
									type="button"
									class="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm text-gray-700 transition-colors hover:bg-gray-100"
									@click="switchToDesk"
								>
									<ExternalLink class="h-4 w-4 text-gray-400" /> Switch to Desk
								</button>
								<button
									type="button"
									class="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm text-red-600 transition-colors hover:bg-red-50"
									@click="logout"
								>
									<LogOut class="h-4 w-4" /> Log out
								</button>
							</div>
						</div>
					</transition>
				</div>
			</div>
		</header>

		<!-- ── Mobile sidebar drawer ───────────────────────────────────────── -->
		<Transition
			enter-active-class="transition-opacity duration-200"
			enter-from-class="opacity-0"
			enter-to-class="opacity-100"
			leave-active-class="transition-opacity duration-150"
			leave-from-class="opacity-100"
			leave-to-class="opacity-0"
		>
			<div v-if="mobileNavOpen" class="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm md:hidden" @click="mobileNavOpen = false" />
		</Transition>
		<Transition
			enter-active-class="transition-transform duration-250 ease-out"
			enter-from-class="-translate-x-full"
			enter-to-class="translate-x-0"
			leave-active-class="transition-transform duration-200 ease-in"
			leave-from-class="translate-x-0"
			leave-to-class="-translate-x-full"
		>
			<aside v-if="mobileNavOpen" class="fixed inset-y-0 left-0 z-50 flex w-72 max-w-[82vw] flex-col bg-coal-900 text-white md:hidden">
				<div class="flex h-14 shrink-0 items-center justify-between px-4">
					<div class="flex items-center gap-2.5">
						<div class="flex h-9 w-9 items-center justify-center rounded-lg bg-gradient-to-br from-brand-400 to-brand-600 text-coal-900 shadow-sm shadow-black/20">
							<BrandLogo :size="22" />
						</div>
						<span class="truncate text-sm font-semibold tracking-tight">{{ businessName }}</span>
					</div>
					<button type="button" class="flex h-8 w-8 items-center justify-center rounded-lg text-white/70 hover:bg-white/[0.08] hover:text-white" @click="mobileNavOpen = false">
						<X class="h-4 w-4" />
					</button>
				</div>
				<nav class="min-h-0 flex-1 space-y-0.5 overflow-y-auto p-3">
					<RouterLink
						v-for="item in mobileNavVisible"
						:key="item.key"
						:to="item.to"
						class="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors"
						:class="isActive(item.to) ? 'bg-brand-500/20 text-brand-300' : 'text-white/70 hover:bg-white/[0.07] hover:text-white'"
					>
						<component :is="item.icon" class="h-[18px] w-[18px] shrink-0" />
						{{ item.label }}
					</RouterLink>
				</nav>
				<div class="shrink-0 border-t border-white/10 p-3">
					<button v-if="canDesk" type="button" class="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-white/70 transition-colors hover:bg-white/[0.07] hover:text-white" @click="switchToDesk">
						<ExternalLink class="h-[18px] w-[18px]" /> Switch to Desk
					</button>
					<button type="button" class="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-red-300 transition-colors hover:bg-white/[0.07]" @click="logout">
						<LogOut class="h-[18px] w-[18px]" /> Log out
					</button>
				</div>
			</aside>
		</Transition>

		<!-- ── Main area ───────────────────────────────────────────────────── -->
		<main class="min-w-0 flex-1 overflow-y-auto p-4 sm:p-6">
			<slot />
		</main>
	</div>
</template>
