# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Operator API — shipments (house consignments), events, invoicing."""

import frappe
from frappe import _
from frappe.utils import cint

from bwm_logistics.api._perm import (
	ANY_STAFF,
	ROLE_ACCOUNTS,
	ROLE_MANAGER,
	ROLE_OPERATIONS,
	ROLE_SYS,
	require,
)

SHIPMENT_FIELDS = [
	"customer", "direction", "status", "container", "notify_customer",
	"shipper_name", "shipper_phone", "origin",
	"consignee_name", "consignee_phone", "destination", "delivery_address",
	"notes",
]

CAN_WRITE = (ROLE_MANAGER, ROLE_OPERATIONS, ROLE_SYS)
CAN_BILL = (ROLE_MANAGER, ROLE_ACCOUNTS, ROLE_SYS)


@frappe.whitelist()
def list_shipments(status=None, container=None, customer=None, search=None, start=0, limit=25):
	require(*ANY_STAFF)
	filters = {}
	if status:
		filters["status"] = status
	if container:
		filters["container"] = container
	if customer:
		filters["customer"] = customer
	or_filters = None
	if search:
		like = f"%{search}%"
		or_filters = {"name": ("like", like), "customer_name": ("like", like), "consignee_name": ("like", like)}

	rows = frappe.get_all(
		"Shipment",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name", "customer", "customer_name", "direction", "status", "current_milestone",
			"container", "destination", "total_packages", "total_weight_kg",
			"total_charges", "sales_invoice", "modified",
		],
		order_by="modified desc",
		start=cint(start),
		limit=min(cint(limit) or 25, 100),
	)
	return {"rows": rows, "total": frappe.db.count("Shipment", filters or None)}


def get_timeline(shipment_name: str) -> list[dict]:
	"""A shipment's merged timeline: its own events + its container's
	container-wide events (the logical cascade)."""
	shipment = frappe.db.get_value("Shipment", shipment_name, ["name", "container"], as_dict=True)
	if not shipment:
		return []
	or_filters = [["shipment", "=", shipment.name]]
	if shipment.container:
		or_filters.append(["container", "=", shipment.container])
	events = frappe.get_all(
		"Tracking Event",
		or_filters=or_filters,
		fields=["name", "event_datetime", "milestone", "location", "remarks", "shipment", "container"],
		order_by="event_datetime desc",
	)
	# Keep container-wide events + this shipment's own; drop sibling shipments'
	# specific events that matched via the container or_filter.
	return [e for e in events if not e.shipment or e.shipment == shipment.name]


@frappe.whitelist()
def get_shipment(name):
	require(*ANY_STAFF)
	doc = frappe.get_doc("Shipment", name)
	out = doc.as_dict(no_nulls=False)
	out["timeline"] = get_timeline(name)
	if doc.sales_invoice:
		out["invoice"] = frappe.db.get_value(
			"Sales Invoice", doc.sales_invoice,
			["name", "status", "grand_total", "outstanding_amount", "currency"], as_dict=True,
		)
	if doc.container:
		out["container_info"] = frappe.db.get_value(
			"Container", doc.container,
			["name", "container_no", "status", "current_milestone", "eta", "vessel"], as_dict=True,
		)
	return out


@frappe.whitelist()
def save_shipment(payload):
	require(*CAN_WRITE)
	data = frappe.parse_json(payload) if isinstance(payload, str) else payload
	name = data.get("name")
	doc = frappe.get_doc("Shipment", name) if name else frappe.new_doc("Shipment")
	for field in SHIPMENT_FIELDS:
		if field in data:
			doc.set(field, data.get(field))
	if "packages" in data:
		doc.set("packages", [])
		for row in data.get("packages") or []:
			doc.append("packages", {
				"description": row.get("description"),
				"qty": cint(row.get("qty") or 1),
				"weight_kg": row.get("weight_kg") or 0,
				"volume_cbm": row.get("volume_cbm") or 0,
				"declared_value": row.get("declared_value") or 0,
			})
	if "charges" in data:
		doc.set("charges", [])
		for row in data.get("charges") or []:
			if row.get("charge_type"):
				doc.append("charges", {"charge_type": row.get("charge_type"), "amount": row.get("amount") or 0})
	doc.save()
	return {"name": doc.name}


@frappe.whitelist()
def record_event(shipment, milestone, location=None, remarks=None, event_datetime=None, notify=1):
	"""Record a shipment-specific milestone (pre/post-container legs, e.g.
	'Received at origin warehouse', 'Out for delivery')."""
	require(*CAN_WRITE)
	if not frappe.db.exists("Shipment", shipment):
		frappe.throw(_("Unknown shipment {0}.").format(shipment))
	event = frappe.get_doc(
		{
			"doctype": "Tracking Event",
			"shipment": shipment,
			"milestone": milestone,
			"location": location,
			"remarks": remarks,
			"event_datetime": event_datetime or frappe.utils.now_datetime(),
			"notify": cint(notify),
			"source": "Manual",
		}
	)
	event.insert()
	return {"event": event.name}


@frappe.whitelist()
def make_invoice(shipment):
	"""One-click Sales Invoice from the shipment's charge lines."""
	require(*CAN_BILL)
	doc = frappe.get_doc("Shipment", shipment)
	invoice = doc.make_sales_invoice()
	return {"sales_invoice": invoice}
