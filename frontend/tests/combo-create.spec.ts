import { test, expect } from "@playwright/test";
import { settle } from "./settle";

// The create-new row in a picker names the new record after whatever has been
// typed into the search box. Clicking it with an empty box used to emit "" —
// and every caller returned silently, so the row looked like a button and did
// nothing at all. That is what "Add supplier does not open anything" was.

test.describe("picker create-new action", () => {
	test.use({ viewport: { width: 390, height: 844 } });

	test("says what it needs instead of doing nothing when nothing is typed", async ({ page }) => {
		await page.goto("/logistics/shipments/new");
		await settle(page);

		await page.getByText("Search supplier…").click();
		await page.waitForTimeout(500);

		// Not a live "Add supplier" that silently fails.
		await expect(page.getByText(/Type a name to add supplier/i)).toBeVisible();

		const before = page.url();
		await page.getByText(/Type a name to add supplier/i).click();
		await page.waitForTimeout(300);
		expect(page.url(), "clicking must not navigate away").toBe(before);
		// The dropdown stays open with the cursor back in the box, ready to type.
		await expect(page.locator("input:focus")).toHaveCount(1);
	});

	test("offers to create the typed name, and does", async ({ page }) => {
		await page.goto("/logistics/shipments/new");
		await settle(page);

		const name = "Playwright Supplier Probe";
		await page.getByText("Search supplier…").click();
		await page.locator("input:focus").fill(name);
		await page.waitForTimeout(700);

		const create = page.getByRole("button", { name: new RegExp(`Add supplier\\s*“?${name}`, "i") });
		await expect(create).toBeVisible();
		await create.click();
		await page.waitForTimeout(1200);

		// The picker now shows the supplier it just made.
		await expect(page.getByText(name).first()).toBeVisible();
	});
});
