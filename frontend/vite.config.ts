import { defineConfig, loadEnv } from "vite";
import vue from "@vitejs/plugin-vue";
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
		plugins: [vue()],
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
