# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

import frappe

# Public marketing landing page (site home). Static at P0 — a later phase
# makes the content tenant-editable (FR-WEB-4). Cached is fine (no session
# data on the page), but keep no_cache off deliberately.
allow_guest = True


def get_context(context):
	context.company_name = frappe.db.get_single_value("Website Settings", "app_name") or "BWM Logistics"
	# The SPA handles login for both staff and customers.
	context.login_url = "/logistics"
	context.is_logged_in = frappe.session.user != "Guest"
