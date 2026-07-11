# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Carrier-API auto-tracking (PRD FR-CTR-5).

Providers (ShipsGo, Terminal49) are thin adapters that normalize a container's
journey into `{"events": [{milestone, event_datetime, location}], "eta", "ata",
"atd", "vessel"}`. sync_container() dedupes against existing Tracking Events
and inserts the new ones with source=API — which flows straight through the
existing cascade + notification pipeline. Manual entry stays as fallback.

Field mappings are written against each provider's public API docs; confirm
against live credentials before production (adapters isolate any adjustment).
"""

import frappe
import requests
from frappe import _
from frappe.utils import cint, get_datetime

REQUEST_TIMEOUT = 20


# ─── Provider adapters ───────────────────────────────────────────────────────
def _shipsgo(container_no: str, api_key: str) -> dict:
	"""ShipsGo v1.2 ContainerService — GET by container number."""
	res = requests.get(
		"https://shipsgo.com/api/v1.2/ContainerService/GetContainerInfo/",
		params={"authCode": api_key, "requestId": container_no, "mapPoint": "true"},
		timeout=REQUEST_TIMEOUT,
	)
	res.raise_for_status()
	payload = res.json()
	row = payload[0] if isinstance(payload, list) and payload else payload if isinstance(payload, dict) else {}

	events = []
	for m in row.get("TSBs") or row.get("Movements") or []:
		milestone = m.get("Status") or m.get("StatusName") or m.get("Movement")
		when = m.get("Date") or m.get("EventDate")
		if milestone and when:
			events.append(
				{
					"milestone": milestone,
					"event_datetime": get_datetime(when),
					"location": m.get("Port") or m.get("Location"),
				}
			)
	# ShipsGo also reports a flat latest status.
	if not events and row.get("StatusName") and row.get("LastUpdateDate"):
		events.append(
			{
				"milestone": row["StatusName"],
				"event_datetime": get_datetime(row["LastUpdateDate"]),
				"location": row.get("Pod"),
			}
		)
	return {
		"events": events,
		"eta": row.get("ETA") or row.get("ArrivalDate"),
		"vessel": row.get("Vessel"),
	}


def _terminal49(container_no: str, api_key: str) -> dict:
	"""Terminal49 v2 — containers are tracked via tracking_requests; once
	tracked, /containers/{no} style lookups come back through shipments.
	We query the container endpoint directly and read transport events."""
	headers = {"Authorization": f"Token {api_key}", "Content-Type": "application/vnd.api+json"}
	res = requests.get(
		f"https://api.terminal49.com/v2/containers?filter[number]={container_no}&include=transport_events",
		headers=headers,
		timeout=REQUEST_TIMEOUT,
	)
	res.raise_for_status()
	payload = res.json()

	events = []
	for item in payload.get("included") or []:
		if item.get("type") != "transport_event":
			continue
		attrs = item.get("attributes") or {}
		when = attrs.get("timestamp")
		milestone = (attrs.get("event") or "").replace("_", " ").title()
		if milestone and when:
			events.append(
				{
					"milestone": milestone,
					"event_datetime": get_datetime(when),
					"location": attrs.get("location_locode"),
				}
			)
	data = payload.get("data") or []
	attrs = (data[0].get("attributes") if data else None) or {}
	return {
		"events": events,
		"eta": attrs.get("pod_eta_at"),
		"ata": attrs.get("pod_arrived_at"),
	}


PROVIDERS = {"ShipsGo": _shipsgo, "Terminal49": _terminal49}


# ─── Sync engine ─────────────────────────────────────────────────────────────
def provider_configured() -> str | None:
	settings = frappe.get_cached_doc("Logistics Settings")
	if settings.tracking_provider and settings.get_password("tracking_api_key", raise_exception=False):
		return settings.tracking_provider
	return None


def sync_container(name: str, notify: int = 1) -> dict:
	"""Pull the provider's journey for one container and append what's new."""
	provider = provider_configured()
	if not provider:
		frappe.throw(_("No carrier tracking provider is configured in Settings."))
	container = frappe.get_doc("Container", name)
	if not container.container_no:
		frappe.throw(_("Container {0} has no container number to track.").format(name))

	settings = frappe.get_cached_doc("Logistics Settings")
	data = PROVIDERS[provider](container.container_no, settings.get_password("tracking_api_key"))
	return apply_tracking_data(container, data, notify=notify)


def apply_tracking_data(container, data: dict, notify: int = 1) -> dict:
	"""Insert new events (deduped by milestone) + update voyage dates."""
	existing = set(
		frappe.get_all(
			"Tracking Event", filters={"container": container.name}, pluck="milestone"
		)
	)
	created = 0
	for event in sorted(data.get("events") or [], key=lambda e: e["event_datetime"]):
		if event["milestone"] in existing:
			continue
		frappe.get_doc(
			{
				"doctype": "Tracking Event",
				"container": container.name,
				"milestone": event["milestone"],
				"location": event.get("location"),
				"event_datetime": event["event_datetime"],
				"notify": cint(notify),
				"source": "API",
			}
		).insert(ignore_permissions=True)
		existing.add(event["milestone"])
		created += 1

	updates = {}
	for field in ("eta", "ata", "atd", "vessel"):
		value = data.get(field)
		if value and str(container.get(field) or "") != str(value):
			updates[field] = value
	if updates:
		frappe.db.set_value("Container", container.name, updates, update_modified=True)

	return {"new_events": created, "updated": list(updates)}


def sync_all_active():
	"""Hourly scheduler job (hooks.scheduler_events). No-op until a provider
	is configured, so it's safe to ship enabled."""
	if not provider_configured():
		return
	for name in frappe.get_all(
		"Container",
		filters={"status": "Active", "container_no": ("is", "set")},
		pluck="name",
	):
		try:
			sync_container(name)
		except Exception:
			frappe.log_error(frappe.get_traceback(), f"carrier sync failed: {name}")
		finally:
			frappe.db.commit()
