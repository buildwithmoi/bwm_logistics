# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""One-time import of the JM Containers working Excel ("Stock and
Distribution 1.xlsx") into containers, trading shipments and distribution
entries. Run with:

    bench --site local16.6 execute bwm_logistics.import_jm_excel.run
    bench --site local16.6 execute bwm_logistics.import_jm_excel.run --kwargs "{'path': '/path/to.xlsx'}"

Idempotent: containers already imported (same container no + BL) are skipped,
as are identical distribution rows — safe to re-run after fixing data.
"""

import os

import frappe
from frappe.utils import flt, getdate

DEFAULT_FILENAME = "Stock and Distribution 1.xlsx"

# JM Containers operates a single branch.
BRANCH = "Accra"

# Their sheet statuses → our tracking milestones (which set shipment status).
STATUS_MILESTONE = {
	"Arrived": "Arrived at Port",
	"In Transit": "In Transit",
	"Pending": None,  # stays Open
	"Delayed": "Delayed",
	"Customs Clearance": "Customs Clearance",
	"Offloaded": "Offloaded",
}


def _norm(text) -> str:
	return (text or "").strip().lower()


def _default_path() -> str:
	# App repo root (…/apps/bwm_logistics), one level above the package dir.
	return os.path.abspath(os.path.join(frappe.get_app_path("bwm_logistics"), "..", DEFAULT_FILENAME))


def run(path=None):
	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True
	import openpyxl

	path = path or _default_path()
	if not os.path.exists(path):
		print(f"File not found: {path}")
		return

	if not frappe.db.exists("Branch", BRANCH):
		frappe.get_doc({"doctype": "Branch", "branch": BRANCH}).insert(ignore_permissions=True)

	wb = openpyxl.load_workbook(path, data_only=True)
	created = {"containers": 0, "shipments": 0, "events": 0, "distributions": 0}
	skipped = []
	shipments_by_row = []

	# ── Stock Tracker → Container + trading Shipment ─────────────────────────
	ws = wb["Stock Tracker"]
	rows = list(ws.iter_rows(values_only=True))
	header_idx = next(i for i, r in enumerate(rows) if r and r[0] == "Date Received")
	seen_containers = set()
	for r in rows[header_idx + 1 :]:
		(date_received, item, bl_no, container_no, eta, qty, unit, supplier, status, invoice_ref, comment) = (
			list(r) + [None] * 11
		)[:11]
		if not container_no or not item:
			continue
		container_no = str(container_no).strip()
		bl_no = str(bl_no).strip() if bl_no else None
		key = (container_no, bl_no)
		if key in seen_containers:
			skipped.append(f"duplicate row in sheet: {container_no} / {bl_no}")
		seen_containers.add(key)

		existing = frappe.db.get_value("Container", {"container_no": container_no, "bl_no": bl_no}, "name")
		if existing:
			ship = frappe.db.get_value(
				"Shipment", {"container": existing, "shipment_type": "Own Goods (Trading)"}, "name"
			)
			shipments_by_row.append(ship)
			skipped.append(f"already imported: {container_no} ({bl_no})")
			continue

		container = frappe.get_doc(
			{
				"doctype": "Container",
				"direction": "Import",
				"container_no": container_no,
				"bl_no": bl_no,
				"branch": BRANCH,
				"eta": getdate(eta) if eta else None,
				"ata": getdate(date_received) if (date_received and status == "Arrived") else None,
				"notes": (comment or "").strip() or None,
			}
		)
		container.flags.ignore_permissions = True
		container.insert(ignore_permissions=True)
		created["containers"] += 1

		# Item column may hold several goods in one container ("A & B").
		item_names = [part.strip() for part in str(item).replace("\n", " ").split("&") if part.strip()]
		packages = []
		for i, item_name in enumerate(item_names):
			packages.append(
				{
					"description": item_name,
					# Sheet has one Qty per row — assign it to the first line;
					# further lines start at 0 and get corrected on arrival.
					"qty": int(flt(qty)) if (i == 0 and qty) else 0,
					"unit": (str(unit).strip().upper() if unit else "PIECES"),
				}
			)
		if len(item_names) > 1 and qty:
			skipped.append(f"{container_no}: qty {qty} put on '{item_names[0]}' — split it manually")

		notes = []
		if supplier:
			notes.append(f"Supplier: {supplier}")
		if invoice_ref:
			notes.append(f"Supplier invoice: {invoice_ref}")
		if comment:
			notes.append(str(comment).strip())

		shipment = frappe.get_doc(
			{
				"doctype": "Shipment",
				"shipment_type": "Own Goods (Trading)",
				"direction": "Import",
				"container": container.name,
				"branch": BRANCH,
				"packages": packages,
				"notes": "\n".join(notes) or None,
			}
		)
		shipment.flags.ignore_permissions = True
		shipment.insert(ignore_permissions=True)
		shipments_by_row.append(shipment.name)
		created["shipments"] += 1

		milestone = STATUS_MILESTONE.get((status or "").strip())
		if milestone:
			frappe.get_doc(
				{
					"doctype": "Tracking Event",
					"container": container.name,
					"milestone": milestone,
					"event_datetime": date_received or eta or frappe.utils.now_datetime(),
					"source": "Manual",
					"notify": 0,
				}
			).insert(ignore_permissions=True)
			created["events"] += 1

	# ── Distribution → Distribution Entries ──────────────────────────────────
	ws = wb["Distribution"]
	rows = list(ws.iter_rows(values_only=True))
	header_idx = next(i for i, r in enumerate(rows) if r and r[0] == "Customer Name")
	for r in rows[header_idx + 1 :]:
		(recipient, product, qty, unit_price, _total, destination, delivery_date) = (list(r) + [None] * 7)[:7]
		if not recipient or not product or not flt(qty):
			continue

		# Find the arrived trading shipment whose package matches this product
		# (their sheet shortens names — "Hen Leg Quarter" vs "US Hen Leg Quarter").
		target, package_desc = None, None
		for ship_name in shipments_by_row:
			if not ship_name:
				continue
			for p in frappe.get_all(
				"Shipment Package",
				filters={"parenttype": "Shipment", "parent": ship_name},
				fields=["description", "qty"],
			):
				if _norm(product) in _norm(p.description) and flt(p.qty) > 0:
					target, package_desc = ship_name, p.description
					break
			if target:
				break
		if not target:
			skipped.append(f"distribution '{product}' → no matching arrived shipment; enter manually")
			continue

		dup = frappe.db.exists(
			"Distribution Entry",
			{
				"shipment": target,
				"recipient": str(recipient).strip(),
				"qty": flt(qty),
				"delivery_date": getdate(delivery_date) if delivery_date else None,
			},
		)
		if dup:
			skipped.append(f"distribution already imported: {recipient} / {product} / {qty}")
			continue

		frappe.get_doc(
			{
				"doctype": "Distribution Entry",
				"shipment": target,
				"product": package_desc,
				"qty": flt(qty),
				"recipient": str(recipient).strip(),
				"destination": (str(destination).strip() if destination else None),
				"unit_price": flt(unit_price) or None,
				"delivery_date": getdate(delivery_date) if delivery_date else None,
			}
		).insert(ignore_permissions=True)
		created["distributions"] += 1

	frappe.db.commit()
	print(
		f"Imported: {created['containers']} containers, {created['shipments']} shipments, "
		f"{created['events']} events, {created['distributions']} distributions"
	)
	for s in skipped:
		print(f"  note: {s}")
	return created
