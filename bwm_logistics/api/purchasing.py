# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Purchasing API (P7) — record what a shipment really costs.

Costs (goods purchases, duties, taxes, clearing, transport…) are REAL ERPNext
Purchase Invoices against Suppliers (update_stock=0, service item), optionally
tagged to a Shipment via the bwm_shipment custom field — that tag is what the
shipment P&L reads. Supplier payments post as Pay-direction Payment Entries.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate, nowdate

from bwm_logistics.api._perm import ANY_STAFF, ROLE_ACCOUNTS, ROLE_MANAGER, ROLE_SYS, require

CAN_BUY = (ROLE_MANAGER, ROLE_ACCOUNTS, ROLE_SYS)


# ─── Suppliers ───────────────────────────────────────────────────────────────
@frappe.whitelist()
def list_suppliers(search=None, start=0, limit=20):
	require(*ANY_STAFF)
	filters = {"disabled": 0}
	or_filters = None
	if search:
		like = f"%{search}%"
		or_filters = {"supplier_name": ("like", like), "name": ("like", like)}
	rows = frappe.get_all(
		"Supplier",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "supplier_name", "supplier_group"],
		order_by="supplier_name",
		start=cint(start),
		limit=min(cint(limit) or 20, 100),
	)
	return rows


@frappe.whitelist()
def create_supplier(supplier_name, phone=None):
	require(*CAN_BUY)
	supplier_name = (supplier_name or "").strip()
	if not supplier_name:
		frappe.throw(_("Supplier name is required."))
	existing = frappe.db.get_value("Supplier", {"supplier_name": supplier_name}, "name")
	if existing:
		return {"name": existing}
	doc = frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": supplier_name,
			"supplier_type": "Company",
			# Leaf group fallback — reqd-adjacent in ERPNext UIs.
			"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0})
			or "All Supplier Groups",
			"mobile_no": phone,
		}
	)
	doc.insert(ignore_permissions=True)
	return {"name": doc.name}


# ─── Purchases ───────────────────────────────────────────────────────────────
@frappe.whitelist()
def record_purchase(payload):
	"""Record a supplier bill: cost lines (goods, duty, tax, clearing…) →
	submitted service Purchase Invoice, optionally tagged to a shipment."""
	require(*CAN_BUY)
	data = frappe.parse_json(payload) if isinstance(payload, str) else payload

	supplier = data.get("supplier")
	if not supplier or not frappe.db.exists("Supplier", supplier):
		frappe.throw(_("Pick a supplier."))
	lines = [l for l in (data.get("lines") or []) if l.get("description") and flt(l.get("amount")) > 0]
	if not lines:
		frappe.throw(_("Add at least one cost line with an amount."))
	shipment = data.get("shipment") or None
	if shipment and not frappe.db.exists("Shipment", shipment):
		frappe.throw(_("Unknown shipment {0}.").format(shipment))

	posting_date = getdate(data.get("posting_date") or nowdate())
	due_date = getdate(data.get("due_date")) if data.get("due_date") else posting_date
	if due_date < posting_date:
		due_date = posting_date

	item_code = _ensure_cost_item()
	expense_account = _default_expense_account()

	pi = frappe.new_doc("Purchase Invoice")
	pi.supplier = supplier
	pi.posting_date = posting_date
	pi.due_date = due_date
	pi.bill_no = data.get("reference") or None
	pi.bwm_shipment = shipment
	pi.update_stock = 0
	for line in lines:
		pi.append(
			"items",
			{
				"item_code": item_code,
				"item_name": line["description"][:140],
				"description": line["description"],
				"qty": 1,
				"rate": flt(line["amount"]),
				"expense_account": expense_account,
			},
		)
	pi.flags.ignore_permissions = True
	pi.set_missing_values()
	pi.insert(ignore_permissions=True)
	pi.submit()
	return {"purchase_invoice": pi.name, "grand_total": pi.grand_total}


@frappe.whitelist()
def list_purchases(supplier=None, shipment=None, status=None, search=None, start=0, limit=25):
	require(*ANY_STAFF)
	filters = {"docstatus": 1}
	if supplier:
		filters["supplier"] = supplier
	if shipment:
		filters["bwm_shipment"] = shipment
	if status == "Unpaid":
		filters["outstanding_amount"] = (">", 0)
	elif status == "Paid":
		filters["outstanding_amount"] = ("<=", 0)
	or_filters = None
	if search:
		like = f"%{search}%"
		or_filters = {"name": ("like", like), "supplier_name": ("like", like), "bill_no": ("like", like)}

	rows = frappe.get_all(
		"Purchase Invoice",
		filters=filters,
		or_filters=or_filters,
		fields=[
			"name", "supplier", "supplier_name", "posting_date", "due_date", "status",
			"bill_no", "bwm_shipment", "grand_total", "outstanding_amount", "currency",
		],
		order_by="posting_date desc, creation desc",
		start=cint(start),
		limit=min(cint(limit) or 25, 100),
	)
	return {"rows": rows, "total": frappe.db.count("Purchase Invoice", filters)}


@frappe.whitelist()
def purchases_overview():
	require(*ANY_STAFF)
	unpaid = frappe.get_all(
		"Purchase Invoice",
		filters={"docstatus": 1, "outstanding_amount": (">", 0)},
		fields=["outstanding_amount", "supplier_name"],
	)
	from frappe.utils import get_first_day

	spent = frappe.get_all(
		"Purchase Invoice",
		filters={"docstatus": 1, "posting_date": (">=", get_first_day(nowdate()))},
		fields=["grand_total"],
	)
	return {
		"owed_total": round(sum(flt(r.outstanding_amount) for r in unpaid), 2),
		"owed_count": len(unpaid),
		"spent_this_month": round(sum(flt(r.grand_total) for r in spent), 2),
	}


@frappe.whitelist()
def pay_supplier(purchase_invoice, amount, mode_of_payment="Cash", reference=None):
	"""Record a payment to a supplier against a purchase invoice (partial OK)."""
	require(*CAN_BUY)
	pi = frappe.db.get_value(
		"Purchase Invoice", purchase_invoice, ["docstatus", "outstanding_amount"], as_dict=True
	)
	if not pi or pi.docstatus != 1:
		frappe.throw(_("Purchase invoice {0} not found or not submitted.").format(purchase_invoice))
	amount = flt(amount)
	if amount <= 0:
		frappe.throw(_("Amount must be positive."))
	if amount > flt(pi.outstanding_amount):
		frappe.throw(_("Amount exceeds the outstanding {0}.").format(pi.outstanding_amount))

	from bwm_logistics.api.billing import make_payment_entry

	pe = make_payment_entry(purchase_invoice, amount, mode_of_payment, reference, doctype="Purchase Invoice")
	return {
		"payment_entry": pe,
		"outstanding": frappe.db.get_value("Purchase Invoice", purchase_invoice, "outstanding_amount"),
	}


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _ensure_cost_item() -> str:
	"""Non-stock service Item carrying purchase cost lines (rate overridden
	per line). Purchase-side twin of shipment.py::_ensure_charge_item."""
	code = "Logistics Cost"
	if not frappe.db.exists("Item", code):
		item = frappe.new_doc("Item")
		item.item_code = code
		item.item_name = code
		item.item_group = frappe.db.get_value("Item Group", {"is_group": 0}) or "All Item Groups"
		item.is_stock_item = 0
		item.is_sales_item = 0
		item.is_purchase_item = 1
		item.stock_uom = "Nos"
		item.flags.ignore_permissions = True
		item.insert(ignore_permissions=True)
	return code


def _default_expense_account() -> str:
	"""Company default expense account, falling back to any leaf Expense
	account (fresh charts always have one)."""
	company = frappe.db.get_default("company") or frappe.db.get_value("Company", {}, "name")
	account = company and frappe.db.get_value("Company", company, "default_expense_account")
	if not account:
		account = frappe.db.get_value(
			"Account", {"company": company, "root_type": "Expense", "is_group": 0}, "name"
		)
	if not account:
		frappe.throw(_("No expense account found — set a Default Expense Account on the Company."))
	return account
