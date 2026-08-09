import { expect, type Page } from "@playwright/test";

/**
 * Wait until the SPA has actually finished, and say so if it hasn't.
 *
 * The earlier version swallowed its own timeout, so a page still showing
 * "Loading…" screenshotted as a blank panel and every assertion after it ran
 * against a half-rendered DOM — the screenshots looked fine to the test and
 * wrong to a human. A stuck page is a real failure and should read like one.
 */
export async function settle(page: Page) {
	await page.waitForLoadState("networkidle").catch(() => {});
	await expect(
		page.getByText(/^Loading…$/),
		"page was still loading after 10s",
	).toHaveCount(0, { timeout: 10_000 });
	await page.waitForTimeout(250); // let transitions and charts paint
}
