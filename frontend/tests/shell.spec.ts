import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import { useFixtures } from "./fixtures";

// Guards the shell contract the operator app depends on:
//   - one menu button, on every breakpoint, opening the full nav
//   - the logo sits in the top-right; no avatar, no "Switch to Desk"
//   - the bottom bar is four plain tabs — no Scan, no Stock, no More
//   - /scan is gone and falls back to the dashboard
const SHOT_DIR = "tests/__shots__";

async function open(page: Page, path = "/logistics/") {
	await useFixtures(page);
	await page.goto(path);
	await page.waitForLoadState("networkidle").catch(() => {});
	await page.waitForTimeout(300);
}

test.describe("top bar", () => {
	test.use({ viewport: { width: 390, height: 844 } });

	test("menu opens the drawer with every page and log out", async ({
		page,
	}) => {
		await open(page);
		await page.getByRole("button", { name: "Open menu" }).click();
		const drawer = page.getByRole("complementary", { name: "All pages" });
		await expect(drawer).toBeVisible();

		for (const label of [
			"Dashboard",
			"Containers",
			"Shipments",
			"Dispatch",
			"Customers",
			"Billing",
			"Stock",
			"Reports",
			"Notifications",
			"Settings",
		]) {
			await expect(
				drawer.getByRole("link", { name: label, exact: true }),
			).toBeVisible();
		}
		await expect(drawer.getByRole("button", { name: "Log out" })).toBeVisible();
		await expect(drawer.getByText("Switch to Desk")).toHaveCount(0);
		await expect(
			drawer.getByRole("link", { name: "Scan", exact: true }),
		).toHaveCount(0);

		fs.mkdirSync(`${SHOT_DIR}/shell`, { recursive: true });
		await page.screenshot({ path: `${SHOT_DIR}/shell/drawer-phone.png` });

		await page.keyboard.press("Escape");
		await expect(drawer).toBeHidden();
	});

	test("logo replaces the avatar in the right corner", async ({ page }) => {
		await open(page);
		const brand = page.getByRole("link", { name: /home$/ });
		await expect(brand).toBeVisible();

		// It really is on the right: past the horizontal midpoint of the bar.
		const box = (await brand.boundingBox())!;
		expect(box.x).toBeGreaterThan(390 / 2);

		// No account/avatar control survives.
		await expect(page.locator("header img.rounded-full")).toHaveCount(0);
	});

	test("bottom tabs are four, without Scan, Stock or More", async ({
		page,
	}) => {
		await open(page);
		const bar = page.getByRole("navigation", { name: "Sections" });
		await expect(bar).toBeVisible();
		await expect(bar.getByRole("link")).toHaveCount(4);
		for (const gone of ["Scan", "Stock", "More"]) {
			await expect(bar.getByText(gone, { exact: true })).toHaveCount(0);
		}
		await expect(bar.getByRole("button")).toHaveCount(0);
	});
});

test.describe("desktop shell", () => {
	test.use({ viewport: { width: 1440, height: 900 } });

	test("menu button is available on desktop too", async ({ page }) => {
		await open(page);
		await page.getByRole("button", { name: "Open menu" }).click();
		await expect(
			page.getByRole("complementary", { name: "All pages" }),
		).toBeVisible();
		fs.mkdirSync(`${SHOT_DIR}/shell`, { recursive: true });
		await page.screenshot({ path: `${SHOT_DIR}/shell/drawer-desktop.png` });
	});

	test("the scan route is gone", async ({ page }) => {
		await open(page, "/logistics/scan");
		await expect(page).toHaveURL(/\/logistics\/$/);
	});
});
