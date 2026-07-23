import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";
import { VitePWA } from "vite-plugin-pwa";
import path from "node:path";

// Vite config for the BWM Logistics SPA (operator app + customer portal).
//
// Build output lands in `../bwm_logistics/public/dist/main` so Frappe serves
// it at `/assets/bwm_logistics/dist/main/...`. The www/logistics.html template
// reads `manifest.json` from that folder to find the hashed entry chunks.
//
// Dev: `yarn dev` starts Vite at :8080 and proxies API/auth calls to the
// Frappe site so we can iterate without rebuilding. The Frappe site itself
// keeps running on :8000 (or wherever bench start binds it).

export default defineConfig(({ mode, command }) => {
	const env = loadEnv(mode, process.cwd(), "");
	// `localhost:8000` relies on Frappe's `serve_default_site = true` to route
	// to the configured `default_site`. If you run multiple sites, set
	// VITE_FRAPPE_URL=http://<site-name>:8000 in frontend/.env.local — the
	// site name has to resolve from the dev machine (check /etc/hosts).
	const frappeUrl = env.VITE_FRAPPE_URL || "http://localhost:8000";

	return {
		// In production the bundle is served from the app's public dir, so
		// lazy-loaded chunks + their CSS must resolve against that subpath. With
		// the default base ("/") Vite emits chunk URLs like `/assets/Dashboard.js`
		// which Frappe answers with an HTML 404 — the browser then blocks the
		// module ("disallowed MIME type") and the route renders blank. The dev
		// server (yarn dev :8080) still serves from root, so only set base on build.
		base: command === "build" ? "/assets/bwm_logistics/dist/main/" : "/",
		plugins: [
			vue(),
			// PWA (P8): manifest + generated service worker. The SW itself is
			// registered from /logistics/sw.js (served by bwm_logistics/pwa.py with
			// Service-Worker-Allowed so its scope can cover /logistics) — see
			// main.ts. Precache = static assets only; the /logistics HTML carries
			// per-user boot + CSRF and must never be cached, so navigations are
			// NetworkOnly with a static offline fallback page.
			VitePWA({
				strategies: "generateSW",
				registerType: "autoUpdate",
				injectRegister: false, // manual registration in main.ts
				manifestFilename: "manifest.webmanifest",
				manifest: {
					id: "/logistics",
					name: "BWM Logistics",
					short_name: "BWM Logistics",
					description: "Container tracking, stock & distribution, and billing.",
					start_url: "/logistics",
					scope: "/logistics",
					display: "standalone",
					theme_color: "#0f0f10",
					background_color: "#ffffff",
					icons: [
						{
							src: "/assets/bwm_logistics/dist/main/icons/pwa-192x192.png",
							sizes: "192x192",
							type: "image/png",
						},
						{
							src: "/assets/bwm_logistics/dist/main/icons/pwa-512x512.png",
							sizes: "512x512",
							type: "image/png",
						},
						{
							src: "/assets/bwm_logistics/dist/main/icons/pwa-maskable-512x512.png",
							sizes: "512x512",
							type: "image/png",
							purpose: "maskable",
						},
					],
				},
				workbox: {
					globPatterns: ["**/*.{js,css,html,svg,png,ico,woff2}"],
					globIgnores: ["**/.vite/**"],
					inlineWorkboxRuntime: true, // single sw.js — no sibling runtime chunk to proxy
					sourcemap: false,
					// CRITICAL: the plugin's default points at base+index.html, which
					// this build never emits — the SW would throw at runtime.
					navigateFallback: null,
					maximumFileSizeToCacheInBytes: 4 * 1024 * 1024, // html5-qrcode chunk
					runtimeCaching: [
						{
							urlPattern: ({ request }) => request.mode === "navigate",
							handler: "NetworkOnly",
							options: {
								precacheFallback: {
									fallbackURL: "/assets/bwm_logistics/dist/main/offline.html",
								},
							},
						},
					],
				},
				devOptions: { enabled: false },
			}),
		],
		resolve: {
			alias: {
				"@": path.resolve(__dirname, "./src"),
			},
		},
		server: {
			port: 8080,
			proxy: {
				// Frappe API endpoints + session cookie endpoints all live under
				// these prefixes. `cookieDomainRewrite: ""` strips the Domain=
				// attribute from Set-Cookie responses so the browser stores them
				// under localhost:8080 — without it, login succeeds on the wire
				// but the sid cookie is dropped and the next request is Guest.
				"^/(app|api|assets|files|private|method|login|logout)": {
					target: frappeUrl,
					changeOrigin: true,
					ws: true,
					cookieDomainRewrite: "",
				},
			},
		},
		build: {
			outDir: path.resolve(__dirname, "../bwm_logistics/public/dist/main"),
			emptyOutDir: true,
			manifest: true,
			rollupOptions: {
				input: path.resolve(__dirname, "src/main.ts"),
			},
		},
	};
});
