# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Operator API — customers and portal-account invitations (FR-AUTH-4:
staff create accounts; Frappe emails the set-new-password link)."""

import frappe
from frappe import _
from frappe.utils import cint, validate_email_address

from bwm_logistics.api._perm import ANY_STAFF, ROLE_MANAGER, ROLE_OPERATIONS, ROLE_SYS, require

CAN_WRITE = (ROLE_MANAGER, ROLE_OPERATIONS, ROLE_SYS)


@frappe.whitelist()
def list_customers(search=None, start=0, limit=25):
	require(*ANY_STAFF)
	filters = {"disabled": 0}
	or_filters = None
	if search:
		like = f"%{search}%"
		or_filters = {"customer_name": ("like", like), "mobile_no": ("like", like), "email_id": ("like", like)}
	rows = frappe.get_all(
		"Customer",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "customer_name", "customer_type", "mobile_no", "email_id", "modified"],
		order_by="modified desc",
		start=cint(start),
		limit=min(cint(limit) or 25, 100),
	)
	if rows:
		from collections import Counter

		names = [r.name for r in rows]
		# Counted in Python — raw SQL aggregates in `fields` are rejected in
		# HTTP request context.
		tagged = frappe.get_all(
			"Shipment",
			filters={"customer": ("in", names)},
			fields=["customer"],
			limit_page_length=0,
		)
		counts = Counter(t.customer for t in tagged)
		portal_users = _portal_users(names)
		for r in rows:
			r["shipment_count"] = counts.get(r.name, 0)
			r["portal_user"] = portal_users.get(r.name)
	return {"rows": rows, "total": frappe.db.count("Customer", filters)}


def _portal_users(customer_names: list[str]) -> dict:
	"""{customer: user_email} for customers with a linked portal login."""
	links = frappe.get_all(
		"Dynamic Link",
		filters={"parenttype": "Contact", "link_doctype": "Customer", "link_name": ("in", customer_names)},
		fields=["parent", "link_name"],
	)
	if not links:
		return {}
	contact_user = dict(
		frappe.get_all(
			"Contact",
			filters={"name": ("in", [l.parent for l in links]), "user": ("is", "set")},
			fields=["name", "user"],
			as_list=True,
		)
	)
	out = {}
	for l in links:
		user = contact_user.get(l.parent)
		if user and l.link_name not in out:
			out[l.link_name] = user
	return out


@frappe.whitelist()
def get_customer(name):
	require(*ANY_STAFF)
	doc = frappe.db.get_value(
		"Customer", name,
		["name", "customer_name", "customer_type", "mobile_no", "email_id",
			"bwm_notify_email", "bwm_notify_sms"],
		as_dict=True,
	)
	if not doc:
		frappe.throw(_("Unknown customer {0}.").format(name))
	doc["portal_user"] = _portal_users([name]).get(name)
	doc["shipments"] = frappe.get_all(
		"Shipment",
		filters={"customer": name},
		fields=["name", "status", "current_milestone", "container", "total_charges", "sales_invoice", "modified"],
		order_by="modified desc",
		limit=50,
	)
	return doc


@frappe.whitelist()
def save_customer(payload):
	"""Create/update a Customer (+ keep a primary Contact in step so email &
	mobile resolve for notifications)."""
	require(*CAN_WRITE)
	data = frappe.parse_json(payload) if isinstance(payload, str) else payload
	name = data.get("name")
	if name:
		doc = frappe.get_doc("Customer", name)
	else:
		doc = frappe.new_doc("Customer")
		doc.customer_type = data.get("customer_type") or "Individual"
	if data.get("customer_name"):
		doc.customer_name = data["customer_name"]
	for field in ("mobile_no", "email_id", "bwm_notify_email", "bwm_notify_sms"):
		if field in data:
			doc.set(field, data.get(field))
	doc.save()
	_sync_primary_contact(doc, data.get("email_id"), data.get("mobile_no"))
	return {"name": doc.name}


def _sync_primary_contact(customer_doc, email, mobile):
	"""Ensure a Contact linked to the customer carrying email/mobile."""
	if not (email or mobile):
		return
	contact_name = frappe.db.get_value(
		"Dynamic Link",
		{"parenttype": "Contact", "link_doctype": "Customer", "link_name": customer_doc.name},
		"parent",
	)
	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
	else:
		contact = frappe.new_doc("Contact")
		contact.first_name = customer_doc.customer_name
		contact.append("links", {"link_doctype": "Customer", "link_name": customer_doc.name})
	if email and not any(e.email_id == email for e in contact.email_ids):
		contact.append("email_ids", {"email_id": email, "is_primary": 1 if not contact.email_ids else 0})
	if mobile and not any(p.phone == mobile for p in contact.phone_nos):
		contact.append("phone_nos", {"phone": mobile, "is_primary_mobile_no": 1 if not contact.phone_nos else 0})
	contact.flags.ignore_permissions = True
	contact.save(ignore_permissions=True)


@frappe.whitelist()
def invite_portal_user(customer, email):
	"""Create the customer's portal login. Frappe sends the standard welcome
	email with a set-new-password link (no password handling here)."""
	require(*CAN_WRITE)
	email = (email or "").strip().lower()
	validate_email_address(email, throw=True)
	if not frappe.db.exists("Customer", customer):
		frappe.throw(_("Unknown customer {0}.").format(customer))

	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
		if "Logistics Customer" not in [r.role for r in user.roles]:
			user.add_roles("Logistics Customer")
	else:
		customer_name = frappe.db.get_value("Customer", customer, "customer_name") or customer
		parts = customer_name.split(None, 1)
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = parts[0]
		user.last_name = parts[1] if len(parts) > 1 else None
		user.user_type = "Website User"
		user.send_welcome_email = 1  # ← Frappe emails the set-password link
		user.insert(ignore_permissions=True)
		user.add_roles("Logistics Customer")

	# Link Contact.user so portal endpoints resolve User → Customer.
	contact_name = frappe.db.get_value(
		"Dynamic Link",
		{"parenttype": "Contact", "link_doctype": "Customer", "link_name": customer},
		"parent",
	)
	if contact_name:
		contact = frappe.get_doc("Contact", contact_name)
	else:
		contact = frappe.new_doc("Contact")
		contact.first_name = frappe.db.get_value("Customer", customer, "customer_name") or customer
		contact.append("links", {"link_doctype": "Customer", "link_name": customer})
	contact.user = email
	if email and not any(e.email_id == email for e in contact.email_ids):
		contact.append("email_ids", {"email_id": email, "is_primary": 1 if not contact.email_ids else 0})
	contact.flags.ignore_permissions = True
	contact.save(ignore_permissions=True)

	return {"user": email}
