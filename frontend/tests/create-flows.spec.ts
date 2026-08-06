import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import { useFixtures } from "./fixtures";
import { measureOverflow } from "./overflow";

// Two things this guards:
//
// 1. The big create flows are pages. Every "New …" button navigates to a real
//    URL — no dialog — and that URL survives a reload and browser Back.
// 2. The dialogs that remain are the small ones, and they still fit a phone.
//    Dialog contents only exist once opened, so the route sweep never sees
//    them; this opens each and measures.

const SHOT_DIR = "tests/__shots__";

async function open(page: Page, path: string) {
	await useFixtures(page);
	await page.goto(path);
	await page.waitForLoadState("networkidle").catch(() => {});
	await page.waitForTimeout(300);
}

test.describe("create screens are pages", () => {
	test.use({ viewport: { width: 1440, height: 900 } });

	const FLOWS = [
		{ from: "/logistics/containers", button: "New container", url: /\/containers\/new$/, heading: "New container" },
		{ from: "/logistics/shipments", button: "New shipment", url: /\/shipments\/new$/, heading: "New shipment" },
		{ from: "/logistics/dispatch", button: "New run", url: /\/dispatch\/new$/, heading: "New delivery run" },
		{ from: "/logistics/billing?tab=sales", button: "New invoice", url: /\/billing\/invoice\/new$/, heading: "New invoice" },
		{ from: "/logistics/billing?tab=purchases", button: "Record purchase", url: /\/billing\/purchase\/new$/, heading: "Record purchase" },
	];

	for (const f of FLOWS) {
		test(`${f.button} opens a page`, async ({ page }) => {
			await open(page, f.from);
			await page.getByRole("button", { name: f.button }).first().click();
			await expect(page).toHaveURL(f.url);
			await expect(page.getByRole("heading", { name: f.heading, level: 1 })).toBeVisible();
			// No modal in sight — this is a page.
			await expect(page.locator("[role='dialog']")).toHaveCount(0);

			// The URL is real: reload lands on the same form.
			await page.reload();
			await page.waitForLoadState("networkidle").catch(() => {});
			await expect(page.getByRole("heading", { name: f.heading, level: 1 })).toBeVisible();

			// And Back returns to the list.
			await page.goBack();
			await expect(page).not.toHaveURL(f.url);
		});
	}
});

test.describe("remaining dialogs fit a phone", () => {
	test.use({ viewport: { width: 390, height: 844 } });

	const DIALOGS = [
		{ slug: "customer", path: "/logistics/customers", button: "New customer" },
		{ slug: "driver", path: "/logistics/dispatch", button: "New driver" },
		{ slug: "rate-card", path: "/logistics/billing?tab=ratecards", button: "New rate card" },
	];

	for (const d of DIALOGS) {
		test(`${d.slug} dialog`, async ({ page }) => {
			await open(page, d.path);
			await page.getByRole("button", { name: d.button }).first().click();
			await page.waitForTimeout(400); // let the dialog transition finish

			fs.mkdirSync(`${SHOT_DIR}/dialogs`, { recursive: true });
			await page.screenshot({ path: `${SHOT_DIR}/dialogs/${d.slug}.png` });

			const of = await measureOverflow(page);
			expect(of.offenders, `${d.slug} dialog is wider than the screen`).toEqual([]);
		});
	}
});
