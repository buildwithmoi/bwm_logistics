# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Milestone notification engine (PRD §6.6).

Tracking Event (after_insert) enqueues dispatch_for_event. Recipients resolve
by tagging: a shipment event notifies that shipment's customer; a container
event notifies every customer with a shipment tagged to it — once each, even
if they have several shipments in the container. Every attempt is written to
Notification Log Entry so operators can see who was told what, when.
"""

import frappe
from frappe.utils import get_url

DEFAULT_SUBJECT = "Update on your shipment {tracking_no}: {milestone}"
DEFAULT_BODY = (
	"Hello {customer_name},\n\n"
	"Your shipment {tracking_no} has a new update: {milestone}{location_suffix}.\n\n"
	"Track it any time: {tracking_link}\n\n"
	"— {business_name}"
)
DEFAULT_SMS = "{business_name}: shipment {tracking_no} update — {milestone}{location_suffix}. Track: {tracking_link}"


def dispatch_for_event(event_name: str):
	"""Send email/SMS for one tracking event. Idempotent-ish: skips if the
	event was already marked notified (e.g. a retried job)."""
	event = frappe.get_doc("Tracking Event", event_name)
	if event.notified or not event.notify:
		return

	settings = frappe.get_cached_doc("Logistics Settings")
	if not (settings.email_enabled or settings.sms_enabled):
		return

	for shipment in _target_shipments(event):
		_notify_shipment(event, shipment, settings)

	event.db_set("notified", 1, update_modified=False)


def _target_shipments(event) -> list[dict]:
	"""Shipments whose customers should hear about this event (opted-in only)."""
	filters = {"notify_customer": 1, "status": ("not in", ["Cancelled"])}
	if event.shipment:
		filters["name"] = event.shipment
	elif event.container:
		filters["container"] = event.container
	else:
		return []
	return frappe.get_all(
		"Shipment",
		filters=filters,
		fields=["name", "customer", "customer_name", "consignee_phone"],
	)


def _notify_shipment(event, shipment, settings):
	customer = shipment.customer
	email, mobile = _customer_contact(customer, fallback_mobile=shipment.consignee_phone)
	prefs = _customer_prefs(customer)
	ctx = _context(event, shipment, settings)

	if settings.email_enabled:
		if email and prefs["email"]:
			_send_email(event, shipment, email, ctx, settings)
		else:
			_log(event, shipment, "Email", email or "", "Skipped",
				error="No email address" if not email else "Customer opted out")

	if settings.sms_enabled:
		if mobile and prefs["sms"]:
			_send_sms(event, shipment, mobile, ctx, settings)
		else:
			_log(event, shipment, "SMS", mobile or "", "Skipped",
				error="No mobile number" if not mobile else "Customer opted out")

	if settings.whatsapp_enabled:
		if mobile and prefs["whatsapp"]:
			_send_whatsapp(event, shipment, mobile, ctx, settings)
		else:
			_log(event, shipment, "WhatsApp", mobile or "", "Skipped",
				error="No mobile number" if not mobile else "Customer opted out")


def _context(event, shipment, settings) -> dict:
	business = settings.business_name or frappe.db.get_default("company") or "BWM Logistics"
	return {
		"customer_name": shipment.customer_name or shipment.customer,
		"tracking_no": shipment.name,
		"milestone": event.milestone,
		"location": event.location or "",
		"location_suffix": f" at {event.location}" if event.location else "",
		"business_name": business,
		"tracking_link": get_url(f"/logistics/portal?track={shipment.name}"),
	}


def _render(template: str, ctx: dict) -> str:
	# str.format-style templates, forgiving about unknown/missing keys.
	class _Safe(dict):
		def __missing__(self, key):
			return "{" + key + "}"

	return (template or "").format_map(_Safe(ctx))


def _send_email(event, shipment, email, ctx, settings):
	subject = _render(settings.email_subject_template or DEFAULT_SUBJECT, ctx)
	body = _render(settings.email_body_template or DEFAULT_BODY, ctx)
	log = _log(event, shipment, "Email", email, "Queued", subject=subject, message=body)
	try:
		frappe.sendmail(recipients=[email], subject=subject, message=body.replace("\n", "<br>"))
		log.db_set("status", "Sent", update_modified=False)
	except Exception as e:
		log.db_set({"status": "Failed", "error": str(e)[:500]}, update_modified=False)


def _send_sms(event, shipment, mobile, ctx, settings):
	message = _render(settings.sms_template or DEFAULT_SMS, ctx)
	log = _log(event, shipment, "SMS", mobile, "Queued", message=message)
	try:
		from frappe.core.doctype.sms_settings.sms_settings import send_sms

		send_sms(receiver_list=[mobile], msg=message, success_msg=False)
		log.db_set("status", "Sent", update_modified=False)
	except Exception as e:
		log.db_set({"status": "Failed", "error": str(e)[:500]}, update_modified=False)


def _send_whatsapp(event, shipment, mobile, ctx, settings):
	"""Generic WhatsApp HTTP gateway: POST {"to", "message"} with a Bearer
	token — wire it to Hubtel, WATI, or any BSP relay (FR-NOT-5)."""
	message = _render(settings.sms_template or DEFAULT_SMS, ctx)
	log = _log(event, shipment, "WhatsApp", mobile, "Queued", message=message)
	try:
		import requests

		url = settings.whatsapp_gateway_url
		if not url:
			raise ValueError("WhatsApp gateway URL not configured")
		headers = {"Content-Type": "application/json"}
		token = settings.get_password("whatsapp_api_token", raise_exception=False)
		if token:
			headers["Authorization"] = f"Bearer {token}"
		res = requests.post(url, json={"to": mobile, "message": message}, headers=headers, timeout=15)
		res.raise_for_status()
		log.db_set("status", "Sent", update_modified=False)
	except Exception as e:
		log.db_set({"status": "Failed", "error": str(e)[:500]}, update_modified=False)


def _log(event, shipment, channel, recipient, status, subject=None, message=None, error=None):
	doc = frappe.get_doc(
		{
			"doctype": "Notification Log Entry",
			"channel": channel,
			"status": status,
			"recipient": recipient,
			"customer": shipment.customer,
			"tracking_event": event.name,
			"shipment": shipment.name,
			"container": event.container,
			"milestone": event.milestone,
			"subject": subject,
			"message": message,
			"error": error,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	return doc


def _customer_contact(customer: str, fallback_mobile: str | None = None) -> tuple[str | None, str | None]:
	"""(email, mobile) for a customer — Customer's primary fields first, then
	any linked Contact, then the shipment's consignee phone for SMS."""
	email, mobile = frappe.db.get_value("Customer", customer, ["email_id", "mobile_no"]) or (None, None)
	if not email or not mobile:
		contact_names = frappe.get_all(
			"Dynamic Link",
			filters={"parenttype": "Contact", "link_doctype": "Customer", "link_name": customer},
			pluck="parent",
		)
		for cn in contact_names:
			c_email, c_mobile, c_phone = frappe.db.get_value("Contact", cn, ["email_id", "mobile_no", "phone"])
			email = email or c_email
			mobile = mobile or c_mobile or c_phone
			if email and mobile:
				break
	return email, mobile or fallback_mobile


def _customer_prefs(customer: str) -> dict:
	"""Per-customer channel opt-in (custom fields added by install.py;
	default opted-in when the fields don't exist yet)."""
	try:
		row = frappe.db.get_value(
			"Customer", customer,
			["bwm_notify_email", "bwm_notify_sms", "bwm_notify_whatsapp"], as_dict=True,
		)
		def opt(v):
			return bool(v) if v is not None else True

		return {
			"email": opt(row.bwm_notify_email) if row else True,
			"sms": opt(row.bwm_notify_sms) if row else True,
			"whatsapp": opt(row.bwm_notify_whatsapp) if row else True,
		}
	except Exception:
		return {"email": True, "sms": True, "whatsapp": True}
