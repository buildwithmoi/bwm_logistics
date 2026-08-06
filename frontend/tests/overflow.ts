import type { Page } from "@playwright/test";

// Measuring sideways overflow correctly is fiddly here, and getting it wrong is
// worse than not checking at all.
//
// The shell scrolls inside `<main>`, not on the document, so
// `documentElement.scrollWidth` never grows no matter how far a form field
// spills — the document check alone always passes. And because `main` is
// `overflow-y: auto`, its *computed* `overflow-x` is `auto` too, so a naive
// "skip anything inside a scroller" walk skips the entire page.
//
// So: measure the scroll container itself, and when it does overflow, name the
// widest elements that stick out past it.

export interface Overflow {
	scrollWidth: number;
	clientWidth: number;
	px: number;
	offenders: string[];
}

export async function measureOverflow(page: Page): Promise<Overflow> {
	return page.evaluate(() => {
		const main = document.querySelector("main") || document.body;
		const doc = document.documentElement;
		const px = Math.max(
			main.scrollWidth - main.clientWidth,
			doc.scrollWidth - doc.clientWidth,
		);
		const offenders: string[] = [];
		if (px > 1) {
			const limit = main.getBoundingClientRect().right;
			for (const el of Array.from(main.querySelectorAll<HTMLElement>("*"))) {
				const r = el.getBoundingClientRect();
				if (r.width === 0 || r.height === 0) continue;
				if (r.right <= limit + 1) continue;
				// A child of a genuine horizontal scroller (a .chip-row, a wide
				// table) is allowed to be wider than the viewport.
				let p: HTMLElement | null = el.parentElement;
				let inScroller = false;
				while (p && p !== main) {
					if (p.scrollWidth > p.clientWidth + 1 && getComputedStyle(p).overflowX !== "visible") {
						inScroller = true;
						break;
					}
					p = p.parentElement;
				}
				if (inScroller) continue;
				const cls = String(el.className).slice(0, 60);
				offenders.push(`${el.tagName.toLowerCase()}.${cls} (w=${Math.round(r.width)})`);
			}
		}
		return { scrollWidth: main.scrollWidth, clientWidth: main.clientWidth, px, offenders: offenders.slice(0, 6) };
	});
}
