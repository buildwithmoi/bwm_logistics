# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""P3 backend smoke verification — run with:

    bench --site local16.6 execute bwm_logistics.p3_verify.run

Covers: settings roundtrip (+ webhook token generation), inbound carrier
webhook (auth, event insert, dedupe, ETA update), demurrage risk surfacing,
portal notification feed, branding, and the CMS-driven landing page.
"""

import frappe

CUSTOMER_USER = "customer@bwm-demo.test"

results = []


def check(label, ok, detail=""):
	results.append(f"{'PASS' if ok else 'FAIL'}  {label}" + (f" — {detail}" if detail else ""))
	return ok


def token():
	"""Print the webhook token (ensures one exists) — used by shell scripts."""
	settings = frappe.get_doc("Logistics Settings")
	if not settings.tracking_webhook_token:
		settings.save(ignore_permissions=True)
		frappe.db.commit()
	print(settings.tracking_webhook_token)
	return settings.tracking_webhook_token


def run():
	results.clear()
	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True

	# ── settings roundtrip + token ────────────────────────────────────────────
	from bwm_logistics.api import settings as sapi

	sapi.save_settings(
		{
			"business_name": "BWM Logistics Demo",
			"hero_title": "Accra to the world, tracked.",
			"contact_phone": "+233 20 000 0000",
			"whatsapp_enabled": 0,
		}
	)
	got = None
	frappe.set_user("ops@bwm-demo.test")
	got = sapi.get_settings()
	frappe.set_user("Administrator")
	check(
		"settings save/get + webhook token generated",
		got["business_name"] == "BWM Logistics Demo" and bool(got["tracking_webhook_token"]),
		f"token={got['tracking_webhook_token'][:8]}…",
	)

	# ── inbound webhook (direct call, as Guest) ──────────────────────────────
	from bwm_logistics.api.carrier_webhook import receive

	container_no = "MSKU1234565"
	tok = got["tracking_webhook_token"]
	# Re-runnable: drop this check's event from previous runs (dedupe would
	# otherwise correctly report 0 new events).
	cname_pre = frappe.db.get_value("Container", {"container_no": container_no}, "name")
	if cname_pre:
		for ev in frappe.get_all(
			"Tracking Event",
			filters={"container": cname_pre, "milestone": "Discharged at Port"},
			pluck="name",
		):
			frappe.delete_doc("Tracking Event", ev, ignore_permissions=True, force=True)
	frappe.set_user("Guest")
	try:
		ok1 = receive(token=tok, container_no=container_no, event="Discharged at Port", location="Tema", eta="2026-07-20")
		ok2 = receive(token=tok, container_no=container_no, event="Discharged at Port")
		try:
			receive(token="wrong", container_no=container_no, event="X")
			bad_blocked = False
		except frappe.PermissionError:
			bad_blocked = True
	finally:
		frappe.set_user("Administrator")
	check("webhook accepts + inserts", ok1["ok"] and ok1["new_events"] == 1, str(ok1))
	check("webhook dedupes repeats", ok2["new_events"] == 0, str(ok2))
	check("webhook rejects bad token", bad_blocked)
	cname = frappe.db.get_value("Container", {"container_no": container_no}, "name")
	eta = frappe.db.get_value("Container", cname, "eta")
	check("webhook updated ETA", str(eta) == "2026-07-20", str(eta))

	# ── demurrage surfacing ──────────────────────────────────────────────────
	frappe.db.set_value(
		"Container", cname,
		{"demurrage_start_date": frappe.utils.add_days(frappe.utils.nowdate(), 2), "status": "Active"},
	)
	from bwm_logistics.api.dashboard import get_overview

	frappe.set_user("ops@bwm-demo.test")
	overview = get_overview()
	frappe.set_user("Administrator")
	check(
		"dashboard surfaces demurrage risk",
		any(r["name"] == cname for r in overview["demurrage_risk"]),
		f"{len(overview['demurrage_risk'])} at risk",
	)

	# ── portal feed + branding ───────────────────────────────────────────────
	frappe.set_user(CUSTOMER_USER)
	from bwm_logistics.api import portal

	feed = portal.my_notifications()
	frappe.set_user("Administrator")
	check("portal notification feed", len(feed) >= 1, f"{len(feed)} items")

	frappe.set_user("Guest")
	branding = sapi.get_branding()
	frappe.set_user("Administrator")
	check("guest branding endpoint", branding["business_name"] == "BWM Logistics Demo", str(branding))

	# ── CMS landing page ─────────────────────────────────────────────────────
	from frappe.utils import set_request
	from frappe.website.serve import get_response

	frappe.set_user("Guest")
	set_request(method="GET", path="/home")
	response = get_response()
	frappe.set_user("Administrator")
	html = response.get_data(as_text=True)
	check(
		"landing renders settings content",
		response.status_code == 200 and "Accra to the world" in html and "+233 20 000 0000" in html,
		f"status {response.status_code}",
	)

	frappe.db.commit()
	print("\n".join(results))
	failed = len([r for r in results if r.startswith("FAIL")])
	print(f"\n{len(results) - failed}/{len(results)} checks passed")
	return {"passed": len(results) - failed, "failed": failed}
