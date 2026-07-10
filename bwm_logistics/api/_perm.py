# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Shared permission helpers for the Logistics API.

The SPA hits whitelisted endpoints rather than the generic /api/resource so
we keep enforcement tight and uniform. These helpers raise PermissionError
(translated to 403 by Frappe) instead of returning empty results — easier
to debug than silently missing data.
"""

import frappe
from frappe import _

# Role tiers used across the API. Listed least → most privileged.
ROLE_DRIVER = "Logistics Driver"
ROLE_ACCOUNTS = "Logistics Accounts"
ROLE_OPERATIONS = "Logistics Operations"
ROLE_MANAGER = "Logistics Manager"
ROLE_CUSTOMER = "Logistics Customer"  # website users (portal only)
ROLE_SYS = "System Manager"

ANY_STAFF = (ROLE_DRIVER, ROLE_ACCOUNTS, ROLE_OPERATIONS, ROLE_MANAGER, ROLE_SYS)
MANAGER_OR_ABOVE = (ROLE_MANAGER, ROLE_SYS)


def require(*roles):
	"""Raise PermissionError if the session user has none of the given roles."""
	user_roles = set(frappe.get_roles())
	if not user_roles.intersection(roles):
		frappe.throw(
			_("You don't have permission for this action."),
			frappe.PermissionError,
		)


def is_staff(user=None) -> bool:
	return bool(set(frappe.get_roles(user)) & set(ANY_STAFF))


def is_customer(user=None) -> bool:
	return ROLE_CUSTOMER in frappe.get_roles(user)


def current_customer(user=None) -> str | None:
	"""The Customer record linked to the session's portal user (via Contact),
	or None for staff / unlinked users. Used to scope every portal endpoint."""
	user = user or frappe.session.user
	if user == "Guest":
		return None
	links = frappe.get_all(
		"Dynamic Link",
		filters={
			"parenttype": "Contact",
			"link_doctype": "Customer",
			"parent": ("in", frappe.get_all("Contact", filters={"user": user}, pluck="name")),
		},
		pluck="link_name",
		limit=1,
	)
	return links[0] if links else None


def require_customer() -> str:
	"""Throw unless the session user is a linked portal customer; returns the
	Customer name so portal endpoints can scope their queries."""
	require(ROLE_CUSTOMER)
	customer = current_customer()
	if not customer:
		frappe.throw(
			_("Your login is not linked to a customer account. Please contact support."),
			frappe.PermissionError,
		)
	return customer
