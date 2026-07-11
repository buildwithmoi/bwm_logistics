# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Operator dashboard aggregates."""

import frappe
from frappe.utils import add_days, nowdate

from bwm_logistics.api._perm import ANY_STAFF, require


@frappe.whitelist()
def get_overview():
	require(*ANY_STAFF)
	today = nowdate()
	unpaid = 0
	if frappe.db.exists("DocType", "Sales Invoice"):
		unpaid = frappe.db.count(
			"Sales Invoice", {"docstatus": 1, "outstanding_amount": (">", 0)}
		)
	from bwm_logistics.alerts import at_risk_containers

	return {
		"containers_active": frappe.db.count("Container", {"status": "Active"}),
		"arriving_soon": frappe.db.count(
			"Container",
			{"status": "Active", "eta": ("between", [today, add_days(today, 7)])},
		),
		"demurrage_risk": at_risk_containers(),
		"active_shipments": frappe.db.count(
			"Shipment", {"status": ("not in", ["Delivered", "Cancelled"])}
		),
		"unpaid_invoices": unpaid,
		"recent_events": frappe.get_all(
			"Tracking Event",
			fields=["name", "event_datetime", "milestone", "location", "container", "shipment"],
			order_by="event_datetime desc",
			limit=8,
		),
	}
