# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Stock & Distribution API (P8) — the client's Excel "Distribution" sheet,
done properly: received vs distributed vs on-hand per product on trading
shipments, with over-distribution blocked by the Distribution Entry doctype.

Quantities are operational data (any staff records them in the field); money
only enters when an entry is converted to a Sales Invoice, which stays behind
the billing roles."""

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt

from bwm_logistics.api._perm import (
	ANY_STAFF,
	ROLE_ACCOUNTS,
	ROLE_MANAGER,
	ROLE_OPERATIONS,
	ROLE_SYS,
	require,
)

CAN_WRITE = (ROLE_MANAGER, ROLE_OPERATIONS, ROLE_SYS)
CAN_INVOICE = (ROLE_MANAGER, ROLE_ACCOUNTS, ROLE_SYS)

TRADING = "Own Goods (Trading)"


def _norm(text) -> str:
	return (text or "").strip().lower()


# ─── Balances ────────────────────────────────────────────────────────────────
def shipment_balances(shipment: str) -> dict:
	"""Received / distributed / remaining per product line (pure helper)."""
	packages = frappe.get_all(
		"Shipment Package",
		filters={"parenttype": "Shipment", "parent": shipment},
		fields=["description", "qty", "unit"],
		order_by="idx",
	)
	lines = {}
	for p in packages:
		key = _norm(p.description)
		if key not in lines:
			lines[key] = {
				"product": (p.description or "").strip(),
				"unit": p.unit or "PIECES",
				"received": 0.0,
				"distributed": 0.0,
			}
		lines[key]["received"] += flt(p.qty)

	for r in frappe.get_all(
		"Distribution Entry", filters={"shipment": shipment}, fields=["product", "qty"]
	):
		key = _norm(r.product)
		if key in lines:
			lines[key]["distributed"] += flt(r.qty)

	out_lines = []
	for line in lines.values():
		line["received"] = round(line["received"], 2)
		line["distributed"] = round(line["distributed"], 2)
		line["remaining"] = round(line["received"] - line["distributed"], 2)
		out_lines.append(line)
	return {
		"lines": out_lines,
		"received_total": round(sum(x["received"] for x in out_lines), 2),
		"distributed_total": round(sum(x["distributed"] for x in out_lines), 2),
		"remaining_total": round(sum(x["remaining"] for x in out_lines), 2),
	}


@frappe.whitelist()
def shipment_stock_balance(shipment):
	require(*ANY_STAFF)
	if not frappe.db.exists("Shipment", shipment):
		frappe.throw(_("Unknown shipment {0}.").format(shipment))
	return shipment_balances(shipment)


# ─── Ledger ──────────────────────────────────────────────────────────────────
@frappe.whitelist()
def record_distribution(payload):
	require(*CAN_WRITE)
	data = frappe.parse_json(payload) if isinstance(payload, str) else payload
	entry = frappe.get_doc(
		{
			"doctype": "Distribution Entry",
			"shipment": data.get("shipment"),
			"product": data.get("product"),
			"qty": flt(data.get("qty")),
			"recipient": (data.get("recipient") or "").strip(),
			"customer": data.get("customer") or None,
			"destination": data.get("destination"),
			"unit_price": flt(data.get("unit_price")) or None,
			"delivery_date": data.get("delivery_date") or None,
			"notes": data.get("notes"),
		}
	)
	if not entry.recipient:
		frappe.throw(_("Who received it? A truck, a person, or Storage."))
	entry.insert(ignore_permissions=True)
	return {"name": entry.name, "balances": shipment_balances(entry.shipment)}


@frappe.whitelist()
def list_distributions(shipment=None, search=None, start=0, limit=25):
	require(*ANY_STAFF)
	filters = {}
	if shipment:
		filters["shipment"] = shipment
	or_filters = None
	if search:
		like = f"%{search}%"
		or_filters = {
			"product": ("like", like),
			"recipient": ("like", like),
			"destination": ("like", like),
			"shipment": ("like", like),
		}
	rows = frappe.get_all(
		"Distribution Entry",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name", "shipment", "product", "qty", "unit", "recipient", "customer",
			"destination", "unit_price", "amount", "delivery_date", "sales_invoice",
			"recorded_by", "creation",
		],
		order_by="delivery_date desc, creation desc",
		start=cint(start),
		limit=min(cint(limit) or 25, 100),
	)
	return {"rows": rows, "total": frappe.db.count("Distribution Entry", filters)}


@frappe.whitelist()
def delete_distribution(name):
	require(*CAN_WRITE)
	entry = frappe.get_doc("Distribution Entry", name)
	shipment = entry.shipment
	entry.delete()  # on_trash blocks invoiced entries
	return {"ok": True, "balances": shipment_balances(shipment)}


# ─── Overview (Stock page) ───────────────────────────────────────────────────
@frappe.whitelist()
def stock_overview():
	require(*ANY_STAFF)
	trading = frappe.get_all(
		"Shipment",
		filters={"shipment_type": TRADING, "status": ("!=", "Cancelled")},
		fields=["name", "status", "current_milestone", "container", "direction", "creation"],
		order_by="creation desc",
		limit_page_length=0,
	)
	container_info = {}
	containers = [s.container for s in trading if s.container]
	if containers:
		container_info = {
			c.name: c
			for c in frappe.get_all(
				"Container",
				filters={"name": ("in", containers)},
				fields=["name", "container_no", "eta", "vessel"],
			)
		}

	incoming, arrived = [], []
	products = defaultdict(lambda: {"received": 0.0, "distributed": 0.0})
	for s in trading:
		cont = container_info.get(s.container)
		row = {
			"shipment": s.name,
			"status": s.status,
			"current_milestone": s.current_milestone,
			"container": s.container,
			"container_no": cont and cont.container_no,
			"eta": cont and str(cont.eta or "") or None,
		}
		balances = shipment_balances(s.name)
		row.update(
			{
				"received": balances["received_total"],
				"distributed": balances["distributed_total"],
				"remaining": balances["remaining_total"],
			}
		)
		if s.status in ("Open", "In Transit"):
			incoming.append(row)
		else:
			arrived.append(row)
			for line in balances["lines"]:
				bucket = products[(_norm(line["product"]), line["unit"])]
				bucket["product"] = line["product"]
				bucket["unit"] = line["unit"]
				bucket["received"] += line["received"]
				bucket["distributed"] += line["distributed"]

	product_rows = []
	for bucket in products.values():
		bucket["received"] = round(bucket["received"], 2)
		bucket["distributed"] = round(bucket["distributed"], 2)
		bucket["remaining"] = round(bucket["received"] - bucket["distributed"], 2)
		product_rows.append(bucket)
	product_rows.sort(key=lambda x: -x["remaining"])

	return {"incoming": incoming, "shipments": arrived, "products": product_rows}


# ─── Invoice conversion (billing roles) ──────────────────────────────────────
@frappe.whitelist()
def invoice_distribution(name):
	"""Turn a priced, customer-linked distribution entry into a submitted
	Sales Invoice tagged to the shipment — the P&L picks it up from the tag."""
	require(*CAN_INVOICE)
	entry = frappe.get_doc("Distribution Entry", name)
	if entry.sales_invoice:
		frappe.throw(_("Already invoiced ({0}).").format(entry.sales_invoice))
	if not entry.customer:
		frappe.throw(_("Link a customer on this entry first — {0} is not a customer record.").format(
			frappe.bold(entry.recipient)
		))
	if flt(entry.unit_price) <= 0:
		frappe.throw(_("Set a unit price on this entry first."))

	from bwm_logistics.api.billing import new_invoice

	result = new_invoice(
		{
			"customer": entry.customer,
			"shipment": entry.shipment,
			"lines": [
				{
					"description": f"{entry.product} — {flt(entry.qty):g} {entry.unit or 'PIECES'}",
					"qty": flt(entry.qty),
					"rate": flt(entry.unit_price),
				}
			],
		}
	)
	frappe.db.set_value("Distribution Entry", name, "sales_invoice", result["sales_invoice"])
	return result
