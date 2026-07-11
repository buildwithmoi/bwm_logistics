# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Reports — aggregated datasets for the Reports page (left-rail sections:
Revenue, Shipments, Customers, Containers, Deliveries, Messaging). One round
trip returns everything for the chosen window."""

from collections import Counter, defaultdict

import frappe
from frappe.utils import add_months, cint, flt, get_first_day, getdate, nowdate

from bwm_logistics.api._perm import ANY_STAFF, require


@frappe.whitelist()
def get_reports(months=6):
	require(*ANY_STAFF)
	months = min(max(cint(months) or 6, 3), 24)
	start = get_first_day(add_months(nowdate(), -(months - 1)))

	return {
		"months": _revenue_by_month(start, months),
		"shipment_months": _shipments_by_month(start, months),
		"top_customers": _top_customers(),
		"status_breakdown": _status_breakdown(),
		"containers": _container_stats(start),
		"deliveries": _delivery_stats(start),
		"messaging": _messaging_stats(start),
	}


# ─── Revenue ─────────────────────────────────────────────────────────────────
def _revenue_by_month(start, months):
	invoiced = defaultdict(float)
	for r in frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "posting_date": (">=", start)},
		fields=["posting_date", "grand_total"],
	):
		invoiced[_month_key(r.posting_date)] += flt(r.grand_total)
	collected = defaultdict(float)
	for r in frappe.get_all(
		"Payment Entry",
		filters={"docstatus": 1, "payment_type": "Receive", "posting_date": (">=", start)},
		fields=["posting_date", "paid_amount"],
	):
		collected[_month_key(r.posting_date)] += flt(r.paid_amount)

	return [
		{
			"month": key,
			"label": getdate(f"{key}-01").strftime("%b"),
			"invoiced": round(invoiced.get(key, 0), 2),
			"collected": round(collected.get(key, 0), 2),
		}
		for key in (_month_key(add_months(start, i)) for i in range(months))
	]


# ─── Shipments ───────────────────────────────────────────────────────────────
def _shipments_by_month(start, months):
	imports = defaultdict(int)
	exports = defaultdict(int)
	for r in frappe.get_all(
		"Shipment",
		filters={"creation": (">=", start)},
		fields=["creation", "direction"],
		limit_page_length=0,
	):
		key = _month_key(r.creation)
		if r.direction == "Export":
			exports[key] += 1
		else:
			imports[key] += 1
	return [
		{
			"month": key,
			"label": getdate(f"{key}-01").strftime("%b"),
			"imports": imports.get(key, 0),
			"exports": exports.get(key, 0),
		}
		for key in (_month_key(add_months(start, i)) for i in range(months))
	]


def _top_customers():
	per_customer = defaultdict(lambda: {"count": 0, "charges": 0.0})
	for r in frappe.get_all(
		"Shipment",
		filters={"status": ("!=", "Cancelled")},
		fields=["customer_name", "total_charges"],
		limit_page_length=0,
	):
		bucket = per_customer[r.customer_name or "—"]
		bucket["count"] += 1
		bucket["charges"] += flt(r.total_charges)
	return sorted(
		({"customer": k, **v} for k, v in per_customer.items()),
		key=lambda x: (-x["charges"], -x["count"]),
	)[:10]


def _status_breakdown():
	status_counts = Counter(
		r.status for r in frappe.get_all("Shipment", fields=["status"], limit_page_length=0)
	)
	return [{"status": s, "count": c} for s, c in sorted(status_counts.items(), key=lambda x: -x[1])]


# ─── Containers ──────────────────────────────────────────────────────────────
def _container_stats(start):
	from bwm_logistics.alerts import at_risk_containers

	by_status = Counter(r.status for r in frappe.get_all("Container", fields=["status"], limit_page_length=0))
	by_direction = Counter(
		r.direction for r in frappe.get_all("Container", fields=["direction"], limit_page_length=0)
	)
	arriving = frappe.get_all(
		"Container",
		filters={"status": "Active", "eta": (">=", nowdate())},
		fields=["name", "container_no", "eta", "port_of_discharge", "vessel"],
		order_by="eta asc",
		limit=10,
	)
	return {
		"by_status": [{"status": s, "count": c} for s, c in by_status.items()],
		"by_direction": [{"direction": d, "count": c} for d, c in by_direction.items()],
		"arriving": arriving,
		"demurrage_risk": at_risk_containers(),
	}


# ─── Deliveries ──────────────────────────────────────────────────────────────
def _delivery_stats(start):
	runs = frappe.get_all(
		"Delivery Run",
		filters={"run_date": (">=", start)},
		fields=["status", "completed_stops", "total_stops", "cod_collected_total", "cod_reconciled"],
		limit_page_length=0,
	)
	stops_failed = frappe.db.count("Run Stop", {"parenttype": "Delivery Run", "status": "Failed"})
	pickups = Counter(
		r.status for r in frappe.get_all("Pickup Request", fields=["status"], limit_page_length=0)
	)
	return {
		"runs_total": len(runs),
		"runs_completed": len([r for r in runs if r.status == "Completed"]),
		"stops_completed": sum(cint(r.completed_stops) for r in runs),
		"stops_failed": stops_failed,
		"cod_collected": round(sum(flt(r.cod_collected_total) for r in runs), 2),
		"cod_unreconciled": round(
			sum(flt(r.cod_collected_total) for r in runs if not r.cod_reconciled and r.status == "Completed"), 2
		),
		"pickups": [{"status": s, "count": c} for s, c in pickups.items()],
	}


# ─── Messaging ───────────────────────────────────────────────────────────────
def _messaging_stats(start):
	rows = frappe.get_all(
		"Notification Log Entry",
		filters={"creation": (">=", start)},
		fields=["channel", "status"],
		limit_page_length=0,
	)
	per_channel = defaultdict(lambda: {"sent": 0, "failed": 0, "skipped": 0, "queued": 0})
	for r in rows:
		key = (r.status or "Queued").lower()
		bucket = per_channel[r.channel or "—"]
		if key in bucket:
			bucket[key] += 1
	total = len(rows)
	sent = sum(b["sent"] for b in per_channel.values())
	return {
		"total": total,
		"delivered_pct": round(sent / total * 100) if total else 0,
		"channels": [{"channel": c, **v} for c, v in per_channel.items()],
	}


def _month_key(d) -> str:
	d = getdate(d)
	return f"{d.year}-{d.month:02d}"
