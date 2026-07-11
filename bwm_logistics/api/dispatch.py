# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Dispatch API — delivery runs, driver actions (POD), and COD reconciliation.

Permission model: managers/operations manage runs; a driver may only read and
act on runs where Driver.user == session user (assert_driver). Stop actions
write with ignore_permissions AFTER that explicit check, so drivers don't need
write perms on the doctype itself.
"""

import frappe
from frappe import _
from frappe.utils import cint, now_datetime, nowdate

from bwm_logistics.api._perm import (
	ANY_STAFF,
	ROLE_ACCOUNTS,
	ROLE_DRIVER,
	ROLE_MANAGER,
	ROLE_OPERATIONS,
	ROLE_SYS,
	require,
)

CAN_MANAGE = (ROLE_MANAGER, ROLE_OPERATIONS, ROLE_SYS)
CAN_RECONCILE = (ROLE_MANAGER, ROLE_ACCOUNTS, ROLE_SYS)


def _is_dispatcher() -> bool:
	return bool(set(frappe.get_roles()) & set(CAN_MANAGE))


def _my_driver() -> str | None:
	return frappe.db.get_value("Driver", {"user": frappe.session.user}, "name")


# ─── Runs ────────────────────────────────────────────────────────────────────
@frappe.whitelist()
def list_runs(status=None, run_date=None, start=0, limit=25):
	"""Dispatchers see all runs; drivers see only their own."""
	require(*ANY_STAFF)
	filters = {}
	if status:
		filters["status"] = status
	if run_date:
		filters["run_date"] = run_date
	if not _is_dispatcher():
		driver = _my_driver()
		if not driver:
			return {"rows": [], "total": 0}
		filters["driver"] = driver

	rows = frappe.get_all(
		"Delivery Run",
		filters=filters,
		fields=[
			"name", "run_date", "status", "driver", "driver_name", "vehicle",
			"total_stops", "completed_stops", "cod_due_total", "cod_collected_total",
			"cod_reconciled", "modified",
		],
		order_by="run_date desc, creation desc",
		start=cint(start),
		limit=min(cint(limit) or 25, 100),
		ignore_permissions=True,
	)
	return {"rows": rows, "total": frappe.db.count("Delivery Run", filters or None)}


@frappe.whitelist()
def get_run(name):
	require(*ANY_STAFF)
	run = frappe.get_doc("Delivery Run", name)
	if not _is_dispatcher():
		run.assert_driver()
	out = run.as_dict(no_nulls=False)
	# Enrich stops with shipment/customer context for the UI.
	for stop in out["stops"]:
		if stop.get("shipment"):
			stop["shipment_info"] = frappe.db.get_value(
				"Shipment", stop["shipment"],
				["customer_name", "total_packages", "status", "current_milestone"], as_dict=True,
			)
	return out


RUN_FIELDS = ["driver", "vehicle", "run_date", "notes"]
STOP_FIELDS = ["stop_type", "shipment", "pickup_request", "address", "contact_name", "contact_phone", "cod_due"]


@frappe.whitelist()
def save_run(payload):
	require(*CAN_MANAGE)
	data = frappe.parse_json(payload) if isinstance(payload, str) else payload
	name = data.get("name")
	doc = frappe.get_doc("Delivery Run", name) if name else frappe.new_doc("Delivery Run")
	if doc.get("status") in ("Completed", "Cancelled"):
		frappe.throw(_("This run is closed."))
	for field in RUN_FIELDS:
		if field in data:
			doc.set(field, data.get(field))
	if "stops" in data:
		doc.set("stops", [])
		for row in data.get("stops") or []:
			doc.append("stops", {f: row.get(f) for f in STOP_FIELDS})
	doc.save()
	return {"name": doc.name}


@frappe.whitelist()
def start_run(name):
	"""Scheduled → In Transit. Records 'Out for Delivery' on every delivery
	stop's shipment (notifying customers). Driver or dispatcher."""
	require(*ANY_STAFF)
	run = frappe.get_doc("Delivery Run", name)
	if not _is_dispatcher():
		run.assert_driver()
	if run.status not in ("Draft", "Scheduled"):
		frappe.throw(_("Run {0} is {1} — it can't be started.").format(name, run.status))

	run.db_set("status", "In Transit")
	for stop in run.stops:
		if stop.stop_type == "Delivery" and stop.shipment:
			_record_event(shipment=stop.shipment, milestone="Out for Delivery", notify=1)
	return {"status": "In Transit"}


# ─── Driver stop actions ─────────────────────────────────────────────────────
def _get_stop(run, stop_name):
	for stop in run.stops:
		if stop.name == stop_name:
			return stop
	frappe.throw(_("Stop not found on this run."))


def _driver_or_dispatcher(run):
	require(ROLE_DRIVER, *CAN_MANAGE)
	if not _is_dispatcher():
		run.assert_driver()


@frappe.whitelist()
def stop_arrived(run, stop):
	doc = frappe.get_doc("Delivery Run", run)
	_driver_or_dispatcher(doc)
	s = _get_stop(doc, stop)
	if s.status not in ("Pending",):
		frappe.throw(_("Stop is already {0}.").format(s.status))
	s.db_set("status", "Arrived", update_modified=False)
	return {"status": "Arrived"}


@frappe.whitelist()
def stop_complete(
	run, stop, receiver=None, signature=None, photo=None, cod_collected=0, geo=None
):
	"""Complete a stop with proof of delivery. Deliveries record a 'Delivered'
	event (notifying the customer); pickups mark their request completed."""
	doc = frappe.get_doc("Delivery Run", run)
	_driver_or_dispatcher(doc)
	if doc.status != "In Transit":
		frappe.throw(_("Start the run before completing stops."))
	s = _get_stop(doc, stop)
	if s.status in ("Completed", "Failed"):
		frappe.throw(_("Stop is already {0}.").format(s.status))

	s.db_set(
		{
			"status": "Completed",
			"pod_receiver": receiver,
			"pod_signature": signature,
			"pod_photo": photo,
			"pod_geo": geo,
			"pod_time": now_datetime(),
			"cod_collected": frappe.utils.flt(cod_collected),
		},
		update_modified=False,
	)

	if s.stop_type == "Delivery" and s.shipment:
		_record_event(
			shipment=s.shipment,
			milestone="Delivered",
			remarks=f"Received by {receiver}" if receiver else None,
			notify=1,
		)
	elif s.stop_type == "Pickup" and s.pickup_request:
		frappe.db.set_value("Pickup Request", s.pickup_request, "status", "Completed")

	_refresh_totals(doc)
	return {"status": "Completed"}


@frappe.whitelist()
def stop_fail(run, stop, reason=None):
	doc = frappe.get_doc("Delivery Run", run)
	_driver_or_dispatcher(doc)
	s = _get_stop(doc, stop)
	if s.status in ("Completed", "Failed"):
		frappe.throw(_("Stop is already {0}.").format(s.status))
	s.db_set({"status": "Failed", "failure_reason": reason}, update_modified=False)
	if s.stop_type == "Delivery" and s.shipment:
		_record_event(
			shipment=s.shipment,
			milestone="Delivery Attempted",
			remarks=reason,
			notify=1,
		)
	_refresh_totals(doc)
	return {"status": "Failed"}


@frappe.whitelist()
def finish_run(name):
	"""In Transit → Completed once every stop is resolved."""
	doc = frappe.get_doc("Delivery Run", name)
	_driver_or_dispatcher(doc)
	doc.reload()
	open_stops = [s for s in doc.stops if s.status in ("Pending", "Arrived")]
	if open_stops:
		frappe.throw(_("{0} stop(s) are still open.").format(len(open_stops)))
	doc.db_set("status", "Completed")
	return {"status": "Completed"}


def _refresh_totals(doc):
	doc.reload()
	doc.compute_totals()
	doc.db_set(
		{
			"completed_stops": doc.completed_stops,
			"cod_collected_total": doc.cod_collected_total,
		},
		update_modified=False,
	)


def _record_event(shipment, milestone, remarks=None, notify=1):
	frappe.get_doc(
		{
			"doctype": "Tracking Event",
			"shipment": shipment,
			"milestone": milestone,
			"remarks": remarks,
			"event_datetime": now_datetime(),
			"notify": cint(notify),
			"source": "System",
		}
	).insert(ignore_permissions=True)


# ─── COD reconciliation ──────────────────────────────────────────────────────
@frappe.whitelist()
def reconcile_cod(name):
	"""Manager/Accounts confirms the driver handed over the cash. Creates a
	Cash Payment Entry against each COD shipment's invoice so the books close
	themselves."""
	require(*CAN_RECONCILE)
	run = frappe.get_doc("Delivery Run", name)
	if run.cod_reconciled:
		frappe.throw(_("Run {0} is already reconciled.").format(name))
	if run.status != "Completed":
		frappe.throw(_("Finish the run before reconciling cash."))

	entries = []
	for stop in run.stops:
		if stop.status != "Completed" or not (stop.cod_collected or 0) > 0 or not stop.shipment:
			continue
		invoice = frappe.db.get_value("Shipment", stop.shipment, "sales_invoice")
		if not invoice:
			continue
		outstanding = frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount") or 0
		if outstanding <= 0:
			continue
		from bwm_logistics.api.billing import make_payment_entry

		entries.append(
			make_payment_entry(invoice, min(stop.cod_collected, outstanding), "Cash", reference=run.name)
		)

	run.db_set(
		{"cod_reconciled": 1, "reconciled_by": frappe.session.user, "reconciled_at": now_datetime()}
	)
	return {"payment_entries": entries}


# ─── Assignment sources + masters ────────────────────────────────────────────
@frappe.whitelist()
def assignable():
	"""What can go on a run: deliverable shipments + open pickup requests,
	plus drivers/vehicles for the form."""
	require(*CAN_MANAGE)
	# Shipments ready to go out that aren't already on an open run.
	busy = set()
	for row in frappe.get_all(
		"Run Stop",
		filters={"parenttype": "Delivery Run", "stop_type": "Delivery", "status": ("in", ["Pending", "Arrived"])},
		fields=["shipment", "parent"],
	):
		parent_status = frappe.db.get_value("Delivery Run", row.parent, "status")
		if row.shipment and parent_status in ("Draft", "Scheduled", "In Transit"):
			busy.add(row.shipment)

	shipments = [
		s
		for s in frappe.get_all(
			"Shipment",
			filters={"status": ("in", ["Arrived", "Ready for Delivery"])},
			fields=["name", "customer_name", "destination", "delivery_address", "total_packages", "sales_invoice"],
			order_by="modified desc",
			limit=200,
		)
		if s.name not in busy
	]
	pickups = frappe.get_all(
		"Pickup Request",
		filters={"status": ("in", ["Requested", "Scheduled"])},
		fields=["name", "customer_name", "pickup_address", "preferred_date", "time_window", "status"],
		order_by="preferred_date asc",
		limit=200,
	)
	drivers = frappe.get_all(
		"Driver",
		filters={"status": "Active"},
		fields=["name", "full_name", "cell_number", "user"],
		order_by="full_name",
	)
	vehicles = frappe.get_all("Vehicle", fields=["name", "make", "model"], order_by="name")
	return {"shipments": shipments, "pickups": pickups, "drivers": drivers, "vehicles": vehicles}


@frappe.whitelist()
def save_driver(payload):
	"""Create a Driver (+ optionally a portal login with the Logistics Driver
	role — Frappe emails the set-password link, same as customers)."""
	require(*CAN_MANAGE)
	data = frappe.parse_json(payload) if isinstance(payload, str) else payload
	full_name = (data.get("full_name") or "").strip()
	if not full_name:
		frappe.throw(_("Driver name is required."))

	email = (data.get("email") or "").strip().lower()
	user = None
	if email:
		if frappe.db.exists("User", email):
			user = frappe.get_doc("User", email)
			if ROLE_DRIVER not in [r.role for r in user.roles]:
				user.add_roles(ROLE_DRIVER)
		else:
			parts = full_name.split(None, 1)
			user = frappe.new_doc("User")
			user.email = email
			user.first_name = parts[0]
			user.last_name = parts[1] if len(parts) > 1 else None
			user.user_type = "Website User"
			user.send_welcome_email = 1
			user.insert(ignore_permissions=True)
			user.add_roles(ROLE_DRIVER)

	existing = frappe.db.get_value("Driver", {"full_name": full_name}, "name")
	if existing:
		driver = frappe.get_doc("Driver", existing)
	else:
		driver = frappe.new_doc("Driver")
		driver.full_name = full_name
	driver.cell_number = data.get("cell_number") or driver.cell_number
	if user:
		driver.user = user.name
	driver.flags.ignore_permissions = True
	driver.save(ignore_permissions=True)
	return {"name": driver.name, "user": user.name if user else None}
