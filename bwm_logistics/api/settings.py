# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Logistics Settings API — the operator Settings page + shell branding."""

import frappe
from frappe import _
from frappe.utils import cint

from bwm_logistics.api._perm import ANY_STAFF, ROLE_MANAGER, ROLE_SYS, require

# Fields the Settings page may read/write. Secrets (Password fields) are write-
# only through the API: save accepts them, get returns only a "set" flag.
PLAIN_FIELDS = [
	"business_name", "logo", "tracking_prefix", "tracking_provider",
	"email_enabled", "sms_enabled", "whatsapp_enabled",
	"email_subject_template", "email_body_template", "sms_template",
	"whatsapp_gateway_url",
	"hero_title", "hero_subtitle", "contact_phone", "contact_email", "office_hours",
]
SECRET_FIELDS = ["tracking_api_key", "whatsapp_api_token"]
CHECK_FIELDS = {"email_enabled", "sms_enabled", "whatsapp_enabled"}


@frappe.whitelist(allow_guest=True)
def get_branding():
	"""Business name + logo for the app shells (guests see the login page,
	so this is deliberately public — it exposes nothing sensitive)."""
	settings = frappe.get_cached_doc("Logistics Settings")
	return {
		"business_name": settings.business_name or "BWM Logistics",
		"logo": settings.logo,
	}


@frappe.whitelist()
def get_settings():
	require(*ANY_STAFF)
	settings = frappe.get_doc("Logistics Settings")
	out = {f: settings.get(f) for f in PLAIN_FIELDS}
	out["tracking_webhook_token"] = settings.tracking_webhook_token
	for secret in SECRET_FIELDS:
		out[f"{secret}_set"] = bool(settings.get_password(secret, raise_exception=False))
	return out


@frappe.whitelist()
def save_settings(payload):
	require(ROLE_MANAGER, ROLE_SYS)
	data = frappe.parse_json(payload) if isinstance(payload, str) else payload
	settings = frappe.get_doc("Logistics Settings")
	for field in PLAIN_FIELDS:
		if field in data:
			value = data.get(field)
			settings.set(field, cint(value) if field in CHECK_FIELDS else value)
	for secret in SECRET_FIELDS:
		# Only overwrite a secret when a new value is supplied.
		if data.get(secret):
			settings.set(secret, data[secret])
	settings.save()
	frappe.clear_cache(doctype="Logistics Settings")
	# The public landing page renders these values and is cached — invalidate
	# so branding/content changes go live immediately.
	from frappe.website.utils import clear_website_cache

	clear_website_cache()
	return {"ok": True}
