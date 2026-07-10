# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Operator API — containers, milestones, and the masters their forms need."""

import frappe
from frappe import _
from frappe.utils import cint

from bwm_logistics.api._perm import ANY_STAFF, ROLE_MANAGER, ROLE_OPERATIONS, ROLE_SYS, require

# Whitelisted writable fields (save_container payloads are filtered to these).
CONTAINER_FIELDS = [
	"direction", "status", "container_no", "container_type", "milestone_template",
	"shipping_line", "vessel", "voyage_no", "bl_no", "booking_no", "seal_no",
	"port_of_loading", "port_of_discharge", "etd", "atd", "eta", "ata",
	"customs_status", "free_days", "demurrage_start_date", "notes",
]

CAN_WRITE = (ROLE_MANAGER, ROLE_OPERATIONS, ROLE_SYS)


@frappe.whitelist()
def list_containers(status=None, direction=None, search=None, start=0, limit=25):
	require(*ANY_STAFF)
	filters = {}
	if status:
		filters["status"] = status
	if direction:
		filters["direction"] = direction
	or_filters = None
	if search:
		like = f"%{search}%"
		or_filters = {"container_no": ("like", like), "bl_no": ("like", like), "vessel": ("like", like), "name": ("like", like)}

	rows = frappe.get_all(
		"Container",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name", "container_no", "direction", "status", "current_milestone",
			"container_type", "shipping_line", "vessel", "eta", "ata", "customs_status",
			"port_of_loading", "port_of_discharge", "modified",
		],
		order_by="modified desc",
		start=cint(start),
		limit=min(cint(limit) or 25, 100),
	)
	# Tagged-shipment counts in one query. (Counted in Python — raw SQL
	# aggregates in `fields` are rejected in HTTP request context.)
	if rows:
		from collections import Counter

		tagged = frappe.get_all(
			"Shipment",
			filters={"container": ("in", [r.name for r in rows])},
			fields=["container"],
			limit_page_length=0,
		)
		counts = Counter(t.container for t in tagged)
		for r in rows:
			r["shipment_count"] = counts.get(r.name, 0)
	return {"rows": rows, "total": frappe.db.count("Container", filters or None)}


@frappe.whitelist()
def get_container(name):
	require(*ANY_STAFF)
	doc = frappe.get_doc("Container", name)
	shipments = frappe.get_all(
		"Shipment",
		filters={"container": name},
		fields=["name", "customer", "customer_name", "status", "current_milestone",
			"total_packages", "total_weight_kg", "total_charges", "sales_invoice"],
		order_by="creation desc",
	)
	timeline = frappe.get_all(
		"Tracking Event",
		filters={"container": name},
		fields=["name", "event_datetime", "milestone", "location", "remarks", "shipment", "notified"],
		order_by="event_datetime desc",
	)
	return {
		"doc": doc.as_dict(no_nulls=False),
		"shipments": shipments,
		"timeline": timeline,
		"milestone_options": doc.milestone_options(),
	}


@frappe.whitelist()
def save_container(payload):
	require(*CAN_WRITE)
	data = frappe.parse_json(payload) if isinstance(payload, str) else payload
	name = data.get("name")
	doc = frappe.get_doc("Container", name) if name else frappe.new_doc("Container")
	for field in CONTAINER_FIELDS:
		if field in data:
			doc.set(field, data.get(field))
	doc.save()
	return {"name": doc.name}


@frappe.whitelist()
def record_milestone(container, milestone, location=None, remarks=None, event_datetime=None, notify=1):
	"""Record a container-wide milestone → cascades to tagged shipments and
	notifies their customers (via Tracking Event.after_insert)."""
	require(*CAN_WRITE)
	if not frappe.db.exists("Container", container):
		frappe.throw(_("Unknown container {0}.").format(container))
	event = frappe.get_doc(
		{
			"doctype": "Tracking Event",
			"container": container,
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
def get_masters():
	"""Dropdown data for container/shipment forms."""
	require(*ANY_STAFF)
	return {
		"shipping_lines": frappe.get_all("Shipping Line", pluck="name", order_by="name"),
		"ports": frappe.get_all("Port", pluck="name", order_by="name"),
		"milestone_templates": frappe.get_all(
			"Milestone Template", fields=["name", "direction", "is_default"], order_by="name"
		),
		"container_types": ["20GP", "40GP", "40HC", "45HC", "Reefer", "LCL / Groupage", "Other"],
	}


QUICK_MASTERS = {"Shipping Line": "line_name", "Port": "port_name"}


@frappe.whitelist()
def quick_add_master(doctype, value):
	"""Inline-create a Shipping Line or Port from the container form."""
	require(*CAN_WRITE)
	if doctype not in QUICK_MASTERS:
		frappe.throw(_("Cannot quick-add {0}.").format(doctype))
	value = (value or "").strip()
	if not value:
		frappe.throw(_("Name is required."))
	if frappe.db.exists(doctype, value):
		return {"name": value}
	doc = frappe.get_doc({"doctype": doctype, QUICK_MASTERS[doctype]: value})
	doc.insert()
	return {"name": doc.name}
