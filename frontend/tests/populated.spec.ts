import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import { useFixtures } from "./fixtures";

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

async function settle(page: Page) {
	await page.waitForLoadState("networkidle").catch(() => {});
	await page
		.getByText(/^Loading…$/)
		.first()
		.waitFor({ state: "detached", timeout: 8000 })
		.catch(() => {});
	await page.waitForTimeout(350);
}

/** Any element whose right edge sits past the viewport — the real culprits. */
async function overflowers(page: Page, width: number) {
	return page.evaluate((vw) => {
		const bad: string[] = [];
		for (const el of Array.from(
			document.body.querySelectorAll<HTMLElement>("*"),
		)) {
			const r = el.getBoundingClientRect();
			if (r.width === 0 || r.height === 0) continue;
			if (r.right > vw + 1 || r.left < -1) {
				// Ignore anything inside a deliberate horizontal scroller.
				let p: HTMLElement | null = el.parentElement;
				let scroller = false;
				while (p && p !== document.body) {
					const ov = getComputedStyle(p).overflowX;
					if (ov === "auto" || ov === "scroll") {
						scroller = true;
						break;
					}
					p = p.parentElement;
				}
				if (scroller) continue;
				bad.push(
					`${el.tagName.toLowerCase()}.${el.className.toString().slice(0, 60)} → right ${Math.round(r.right)}`,
				);
			}
		}
		return bad.slice(0, 8);
	}, width);
}

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
					const doc = await page.evaluate(
						() =>
							document.documentElement.scrollWidth -
							document.documentElement.clientWidth,
					);
					expect(
						doc,
						`${route.slug} page scrolls sideways`,
					).toBeLessThanOrEqual(1);
					expect(
						await overflowers(page, vp.width),
						`${route.slug} content past the fold`,
					).toEqual([]);
				}

				const real = errors.filter(
					(e) => !/favicon|manifest|Failed to load resource/i.test(e),
				);
				expect(real, `console errors on ${route.slug}`).toEqual([]);
			});
		}
	});
}
