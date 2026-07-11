# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Role-based page access + post-login destinations.

P0 keeps the role → page map static in code (an admin-configurable Roles
screen à la ex_beauty can come later). The frontend session store reads
`my_permissions` to hide nav items/pages/buttons; every API endpoint still
enforces its own role check — the map here is UX, not the security gate.

Page keys must match the SPA route names (frontend/src/router/index.ts).
"""

import frappe

from bwm_logistics.api._perm import (
	ANY_STAFF,
	ROLE_ACCOUNTS,
	ROLE_CUSTOMER,
	ROLE_DRIVER,
	ROLE_MANAGER,
	ROLE_OPERATIONS,
	current_customer,
	require,
)

# ─── Page catalog ────────────────────────────────────────────────────────────
OPERATOR_PAGES = [
	{"key": "dashboard", "label": "Dashboard"},
	{"key": "containers", "label": "Containers"},
	{"key": "shipments", "label": "Shipments"},
	{"key": "scan", "label": "Scan"},
	{"key": "dispatch", "label": "Dispatch"},
	{"key": "customers", "label": "Customers"},
	{"key": "billing", "label": "Billing"},
	{"key": "reports", "label": "Reports"},
	{"key": "notifications", "label": "Notifications"},
	{"key": "settings", "label": "Settings"},
]
PORTAL_PAGES = [
	{"key": "portal", "label": "My Portal"},
	{"key": "portal-shipments", "label": "My Shipments"},
	{"key": "portal-pickups", "label": "Pickups"},
	{"key": "portal-invoices", "label": "Invoices"},
	{"key": "portal-profile", "label": "Profile"},
]

OPERATOR_KEYS = {p["key"] for p in OPERATOR_PAGES}
PORTAL_KEYS = {p["key"] for p in PORTAL_PAGES}

# ─── Static role → pages map (P0) ────────────────────────────────────────────
# System Manager / Administrator / Logistics Manager see everything on the
# operator side. Other staff roles get focused subsets.
ROLE_PAGES = {
	ROLE_MANAGER: OPERATOR_KEYS,
	ROLE_OPERATIONS: OPERATOR_KEYS - {"settings"},
	ROLE_ACCOUNTS: {"dashboard", "customers", "billing", "reports", "notifications"},
	ROLE_DRIVER: {"dispatch"},
	ROLE_CUSTOMER: PORTAL_KEYS,
}

SUPER_ROLES = {"System Manager", "Administrator", ROLE_MANAGER}


def _full_perm(page) -> dict:
	return {"page": page, "scope": "all", "read": 1, "create": 1, "edit": 1, "delete": 1}


def user_perms(user=None) -> dict:
	"""{page_key: perm} — the resolved access map for a user.

	Supers → every operator page. Staff → union of their roles' pages.
	Customers → the portal pages (scoped 'own'; scoping itself is enforced
	by the portal endpoints via require_customer()).
	"""
	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))

	pages: set = set()
	if roles & SUPER_ROLES:
		pages |= OPERATOR_KEYS
	for role, keys in ROLE_PAGES.items():
		if role in roles:
			pages |= keys

	perms = {}
	for key in pages:
		p = _full_perm(key)
		if key in PORTAL_KEYS:
			p["scope"] = "own"
			p["delete"] = 0
		perms[key] = p
	return perms


def can(page, action, user=None) -> bool:
	"""Whether a user may do `action` (read/create/edit/delete) on a page."""
	p = user_perms(user).get(page)
	if not p:
		return False
	if action == "read":
		return True
	return bool(p.get(action))


@frappe.whitelist()
def my_permissions():
	"""Per-page permissions for the current user — {page: {scope, create, edit,
	delete}}. Drives SPA nav + route guard; backend endpoints enforce their
	own copy of this."""
	require(ROLE_CUSTOMER, *ANY_STAFF)
	return user_perms()


@frappe.whitelist()
def login_destinations():
	"""Right after login: where may this user go? Drives the post-login redirect
	and (for multi-home users) the Operator/Desk chooser.

	- has_operator → the operator app (staff roles)
	- has_customer → the customer portal (Logistics Customer + linked Customer)
	- has_desk → Frappe Desk (System Users with System Manager)
	"""
	user = frappe.session.user
	roles = set(frappe.get_roles())
	is_system_user = frappe.db.get_value("User", user, "user_type") == "System User"
	return {
		"user": user,
		"full_name": frappe.db.get_value("User", user, "full_name") or user,
		"has_operator": bool(roles & set(ANY_STAFF)),
		"has_customer": ROLE_CUSTOMER in roles and bool(current_customer()),
		"has_desk": bool(is_system_user and {"System Manager", "Administrator"} & roles),
	}
