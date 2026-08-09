# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Re-derive shipment totals from the manifest on the container.

`compute_totals()` used to sum `Shipment.packages`. That table was retired by
move_packages_to_containers but kept on the doctype, so the totals stayed
frozen at whatever it held: correct-looking on migrated bookings, and zero on
every booking made since — which is what the portal was showing the customer.
"""

import frappe

from bwm_logistics.bwm_logistics.doctype.shipment.shipment import refresh_stored_totals


def execute():
	if not frappe.db.exists("DocType", "Container Content"):
		return

	changed = refresh_stored_totals(frappe.get_all("Shipment", pluck="name", limit_page_length=0))
	frappe.db.commit()
	print(f"Recomputed totals on {changed} shipment(s) from their container manifests")
