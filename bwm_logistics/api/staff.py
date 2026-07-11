# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Staff & role management (Settings screen). Managers create staff logins
(Frappe emails the set-password link) and assign each user ONE admin-managed
Logistics Role that controls their operator pages. Frappe roles stay the API
permission gate and are synced from the app role:

	every staff        → Logistics Operations (base gate)
	billing/reports    → + Logistics Accounts
	is_admin           → + Logistics Manager
"""

import json

import frappe
from frappe import _
from frappe.utils import validate_email_address

from bwm_logistics.api._perm import (
	ANY_STAFF,
	ROLE_ACCOUNTS,
	ROLE_CUSTOMER,
	ROLE_DRIVER,
	ROLE_MANAGER,
	ROLE_OPERATIONS,
	ROLE_SYS,
	require,
)

CAN_MANAGE = (ROLE_MANAGER, ROLE_SYS)
SYNCED_FRAPPE_ROLES = {ROLE_OPERATIONS, ROLE_ACCOUNTS, ROLE_MANAGER}
BILLING_PAGES = {"billing", "reports"}


# ─── Roles ───────────────────────────────────────────────────────────────────
@frappe.whitelist()
def list_roles():
	"""All Logistics Roles + the page catalog for the roles editor."""
	require(*ANY_STAFF)
	from bwm_logistics.api.access import OPERATOR_PAGES

	roles = []
	for name in frappe.get_all("Logistics Role", pluck="name", order_by="role_name"):
		doc = frappe.get_cached_doc("Logistics Role", name)
		roles.append(
			{
				"name": doc.name,
				"role_name": doc.role_name,
				"is_admin": doc.is_admin,
				"all_pages": doc.all_pages,
				"pages": sorted(doc.page_keys() - {"settings"}) if not doc.is_admin else [],
				"members": frappe.db.count("User", {"bwm_logistics_role": name, "enabled": 1}),
			}
		)
	return {
		"pages": [p for p in OPERATOR_PAGES if p["key"] != "settings"],
		"roles": roles,
	}


@frappe.whitelist()
def save_role(payload):
	require(*CAN_MANAGE)
	data = frappe.parse_json(payload) if isinstance(payload, str) else payload
	name = data.get("name")
	role_name = (data.get("role_name") or "").strip()
	if not role_name:
		frappe.throw(_("Role name is required."))
	# Upsert by role name (it's the primary key).
	if not name and frappe.db.exists("Logistics Role", role_name):
		name = role_name
	doc = frappe.get_doc("Logistics Role", name) if name else frappe.new_doc("Logistics Role")
	doc.role_name = role_name
	doc.is_admin = 1 if data.get("is_admin") else 0
	doc.all_pages = 1 if data.get("all_pages") else 0
	doc.pages = json.dumps(data.get("pages") or [])
	doc.save()
	# Members' Frappe-role gates may change with the role definition.
	for user in frappe.get_all("User", filters={"bwm_logistics_role": doc.name}, pluck="name"):
		_sync_frappe_roles(user, doc)
	return {"name": doc.name}


@frappe.whitelist()
def delete_role(name):
	require(*CAN_MANAGE)
	if frappe.db.count("User", {"bwm_logistics_role": name, "enabled": 1}):
		frappe.throw(_("Reassign the members of {0} before deleting it.").format(name))
	frappe.delete_doc("Logistics Role", name)
	return {"ok": True}


# ─── Staff ───────────────────────────────────────────────────────────────────
@frappe.whitelist()
def list_staff():
	require(*ANY_STAFF)
	users = frappe.get_all(
		"User",
		filters={"enabled": 1, "name": ("not in", ["Administrator", "Guest"])},
		fields=["name", "full_name", "bwm_logistics_role", "last_active"],
		order_by="full_name",
		limit_page_length=0,
	)
	staff = []
	for u in users:
		roles = set(frappe.get_roles(u.name))
		if not (roles & set(ANY_STAFF)):
			continue
		if ROLE_CUSTOMER in roles and not (roles & {ROLE_OPERATIONS, ROLE_ACCOUNTS, ROLE_MANAGER}):
			continue  # portal customers aren't staff
		u["is_driver"] = ROLE_DRIVER in roles
		u["is_super"] = bool(roles & {"System Manager", ROLE_MANAGER})
		staff.append(u)
	return staff


@frappe.whitelist()
def create_staff(full_name, email, logistics_role=None):
	"""New staff login — Frappe emails the set-new-password link."""
	require(*CAN_MANAGE)
	email = (email or "").strip().lower()
	validate_email_address(email, throw=True)
	full_name = (full_name or "").strip()
	if not full_name:
		frappe.throw(_("Name is required."))

	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		parts = full_name.split(None, 1)
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = parts[0]
		user.last_name = parts[1] if len(parts) > 1 else None
		user.user_type = "Website User"
		user.send_welcome_email = 1
		user.insert(ignore_permissions=True)

	return assign_role(email, logistics_role)


@frappe.whitelist()
def assign_role(user, logistics_role=None):
	"""Assign the single Logistics Role (or clear it) + sync Frappe gates."""
	require(*CAN_MANAGE)
	logistics_role = logistics_role or None
	if logistics_role and not frappe.db.exists("Logistics Role", logistics_role):
		frappe.throw(_("Unknown role {0}.").format(logistics_role))
	frappe.db.set_value("User", user, "bwm_logistics_role", logistics_role)
	role_doc = frappe.get_cached_doc("Logistics Role", logistics_role) if logistics_role else None
	_sync_frappe_roles(user, role_doc)
	return {"user": user, "logistics_role": logistics_role}


def _sync_frappe_roles(user, role_doc):
	"""Frappe roles = coarse API gate, derived from the app role's pages."""
	udoc = frappe.get_doc("User", user)
	current = set(frappe.get_roles(user)) & SYNCED_FRAPPE_ROLES

	want = {ROLE_OPERATIONS}
	if role_doc:
		pages = role_doc.page_keys()
		if role_doc.is_admin:
			want |= {ROLE_MANAGER, ROLE_ACCOUNTS}
		elif role_doc.all_pages or (pages & BILLING_PAGES):
			want.add(ROLE_ACCOUNTS)

	to_remove = current - want
	to_add = want - current
	if to_remove:
		udoc.remove_roles(*to_remove)
	if to_add:
		udoc.add_roles(*to_add)
