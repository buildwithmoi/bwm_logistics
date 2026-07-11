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


# ─── Statements & receipts ───────────────────────────────────────────────────
def build_statement(customer: str, from_date: str, to_date: str) -> dict:
	"""Invoices (debits) + received payments (credits) with a running balance.
	Shared by the operator statement page and the portal's My Statement."""
	inv_filters = {"docstatus": 1, "customer": customer}
	pay_filters = {"docstatus": 1, "payment_type": "Receive", "party_type": "Customer", "party": customer}

	def total(doctype, field, filters, upto=None, since=None):
		f = dict(filters)
		if upto:
			f["posting_date"] = ("<", upto)
		if since:
			f["posting_date"] = ("between", [since, to_date])
		return sum(flt(r[field]) for r in frappe.get_all(doctype, filters=f, fields=[field]))

	opening = total("Sales Invoice", "grand_total", inv_filters, upto=from_date) - total(
		"Payment Entry", "paid_amount", pay_filters, upto=from_date
	)

	rows = []
	for r in frappe.get_all(
		"Sales Invoice",
		filters={**inv_filters, "posting_date": ("between", [from_date, to_date])},
		fields=["name", "posting_date", "grand_total"],
	):
		rows.append({"date": str(r.posting_date), "ref": r.name, "type": "Invoice", "debit": flt(r.grand_total), "credit": 0})
	for r in frappe.get_all(
		"Payment Entry",
		filters={**pay_filters, "posting_date": ("between", [from_date, to_date])},
		fields=["name", "posting_date", "paid_amount", "mode_of_payment"],
	):
		rows.append(
			{
				"date": str(r.posting_date), "ref": r.name,
				"type": f"Payment ({r.mode_of_payment})" if r.mode_of_payment else "Payment",
				"debit": 0, "credit": flt(r.paid_amount),
			}
		)
	rows.sort(key=lambda x: (x["date"], x["type"]))
	balance = opening
	for row in rows:
		balance += row["debit"] - row["credit"]
		row["balance"] = round(balance, 2)

	settings = frappe.get_cached_doc("Logistics Settings")
	return {
		"customer": customer,
		"customer_name": frappe.db.get_value("Customer", customer, "customer_name"),
		"business_name": settings.business_name or "BWM Logistics",
		"from_date": from_date,
		"to_date": to_date,
		"opening_balance": round(opening, 2),
		"rows": rows,
		"total_invoiced": round(sum(r["debit"] for r in rows), 2),
		"total_paid": round(sum(r["credit"] for r in rows), 2),
		"closing_balance": round(balance, 2),
	}


@frappe.whitelist()
def customer_statement(customer, from_date=None, to_date=None):
	require(*ANY_STAFF)
	if not frappe.db.exists("Customer", customer):
		frappe.throw(_("Unknown customer {0}.").format(customer))
	from frappe.utils import add_months

	from_date = from_date or add_months(nowdate(), -3)
	to_date = to_date or nowdate()
	return build_statement(customer, str(from_date), str(to_date))


@frappe.whitelist()
def get_receipt(payment_entry):
	"""Everything the branded payment receipt needs (print page)."""
	require(*ANY_STAFF)
	pe = frappe.db.get_value(
		"Payment Entry", payment_entry,
		["name", "posting_date", "party", "party_name", "paid_amount",
			"mode_of_payment", "reference_no", "paid_to_account_currency", "docstatus"],
		as_dict=True,
	)
	if not pe or pe.docstatus != 1:
		frappe.throw(_("Payment {0} not found.").format(payment_entry))
	refs = frappe.get_all(
		"Payment Entry Reference",
		filters={"parenttype": "Payment Entry", "parent": payment_entry},
		fields=["reference_name", "allocated_amount"],
	)
	invoices = []
	for r in refs:
		invoices.append(
			{
				"invoice": r.reference_name,
				"allocated": flt(r.allocated_amount),
				"outstanding": frappe.db.get_value("Sales Invoice", r.reference_name, "outstanding_amount"),
			}
		)
	from frappe.utils import money_in_words

	settings = frappe.get_cached_doc("Logistics Settings")
	return {
		**pe,
		"invoices": invoices,
		"in_words": money_in_words(pe.paid_amount, pe.paid_to_account_currency),
		"business_name": settings.business_name or "BWM Logistics",
		"contact_phone": settings.contact_phone,
		"contact_email": settings.contact_email,
	}


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
