import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import { measureOverflow } from "./overflow";

// Detail screens can only be reached by opening a record, so the route sweep
// never sees them. This walks in the way an operator does — tap a row — and
// captures what they actually land on, including the sheets behind the buttons.

const SHOT_DIR = "tests/__shots__";

const VIEWPORTS = [
	{ name: "phone", width: 390, height: 844 },
	{ name: "desktop", width: 1440, height: 900 },
];

async function settle(page: Page) {
	await page.waitForLoadState("networkidle").catch(() => {});
	await page
		.getByText(/^Loading…$/)
		.first()
		.waitFor({ state: "detached", timeout: 8000 })
		.catch(() => {});
	await page.waitForTimeout(400);
}

/** Open the first record in a list the way a user does. */
async function openFirst(page: Page, list: string, width: number) {
	await page.goto(list);
	await settle(page);
	const row = width < 768 ? page.locator("button.w-full").first() : page.locator("tbody tr").first();
	await row.click();
	await settle(page);
}

for (const vp of VIEWPORTS) {
	test.describe(`detail ${vp.name}`, () => {
		test.use({ viewport: { width: vp.width, height: vp.height } });

		for (const [slug, list] of [
			["container-detail", "/logistics/containers"],
			["shipment-detail", "/logistics/shipments"],
		] as const) {
			test(slug, async ({ page }) => {
				const errors: string[] = [];
				page.on("pageerror", (e) => errors.push(String(e)));

				await openFirst(page, list, vp.width);
				fs.mkdirSync(`${SHOT_DIR}/detail-${vp.name}`, { recursive: true });
				await page.screenshot({ path: `${SHOT_DIR}/detail-${vp.name}/${slug}.png`, fullPage: true });

				// Back must be a real, labelled control — not a bare arrow.
				const back = page.getByRole("button", { name: /Containers|Shipments/ }).first();
				await expect(back).toBeVisible();
				const box = (await back.boundingBox())!;
				expect(box.height, "back control is a 40px+ touch target").toBeGreaterThanOrEqual(36);

				if (vp.width <= 430) {
					const of = await measureOverflow(page);
					expect(of.offenders, `${slug} content wider than the screen`).toEqual([]);
				}
				expect(errors, `page errors on ${slug}`).toEqual([]);
			});
		}

		// The flow the operator could not find before: changing where a record is.
		test("status sheet offers real options", async ({ page }) => {
			await openFirst(page, "/logistics/shipments", vp.width);
			await page.getByRole("button", { name: /Update status|^Status$/ }).first().click();
			await page.waitForTimeout(450);

			const sheet = page.getByRole("dialog");
			await expect(sheet).toBeVisible();
			// Pickable milestones, not a free-text box you have to guess.
			const options = sheet.locator("input[type=radio]");
			expect(await options.count(), "milestones are offered as choices").toBeGreaterThan(3);

			fs.mkdirSync(`${SHOT_DIR}/detail-${vp.name}`, { recursive: true });
			await page.screenshot({ path: `${SHOT_DIR}/detail-${vp.name}/status-sheet.png` });

			if (vp.width <= 430) {
				const of = await measureOverflow(page);
				expect(of.offenders, "status sheet wider than the screen").toEqual([]);
			}
		});
	});
}
