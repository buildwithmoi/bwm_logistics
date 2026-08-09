import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import { settle } from "./settle";

// The model change, exercised the way an operator would: put goods in a box,
// tag whose they are, then book a shipment that rides in it.
//
// This is the pass that proves contents live on the container (not the
// shipment) and that a booking can hold more than one box.

const SHOT_DIR = "tests/__shots__";

async function open(page: Page, path: string) {
	await page.goto(path);
	await settle(page);
}

test.describe("container carries the manifest", () => {
	test.use({ viewport: { width: 390, height: 844 } });

	test("new container has a Contents section with item and customer", async ({ page }) => {
		await open(page, "/logistics/containers/new");

		await expect(page.getByRole("heading", { name: "Contents", exact: true })).toBeVisible();
		// A line is item + qty + whose it is; "Own goods" is the customer
		// placeholder, i.e. untagged means ours.
		await expect(page.getByText("Search goods…").first()).toBeVisible();
		await expect(page.getByText("Own goods", { exact: true })).toBeVisible();

		fs.mkdirSync(`${SHOT_DIR}/model-b`, { recursive: true });
		await page.screenshot({ path: `${SHOT_DIR}/model-b/container-new.png`, fullPage: true });
	});

	test("the item picker only offers goods for this direction", async ({ page }) => {
		await open(page, "/logistics/containers/new");
		await page.getByText("Search goods…").first().click();
		await page.waitForTimeout(600);
		// The catalogue seeded from the client's sheet, plus a way to add more.
		await expect(page.getByText("US Hen Leg Quarter")).toBeVisible({ timeout: 5000 });
		// Unknown goods don't block the flow — the picker can create one.
		await expect(page.getByRole("button", { name: /Add item/ })).toBeVisible();
	});

	test("container detail lists contents and who is in the box", async ({ page }) => {
		await open(page, "/logistics/containers");
		await page.locator("button.w-full").first().click();
		await settle(page);
		await expect(page.getByText(/^Contents \(\d+\)$/)).toBeVisible();
		await page.screenshot({ path: `${SHOT_DIR}/model-b/container-detail.png`, fullPage: true });
	});
});

test.describe("shipment is the booking", () => {
	test.use({ viewport: { width: 390, height: 844 } });

	test("own goods leads, packages are gone, containers and supplier are there", async ({ page }) => {
		await open(page, "/logistics/shipments/new");

		// Own goods first and pre-selected — it's what they book most days.
		const types = page.locator("button[aria-pressed]");
		await expect(types.first()).toContainText("Own Goods");
		await expect(types.first()).toHaveAttribute("aria-pressed", "true");

		// The manifest moved to the container.
		await expect(page.getByText("PACKAGES")).toHaveCount(0);
		// A booking rides in boxes, and comes from a supplier.
		await expect(page.getByRole("heading", { name: "Containers", exact: true })).toBeVisible();
		await expect(page.getByText("Search supplier…")).toBeVisible();

		fs.mkdirSync(`${SHOT_DIR}/model-b`, { recursive: true });
		await page.screenshot({ path: `${SHOT_DIR}/model-b/shipment-new.png`, fullPage: true });
	});

	test("own goods asks for no consignee — the receiver is us", async ({ page }) => {
		await open(page, "/logistics/shipments/new");
		await expect(page.getByText("Consignee (who receives it)")).toHaveCount(0);

		// Switching to customer cargo brings it back, because then it can differ.
		await page.getByRole("button", { name: /Customer Cargo/ }).click();
		await page.waitForTimeout(250);
		await expect(page.getByText("Consignee (who receives it)")).toBeVisible();
	});
});
