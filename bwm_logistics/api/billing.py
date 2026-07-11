# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Billing API — the operator billing workspace (FR-PAY-1/2/5/6 slice):
invoice overview, manual payment recording, uninvoiced shipments, rate cards.
Online portal payment stays in api/portal.py; COD reconciliation calls
make_payment_entry() from here too.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, get_first_day, nowdate

from bwm_logistics.api._perm import (
	ANY_STAFF,
	ROLE_ACCOUNTS,
	ROLE_MANAGER,
	ROLE_OPERATIONS,
	ROLE_SYS,
	require,
)

CAN_BILL = (ROLE_MANAGER, ROLE_ACCOUNTS, ROLE_SYS)
CAN_RATE = (ROLE_MANAGER, ROLE_ACCOUNTS, ROLE_SYS)


# ─── Overview ────────────────────────────────────────────────────────────────
@frappe.whitelist()
def overview():
	require(*ANY_STAFF)
	unpaid = frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "outstanding_amount": (">", 0)},
		fields=["outstanding_amount", "status"],
	)
	collected = frappe.get_all(
		"Payment Entry",
		filters={
			"docstatus": 1,
			"payment_type": "Receive",
			"posting_date": (">=", get_first_day(nowdate())),
		},
		fields=["paid_amount"],
	)
	return {
		"unpaid_total": sum(flt(r.outstanding_amount) for r in unpaid),
		"unpaid_count": len(unpaid),
		"overdue_count": len([r for r in unpaid if r.status == "Overdue"]),
		"collected_this_month": sum(flt(r.paid_amount) for r in collected),
		"uninvoiced": uninvoiced_shipments(),
	}


def uninvoiced_shipments() -> list[dict]:
	"""Shipments with charges but no Sales Invoice yet."""
	return frappe.get_all(
		"Shipment",
		filters={
			"sales_invoice": ("is", "not set"),
			"total_charges": (">", 0),
			"status": ("not in", ["Cancelled"]),
		},
		fields=["name", "customer_name", "status", "total_charges", "modified"],
		order_by="modified desc",
		limit=50,
	)


# ─── Invoices ────────────────────────────────────────────────────────────────
@frappe.whitelist()
def list_invoices(status=None, search=None, start=0, limit=25):
	require(*ANY_STAFF)
	filters = {"docstatus": 1}
	if status == "Unpaid":
		filters["outstanding_amount"] = (">", 0)
	elif status == "Paid":
		filters["outstanding_amount"] = ("<=", 0)
	elif status == "Overdue":
		filters["status"] = "Overdue"
	or_filters = None
	if search:
		like = f"%{search}%"
		or_filters = {"name": ("like", like), "customer_name": ("like", like)}

	rows = frappe.get_all(
		"Sales Invoice",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name", "customer", "customer_name", "posting_date", "due_date",
			"status", "grand_total", "outstanding_amount", "currency",
		],
		order_by="posting_date desc, creation desc",
		start=cint(start),
		limit=min(cint(limit) or 25, 100),
	)
	# Link each invoice back to its shipment (tracking number).
	if rows:
		ship_map = dict(
			frappe.get_all(
				"Shipment",
				filters={"sales_invoice": ("in", [r.name for r in rows])},
				fields=["sales_invoice", "name"],
				as_list=True,
			)
		)
		for r in rows:
			r["shipment"] = ship_map.get(r.name)
	return {"rows": rows, "total": frappe.db.count("Sales Invoice", filters)}


# ─── Payments ────────────────────────────────────────────────────────────────
def make_payment_entry(invoice: str, amount: float, mode_of_payment: str, reference: str | None = None) -> str:
	"""Submit a Payment Entry against an invoice. Shared by manual recording
	(here) and COD reconciliation (api/dispatch.py)."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	pe = get_payment_entry("Sales Invoice", invoice)
	pe.mode_of_payment = mode_of_payment
	pe.paid_amount = amount
	pe.received_amount = amount
	if pe.references:
		pe.references[0].allocated_amount = amount
	if reference:
		pe.reference_no = reference
		pe.reference_date = nowdate()
	pe.flags.ignore_permissions = True
	pe.insert(ignore_permissions=True)
	pe.submit()
	return pe.name


@frappe.whitelist()
def record_payment(invoice, amount, mode_of_payment="Cash", reference=None):
	"""Record cash/bank/MoMo received outside the online gateway. Partial
	amounts allowed (FR-PAY-6)."""
	require(*CAN_BILL)
	inv = frappe.db.get_value(
		"Sales Invoice", invoice, ["docstatus", "outstanding_amount"], as_dict=True
	)
	if not inv or inv.docstatus != 1:
		frappe.throw(_("Invoice {0} not found or not submitted.").format(invoice))
	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("Amount must be positive."))
	if amount > flt(inv.outstanding_amount):
		frappe.throw(
			_("Amount exceeds the outstanding {0}.").format(inv.outstanding_amount)
		)
	pe = make_payment_entry(invoice, amount, mode_of_payment, reference)
	return {
		"payment_entry": pe,
		"outstanding": frappe.db.get_value("Sales Invoice", invoice, "outstanding_amount"),
	}


@frappe.whitelist()
def modes_of_payment():
	require(*ANY_STAFF)
	return frappe.get_all("Mode of Payment", filters={"enabled": 1}, pluck="name", order_by="name")


# ─── Rate cards ──────────────────────────────────────────────────────────────
@frappe.whitelist()
def list_rate_cards():
	require(*ANY_STAFF)
	cards = []
	for name in frappe.get_all("Rate Card", pluck="name", order_by="card_name"):
		doc = frappe.get_doc("Rate Card", name)
		cards.append(
			{
				"name": doc.name,
				"card_name": doc.card_name,
				"direction": doc.direction,
				"is_default": doc.is_default,
				"items": [
					{"charge_type": i.charge_type, "calc_basis": i.calc_basis, "rate": i.rate, "minimum": i.minimum}
					for i in doc.items
				],
			}
		)
	return cards


@frappe.whitelist()
def save_rate_card(payload):
	require(*CAN_RATE)
	data = frappe.parse_json(payload) if isinstance(payload, str) else payload
	name = data.get("name")
	doc = frappe.get_doc("Rate Card", name) if name else frappe.new_doc("Rate Card")
	doc.card_name = data.get("card_name") or doc.card_name
	doc.direction = data.get("direction") or ""
	doc.is_default = cint(data.get("is_default") or 0)
	doc.set("items", [])
	for row in data.get("items") or []:
		if row.get("charge_type") and row.get("rate") is not None:
			doc.append(
				"items",
				{
					"charge_type": row["charge_type"],
					"calc_basis": row.get("calc_basis") or "Flat",
					"rate": flt(row["rate"]),
					"minimum": flt(row.get("minimum") or 0),
				},
			)
	doc.save()
	return {"name": doc.name}


@frappe.whitelist()
def delete_rate_card(name):
	require(*CAN_RATE)
	frappe.delete_doc("Rate Card", name)
	return {"ok": True}
