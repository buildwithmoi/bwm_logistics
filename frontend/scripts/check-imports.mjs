// Every component used in a template must be imported.
//
// Vue renders an unimported `<Trash2 />` as an unknown HTML element: no build
// error, no type error, just a control that quietly isn't there. Both instances
// this found had survived a typecheck and a production build.
//
//   node scripts/check-imports.mjs
import fs from "node:fs";
import path from "node:path";

const BUILT_IN =
	/^(template|component|slot|transition|Transition|TransitionGroup|Teleport|Suspense|KeepAlive|RouterLink|RouterView)$/;

function walk(dir) {
	return fs
		.readdirSync(dir, { withFileTypes: true })
		.flatMap((e) => (e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)]));
}

let failures = 0;
for (const file of walk("src").filter((f) => f.endsWith(".vue"))) {
	const src = fs.readFileSync(file, "utf8");
	const split = src.indexOf("</script>");
	if (split < 0) continue;
	const script = src.slice(0, split);
	const template = src.slice(split);

	const used = new Set([...template.matchAll(/<([A-Z][A-Za-z0-9]*)/g)].map((m) => m[1]));
	const missing = [...used].filter(
		(name) => !BUILT_IN.test(name) && !new RegExp(`\\b${name}\\b`).test(script),
	);
	if (missing.length) {
		console.error(`${file}: used in template but never imported — ${missing.join(", ")}`);
		failures++;
	}
}

if (failures) {
	console.error(`\n${failures} file(s) with unimported components.`);
	process.exit(1);
}
console.log("check-imports: every component in a template is imported");
