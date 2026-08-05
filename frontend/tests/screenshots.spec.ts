import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";

// UI-audit sweep: every operator + portal route, at the three widths that
// matter (phone / tablet / desktop). Output lands in tests/__shots__/<width>/
// so a design change can be eyeballed side-by-side before and after.
//
// It also fails loudly on two things a screenshot can hide:
//   - console errors on any page
//   - horizontal overflow (content wider than the viewport) on phones —
//     the classic "the table doesn't fit the screen" bug.

const SHOT_DIR = "tests/__shots__";

const VIEWPORTS = [
	{ name: "phone", width: 390, height: 844 },
	{ name: "tablet", width: 768, height: 1024 },
	{ name: "desktop", width: 1440, height: 900 },
];

const ROUTES = [
	{ slug: "dashboard", path: "/logistics/" },
	{ slug: "containers", path: "/logistics/containers" },
	{ slug: "shipments", path: "/logistics/shipments" },
	{ slug: "stock", path: "/logistics/stock" },
	{ slug: "dispatch", path: "/logistics/dispatch" },
	{ slug: "customers", path: "/logistics/customers" },
	{ slug: "billing", path: "/logistics/billing" },
	{ slug: "reports", path: "/logistics/reports" },
	{ slug: "notifications", path: "/logistics/notifications" },
	{ slug: "settings", path: "/logistics/settings" },
	{ slug: "portal-home", path: "/logistics/portal" },
	{ slug: "portal-shipments", path: "/logistics/portal/shipments" },
	{ slug: "portal-invoices", path: "/logistics/portal/invoices" },
];

/** Wait for the SPA to settle: router resolved, loading text gone. */
async function settle(page: Page) {
	await page.waitForLoadState("networkidle").catch(() => {});
	await page
		.getByText(/^Loading…$/)
		.first()
		.waitFor({ state: "detached", timeout: 8000 })
		.catch(() => {});
	await page.waitForTimeout(350); // let transitions/charts finish painting
}

/** How far the document scrolls sideways past the viewport, in CSS px. */
async function overflowPx(page: Page) {
	return page.evaluate(
		() =>
			document.documentElement.scrollWidth -
			document.documentElement.clientWidth,
	);
}

for (const vp of VIEWPORTS) {
	test.describe(`${vp.name} (${vp.width}px)`, () => {
		test.use({ viewport: { width: vp.width, height: vp.height } });

		for (const route of ROUTES) {
			test(`${route.slug}`, async ({ page }) => {
				const errors: string[] = [];
				page.on(
					"console",
					(m) => m.type() === "error" && errors.push(m.text()),
				);
				page.on("pageerror", (e) => errors.push(String(e)));

				await page.goto(route.path);
				await settle(page);

				fs.mkdirSync(`${SHOT_DIR}/${vp.name}`, { recursive: true });
				await page.screenshot({
					path: `${SHOT_DIR}/${vp.name}/${route.slug}.png`,
					fullPage: true,
				});

				// Phones are where overflow actually hurts; allow 1px for rounding.
				if (vp.width <= 430) {
					expect(
						await overflowPx(page),
						`${route.slug} scrolls sideways`,
					).toBeLessThanOrEqual(1);
				}

				const real = errors.filter(
					(e) => !/favicon|manifest|Failed to load resource/i.test(e),
				);
				expect(real, `console errors on ${route.slug}`).toEqual([]);
			});
		}
	});
}
