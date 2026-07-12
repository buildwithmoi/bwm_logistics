# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Reports (P7 — advanced): one round trip returns every section for the
chosen window + filters. Custom date range, branch and direction filters;
receivables aging; profitability (server-gated to Manager/Accounts)."""

from collections import Counter, defaultdict

import frappe
from frappe.utils import (
	add_months,
	cint,
	date_diff,
	flt,
	get_first_day,
	getdate,
	nowdate,
)

from bwm_logistics.api._perm import ANY_STAFF, ROLE_ACCOUNTS, ROLE_MANAGER, ROLE_SYS, require

CAN_SEE_PROFIT = {ROLE_MANAGER, ROLE_ACCOUNTS, ROLE_SYS, "Administrator"}


@frappe.whitelist()
def get_reports(months=6, from_date=None, to_date=None, branch=None, direction=None):
	require(*ANY_STAFF)

	# Window: explicit range wins; otherwise last N whole months.
	if from_date and to_date:
		start, end = getdate(from_date), getdate(to_date)
		if start > end:
			start, end = end, start
	else:
		months = min(max(cint(months) or 6, 3), 24)
		end = getdate(nowdate())
		start = get_first_day(add_months(end, -(months - 1)))

	ship_filters = {}
	if branch:
		ship_filters["branch"] = branch
	if direction:
		ship_filters["direction"] = direction

	out = {
		"window": {"from": str(start), "to": str(end)},
		"months": _revenue_by_month(start, _month_count(start, end)),
		"shipment_months": _shipments_by_month(start, _month_count(start, end), ship_filters),
		"collection": _collection(start, end),
		"aging": _receivables_aging(),
		"top_customers": _top_customers(ship_filters),
		"status_breakdown": _status_breakdown(ship_filters),
		"containers": _container_stats(ship_filters),
		"deliveries": _delivery_stats(start, end),
		"messaging": _messaging_stats(start, end),
	}
	# Profitability is sensitive — section omitted for other roles.
	if set(frappe.get_roles()) & CAN_SEE_PROFIT:
		out["profitability"] = _profitability(ship_filters)
	return out


def _month_count(start, end) -> int:
	return min(max((end.year - start.year) * 12 + end.month - start.month + 1, 1), 24)


# ─── Revenue & collection ────────────────────────────────────────────────────
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


def _collection(start, end):
	invoiced = sum(
		flt(r.grand_total)
		for r in frappe.get_all(
			"Sales Invoice",
			filters={"docstatus": 1, "posting_date": ("between", [start, end])},
			fields=["grand_total"],
		)
	)
	collected = sum(
		flt(r.paid_amount)
		for r in frappe.get_all(
			"Payment Entry",
			filters={"docstatus": 1, "payment_type": "Receive", "posting_date": ("between", [start, end])},
			fields=["paid_amount"],
		)
	)
	return {
		"invoiced": round(invoiced, 2),
		"collected": round(collected, 2),
		"rate_pct": round(collected / invoiced * 100) if invoiced else None,
	}


def _receivables_aging():
	"""Unpaid receivables bucketed by days overdue (real accounting insight)."""
	buckets = {"current": 0.0, "b1_30": 0.0, "b31_60": 0.0, "b61_90": 0.0, "b90_plus": 0.0}
	rows = frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "outstanding_amount": (">", 0)},
		fields=["name", "customer_name", "due_date", "posting_date", "outstanding_amount"],
	)
	today = getdate(nowdate())
	detail = []
	for r in rows:
		overdue_days = date_diff(today, r.due_date or r.posting_date)
		amount = flt(r.outstanding_amount)
		if overdue_days <= 0:
			buckets["current"] += amount
		elif overdue_days <= 30:
			buckets["b1_30"] += amount
		elif overdue_days <= 60:
			buckets["b31_60"] += amount
		elif overdue_days <= 90:
			buckets["b61_90"] += amount
		else:
			buckets["b90_plus"] += amount
		detail.append(
			{
				"invoice": r.name,
				"customer": r.customer_name,
				"due_date": str(r.due_date or r.posting_date),
				"overdue_days": max(overdue_days, 0),
				"outstanding": amount,
			}
		)
	detail.sort(key=lambda x: -x["overdue_days"])
	return {
		"buckets": {k: round(v, 2) for k, v in buckets.items()},
		"total": round(sum(buckets.values()), 2),
		"worst": detail[:15],
	}


# ─── Profitability (Managers/Accounts only) ──────────────────────────────────
def _profitability(ship_filters):
	"""Per-shipment P&L for every shipment that has tagged money on it."""
	revenue = defaultdict(float)
	for r in frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "bwm_shipment": ("is", "set")},
		fields=["bwm_shipment", "grand_total"],
	):
		revenue[r.bwm_shipment] += flt(r.grand_total)
	cost = defaultdict(float)
	for r in frappe.get_all(
		"Purchase Invoice",
		filters={"docstatus": 1, "bwm_shipment": ("is", "set")},
		fields=["bwm_shipment", "grand_total"],
	):
		cost[r.bwm_shipment] += flt(r.grand_total)

	names = set(revenue) | set(cost)
	if not names:
		return {"rows": [], "totals": {"revenue": 0, "cost": 0, "profit": 0}}
	meta = {
		s.name: s
		for s in frappe.get_all(
			"Shipment",
			filters={"name": ("in", list(names)), **ship_filters},
			fields=["name", "shipment_type", "customer_name", "direction", "status"],
		)
	}
	rows = []
	for name in names:
		if name not in meta:  # filtered out by branch/direction
			continue
		rev, cst = round(revenue.get(name, 0), 2), round(cost.get(name, 0), 2)
		rows.append(
			{
				"shipment": name,
				"type": meta[name].shipment_type or "Customer Cargo",
				"customer": meta[name].customer_name,
				"direction": meta[name].direction,
				"status": meta[name].status,
				"revenue": rev,
				"cost": cst,
				"profit": round(rev - cst, 2),
				"margin_pct": round((rev - cst) / rev * 100, 1) if rev else None,
			}
		)
	rows.sort(key=lambda x: -abs(x["profit"]))
	return {
		"rows": rows[:50],
		"totals": {
			"revenue": round(sum(r["revenue"] for r in rows), 2),
			"cost": round(sum(r["cost"] for r in rows), 2),
			"profit": round(sum(r["profit"] for r in rows), 2),
		},
	}


# ─── Shipments ───────────────────────────────────────────────────────────────
def _shipments_by_month(start, months, ship_filters=None):
	imports = defaultdict(int)
	exports = defaultdict(int)
	for r in frappe.get_all(
		"Shipment",
		filters={"creation": (">=", start), **(ship_filters or {})},
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


def _top_customers(ship_filters):
	per_customer = defaultdict(lambda: {"count": 0, "charges": 0.0})
	for r in frappe.get_all(
		"Shipment",
		filters={"status": ("!=", "Cancelled"), "customer": ("is", "set"), **ship_filters},
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


def _status_breakdown(ship_filters):
	status_counts = Counter(
		r.status
		for r in frappe.get_all("Shipment", filters=ship_filters or None, fields=["status"], limit_page_length=0)
	)
	return [{"status": s, "count": c} for s, c in sorted(status_counts.items(), key=lambda x: -x[1])]


# ─── Containers ──────────────────────────────────────────────────────────────
def _container_stats(ship_filters):
	from bwm_logistics.alerts import at_risk_containers

	cont_filters = {k: v for k, v in ship_filters.items() if k in ("branch", "direction")}
	by_status = Counter(
		r.status for r in frappe.get_all("Container", filters=cont_filters or None, fields=["status"], limit_page_length=0)
	)
	by_direction = Counter(
		r.direction
		for r in frappe.get_all("Container", filters=cont_filters or None, fields=["direction"], limit_page_length=0)
	)
	arriving = frappe.get_all(
		"Container",
		filters={"status": "Active", "eta": (">=", nowdate()), **cont_filters},
		fields=["name", "container_no", "eta", "port_of_discharge", "vessel", "direction"],
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
def _delivery_stats(start, end):
	runs = frappe.get_all(
		"Delivery Run",
		filters={"run_date": ("between", [start, end])},
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
def _messaging_stats(start, end):
	rows = frappe.get_all(
		"Notification Log Entry",
		filters={"creation": ("between", [start, f"{end} 23:59:59"])},
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
