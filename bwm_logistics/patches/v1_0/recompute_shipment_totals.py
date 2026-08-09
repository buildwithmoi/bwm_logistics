# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Re-derive shipment totals from the manifest on the container.

`compute_totals()` used to sum `Shipment.packages`. That table was retired by
move_packages_to_containers but kept on the doctype, so the totals stayed
frozen at whatever it held: correct-looking on migrated bookings, and zero on
every booking made since — which is what the portal was showing the customer.

The totals themselves are cached sums, so this rewrites them in place rather
than re-saving each document: a full save would run validation over historical
rows that were never required to pass it.
"""

import frappe

from bwm_logistics.bwm_logistics.doctype.shipment.shipment import manifests_for

BATCH = 500


def execute():
	if not frappe.db.exists("DocType", "Container Content"):
		return

	names = frappe.get_all("Shipment", pluck="name", limit_page_length=0)
	changed = 0
	for start in range(0, len(names), BATCH):
		chunk = names[start : start + BATCH]
		for shipment, lines in manifests_for(chunk).items():
			totals = {
				"total_packages": sum((line["qty"] or 0) for line in lines),
				"total_weight_kg": sum((line["weight_kg"] or 0) * (line["qty"] or 1) for line in lines),
				"total_declared_value": sum((line["declared_value"] or 0) for line in lines),
			}
			was = frappe.db.get_value("Shipment", shipment, list(totals), as_dict=True)
			if any(round(float(was[k] or 0), 4) != round(float(v), 4) for k, v in totals.items()):
				frappe.db.set_value("Shipment", shipment, totals, update_modified=False)
				changed += 1

	frappe.db.commit()
	print(f"Recomputed totals on {changed} shipment(s) from their container manifests")
