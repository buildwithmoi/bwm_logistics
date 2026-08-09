import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
import { settle } from "./settle";
import { measureOverflow } from "./overflow";

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

// Stock is counted off the container manifest now. Before this, the Goods
// section read Shipment.packages — a table nothing writes to any more — so a
// booking made with the new form reported nothing received and offered nothing
// to distribute.
test.describe("goods are counted off the box", () => {
	/** The own-goods booking carrying the most, and what the list says it holds. */
	async function busiestOwnGoods(page: Page) {
		await open(page, "/logistics/shipments");
		return page.evaluate(async () => {
			const res = await fetch("/api/method/bwm_logistics.api.shipments.list_shipments?limit=100", {
				headers: { Accept: "application/json" },
			});
			const body = await res.json();
			const rows: Array<{ name: string; shipment_type?: string; total_packages?: number }> =
				body?.message?.rows || [];
			const own = rows
				.filter((r) => r.shipment_type === "Own Goods (Trading)")
				.sort((a, b) => (b.total_packages || 0) - (a.total_packages || 0));
			return own[0] ? { name: own[0].name, total: own[0].total_packages || 0 } : null;
		});
	}

	async function openGoods(page: Page, name: string) {
		await open(page, `/logistics/shipments/${name}`);
		const goods = page.getByRole("button", { name: "Goods", exact: true });
		if (!(await goods.count())) return false;
		await goods.click();
		await page.waitForTimeout(500);
		return true;
	}

	test("an own-goods booking reports what its container received", async ({ page }) => {
		const ship = await busiestOwnGoods(page);
		test.skip(!ship || ship.total <= 0, "no own-goods booking with goods on this site");
		test.skip(!(await openGoods(page, ship!.name)), "shipment has no Goods section");

		await expect(page.getByText("Stock & distribution")).toBeVisible();
		// "N of M distributed · X left". M is the manifest total, which must be
		// the same number the list shows — both come off the container now, and
		// reading the retired `packages` table made this 0 on every new booking.
		// The section summary, not a per-product caption: only the summary
		// carries the "· N left" tail.
		const summary = await page.getByText(/of [\d,.]+ distributed ·/).innerText();
		const received = Number(summary.match(/of ([\d,.]+) distributed/)?.[1]?.replace(/,/g, "") || 0);
		expect(received, `panel says ${received} received, the list says ${ship!.total}`).toBe(ship!.total);
	});

	test("the distribution ledger fits a phone", async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 844 });
		const ship = await busiestOwnGoods(page);
		test.skip(!ship, "no own-goods booking on this site");
		test.skip(!(await openGoods(page, ship!.name)), "shipment has no Goods section");

		// It used to be a table with min-w-[680px], which a phone had to scroll.
		const overflow = await measureOverflow(page);
		expect(overflow.px, `overflows by ${overflow.px}px: ${overflow.offenders.join(", ")}`).toBeLessThanOrEqual(1);

		fs.mkdirSync(`${SHOT_DIR}/model-b`, { recursive: true });
		await page.screenshot({ path: `${SHOT_DIR}/model-b/shipment-goods.png`, fullPage: true });
	});
});
