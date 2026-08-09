import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import { settle } from "./settle";
import { useFixtures } from "./fixtures";
import { measureOverflow } from "./overflow";

// The same sweep as screenshots.spec.ts, but with lists and tiles full of data
// (see fixtures.ts — nothing is written to the database). This is the pass that
// actually catches layout bugs: a phone-width table that clips its last column,
// a card whose figure wraps, a filter row that runs off-screen.

const SHOT_DIR = "tests/__shots__";

const VIEWPORTS = [
	{ name: "phone", width: 390, height: 844 },
	{ name: "tablet", width: 768, height: 1024 },
	{ name: "desktop", width: 1440, height: 900 },
];

const ROUTES = [
	{ slug: "dashboard", path: "/logistics/" },
	{ slug: "customers", path: "/logistics/customers" },
	{ slug: "shipments", path: "/logistics/shipments" },
	{ slug: "containers", path: "/logistics/containers" },
	{ slug: "billing", path: "/logistics/billing" },
	{ slug: "dispatch", path: "/logistics/dispatch" },
];


for (const vp of VIEWPORTS) {
	test.describe(`populated ${vp.name} (${vp.width}px)`, () => {
		test.use({ viewport: { width: vp.width, height: vp.height } });

		for (const route of ROUTES) {
			test(`${route.slug}`, async ({ page }) => {
				const errors: string[] = [];
				page.on(
					"console",
					(m) => m.type() === "error" && errors.push(m.text()),
				);
				page.on("pageerror", (e) => errors.push(String(e)));

				await useFixtures(page);
				await page.goto(route.path);
				await settle(page);

				fs.mkdirSync(`${SHOT_DIR}/full-${vp.name}`, { recursive: true });
				await page.screenshot({
					path: `${SHOT_DIR}/full-${vp.name}/${route.slug}.png`,
					fullPage: true,
				});

				if (vp.width <= 430) {
					const of = await measureOverflow(page);
					expect(
						of.offenders,
						`${route.slug} has content wider than the screen`,
					).toEqual([]);
					expect(of.px, `${route.slug} scrolls sideways`).toBeLessThanOrEqual(1);
				}

				const real = errors.filter(
					(e) => !/favicon|manifest|Failed to load resource/i.test(e),
				);
				expect(real, `console errors on ${route.slug}`).toEqual([]);
			});
		}
	});
}
