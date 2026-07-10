# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Customer portal API. Every endpoint resolves the session user to their
Customer via require_customer() and scopes queries to it — a customer can
never read another customer's documents (NFR-2)."""

import frappe
from frappe import _
from frappe.utils import cint

from bwm_logistics.api._perm import require_customer

ACTIVE = ("not in", ["Delivered", "Cancelled"])


@frappe.whitelist()
def overview():
	customer = require_customer()
	shipments = frappe.get_all(
		"Shipment",
		filters={"customer": customer},
		fields=["name", "status", "current_milestone", "direction", "destination", "modified"],
		order_by="modified desc",
		limit=5,
	)
	unpaid = frappe.db.count(
		"Sales Invoice", {"customer": customer, "docstatus": 1, "outstanding_amount": (">", 0)}
	)
	return {
		"active_count": frappe.db.count("Shipment", {"customer": customer, "status": ACTIVE}),
		"unpaid_invoices": unpaid,
		"recent": shipments,
	}


@frappe.whitelist()
def my_shipments(start=0, limit=25):
	customer = require_customer()
	rows = frappe.get_all(
		"Shipment",
		filters={"customer": customer},
		fields=[
			"name", "status", "current_milestone", "direction", "origin", "destination",
			"container", "total_packages", "total_charges", "sales_invoice", "modified",
		],
		order_by="modified desc",
		start=cint(start),
		limit=min(cint(limit) or 25, 100),
	)
	return {"rows": rows, "total": frappe.db.count("Shipment", {"customer": customer})}


@frappe.whitelist()
def shipment_detail(name):
	customer = require_customer()
	shipment = frappe.db.get_value(
		"Shipment", name,
		["name", "customer", "status", "current_milestone", "direction", "origin",
			"destination", "delivery_address", "container", "total_packages",
			"total_weight_kg", "total_volume_cbm", "total_charges", "sales_invoice"],
		as_dict=True,
	)
	if not shipment or shipment.customer != customer:
		frappe.throw(_("Shipment not found."), frappe.DoesNotExistError)

	from bwm_logistics.api.shipments import get_timeline

	out = shipment
	out["timeline"] = get_timeline(name)
	out["packages"] = frappe.get_all(
		"Shipment Package",
		filters={"parenttype": "Shipment", "parent": name},
		fields=["description", "qty", "weight_kg", "volume_cbm"],
		order_by="idx",
	)
	if shipment.container:
		out["eta"] = frappe.db.get_value("Container", shipment.container, "eta")
	if shipment.sales_invoice:
		out["invoice"] = frappe.db.get_value(
			"Sales Invoice", shipment.sales_invoice,
			["name", "status", "grand_total", "outstanding_amount", "currency"], as_dict=True,
		)
	out.pop("customer", None)
	out.pop("container", None)
	return out


@frappe.whitelist()
def my_invoices():
	customer = require_customer()
	return frappe.get_all(
		"Sales Invoice",
		filters={"customer": customer, "docstatus": 1},
		fields=["name", "posting_date", "status", "grand_total", "outstanding_amount", "currency"],
		order_by="posting_date desc",
		limit=100,
	)


@frappe.whitelist()
def get_profile():
	customer = require_customer()
	row = frappe.db.get_value(
		"Customer", customer,
		["customer_name", "email_id", "mobile_no", "bwm_notify_email", "bwm_notify_sms"],
		as_dict=True,
	)
	row["user"] = frappe.session.user
	return row


@frappe.whitelist()
def update_prefs(notify_email=None, notify_sms=None):
	customer = require_customer()
	updates = {}
	if notify_email is not None:
		updates["bwm_notify_email"] = cint(notify_email)
	if notify_sms is not None:
		updates["bwm_notify_sms"] = cint(notify_sms)
	if updates:
		frappe.db.set_value("Customer", customer, updates)
	return {"ok": True}


@frappe.whitelist()
def payment_link(invoice):
	"""'Pay now' — a Payment Request routed through frappe/payments. Returns
	the gateway checkout URL. Clear error when no gateway is configured yet."""
	customer = require_customer()
	inv = frappe.db.get_value(
		"Sales Invoice", invoice,
		["name", "customer", "docstatus", "outstanding_amount"], as_dict=True,
	)
	if not inv or inv.customer != customer:
		frappe.throw(_("Invoice not found."), frappe.DoesNotExistError)
	if inv.docstatus != 1 or not inv.outstanding_amount:
		frappe.throw(_("This invoice has nothing outstanding."))

	if not frappe.db.exists("DocType", "Payment Gateway Account") or not frappe.db.exists(
		"Payment Gateway Account", {"is_default": 1}
	):
		frappe.throw(
			_("Online payment is not configured yet. Please contact us to pay this invoice.")
		)

	# Reuse an open Payment Request if one exists for this invoice.
	existing = frappe.db.get_value(
		"Payment Request",
		{"reference_doctype": "Sales Invoice", "reference_name": invoice, "status": ("in", ["Initiated", "Requested"])},
		["name", "payment_url"],
		as_dict=True,
	)
	if existing and existing.payment_url:
		return {"payment_url": existing.payment_url}

	from erpnext.accounts.doctype.payment_request.payment_request import make_payment_request

	pr = make_payment_request(
		dt="Sales Invoice",
		dn=invoice,
		recipient_id=frappe.session.user,
		submit_doc=True,
		return_doc=True,
		mute_email=True,
	)
	return {"payment_url": pr.get_payment_url()}
