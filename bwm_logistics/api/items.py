# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""The goods catalogue.

Container contents used to be typed as free text, so "US Hen Leg Quarter",
"Hen Leg Quarter" and "hen leg quarters" were three different products and no
balance could be trusted. Contents now point at ERPNext `Item`, and this module
is the thin slice of Item the operator app needs: list, create, and classify as
import or export goods so the picker on a container offers the right ones.

Direction lives in the custom field `bwm_trade_direction` (Import / Export /
Both), created in install.ensure_item_fields().
"""

import frappe
from frappe import _

from bwm_logistics.api._perm import ANY_STAFF, require

# Everything the app trades sits under one group, so the catalogue stays
# separable from whatever else ERPNext accumulates on the site.
ITEM_GROUP = "Logistics Goods"
UNITS = ["Nos", "Cartons", "Bags", "Boxes", "Pallets", "Kg", "Pieces", "Units"]


def _ensure_group() -> str:
	if not frappe.db.exists("Item Group", ITEM_GROUP):
		parent = frappe.db.get_value("Item Group", {"is_group": 1, "parent_item_group": ""}) or "All Item Groups"
		doc = frappe.new_doc("Item Group")
		doc.item_group_name = ITEM_GROUP
		doc.parent_item_group = parent
		doc.is_group = 0
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
	return ITEM_GROUP


def ensure_item(description: str, direction: str | None = None) -> str | None:
	"""Find or create the catalogue Item a free-text description meant.

	Matching is on the name as typed. The client's sheet shortens names
	inconsistently ("Hen Leg Quarter" vs "US Hen Leg Quarter"), so anything
	unmatched becomes its own item rather than being guessed into the wrong one —
	merging two items later is easy, un-merging is not.

	Shared by the opening-data importer and the packages→contents patch so a
	fresh install and a migrated site end up with the same catalogue.
	"""
	description = (description or "").strip()
	if not description:
		return None

	existing = frappe.db.get_value("Item", {"item_name": description, "item_group": ITEM_GROUP})
	if existing:
		return existing

	_ensure_group()
	item = frappe.new_doc("Item")
	item.item_code = description[:140]
	item.item_name = description
	item.item_group = ITEM_GROUP
	item.is_stock_item = 0
	item.is_sales_item = 1
	item.is_purchase_item = 1
	item.stock_uom = "Nos"
	if frappe.db.has_column("Item", "bwm_trade_direction"):
		item.bwm_trade_direction = direction if direction in ("Import", "Export") else "Both"
	item.flags.ignore_permissions = True
	item.insert(ignore_permissions=True)
	return item.name


@frappe.whitelist()
def list_items(search=None, direction=None, limit=50):
	"""The catalogue, optionally narrowed to what a direction can carry.

	`direction` filters to that direction plus "Both", so a general-purpose
	item doesn't have to be entered twice.
	"""
	require(*ANY_STAFF)
	filters = [["item_group", "=", ITEM_GROUP], ["disabled", "=", 0]]
	if direction in ("Import", "Export"):
		filters.append(["bwm_trade_direction", "in", [direction, "Both", ""]])
	or_filters = None
	if search:
		or_filters = [["item_code", "like", f"%{search}%"], ["item_name", "like", f"%{search}%"]]
	return frappe.get_all(
		"Item",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "item_code", "item_name", "stock_uom", "bwm_trade_direction"],
		order_by="item_name asc",
		limit_page_length=min(int(limit or 50), 200),
	)


@frappe.whitelist()
def save_item(payload):
	"""Create or rename-safe update one catalogue item."""
	require(*ANY_STAFF)
	data = frappe.parse_json(payload)
	name = data.get("name")
	item_name = (data.get("item_name") or "").strip()
	if not item_name:
		frappe.throw(_("Give the item a name."))

	doc = frappe.get_doc("Item", name) if name else frappe.new_doc("Item")
	if not name:
		doc.item_code = item_name
		doc.item_group = _ensure_group()
		doc.is_stock_item = 0  # quantities are tracked per container, not in a warehouse
		doc.is_sales_item = 1
		doc.is_purchase_item = 1
	doc.item_name = item_name
	doc.stock_uom = data.get("unit") or doc.stock_uom or "Nos"
	doc.bwm_trade_direction = data.get("direction") or "Both"
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	return {"name": doc.name, "item_name": doc.item_name, "stock_uom": doc.stock_uom}


@frappe.whitelist()
def disable_item(name):
	"""Retire an item without deleting history that references it."""
	require(*ANY_STAFF)
	frappe.db.set_value("Item", name, "disabled", 1)
	return {"name": name}


@frappe.whitelist()
def units():
	require(*ANY_STAFF)
	existing = frappe.get_all("UOM", pluck="name", limit_page_length=0)
	return [u for u in UNITS if u in existing] or UNITS
