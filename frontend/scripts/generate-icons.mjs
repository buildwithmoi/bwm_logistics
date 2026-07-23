// One-time PWA icon generation: rasterizes public/brand-icon.svg into the
// committed PNGs under public/icons/. Run `yarn icons` after changing the
// brand mark; sharp is a devDependency only — builds never need it.
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const root = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(root, "../public/brand-icon.svg");
const out = path.join(root, "../public/icons");
await mkdir(out, { recursive: true });

// Regular icons — the rounded-rect artwork as-is.
for (const size of [192, 512]) {
	await sharp(src).resize(size, size).png().toFile(path.join(out, `pwa-${size}x${size}.png`));
	console.log(`pwa-${size}x${size}.png`);
}

// Maskable — same art shrunk onto a full-bleed coal square so any mask shape
// (circle, squircle) keeps the mark inside the safe zone.
const inner = await sharp(src).resize(410, 410).png().toBuffer();
await sharp({
	create: { width: 512, height: 512, channels: 4, background: "#0f0f10" },
})
	.composite([{ input: inner, gravity: "centre" }])
	.png()
	.toFile(path.join(out, "pwa-maskable-512x512.png"));
console.log("pwa-maskable-512x512.png");

// Apple touch icon — 180×180, opaque (iOS applies its own corner radius).
const apple = await sharp(src).resize(180, 180).png().toBuffer();
await sharp({
	create: { width: 180, height: 180, channels: 4, background: "#0f0f10" },
})
	.composite([{ input: apple }])
	.flatten({ background: "#0f0f10" })
	.png()
	.toFile(path.join(out, "apple-touch-icon.png"));
console.log("apple-touch-icon.png");
