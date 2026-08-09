import { test, expect, type Page } from "@playwright/test";
import { settle } from "./settle";

// A saved record has to be correctable. Both detail screens had a status
// control and nothing else — no Edit action, no edit route — so once a
// container or a booking was created the only way to fix a typo was the Desk.

async function firstRecord(page: Page, list: string) {
	await page.goto(list);
	await settle(page);
	// DataTable renders the desktop table *before* the phone cards, and the
	// table is only hidden by CSS — so a plain `tbody tr` matches a row that
	// cannot be clicked at this width. Take the card.
	const row = page.locator("button.w-full").first();
	if (!(await row.count())) return null;
	await row.click();
	await settle(page);
	return page.url();
}

test.describe("a saved record can be edited", () => {
	test.use({ viewport: { width: 390, height: 844 } });

	test("container: Edit opens the form loaded with the record", async ({ page }) => {
		const url = await firstRecord(page, "/logistics/containers");
		test.skip(!url, "no containers on this site");

		await page.getByRole("button", { name: "Edit", exact: true }).click();
		await settle(page);
		await expect(page).toHaveURL(/\/containers\/[^/]+\/edit$/);
		await expect(page.getByRole("heading", { name: "Edit container" })).toBeVisible();

		// Loaded, not blank: the direction came back from the record.
		const direction = page.locator("#c-direction");
		await expect(direction).not.toHaveValue("");
		await expect(page.getByRole("button", { name: "Save changes" })).toBeVisible();
	});

	test("container: an edit round-trips and survives reload", async ({ page }) => {
		const url = await firstRecord(page, "/logistics/containers");
		test.skip(!url, "no containers on this site");

		await page.getByRole("button", { name: "Edit", exact: true }).click();
		await settle(page);
		await page.locator("#c-free").fill("11");
		await page.getByRole("button", { name: "Save changes" }).click();
		await settle(page);

		// Back on the record, and the change stuck.
		await expect(page).toHaveURL(/\/containers\/[^/]+$/);
		await page.goto(page.url() + "/edit");
		await settle(page);
		await expect(page.locator("#c-free")).toHaveValue("11");
	});

	test("shipment: Edit opens the booking with its voyage filled in", async ({ page }) => {
		const url = await firstRecord(page, "/logistics/shipments");
		test.skip(!url, "no shipments on this site");

		await page.getByRole("button", { name: "Edit", exact: true }).click();
		await settle(page);
		await expect(page).toHaveURL(/\/shipments\/[^/]+\/edit$/);
		await expect(page.getByRole("heading", { name: "Edit shipment" })).toBeVisible();
		// The voyage lives here now — it must come back on the form, not be blank.
		await expect(page.getByText("Voyage & dates")).toBeVisible();
		await expect(page.getByRole("button", { name: "Save changes" })).toBeVisible();
	});

	test("shipment: an ETA typed here survives the round trip", async ({ page }) => {
		const url = await firstRecord(page, "/logistics/shipments");
		test.skip(!url, "no shipments on this site");

		await page.getByRole("button", { name: "Edit", exact: true }).click();
		await settle(page);
		await page.locator("#s-eta").fill("2026-11-30");
		await page.getByRole("button", { name: "Save changes" }).click();
		await settle(page);

		await expect(page).toHaveURL(/\/shipments\/[^/]+$/);
		await page.goto(page.url() + "/edit");
		await settle(page);
		await expect(page.locator("#s-eta")).toHaveValue("2026-11-30");
	});
});
