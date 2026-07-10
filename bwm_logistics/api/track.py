# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Public (guest) tracking — FR-WEB-3 / FR-API-2.

Returns only the shipment's own movement data: status + milestone timeline.
No names, phone numbers, values, or charges. Rate-limited.
"""

import frappe
from frappe.rate_limiter import rate_limit


@frappe.whitelist(allow_guest=True, methods=["GET", "POST"])
@rate_limit(limit=60, seconds=60 * 60)
def track(tracking_no):
	tracking_no = (tracking_no or "").strip().upper()
	if not tracking_no:
		return {"found": False}

	shipment = frappe.db.get_value(
		"Shipment",
		tracking_no,
		["name", "status", "current_milestone", "direction", "origin", "destination", "container"],
		as_dict=True,
	)
	if not shipment:
		return {"found": False}

	from bwm_logistics.api.shipments import get_timeline

	eta = frappe.db.get_value("Container", shipment.container, "eta") if shipment.container else None
	return {
		"found": True,
		"tracking_no": shipment.name,
		"status": shipment.status,
		"current_milestone": shipment.current_milestone,
		"direction": shipment.direction,
		"origin": shipment.origin,
		"destination": shipment.destination,
		"eta": eta,
		"timeline": [
			{
				"event_datetime": e.event_datetime,
				"milestone": e.milestone,
				"location": e.location,
			}
			for e in get_timeline(shipment.name)
		],
	}
