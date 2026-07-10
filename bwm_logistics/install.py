# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Idempotent install/migrate setup. Wired to after_install AND after_migrate
(hooks.py) so a deployment that misses an install run self-heals."""

import frappe

# (role_name, desk_access, description)
LOGISTICS_ROLES = (
	("Logistics Manager", 1, "Full access to the logistics operator app and its settings."),
	("Logistics Operations", 0, "Day-to-day operations: containers, shipments, dispatch, customers."),
	("Logistics Accounts", 0, "Billing: invoices, payments, customer accounts."),
	("Logistics Driver", 0, "Driver: assigned delivery runs and proof of delivery."),
	("Logistics Customer", 0, "Portal customer: track shipments, invoices, online payment."),
)


DEFAULT_MILESTONES = {
	"Import": [
		"Booked",
		"Loaded at Origin",
		"Vessel Departed",
		"In Transit",
		"Arrived at Port",
		"Customs Clearance",
		"Released",
		"At Warehouse",
		"Ready for Delivery",
		"Delivered",
	],
	"Export": [
		"Received at Warehouse",
		"Loaded",
		"Customs Clearance",
		"Vessel Departed",
		"In Transit",
		"Arrived at Destination",
		"Delivered",
	],
}


def after_install():
	ensure_roles()
	ensure_customer_fields()
	seed_milestone_templates()
	frappe.db.commit()


def ensure_roles():
	for role_name, desk_access, desc in LOGISTICS_ROLES:
		if frappe.db.exists("Role", role_name):
			continue
		role = frappe.new_doc("Role")
		role.role_name = role_name
		role.desk_access = desk_access
		role.description = desc
		role.insert(ignore_permissions=True)


def ensure_customer_fields():
	"""Per-customer notification opt-ins, read by the notification engine and
	editable from the portal profile page."""
	if not frappe.db.exists("DocType", "Customer"):
		return  # ERPNext missing — nothing to extend
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"Customer": [
				{
					"fieldname": "bwm_notifications_section",
					"fieldtype": "Section Break",
					"label": "Logistics Notifications",
					"insert_after": "customer_details",
				},
				{
					"fieldname": "bwm_notify_email",
					"fieldtype": "Check",
					"label": "Notify by Email",
					"default": "1",
					"insert_after": "bwm_notifications_section",
				},
				{
					"fieldname": "bwm_notify_sms",
					"fieldtype": "Check",
					"label": "Notify by SMS",
					"default": "1",
					"insert_after": "bwm_notify_email",
				},
			]
		},
		ignore_validate=True,
	)


def seed_milestone_templates():
	"""Ship sensible default milestone flows; runs only while none exist so
	the operator owns them afterwards."""
	if not frappe.db.exists("DocType", "Milestone Template"):
		return
	if frappe.get_all("Milestone Template", limit=1):
		return
	for direction, milestones in DEFAULT_MILESTONES.items():
		doc = frappe.new_doc("Milestone Template")
		doc.template_name = f"Standard {direction}"
		doc.direction = direction
		doc.is_default = 1
		for m in milestones:
			doc.append("milestones", {"milestone": m, "notify_customer": 1})
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
