<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import AppShell from "@/components/AppShell.vue";
import ToastViewport from "@/components/ui/ToastViewport.vue";
import Login from "@/pages/Login.vue";
import BrandLogo from "@/components/BrandLogo.vue";
import { router } from "@/router";
import { useSessionStore } from "@/stores/session";

// Guard the SPA at the root: Guests see the branded Login page; everyone
// else gets the AppShell + routed page. We deliberately bypass the router for
// Guests so we don't waste a lazy-loaded chunk on a page they won't see.
const session = useSessionStore();
const authed = computed(() => session.isLoggedIn);
const ready = computed(() => session.ready);

// Page components are lazy-loaded (route-level code splitting), so switching
// tabs waits on a chunk download + the page's first data fetch. Surface a slim
// top progress bar while navigating; a short delay keeps instant (cached)
// transitions from flickering it.
const navigating = ref(false);
let navTimer: ReturnType<typeof setTimeout> | undefined;
router.beforeEach(() => {
	clearTimeout(navTimer);
	navTimer = setTimeout(() => {
		navigating.value = true;
	}, 120);
});
const stopNavigating = () => {
	clearTimeout(navTimer);
	navigating.value = false;
};
router.afterEach(stopNavigating);
router.onError(stopNavigating);

// In dev mode the bootinfo isn't server-rendered (Vite serves index.html);
// `bootstrap()` asks Frappe `who am I?` so an existing session is detected
// without forcing the user to re-login. In prod this returns immediately
// because the bootinfo is already populated.
onMounted(() => {
	session.bootstrap();
});
</script>

<template>
	<template v-if="!ready">
		<!-- Tiny splash so we don't flash the Login page while bootstrap()
		     resolves. Only visible for ~100ms in prod, slightly longer in dev. -->
		<div class="flex min-h-screen items-center justify-center bg-white text-brand-500">
			<div class="animate-pulse">
				<BrandLogo :size="56" />
			</div>
		</div>
	</template>
	<template v-else-if="authed">
		<!-- Indeterminate top progress bar shown during route navigation. -->
		<div
			v-if="navigating"
			class="fixed inset-x-0 top-0 z-[60] h-0.5 animate-pulse bg-brand-500"
		></div>
		<AppShell>
			<RouterView />
		</AppShell>
	</template>
	<template v-else>
		<Login />
	</template>
	<ToastViewport />
</template>
