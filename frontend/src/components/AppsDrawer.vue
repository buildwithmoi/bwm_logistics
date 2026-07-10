<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";
import { useSessionStore } from "@/stores/session";
import {
	LayoutDashboard,
	Container,
	Package,
	MapPin,
	Users,
	ReceiptText,
	BellRing,
	Settings,
} from "lucide-vue-next";

// App launcher — a wide, categorised grid (ex_beauty pattern). Core Apps span
// three columns; Setup & Management sits in its own column. Opened from the
// "Apps" button in the nav. Staff only — the customer portal has no drawer.

defineProps<{ open: boolean }>();
const emit = defineEmits<{ (e: "close"): void }>();

const session = useSessionStore();

interface App {
	key: string;
	label: string;
	to: string;
	icon: unknown;
}
const CORE: App[] = [
	{ key: "dashboard", label: "Dashboard", to: "/", icon: LayoutDashboard },
	{ key: "containers", label: "Containers", to: "/containers", icon: Container },
	{ key: "shipments", label: "Shipments", to: "/shipments", icon: Package },
	{ key: "dispatch", label: "Dispatch", to: "/dispatch", icon: MapPin },
	{ key: "customers", label: "Customers", to: "/customers", icon: Users },
	{ key: "billing", label: "Billing", to: "/billing", icon: ReceiptText },
	{ key: "notifications", label: "Notifications", to: "/notifications", icon: BellRing },
];
const SETUP: App[] = [
	{ key: "settings", label: "Settings", to: "/settings", icon: Settings },
];

const CORE_TINT = "#b8860b"; // brand gold — the one accent, used softly
const SETUP_TINT = "#64748b"; // slate

const coreVisible = computed(() => CORE.filter((a) => session.canSee(a.key)));
const setupVisible = computed(() => SETUP.filter((a) => session.canSee(a.key)));
const canManage = computed(() => session.canSee("settings"));
</script>

<template>
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
			class="absolute right-0 top-full z-50 mt-2.5 w-[42rem] max-w-[95vw] overflow-hidden rounded-2xl border border-border bg-white px-8 py-7 text-gray-900 shadow-modal"
		>
			<div class="grid grid-cols-4 gap-x-10 gap-y-6">
				<!-- Core Apps — spans three columns -->
				<div class="col-span-3">
					<div class="mb-4 label-caps">Core Apps</div>
					<div class="grid grid-cols-3 gap-x-6 gap-y-1">
						<RouterLink
							v-for="a in coreVisible"
							:key="a.key"
							:to="a.to"
							class="group flex items-center gap-3 rounded-xl px-2 py-2.5 transition-colors hover:bg-gray-50"
							@click="emit('close')"
						>
							<span
								class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-transform group-hover:scale-105"
								:style="{ backgroundColor: CORE_TINT + '1f', color: CORE_TINT }"
							>
								<component :is="a.icon" class="h-5 w-5" />
							</span>
							<span class="truncate text-[14px] font-medium text-gray-700">{{ a.label }}</span>
						</RouterLink>
					</div>
				</div>

				<!-- Setup & Management -->
				<div v-if="setupVisible.length" class="col-span-1">
					<div class="mb-4 label-caps">Setup</div>
					<div class="grid grid-cols-1 gap-y-1">
						<RouterLink
							v-for="a in setupVisible"
							:key="a.key"
							:to="a.to"
							class="group flex items-center gap-3 rounded-xl px-2 py-2.5 transition-colors hover:bg-gray-50"
							@click="emit('close')"
						>
							<span
								class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl transition-transform group-hover:scale-105"
								:style="{ backgroundColor: SETUP_TINT + '1f', color: SETUP_TINT }"
							>
								<component :is="a.icon" class="h-5 w-5" />
							</span>
							<span class="truncate text-[14px] font-medium text-gray-700">{{ a.label }}</span>
						</RouterLink>
					</div>
				</div>
			</div>

			<!-- Footer -->
			<div v-if="canManage" class="mt-5 border-t border-border pt-4">
				<RouterLink
					to="/settings"
					class="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground transition-colors hover:text-gray-800"
					@click="emit('close')"
				>
					<Settings class="h-4 w-4" /> Settings
				</RouterLink>
			</div>
		</div>
	</transition>
</template>
