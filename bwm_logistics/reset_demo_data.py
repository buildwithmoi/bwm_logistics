# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Wipe all sample/demo TRANSACTIONAL data from a site so it can be handed
over with real data only. Run with:

    bench --site local16.6 execute bwm_logistics.reset_demo_data.run

Deletes (in dependency order): notification logs, payments, distribution
entries, sales/purchase invoices, delivery runs, pickup requests, tracking
events, shipments, containers, customers + their contacts/addresses,
suppliers, drivers, vehicles, rate cards and branches — then recreates the
single production branch and resets the naming-series counters so fresh
documents start from 1.

KEEPS configuration: Logistics Settings, Milestone Templates, Logistics
Roles, users, print formats, and the Logistics Charge/Cost items.
"""

import frappe

BRANCH = "Accra"

# tabSeries prefixes to reset once their documents are gone.
SERIES_PREFIXES = ("BWM-", "CONT-", "DIST-", "PKR-", "DRUN-", "ACC-SINV-", "ACC-PINV-", "ACC-PAY-")

deleted = {}


def _wipe(doctype, filters=None):
	"""Cancel (if submitted) and permanently delete every matching document."""
	if not frappe.db.exists("DocType", doctype):
		return 0
	names = frappe.get_all(doctype, filters=filters, pluck="name")
	for name in names:
		doc = frappe.get_doc(doctype, name)
		if doc.meta.is_submittable and doc.docstatus == 1:
			doc.flags.ignore_permissions = True
			doc.cancel()
		frappe.delete_doc(doctype, name, force=1, ignore_permissions=True, delete_permanently=True)
	deleted[doctype] = deleted.get(doctype, 0) + len(names)
	return len(names)


def _wipe_party_links(party_doctype):
	"""Contacts/Addresses hang off parties via Dynamic Link — clear them first."""
	for linked in ("Contact", "Address"):
		parents = set(
			frappe.get_all(
				"Dynamic Link",
				filters={"link_doctype": party_doctype, "parenttype": linked},
				pluck="parent",
			)
		)
		for parent in parents:
			if frappe.db.exists(linked, parent):
				frappe.delete_doc(linked, parent, force=1, ignore_permissions=True, delete_permanently=True)
		if parents:
			deleted[linked] = deleted.get(linked, 0) + len(parents)


def run():
	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True
	deleted.clear()

	# ── logs & queues ────────────────────────────────────────────────────────
	deleted["Notification Log Entry"] = frappe.db.count("Notification Log Entry")
	frappe.db.delete("Notification Log Entry")
	frappe.db.delete("Email Queue Recipient")
	frappe.db.delete("Email Queue")

	# ── money (children first: payments → invoices) ──────────────────────────
	_wipe("Payment Entry")
	_wipe("Payment Request")

	# Distribution entries reference Sales Invoices (on_trash guard) — unlink,
	# then delete the ledger before the invoices.
	frappe.db.sql("update `tabDistribution Entry` set sales_invoice = NULL")
	_wipe("Distribution Entry")

	# Shipments hold a read-only link to their freight invoice — clear it so
	# invoice deletion isn't blocked.
	frappe.db.sql("update `tabShipment` set sales_invoice = NULL")
	_wipe("Sales Invoice")
	_wipe("Purchase Invoice")

	# ── operations ───────────────────────────────────────────────────────────
	_wipe("Delivery Run")  # Run Stops are children, cascade
	_wipe("Pickup Request")
	_wipe("Tracking Event")
	_wipe("Shipment")
	_wipe("Container")

	# ── parties & fleet ──────────────────────────────────────────────────────
	_wipe_party_links("Customer")
	_wipe("Customer")
	_wipe_party_links("Supplier")
	_wipe("Supplier")
	_wipe("Driver")
	_wipe("Vehicle")

	# ── config-ish sample data ───────────────────────────────────────────────
	_wipe("Rate Card")
	_wipe("Branch")
	frappe.get_doc({"doctype": "Branch", "branch": BRANCH}).insert(ignore_permissions=True)

	# ── naming series: fresh documents start from 1 again ───────────────────
	for prefix in SERIES_PREFIXES:
		frappe.db.sql("delete from `tabSeries` where name like %s", (prefix + "%",))

	frappe.db.commit()

	print("Deleted:")
	for doctype, count in sorted(deleted.items()):
		if count:
			print(f"  {doctype}: {count}")
	print(f"Branches now: {frappe.get_all('Branch', pluck='name')}")
	print("Kept: settings, milestone templates, roles, users, print formats, service items.")
	return deleted
