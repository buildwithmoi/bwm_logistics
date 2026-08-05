import { defineConfig, devices } from "@playwright/test";

// Playwright drives the SPA against a running bench (default: the local dev
// site on :8004). It is a UI-audit / smoke harness, not a unit-test runner —
// `yarn shots` walks every route at phone/tablet/desktop widths and writes PNGs
// so design regressions are reviewable as images.
//
//   BWM_BASE_URL   bench origin              (default http://localhost:8004)
//   BWM_USER/PWD   staff login for the run   (default: the dev demo user)

export const BASE_URL = process.env.BWM_BASE_URL || "http://localhost:8004";
export const STAFF_USER = process.env.BWM_USER || "ui-audit@bwm-demo.test";
export const STAFF_PWD = process.env.BWM_PWD || "bwm-demo-2026";
export const STORAGE_STATE = "tests/.auth/staff.json";

export default defineConfig({
	testDir: "./tests",
	outputDir: "./tests/.output",
	fullyParallel: false,
	workers: 1,
	retries: 0,
	reporter: [["list"]],
	timeout: 60_000,
	use: {
		baseURL: BASE_URL,
		trace: "retain-on-failure",
		screenshot: "only-on-failure",
	},
	projects: [
		{ name: "setup", testMatch: /auth\.setup\.ts/ },
		{
			name: "audit",
			testMatch: /.*\.spec\.ts/,
			dependencies: ["setup"],
			use: { ...devices["Desktop Chrome"], storageState: STORAGE_STATE },
		},
	],
});
