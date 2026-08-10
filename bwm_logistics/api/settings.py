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


FALLBACK_NAME = "Logistics"


def business_name() -> str:
	"""What this installation calls itself — the one answer, used everywhere.

	Logistics Settings first, because that is what an operator can edit. A site
	that has never been branded falls back to the ERPNext Company (there is only
	ever one on these installs), so a fresh deploy shows the client's own name
	instead of ours.
	"""
	name = (frappe.db.get_single_value("Logistics Settings", "business_name") or "").strip()
	if name:
		return name
	if frappe.db.exists("DocType", "Company"):
		company = (frappe.db.get_value("Company", {}, "company_name") or "").strip()
		if company:
			return company
	return FALLBACK_NAME


def monogram(name: str | None = None) -> str:
	"""The single letter that stands in for a logo nobody has uploaded."""
	return ((name or business_name()).strip()[:1] or "?").upper()


@frappe.whitelist(allow_guest=True)
def get_branding():
	"""Business name + logo for the app shells (guests see the login page,
	so this is deliberately public — it exposes nothing sensitive)."""
	name = business_name()
	return {
		"business_name": name,
		"logo": frappe.db.get_single_value("Logistics Settings", "logo"),
		"monogram": monogram(name),
	}


@frappe.whitelist()
def upload_logo(filename=None, content=None):
	"""Store a logo sent as a base64 data URL and point Settings at it.

	The operator app has no Desk attach control, so the file arrives inline from
	the Settings page. Kept behind the same roles that can edit settings.
	"""
	require(ROLE_MANAGER, ROLE_SYS)
	if not content:
		frappe.throw(_("No image was sent."))

	import base64

	header, _sep, payload = str(content).partition(",")
	if "base64" not in header:
		frappe.throw(_("Send the image as a base64 data URL."))
	try:
		data = base64.b64decode(payload)
	except Exception:
		frappe.throw(_("That image could not be read."))
	if len(data) > 2 * 1024 * 1024:
		frappe.throw(_("Logo must be under 2MB."))

	doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": (filename or "logo.png").rsplit("/", 1)[-1][:140],
			"is_private": 0,
			"content": data,
			"decode": False,
			"attached_to_doctype": "Logistics Settings",
			"attached_to_name": "Logistics Settings",
			"attached_to_field": "logo",
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	frappe.db.set_single_value("Logistics Settings", "logo", doc.file_url)
	frappe.clear_cache(doctype="Logistics Settings")
	return {"logo": doc.file_url}


@frappe.whitelist()
def clear_logo():
	"""Drop back to the monogram."""
	require(ROLE_MANAGER, ROLE_SYS)
	frappe.db.set_single_value("Logistics Settings", "logo", None)
	frappe.clear_cache(doctype="Logistics Settings")
	return {"logo": None}


@frappe.whitelist()
def list_branches():
	"""Branches for the top-bar picker (reuses ERPNext's Branch master)."""
	require(*ANY_STAFF)
	if not frappe.db.exists("DocType", "Branch"):
		return []
	return frappe.get_all("Branch", pluck="name", order_by="name")


@frappe.whitelist()
def add_branch(name):
	require(ROLE_MANAGER, ROLE_SYS)
	name = (name or "").strip()
	if not name:
		frappe.throw(_("Branch name is required."))
	if not frappe.db.exists("Branch", name):
		frappe.get_doc({"doctype": "Branch", "branch": name}).insert(ignore_permissions=True)
	return {"name": name}


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


# ── Milestone templates (the statuses a company works to) ────────────────────
# These already existed as a doctype driving container milestones; they were
# just never editable outside the Desk. This is the "let the company define
# their own statuses" surface — one list per direction, ordered, each row
# saying whether reaching it notifies the customer.


@frappe.whitelist()
def list_milestone_templates():
	require(*ANY_STAFF)
	rows = []
	for t in frappe.get_all(
		"Milestone Template", fields=["name", "template_name", "direction", "is_default"], order_by="direction, name"
	):
		doc = frappe.get_cached_doc("Milestone Template", t.name)
		rows.append(
			{
				**t,
				"milestones": [
					{"milestone": m.milestone, "notify_customer": m.notify_customer, "description": m.description}
					for m in doc.milestones
				],
				"in_use": frappe.db.count("Container", {"milestone_template": t.name}),
			}
		)
	return rows


@frappe.whitelist()
def save_milestone_template(payload):
	require(ROLE_MANAGER, ROLE_SYS)
	data = frappe.parse_json(payload) if isinstance(payload, str) else payload
	name = data.get("name")
	doc = frappe.get_doc("Milestone Template", name) if name else frappe.new_doc("Milestone Template")
	doc.template_name = (data.get("template_name") or "").strip() or doc.template_name
	doc.direction = data.get("direction") or doc.direction
	doc.is_default = cint(data.get("is_default"))

	milestones = [m for m in (data.get("milestones") or []) if (m.get("milestone") or "").strip()]
	if not milestones:
		frappe.throw(_("A template needs at least one milestone."))
	doc.set("milestones", [])
	for m in milestones:
		doc.append(
			"milestones",
			{
				"milestone": m["milestone"].strip(),
				"notify_customer": cint(m.get("notify_customer")),
				"description": m.get("description"),
			},
		)
	doc.save()
	frappe.clear_cache(doctype="Milestone Template")
	return {"name": doc.name}
