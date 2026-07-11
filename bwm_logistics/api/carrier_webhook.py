# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Inbound tracking webhook — push updates from carrier-visibility providers
(or anything else that can POST JSON).

	POST /api/method/bwm_logistics.api.carrier_webhook.receive?token=<secret>
	{"container_no": "MSKU1234565", "event": "Vessel Arrived",
	 "datetime": "2026-07-11 08:00:00", "location": "Tema", "eta": "2026-07-24"}

Authenticated by the shared token from Logistics Settings (auto-generated).
Events flow through the same dedupe + cascade + notification pipeline as
manual and polled updates.
"""

import frappe
from frappe.utils import get_datetime, now_datetime


@frappe.whitelist(allow_guest=True, methods=["POST"])
def receive(token=None, container_no=None, event=None, datetime=None, location=None, eta=None):
	settings = frappe.get_cached_doc("Logistics Settings")
	if not settings.tracking_webhook_token or token != settings.tracking_webhook_token:
		frappe.throw(frappe._("Invalid webhook token."), frappe.PermissionError)

	container_no = (container_no or "").replace(" ", "").upper()
	if not container_no or not event:
		frappe.throw(frappe._("container_no and event are required."))

	name = frappe.db.get_value(
		"Container", {"container_no": container_no, "status": "Active"}, "name"
	) or frappe.db.get_value("Container", {"container_no": container_no}, "name")
	if not name:
		return {"ok": False, "reason": "unknown container"}

	from bwm_logistics.carrier_tracking import apply_tracking_data

	container = frappe.get_doc("Container", name)
	result = apply_tracking_data(
		container,
		{
			"events": [
				{
					"milestone": event,
					"event_datetime": get_datetime(datetime) if datetime else now_datetime(),
					"location": location,
				}
			],
			"eta": eta,
		},
		notify=1,
	)
	frappe.db.commit()
	return {"ok": True, **result}
