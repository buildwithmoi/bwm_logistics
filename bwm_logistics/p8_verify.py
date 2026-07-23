# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""P8 backend smoke verification — run with:

    bench --site local16.6 execute bwm_logistics.p8_verify.run

Covers stock & distribution (unit field, balance math, over-distribution
block, package-rename integrity guard, invoice conversion feeding the P&L,
role gates), the Offloaded/Delayed milestones, the Stock access page key, and
the PWA plumbing (renderer hook + built files + headers).
"""

import json
import os

import frappe
from frappe.utils import flt

results = []

OPS_USER = "ops@bwm-demo.test"
ACCOUNTS_USER = "accounts@bwm-demo.test"


def check(label, ok, detail=""):
	results.append(f"{'PASS' if ok else 'FAIL'}  {label}" + (f" — {detail}" if detail else ""))
	return ok


def _make_customer(name):
	existing = frappe.db.get_value("Customer", {"customer_name": name}, "name")
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": name,
			"customer_type": "Individual",
			"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}) or "All Customer Groups",
			"territory": frappe.db.get_value("Territory", {"is_group": 0}) or "All Territories",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def run():
	results.clear()
	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True
	from bwm_logistics.install import after_install, ensure_p8_milestones

	after_install()

	from bwm_logistics.api import access, billing, stock
	from bwm_logistics.api.dashboard import get_overview
	from bwm_logistics.api.shipments import get_shipment, save_shipment

	# ── unit field roundtrip via the SPA API ─────────────────────────────────
	ship_name = save_shipment(
		{
			"shipment_type": "Own Goods (Trading)",
			"direction": "Import",
			"packages": [
				{"description": "P8 Hen Leg Quarter", "qty": 2568, "unit": "PIECES"},
				{"description": "P8 Frozen Hake", "qty": 400, "unit": "CARTONS"},
			],
		}
	)["name"]
	doc = get_shipment(ship_name)
	units = {p["description"]: p["unit"] for p in doc["packages"]}
	check(
		"package unit roundtrip (PIECES + CARTONS)",
		units.get("P8 Hen Leg Quarter") == "PIECES" and units.get("P8 Frozen Hake") == "CARTONS",
		str(units),
	)

	# ── distribution: balances + the Excel reconciliation ────────────────────
	for recipient, qty in (("Truck 1", 1496), ("Truck 2", 600), ("Ella", 200), ("Storage", 272)):
		stock.record_distribution(
			{"shipment": ship_name, "product": "P8 Hen Leg Quarter", "qty": qty, "recipient": recipient}
		)
	bal = stock.shipment_stock_balance(ship_name)
	hen = next(line for line in bal["lines"] if line["product"] == "P8 Hen Leg Quarter")
	check(
		"balance math: 1496+600+200+272 = 2568 → 0 remaining",
		hen["distributed"] == 2568 and hen["remaining"] == 0 and bal["remaining_total"] == 400,
		f"hen remaining={hen['remaining']} total remaining={bal['remaining_total']}",
	)

	# over-distribution blocked
	try:
		stock.record_distribution(
			{"shipment": ship_name, "product": "P8 Hen Leg Quarter", "qty": 1, "recipient": "Oops"}
		)
		blocked = False
	except frappe.ValidationError:
		blocked = True
	check("over-distribution blocked", blocked)

	# unknown product blocked
	try:
		stock.record_distribution(
			{"shipment": ship_name, "product": "Not A Product", "qty": 1, "recipient": "X"}
		)
		blocked = False
	except frappe.ValidationError:
		blocked = True
	check("unknown product blocked", blocked)

	# customer-cargo shipments rejected
	cargo_customer = _make_customer("P8 Cargo Customer")
	cargo = save_shipment(
		{
			"customer": cargo_customer,
			"direction": "Import",
			"packages": [{"description": "Box", "qty": 5}],
		}
	)["name"]
	try:
		stock.record_distribution({"shipment": cargo, "product": "Box", "qty": 1, "recipient": "X"})
		blocked = False
	except frappe.ValidationError:
		blocked = True
	check("distribution on customer cargo blocked", blocked)

	# ── row-churn resilience + integrity guard ───────────────────────────────
	save_shipment(
		{
			"name": ship_name,
			"packages": [
				{"description": "P8 Hen Leg Quarter", "qty": 2568, "unit": "PIECES"},
				{"description": "P8 Frozen Hake", "qty": 400, "unit": "CARTONS"},
			],
		}
	)
	bal2 = stock.shipment_stock_balance(ship_name)
	check(
		"balances survive package-row rewrite",
		bal2["distributed_total"] == 2568 and bal2["remaining_total"] == 400,
		f"distributed={bal2['distributed_total']}",
	)
	try:
		save_shipment(
			{"name": ship_name, "packages": [{"description": "Renamed Product", "qty": 2568}]}
		)
		blocked = False
	except frappe.ValidationError:
		blocked = True
	check("renaming a distributed package blocked", blocked)

	# ── invoice conversion feeds the P&L ─────────────────────────────────────
	buyer = _make_customer("P8 Wholesale Buyer")
	entry = stock.record_distribution(
		{
			"shipment": ship_name,
			"product": "P8 Frozen Hake",
			"qty": 100,
			"recipient": "P8 Wholesale Buyer",
			"customer": buyer,
			"unit_price": 25,
		}
	)["name"]
	res = stock.invoice_distribution(entry)
	pnl = billing.shipment_pnl(ship_name)
	check(
		"distribution → invoice (2500) lands in shipment P&L",
		flt(res["grand_total"]) == 2500 and flt(pnl["revenue"]) >= 2500,
		f"invoice={res['sales_invoice']} revenue={pnl['revenue']}",
	)
	try:
		stock.invoice_distribution(entry)
		blocked = False
	except frappe.ValidationError:
		blocked = True
	check("double-invoicing blocked", blocked)
	try:
		stock.delete_distribution(entry)
		blocked = False
	except frappe.ValidationError:
		blocked = True
	check("deleting an invoiced entry blocked", blocked)

	# ── role gates ───────────────────────────────────────────────────────────
	frappe.set_user(OPS_USER)
	ops_ok, ops_blocked = False, False
	try:
		e2 = stock.record_distribution(
			{"shipment": ship_name, "product": "P8 Frozen Hake", "qty": 5, "recipient": "Ops Truck"}
		)["name"]
		stock.delete_distribution(e2)
		ops_ok = True
	except frappe.PermissionError:
		pass
	try:
		stock.invoice_distribution(entry)
	except (frappe.PermissionError, frappe.ValidationError) as e:
		ops_blocked = isinstance(e, frappe.PermissionError)
	frappe.set_user("Administrator")
	check("Operations can record/delete distributions", ops_ok)
	check("Operations blocked from invoicing", ops_blocked)

	perms = access.user_perms(OPS_USER)
	check("'stock' page resolves for Operations", "stock" in perms, f"{len(perms)} pages")

	# ── stock overview + dashboard ───────────────────────────────────────────
	# Arrive the shipment first — the products aggregate only counts landed stock.
	frappe.get_doc(
		{"doctype": "Tracking Event", "shipment": ship_name, "milestone": "Arrived at Port", "notify": 0}
	).insert(ignore_permissions=True)
	overview = stock.stock_overview()
	hake = next(
		(p for p in overview["products"] if p["product"] == "P8 Frozen Hake" and p["unit"] == "CARTONS"),
		None,
	)
	check(
		"stock_overview aggregates products",
		bool(hake) and {"incoming", "shipments", "products"} <= set(overview),
		str(hake),
	)
	dash = get_overview()
	check("dashboard has stock_on_hand", "stock_on_hand" in dash, str(dash.get("stock_on_hand", {}).get("product_count")))

	# ── milestones: Offloaded/Delayed ────────────────────────────────────────
	ensure_p8_milestones()
	ensure_p8_milestones()  # idempotent
	tmpl = frappe.get_doc("Milestone Template", "Standard Import")
	names = [r.milestone for r in tmpl.milestones]
	check(
		"Offloaded after Customs Clearance, Delayed present, no dupes",
		names.count("Offloaded") == 1
		and names.count("Delayed") == 1
		and names.index("Offloaded") == names.index("Customs Clearance") + 1,
		str(names),
	)

	frappe.get_doc(
		{"doctype": "Tracking Event", "shipment": ship_name, "milestone": "Offloaded", "notify": 0}
	).insert(ignore_permissions=True)
	status_after = frappe.db.get_value("Shipment", ship_name, "status")
	check("Offloaded → status Arrived", status_after == "Arrived", status_after)

	frappe.get_doc(
		{"doctype": "Tracking Event", "shipment": ship_name, "milestone": "Delayed", "notify": 0}
	).insert(ignore_permissions=True)
	after = frappe.db.get_value("Shipment", ship_name, ["status", "current_milestone"], as_dict=True)
	check(
		"Delayed → milestone set, status unchanged",
		after.status == "Arrived" and after.current_milestone == "Delayed",
		f"{after.status}/{after.current_milestone}",
	)

	# ── PWA plumbing ─────────────────────────────────────────────────────────
	check(
		"PWARenderer registered in page_renderer hooks",
		"bwm_logistics.pwa.PWARenderer" in (frappe.get_hooks("page_renderer") or []),
	)
	dist = frappe.get_app_path("bwm_logistics", "public", "dist", "main")
	built = {f: os.path.exists(os.path.join(dist, f)) for f in ("sw.js", "manifest.webmanifest", "offline.html")}
	icons_ok = all(
		os.path.exists(os.path.join(dist, "icons", f))
		for f in ("pwa-192x192.png", "pwa-512x512.png", "pwa-maskable-512x512.png", "apple-touch-icon.png")
	)
	check("PWA files built (sw.js, manifest, offline, icons)", all(built.values()) and icons_ok, str(built))

	if built["manifest.webmanifest"]:
		with open(os.path.join(dist, "manifest.webmanifest")) as f:
			manifest = json.load(f)
		check(
			"manifest scope/start_url = /logistics",
			manifest.get("scope") == "/logistics" and manifest.get("start_url") == "/logistics",
			f"scope={manifest.get('scope')}",
		)
	if built["sw.js"]:
		with open(os.path.join(dist, "sw.js")) as f:
			sw = f.read()
		# navigateFallback must stay off (it would bind base+index.html, which
		# is never emitted); the offline fallback rides on precacheFallback.
		check(
			"sw.js: no navigateFallback binding, offline fallback wired",
			"/assets/bwm_logistics/dist/main/index.html" not in sw
			and "fallbackURL" in sw
			and "offline.html" in sw,
			f"{len(sw)} bytes",
		)

	# renderer unit check (headers + content type)
	from bwm_logistics.pwa import PWARenderer

	frappe.local.path = "logistics/sw.js"
	old_request = getattr(frappe.local, "request", None)
	frappe.local.request = frappe._dict(path="/logistics/sw.js")
	try:
		renderer = PWARenderer("logistics")
		can = renderer.can_render()
		if can:
			resp = renderer.render()
			check(
				"renderer serves sw.js with Service-Worker-Allowed",
				resp.headers.get("Service-Worker-Allowed") == "/logistics"
				and resp.content_type.startswith("text/javascript"),
				resp.content_type,
			)
		else:
			check("renderer serves sw.js with Service-Worker-Allowed", False, "can_render() False (bundle built?)")
	finally:
		if old_request is not None:
			frappe.local.request = old_request

	frappe.db.commit()
	print("\n".join(results))
	failed = len([r for r in results if r.startswith("FAIL")])
	print(f"\n{len(results) - failed}/{len(results)} checks passed")
	return {"passed": len(results) - failed, "failed": failed}
