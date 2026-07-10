# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""P1 backend smoke verification — run with:

    bench --site local16.6 execute bwm_logistics.p1_verify.run

Exercises the MVP flow end-to-end at the API layer:
  container → two customers' shipments tagged → container milestone recorded
  → cascade to both shipments → notifications resolved + logged → guest
  tracking → portal scoping → charges → Sales Invoice.

Uses the P0 demo users (ops@bwm-demo.test staff, customer@bwm-demo.test
portal customer with 'Ama Customer'); creates a second customer for the
cascade check. Idempotent-ish: creates fresh docs each run (cheap), leaves
demo data in place for browser testing.
"""

import frappe

OPS_USER = "ops@bwm-demo.test"
CUSTOMER_USER = "customer@bwm-demo.test"

results = []


def notify_errors():
	"""Print the captured errors on failed notification sends."""
	for row in frappe.get_all(
		"Notification Log Entry",
		filters={"status": "Failed"},
		fields=["recipient", "channel", "error"],
		order_by="creation desc",
		limit=3,
	):
		print(f"{row.channel} → {row.recipient}\n  {row.error}\n")


def check(label, ok, detail=""):
	results.append(f"{'PASS' if ok else 'FAIL'}  {label}" + (f" — {detail}" if detail else ""))
	return ok


def run():
	results.clear()
	frappe.set_user("Administrator")
	from bwm_logistics.install import after_install

	after_install()  # roles + customer fields + default milestone templates

	# ── masters seeded ────────────────────────────────────────────────────────
	templates = frappe.get_all("Milestone Template", fields=["name", "direction"])
	check("default milestone templates", len(templates) >= 2, str([t.name for t in templates]))

	# ── operator flow (as ops user) ──────────────────────────────────────────
	frappe.set_user(OPS_USER)
	from bwm_logistics.api import containers as capi
	from bwm_logistics.api import customers as cuapi
	from bwm_logistics.api import shipments as sapi

	capi.quick_add_master("Shipping Line", "Maersk")
	capi.quick_add_master("Port", "Tema")
	capi.quick_add_master("Port", "Rotterdam")

	container = capi.save_container(
		{
			"direction": "Import",
			"container_no": "MSKU1234565",
			"container_type": "40HC",
			"shipping_line": "Maersk",
			"vessel": "Maersk Ohio",
			"bl_no": "MAEU12345678",
			"port_of_loading": "Rotterdam",
			"port_of_discharge": "Tema",
			"eta": frappe.utils.add_days(frappe.utils.nowdate(), 14),
			"free_days": 7,
		}
	)["name"]
	cdoc = frappe.get_doc("Container", container)
	check(
		"container created w/ default template",
		bool(cdoc.milestone_template) and cdoc.direction == "Import",
		f"{container}, template={cdoc.milestone_template}",
	)

	# Second customer for the cascade test.
	frappe.set_user("Administrator")
	second = cuapi.save_customer({"customer_name": "Kofi Trader", "email_id": "kofi@bwm-demo.test", "mobile_no": "+233200000001"})["name"]
	frappe.set_user(OPS_USER)

	ship1 = sapi.save_shipment(
		{
			"customer": frappe.db.get_value("Customer", {"customer_name": "Ama Customer"}, "name"),
			"container": container,
			"consignee_name": "Ama",
			"consignee_phone": "+233200000000",
			"destination": "Accra",
			"packages": [
				{"description": "Barrel — household goods", "qty": 2, "weight_kg": 60, "declared_value": 1500},
				{"description": "Box — electronics", "qty": 1, "weight_kg": 12, "declared_value": 800},
			],
			"charges": [{"charge_type": "Freight", "amount": 1200}, {"charge_type": "Handling", "amount": 150}],
		}
	)["name"]
	ship2 = sapi.save_shipment(
		{
			"customer": second,
			"container": container,
			"consignee_name": "Kofi",
			"destination": "Kumasi",
			"packages": [{"description": "Pallet — spare parts", "qty": 1, "weight_kg": 240, "declared_value": 5000}],
		}
	)["name"]
	prefix = (frappe.db.get_single_value("Logistics Settings", "tracking_prefix") or "BWM").upper()
	check(
		"tracking numbers generated",
		ship1.startswith(prefix + "-") and ship2.startswith(prefix + "-"),
		f"{ship1}, {ship2}",
	)
	totals = frappe.db.get_value("Shipment", ship1, ["total_packages", "total_weight_kg", "total_charges"], as_dict=True)
	check(
		"shipment totals computed",
		totals.total_packages == 3 and totals.total_weight_kg == 132 and totals.total_charges == 1350,
		str(totals),
	)

	# ── milestone cascade + notifications ────────────────────────────────────
	capi.record_milestone(container, "Vessel Departed", location="Rotterdam")
	event = frappe.get_all("Tracking Event", filters={"container": container}, pluck="name")[0]
	# The notify job is enqueued after commit; in bench-execute run it inline.
	from bwm_logistics.notifications import dispatch_for_event

	frappe.set_user("Administrator")
	dispatch_for_event(event)
	frappe.set_user(OPS_USER)

	s1 = frappe.db.get_value("Shipment", ship1, ["status", "current_milestone"], as_dict=True)
	s2 = frappe.db.get_value("Shipment", ship2, ["status", "current_milestone"], as_dict=True)
	check(
		"cascade updated both shipments",
		s1.current_milestone == "Vessel Departed" and s2.current_milestone == "Vessel Departed"
		and s1.status == "In Transit" and s2.status == "In Transit",
		f"s1={s1}, s2={s2}",
	)

	logs = frappe.get_all(
		"Notification Log Entry",
		filters={"tracking_event": event},
		fields=["channel", "status", "recipient", "customer", "error"],
	)
	emails = [l for l in logs if l.channel == "Email"]
	distinct_customers = {l.customer for l in logs}
	check(
		"notifications resolved per tagged customer",
		len(distinct_customers) == 2 and len(emails) == 2,
		f"{len(logs)} log rows, customers={sorted(distinct_customers)}, emails={[(e.recipient, e.status) for e in emails]}",
	)
	# A dev site without an outgoing Email Account fails sends for an
	# environmental reason — the engine must still log it cleanly. Any other
	# failure is a code bug.
	def _acceptable(l):
		if l.status in ("Sent", "Skipped"):
			return True
		return l.status == "Failed" and "outgoing Email Account" in (l.error or "")

	check(
		"sends OK (or cleanly logged as env-unconfigured)",
		all(_acceptable(l) for l in logs),
		str([(l.channel, l.status) for l in logs]),
	)

	# Shipment-specific event does NOT touch the sibling.
	sapi.record_event(ship1, "Out for Delivery", location="Accra depot", notify=0)
	s2_after = frappe.db.get_value("Shipment", ship2, "current_milestone")
	s1_after = frappe.db.get_value("Shipment", ship1, ["current_milestone", "status"], as_dict=True)
	check(
		"shipment-specific event stays specific",
		s1_after.current_milestone == "Out for Delivery" and s2_after == "Vessel Departed",
		f"s1={s1_after}, s2={s2_after}",
	)

	# Timeline merge: ship1 = container event + own event; ship2 = container event only.
	t1 = sapi.get_timeline(ship1)
	t2 = sapi.get_timeline(ship2)
	check(
		"timeline merge (own + container, no siblings)",
		len(t1) == 2 and len(t2) == 1,
		f"ship1 has {len(t1)}, ship2 has {len(t2)}",
	)

	# ── guest tracking ────────────────────────────────────────────────────────
	frappe.set_user("Guest")
	from bwm_logistics.api.track import track

	public = track(ship1)
	frappe.set_user(OPS_USER)
	safe = public.get("found") and public.get("current_milestone") == "Out for Delivery"
	no_pii = "customer" not in public and "consignee_name" not in str(public.get("timeline"))
	check("guest tracking works, no PII", bool(safe and no_pii), str(public.get("current_milestone")))

	# ── portal scoping (as the customer user) ────────────────────────────────
	frappe.set_user(CUSTOMER_USER)
	from bwm_logistics.api import portal

	mine = portal.my_shipments()
	mine_names = [r.name for r in mine["rows"]]
	check("portal lists own shipments only", ship1 in mine_names and ship2 not in mine_names, str(mine_names[:5]))

	try:
		portal.shipment_detail(ship2)
		check("portal cannot read another customer's shipment", False, "no exception raised")
	except Exception:
		check("portal cannot read another customer's shipment", True, "DoesNotExistError")

	detail = portal.shipment_detail(ship1)
	check(
		"portal detail has timeline + packages",
		len(detail["timeline"]) == 2 and len(detail["packages"]) == 2,
		f"timeline={len(detail['timeline'])}, packages={len(detail['packages'])}",
	)

	# ── invoicing ─────────────────────────────────────────────────────────────
	frappe.set_user("Administrator")  # SI needs accounts setup permissions
	try:
		inv = sapi.make_invoice(ship1)["sales_invoice"]
		amount = frappe.db.get_value("Sales Invoice", inv, "grand_total")
		check("sales invoice from charges", bool(inv) and amount >= 1350, f"{inv} = {amount}")
		invoices = None
		frappe.set_user(CUSTOMER_USER)
		invoices = portal.my_invoices()
		check("portal sees the invoice", any(i.name == inv for i in invoices), str([i.name for i in invoices]))
	except Exception as e:
		check("sales invoice from charges", False, str(e)[:200])
	finally:
		frappe.set_user("Administrator")

	frappe.db.commit()
	print("\n".join(results))
	failed = len([r for r in results if r.startswith("FAIL")])
	print(f"\n{len(results) - failed}/{len(results)} checks passed")
	return {"passed": len(results) - failed, "failed": failed}
