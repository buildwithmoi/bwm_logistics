import { test, expect, type Page } from "@playwright/test";
import { settle } from "./settle";
import { useFixtures, EMPTY_RESPONSES, LEAKY_PORTAL } from "./fixtures";
import { PORTAL_STATE } from "../playwright.config";

// The rules that keep screens from silting up again. Each one encodes a bug we
// actually shipped, so a regression reads as a failure rather than as a slightly
// longer page nobody notices.

const PHONE = { width: 390, height: 844 };

async function open(page: Page, path: string) {
	await page.goto(path);
	await settle(page);
}

/** Open the first record in a list the way a user does. */
async function openFirst(page: Page, list: string) {
	await page.goto(list);
	await settle(page);
	await page.locator("button.w-full").first().click();
	await settle(page);
}

test.describe("detail screens answer a question", () => {
	test.use({ viewport: PHONE });

	// The finding this whole pass came from: Voyage details rendered 11 rows,
	// 8 of them em-dashes, and the reader had to hunt for the 3 that spoke.
	for (const [slug, list] of [
		["container", "/logistics/containers"],
		["shipment", "/logistics/shipments"],
	] as const) {
		test(`${slug}: at most a quarter of rows are em-dashes`, async ({ page }) => {
			await openFirst(page, list);
			const { total, blank, labels } = await page.evaluate(() => {
				const rows = [...document.querySelectorAll("main dl > div")];
				const blanks = rows.filter((r) => /^[—–\-/\s]*$/.test(r.querySelector("dd")?.textContent || ""));
				return {
					total: rows.length,
					blank: blanks.length,
					labels: blanks.map((r) => r.querySelector("dt")?.textContent?.trim() || "?"),
				};
			});
			if (!total) return; // nothing recorded at all — the collapse path
			expect(blank / total, `${blank}/${total} rows are blank: ${labels.join(", ")}`).toBeLessThanOrEqual(0.25);
		});

		test(`${slug}: no run of consecutive blank rows`, async ({ page }) => {
			await openFirst(page, list);
			const longestRun = await page.evaluate(() => {
				const rows = [...document.querySelectorAll("main dl > div")];
				let run = 0;
				let worst = 0;
				for (const r of rows) {
					const blank = /^[—–\-/\s]*$/.test(r.querySelector("dd")?.textContent || "");
					run = blank ? run + 1 : 0;
					worst = Math.max(worst, run);
				}
				return worst;
			});
			expect(longestRun, "consecutive em-dashes").toBeLessThanOrEqual(1);
		});
	}
});

test.describe("list screens carry no dead columns", () => {
	test.use({ viewport: { width: 1440, height: 900 } });

	for (const [slug, path] of [
		["containers", "/logistics/containers"],
		["shipments", "/logistics/shipments"],
		["customers", "/logistics/customers"],
	] as const) {
		test(`${slug}: every column varies`, async ({ page }) => {
			await useFixtures(page);
			await open(page, path);

			const dead = await page.evaluate(() => {
				const table = document.querySelector("main table");
				if (!table) return [];
				const heads = [...table.querySelectorAll("thead th")].map((th) => th.textContent?.trim() || "");
				const bodyRows = [...table.querySelectorAll("tbody tr")];
				if (bodyRows.length < 2) return [];
				const out: string[] = [];
				heads.forEach((label, i) => {
					if (!label) return; // action columns legitimately repeat
					const values = bodyRows.map((r) => r.children[i]?.textContent?.trim() || "");
					if (new Set(values).size === 1) out.push(`${label} = "${values[0]}"`);
				});
				return out;
			});
			expect(dead, `${slug} has columns identical in every row`).toEqual([]);
		});
	}

	test("one filter bar, and never two controls labelled All", async ({ page }) => {
		await useFixtures(page);
		await open(page, "/logistics/containers");
		const alls = await page.evaluate(
			() =>
				[...document.querySelectorAll("main button")].filter(
					(b) => (b.textContent || "").trim().toLowerCase() === "all",
				).length,
		);
		expect(alls, 'two pill rows each starting with "All"').toBeLessThanOrEqual(1);
	});
});

test.describe("empty states name the next action", () => {
	test.use({ viewport: PHONE });

	for (const [slug, path] of [
		["dashboard", "/logistics/"],
		["containers", "/logistics/containers"],
		["shipments", "/logistics/shipments"],
		["billing", "/logistics/billing"],
	] as const) {
		test(`${slug} on a fresh site`, async ({ page }) => {
			await useFixtures(page, EMPTY_RESPONSES);
			await open(page, path);
			const text = (await page.locator("main").innerText()).toLowerCase();
			// "No data" tells the reader nothing they can act on.
			expect(text, `${slug} says "no data"`).not.toContain("no data");
			// A card whose whole content is a zero is a statement that nothing
			// happened, dressed as a figure.
			const zeroCards = await page.evaluate(
				() =>
					[...document.querySelectorAll("main .rounded-2xl")].filter((c) =>
						/^0(\.00)?$/.test((c as HTMLElement).innerText.trim()),
					).length,
			);
			expect(zeroCards, `${slug} has a card containing only a zero`).toBe(0);
		});
	}
});

// The portal is a different tenant's window onto our data. Cost, margin,
// supplier and purchase totals are ours, not theirs — a leak here is a bug
// class, not a design preference.
test.describe("customer portal never shows our costs", () => {
	// A real customer session: a staff one is bounced to the dashboard, which
	// would make every assertion below pass without ever loading the portal.
	test.use({ viewport: PHONE, storageState: PORTAL_STATE });

	const SECRETS = ["margin", "supplier", "purchase", "profit", "cost price"];

	for (const path of [
		"/logistics/portal",
		"/logistics/portal/shipments",
		"/logistics/portal/invoices",
		"/logistics/portal/pickups",
	]) {
		test(`${path} leaks nothing`, async ({ page }) => {
			// Fixtures deliberately return the forbidden keys; if the page reads
			// any of them, it renders and this fails.
			await useFixtures(page, LEAKY_PORTAL);
			await open(page, path);
			const text = (await page.locator("body").innerText()).toLowerCase();
			for (const word of SECRETS) {
				expect(text, `"${word}" reached the portal DOM`).not.toContain(word);
			}
			expect(text, "a supplier name reached the portal DOM").not.toContain("shanghai poultry co");
		});
	}
});
