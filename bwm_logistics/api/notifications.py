# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Operator API — the notification send log ("who was told what, when")."""

import frappe
from frappe.utils import cint

from bwm_logistics.api._perm import ANY_STAFF, require


@frappe.whitelist()
def list_log(channel=None, status=None, search=None, start=0, limit=25):
	require(*ANY_STAFF)
	filters = {}
	if channel:
		filters["channel"] = channel
	if status:
		filters["status"] = status
	or_filters = None
	if search:
		like = f"%{search}%"
		or_filters = {"recipient": ("like", like), "shipment": ("like", like), "milestone": ("like", like)}
	rows = frappe.get_all(
		"Notification Log Entry",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name", "creation", "channel", "status", "recipient", "customer",
			"shipment", "container", "milestone", "error",
		],
		order_by="creation desc",
		start=cint(start),
		limit=min(cint(limit) or 25, 100),
	)
	return {"rows": rows, "total": frappe.db.count("Notification Log Entry", filters or None)}
