import { createApp } from "vue";
import { createPinia } from "pinia";
import App from "./App.vue";
import { router } from "./router";
import "./style.css";

// Entry for the BWM Logistics SPA. The www/logistics.html template renders an
// empty shell, sets `window.csrf_token` + `window.frappe.boot`, and references
// the bundle Vite emits at `/assets/bwm_logistics/dist/main/...`.

const app = createApp(App);
app.use(createPinia());
app.use(router);

// Wait for the router's initial navigation (route match + lazy component load
// + guards) to settle before mounting. Without this, a hard reload can mount
// the app before the first route resolves, leaving the content area blank
// until an in-app navigation forces a re-render. `isReady()` resolves even if
// the first navigation redirects or fails, so mounting always proceeds.
router.isReady().finally(() => app.mount("#app"));

// PWA service worker — registered from /logistics/sw.js (bwm_logistics/pwa.py
// serves the built worker with Service-Worker-Allowed: /logistics, letting the
// scope cover the whole app even though the file lives under /assets).
if (import.meta.env.PROD && "serviceWorker" in navigator) {
	window.addEventListener("load", () => {
		navigator.serviceWorker.register("/logistics/sw.js", { scope: "/logistics" }).catch(() => {
			/* unsupported/blocked — the app works fine without it */
		});
	});
}
