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
	ensure_user_role_field()
	ensure_invoice_shipment_fields()
	backfill_invoice_shipment_tags()
	ensure_default_print_format()
	ensure_invoice_print_permissions()
	seed_milestone_templates()
	seed_logistics_roles()
	frappe.db.commit()


def ensure_invoice_print_permissions():
	"""Billing staff (Manager/Accounts) download branded invoice PDFs through
	frappe's download_pdf endpoint, which checks DocType read/print perms —
	our custom roles need them granted explicitly (portal customers already
	get theirs from ERPNext's standard Customer role)."""
	from frappe.permissions import add_permission, update_permission_property

	if not frappe.db.exists("DocType", "Sales Invoice"):
		return
	for role in ("Logistics Manager", "Logistics Accounts"):
		for doctype in ("Sales Invoice", "Purchase Invoice"):
			add_permission(doctype, role, permlevel=0)  # read=1, idempotent
			update_permission_property(doctype, role, 0, "print", 1, validate=False)
			update_permission_property(doctype, role, 0, "submit", 0, validate=False)


def ensure_invoice_shipment_fields():
	"""Sales/Purchase Invoice → Shipment tag. The SINGLE source of truth for
	shipment P&L: revenue = tagged Sales Invoices, cost = tagged Purchase
	Invoices (PRD P7)."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	field = {
		"fieldname": "bwm_shipment",
		"fieldtype": "Link",
		"label": "Shipment",
		"options": "Shipment",
		"insert_after": "customer" if frappe.db.exists("DocType", "Sales Invoice") else None,
		"search_index": 1,
	}
	doctypes = {}
	if frappe.db.exists("DocType", "Sales Invoice"):
		doctypes["Sales Invoice"] = [dict(field, insert_after="customer")]
	if frappe.db.exists("DocType", "Purchase Invoice"):
		doctypes["Purchase Invoice"] = [dict(field, insert_after="supplier")]
	if doctypes:
		create_custom_fields(doctypes, ignore_validate=True)


def backfill_invoice_shipment_tags():
	"""Tag legacy freight invoices (created before P7) from
	Shipment.sales_invoice. Idempotent — only fills empty tags."""
	if not frappe.db.exists("DocType", "Sales Invoice"):
		return
	if not frappe.db.has_column("Sales Invoice", "bwm_shipment"):
		return
	for row in frappe.get_all(
		"Shipment",
		filters={"sales_invoice": ("is", "set")},
		fields=["name", "sales_invoice"],
		limit_page_length=0,
	):
		if not frappe.db.get_value("Sales Invoice", row.sales_invoice, "bwm_shipment"):
			frappe.db.set_value(
				"Sales Invoice", row.sales_invoice, "bwm_shipment", row.name, update_modified=False
			)


def ensure_default_print_format():
	"""Make the branded 'BWM Invoice' format the Sales Invoice default so
	every Download PDF (operator + portal) uses it."""
	if not frappe.db.exists("Print Format", "BWM Invoice"):
		return  # synced on migrate; next run picks it up
	frappe.make_property_setter(
		{
			"doctype": "Sales Invoice",
			"doctype_or_field": "DocType",
			"property": "default_print_format",
			"value": "BWM Invoice",
			"property_type": "Data",
		},
		is_system_generated=True,
	)


def ensure_user_role_field():
	"""User.bwm_logistics_role — the single admin-managed app role that
	controls which operator pages a staff user sees (ex_beauty pattern)."""
	from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

	create_custom_fields(
		{
			"User": [
				{
					"fieldname": "bwm_logistics_role",
					"fieldtype": "Link",
					"label": "Logistics Role",
					"options": "Logistics Role",
					"insert_after": "role_profile_name",
					"description": "The logistics app role controlling which operator pages this user sees (managed in the app's Settings).",
				}
			]
		},
		ignore_validate=True,
	)


def seed_logistics_roles():
	"""First-time setup of admin-managed roles. Runs only while none exist so
	the operator owns them afterwards. Mirrors the previous static role maps."""
	import json

	if not frappe.db.exists("DocType", "Logistics Role"):
		return
	if frappe.get_all("Logistics Role", limit=1):
		return

	def make(role_name, is_admin=0, all_pages=0, pages=None):
		frappe.get_doc(
			{
				"doctype": "Logistics Role",
				"role_name": role_name,
				"is_admin": is_admin,
				"all_pages": all_pages,
				"pages": json.dumps(pages or []),
			}
		).insert(ignore_permissions=True)

	make("Admin", is_admin=1)
	make("Manager", all_pages=1)
	make(
		"Operations",
		pages=["dashboard", "containers", "shipments", "scan", "dispatch", "customers", "billing", "reports", "notifications"],
	)
	make("Accounts", pages=["dashboard", "customers", "billing", "reports", "notifications"])


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
				{
					"fieldname": "bwm_notify_whatsapp",
					"fieldtype": "Check",
					"label": "Notify by WhatsApp",
					"default": "1",
					"insert_after": "bwm_notify_sms",
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
