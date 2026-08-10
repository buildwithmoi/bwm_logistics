import { test, expect } from "@playwright/test";
import fs from "node:fs";
import { settle } from "./settle";

// The app used to spell its own name into the source in six places, so a client
// site called itself by ours. It now comes from Logistics Settings, falling back
// to the ERPNext company on the site — and when nobody has uploaded a logo, the
// mark is the first letter of that name.

const SHOT_DIR = "tests/__shots__";

async function branding(page: import("@playwright/test").Page) {
	return page.evaluate(async () => {
		const res = await fetch("/api/method/bwm_logistics.api.settings.get_branding", {
			headers: { Accept: "application/json" },
		});
		return (await res.json())?.message as { business_name: string; logo: string | null; monogram: string };
	});
}

test.describe("the app wears the tenant's name", () => {
	test.use({ viewport: { width: 390, height: 844 } });

	test("no BWM Logistics anywhere in the shell", async ({ page }) => {
		await page.goto("/logistics/");
		await settle(page);
		const text = await page.locator("body").innerText();
		expect(text, "the app named itself in the source again").not.toContain("BWM Logistics");
	});

	test("the shell shows the configured business name", async ({ page }) => {
		await page.goto("/logistics/");
		await settle(page);
		const b = await branding(page);
		expect(b.business_name).toBeTruthy();

		// Open the drawer — the name is always rendered there, at every width.
		// Filter to visible: the header also renders it in an `lg:inline` span
		// that is hidden at this width but matches first in DOM order.
		await page.getByRole("button", { name: /menu/i }).first().click();
		await page.waitForTimeout(400);
		await expect(page.getByText(b.business_name).filter({ visible: true }).first()).toBeVisible();

		fs.mkdirSync(`${SHOT_DIR}/branding`, { recursive: true });
		await page.screenshot({ path: `${SHOT_DIR}/branding/drawer.png` });
	});

	test("with no logo the mark is the first letter of the name", async ({ page }) => {
		await page.goto("/logistics/");
		await settle(page);
		const b = await branding(page);
		test.skip(!!b.logo, "this site has a logo uploaded");

		expect(b.monogram).toBe(b.business_name.trim().charAt(0).toUpperCase());
		// And it is on the page, not just in the payload.
		const mark = page.locator("header").getByText(b.monogram, { exact: true });
		await expect(mark.first()).toBeVisible();
	});

	test("the tab title and installed-app name follow settings too", async ({ page }) => {
		await page.goto("/logistics/");
		await settle(page);
		const b = await branding(page);
		await expect(page).toHaveTitle(b.business_name);

		// The manifest is served through Frappe precisely so it can be branded.
		const manifest = await page.evaluate(async () => {
			const res = await fetch("/logistics/manifest.webmanifest");
			return res.json();
		});
		expect(manifest.name).toBe(b.business_name);
	});

	test("the public website carries it as well", async ({ page }) => {
		await page.goto("/");
		await page.waitForLoadState("domcontentloaded");
		const text = await page.locator("body").innerText();
		expect(text).not.toContain("BWM Logistics");
	});
});
