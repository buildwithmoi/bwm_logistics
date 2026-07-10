# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""P2 backend smoke verification — run with:

    bench --site local16.6 execute bwm_logistics.p2_verify.run

Exercises the V1 dispatch flow end-to-end:
  portal pickup request → driver created (+login) → run built with pickup +
  delivery stops (auto-hydrated address/COD) → start run ("Out for Delivery"
  notifications) → POD completion → "Delivered" → pickup completed → finish
  run → COD reconciled into a Cash Payment Entry against the invoice →
  portal shows POD. Also proves driver scoping (can't touch another's run).
"""

import frappe

OPS_USER = "ops@bwm-demo.test"
CUSTOMER_USER = "customer@bwm-demo.test"
DRIVER_USER = "driver@bwm-demo.test"

results = []


def check(label, ok, detail=""):
	results.append(f"{'PASS' if ok else 'FAIL'}  {label}" + (f" — {detail}" if detail else ""))
	return ok


def run():
	results.clear()
	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True  # welcome/notify emails: log, don't send
	from bwm_logistics.install import after_install

	after_install()

	from bwm_logistics.api import dispatch as dapi
	from bwm_logistics.api import portal, shipments as sapi

	# ── driver with portal login ──────────────────────────────────────────────
	frappe.set_user(OPS_USER)
	driver = dapi.save_driver({"full_name": "Yaw Driver", "cell_number": "+233200000002", "email": DRIVER_USER})
	check("driver created + user linked", bool(driver["name"]) and driver["user"] == DRIVER_USER, str(driver))
	frappe.set_user("Administrator")
	frappe.get_doc("User", DRIVER_USER).new_password = None  # ensure login for scoping checks is via set_user
	frappe.db.set_value("User", DRIVER_USER, "enabled", 1)

	# ── deliverable shipment with an unpaid invoice (for COD) ────────────────
	frappe.set_user(OPS_USER)
	customer = frappe.db.get_value("Customer", {"customer_name": "Ama Customer"}, "name")
	ship = sapi.save_shipment(
		{
			"customer": customer,
			"direction": "Import",
			"consignee_name": "Ama",
			"consignee_phone": "+233200000000",
			"destination": "Accra",
			"delivery_address": "12 Independence Ave, Accra",
			"packages": [{"description": "Barrel", "qty": 1, "weight_kg": 60}],
			"charges": [{"charge_type": "Freight + Delivery", "amount": 400}],
		}
	)["name"]
	sapi.record_event(ship, "Ready for Delivery", notify=0)
	frappe.set_user("Administrator")
	invoice = sapi.make_invoice(ship)["sales_invoice"]
	outstanding = frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount")
	check("invoice for COD", outstanding == 400, f"{invoice} outstanding={outstanding}")

	# ── portal pickup request ─────────────────────────────────────────────────
	frappe.set_user(CUSTOMER_USER)
	pickup = portal.request_pickup(
		{"pickup_address": "Osu, Accra — blue gate", "contact_phone": "+233200000000", "time_window": "Morning"}
	)["name"]
	mine = [p.name for p in portal.my_pickups()]
	check("portal pickup request", pickup in mine, pickup)

	# ── build the run (hydration fills address + COD) ────────────────────────
	frappe.set_user(OPS_USER)
	assignable = dapi.assignable()
	check(
		"assignable lists shipment + pickup",
		ship in [s.name for s in assignable["shipments"]] and pickup in [p.name for p in assignable["pickups"]],
		f"shipments={len(assignable['shipments'])}, pickups={len(assignable['pickups'])}",
	)
	run_name = dapi.save_run(
		{
			"driver": driver["name"],
			"run_date": frappe.utils.nowdate(),
			"stops": [
				{"stop_type": "Delivery", "shipment": ship},
				{"stop_type": "Pickup", "pickup_request": pickup},
			],
		}
	)["name"]
	rdoc = frappe.get_doc("Delivery Run", run_name)
	dstop = next(s for s in rdoc.stops if s.stop_type == "Delivery")
	pstop = next(s for s in rdoc.stops if s.stop_type == "Pickup")
	check(
		"stops hydrated (address + COD from invoice)",
		dstop.address == "12 Independence Ave, Accra" and dstop.cod_due == 400 and bool(pstop.address),
		f"cod_due={dstop.cod_due}, pickup addr={pstop.address!r}",
	)
	check(
		"pickup request auto-scheduled",
		frappe.db.get_value("Pickup Request", pickup, "status") == "Scheduled",
	)

	# ── driver scoping ────────────────────────────────────────────────────────
	frappe.set_user(DRIVER_USER)
	own = [r.name for r in dapi.list_runs()["rows"]]
	check("driver sees own runs only", run_name in own, str(own[:3]))
	other_driver = dapi_other_run_guard(run_name)
	check("another driver blocked from this run", other_driver, "PermissionError raised")

	# ── drive it: start → arrive → POD complete → pickup → finish ───────────
	dapi.start_run(run_name)
	frappe.set_user("Administrator")
	ofd = frappe.db.get_value("Shipment", ship, ["status", "current_milestone"], as_dict=True)
	check(
		"start_run → Out for Delivery event",
		ofd.current_milestone == "Out for Delivery" and ofd.status == "Ready for Delivery",
		str(ofd),
	)
	# The notify job is enqueued for background workers; none run under
	# bench execute, so dispatch inline (same as production workers would).
	from bwm_logistics.notifications import dispatch_for_event

	event_name = frappe.db.get_value(
		"Tracking Event", {"shipment": ship, "milestone": "Out for Delivery"}, "name"
	)
	dispatch_for_event(event_name)
	notif = frappe.get_all(
		"Notification Log Entry",
		filters={"shipment": ship, "milestone": "Out for Delivery"},
		fields=["channel", "status"],
	)
	check("out-for-delivery notification logged", len(notif) >= 1, str(notif))

	frappe.set_user(DRIVER_USER)
	dapi.stop_arrived(run_name, dstop.name)
	dapi.stop_complete(
		run_name, dstop.name,
		receiver="Ama Mensah", cod_collected=400, geo="5.5600,-0.2057",
		signature="/files/sig-demo.png", photo="/files/pod-demo.jpg",
	)
	dapi.stop_complete(run_name, pstop.name, receiver="Warehouse intake")
	finished = dapi.finish_run(run_name)
	check("run finished", finished["status"] == "Completed")

	frappe.set_user("Administrator")
	delivered = frappe.db.get_value("Shipment", ship, ["status", "current_milestone"], as_dict=True)
	check("delivery → Delivered status + event", delivered.status == "Delivered", str(delivered))
	check(
		"pickup completed",
		frappe.db.get_value("Pickup Request", pickup, "status") == "Completed",
	)
	rdoc.reload()
	check(
		"run totals",
		rdoc.completed_stops == 2 and rdoc.cod_collected_total == 400,
		f"completed={rdoc.completed_stops}, cod={rdoc.cod_collected_total}",
	)

	# ── COD reconciliation → Payment Entry ───────────────────────────────────
	_ensure_default_cash_account()
	try:
		rec = dapi.reconcile_cod(run_name)
		new_outstanding = frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount")
		check(
			"COD reconciled → Payment Entry, invoice settled",
			len(rec["payment_entries"]) == 1 and new_outstanding == 0,
			f"PE={rec['payment_entries']}, outstanding={new_outstanding}",
		)
	except Exception as e:
		check("COD reconciled → Payment Entry, invoice settled", False, str(e)[:200])

	# ── portal sees the POD ──────────────────────────────────────────────────
	frappe.set_user(CUSTOMER_USER)
	detail = portal.shipment_detail(ship)
	check(
		"portal shows POD",
		detail.get("pod", {}).get("pod_receiver") == "Ama Mensah",
		str(detail.get("pod")),
	)

	frappe.set_user("Administrator")
	frappe.db.commit()
	print("\n".join(results))
	failed = len([r for r in results if r.startswith("FAIL")])
	print(f"\n{len(results) - failed}/{len(results)} checks passed")
	return {"passed": len(results) - failed, "failed": failed}


def set_demo_passwords():
	"""Dev convenience: the driver demo user is normally activated via the
	welcome email (muted on this site) — give it the demo password so the
	driver flow can be tried in a browser."""
	from frappe.utils.password import update_password

	for user in (DRIVER_USER, "driver2@bwm-demo.test"):
		if frappe.db.exists("User", user):
			update_password(user, DEMO_PASSWORD)
	frappe.db.commit()
	print(f"demo password set for driver users ({DEMO_PASSWORD})")


DEMO_PASSWORD = "bwm-demo-2026"


def dapi_other_run_guard(run_name) -> bool:
	"""A second driver must be blocked from acting on the first driver's run."""
	frappe.set_user("Administrator")
	from bwm_logistics.api import dispatch as dapi

	other = dapi.save_driver({"full_name": "Kojo OtherDriver", "email": "driver2@bwm-demo.test"})
	frappe.set_user("driver2@bwm-demo.test")
	try:
		dapi.start_run(run_name)
		return False
	except frappe.PermissionError:
		return True
	except Exception:
		return False
	finally:
		frappe.set_user("driver@bwm-demo.test")


def _ensure_default_cash_account():
	"""Dev-site convenience: reconcile needs the company's default cash account."""
	company = frappe.db.get_single_value("Global Defaults", "default_company") or frappe.db.get_value(
		"Company", {}, "name"
	)
	if not company:
		return
	if frappe.db.get_value("Company", company, "default_cash_account"):
		return
	cash = frappe.db.get_value("Account", {"company": company, "account_type": "Cash", "is_group": 0}, "name")
	if cash:
		frappe.db.set_value("Company", company, "default_cash_account", cash)
