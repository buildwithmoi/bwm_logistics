# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Executive dashboard (P7) — the numbers a manager/CEO needs at a glance.
Profit is sensitive: profit_mtd is only present in the payload for
Manager/Accounts roles (server-side gate, not just hidden in the UI)."""

from collections import Counter

import frappe
from frappe.utils import add_days, add_months, flt, get_first_day, getdate, nowdate

from bwm_logistics.api._perm import ANY_STAFF, ROLE_ACCOUNTS, ROLE_MANAGER, ROLE_SYS, require

CAN_SEE_PROFIT = {ROLE_MANAGER, ROLE_ACCOUNTS, ROLE_SYS, "Administrator"}


@frappe.whitelist()
def get_overview():
	require(*ANY_STAFF)
	today = nowdate()
	month_start = get_first_day(today)

	# ── money ────────────────────────────────────────────────────────────────
	def _sum(doctype, field, filters):
		return round(
			sum(flt(r[field]) for r in frappe.get_all(doctype, filters=filters, fields=[field])), 2
		)

	revenue_mtd = _sum("Sales Invoice", "grand_total", {"docstatus": 1, "posting_date": (">=", month_start)})
	collected_mtd = _sum(
		"Payment Entry", "paid_amount",
		{"docstatus": 1, "payment_type": "Receive", "posting_date": (">=", month_start)},
	)
	unpaid = frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "outstanding_amount": (">", 0)},
		fields=["outstanding_amount", "status"],
	)

	# ── operations ───────────────────────────────────────────────────────────
	containers_by_direction = Counter(
		r.direction
		for r in frappe.get_all("Container", filters={"status": "Active"}, fields=["direction"])
	)
	shipments_by_direction = Counter(
		r.direction
		for r in frappe.get_all(
			"Shipment",
			filters={"status": ("not in", ["Delivered", "Cancelled"])},
			fields=["direction"],
		)
	)
	pipeline = Counter(
		r.status
		for r in frappe.get_all("Shipment", filters={"status": ("!=", "Cancelled")}, fields=["status"])
	)

	cod_unreconciled = _sum(
		"Delivery Run", "cod_collected_total",
		{"status": "Completed", "cod_reconciled": 0, "cod_collected_total": (">", 0)},
	)

	from bwm_logistics.alerts import at_risk_containers

	# ── series (12 months) ───────────────────────────────────────────────────
	from bwm_logistics.api.reports import _revenue_by_month, _shipments_by_month

	series_start = get_first_day(add_months(today, -11))

	out = {
		"revenue_mtd": revenue_mtd,
		"collected_mtd": collected_mtd,
		"outstanding_total": round(sum(flt(r.outstanding_amount) for r in unpaid), 2),
		"overdue_count": len([r for r in unpaid if r.status == "Overdue"]),
		"containers_active": sum(containers_by_direction.values()),
		"containers_import": containers_by_direction.get("Import", 0),
		"containers_export": containers_by_direction.get("Export", 0),
		"shipments_active": sum(shipments_by_direction.values()),
		"shipments_import": shipments_by_direction.get("Import", 0),
		"shipments_export": shipments_by_direction.get("Export", 0),
		"pipeline": [{"status": s, "count": c} for s, c in sorted(pipeline.items(), key=lambda x: -x[1])],
		"demurrage_risk": at_risk_containers(),
		"cod_unreconciled": cod_unreconciled,
		"arriving_week": frappe.get_all(
			"Container",
			filters={"status": "Active", "eta": ("between", [today, add_days(today, 7)])},
			fields=["name", "container_no", "eta", "vessel", "port_of_discharge", "direction"],
			order_by="eta asc",
			limit=6,
		),
		"top_customers": _top_customers_mtd(month_start),
		"recent_payments": frappe.get_all(
			"Payment Entry",
			filters={"docstatus": 1, "payment_type": "Receive"},
			fields=["name", "posting_date", "party_name", "paid_amount", "mode_of_payment"],
			order_by="creation desc",
			limit=5,
		),
		"revenue_months": _revenue_by_month(series_start, 12),
		"shipment_months": _shipments_by_month(series_start, 12),
		"recent_events": frappe.get_all(
			"Tracking Event",
			fields=["name", "event_datetime", "milestone", "location", "container", "shipment"],
			order_by="event_datetime desc",
			limit=8,
		),
	}

	# ── stock on hand (trading shipments — quantities, not money) ───────────
	try:
		from bwm_logistics.api.stock import stock_overview

		products = stock_overview()["products"]
		out["stock_on_hand"] = {
			"products": [p for p in products if p["remaining"] > 0][:5],
			"product_count": len(products),
		}
	except Exception:
		out["stock_on_hand"] = {"products": [], "product_count": 0}

	# ── profit (Managers/Accounts only — key omitted otherwise) ─────────────
	if set(frappe.get_roles()) & CAN_SEE_PROFIT:
		spent_mtd = _sum(
			"Purchase Invoice", "grand_total", {"docstatus": 1, "posting_date": (">=", month_start)}
		)
		out["profit_mtd"] = round(revenue_mtd - spent_mtd, 2)
		out["spent_mtd"] = spent_mtd

	return out


def _top_customers_mtd(month_start):
	"""Top 5 customers by invoiced value this month."""
	totals = {}
	for r in frappe.get_all(
		"Sales Invoice",
		filters={"docstatus": 1, "posting_date": (">=", month_start)},
		fields=["customer_name", "grand_total"],
	):
		key = r.customer_name or "—"
		totals[key] = totals.get(key, 0) + flt(r.grand_total)
	return [
		{"customer": k, "total": round(v, 2)}
		for k, v in sorted(totals.items(), key=lambda x: -x[1])[:5]
	]
