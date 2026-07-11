# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

import frappe

# Public marketing landing page (site home). Static at P0 — a later phase
# makes the content tenant-editable (FR-WEB-4). Cached is fine (no session
# data on the page), but keep no_cache off deliberately.
allow_guest = True


def get_context(context):
	# Tenant-editable content from Logistics Settings (FR-WEB-4) with
	# sensible fallbacks so a fresh install still looks complete.
	settings = frappe.get_cached_doc("Logistics Settings")
	context.company_name = settings.business_name or "BWM Logistics"
	context.hero_title = settings.hero_title or ""
	context.hero_subtitle = settings.hero_subtitle or ""
	context.contact_phone = settings.contact_phone or "+000 00 000 0000"
	context.contact_email = settings.contact_email or "hello@example.com"
	context.office_hours = settings.office_hours or "Mon–Sat, 8:00–18:00"
	# The SPA handles login for both staff and customers.
	context.login_url = "/logistics"
	context.is_logged_in = frappe.session.user != "Guest"
