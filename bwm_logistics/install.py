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


def after_install():
	ensure_roles()
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
