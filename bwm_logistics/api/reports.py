# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Reports — small, aggregated, one round-trip for the Reports page."""

from collections import Counter, defaultdict

import frappe
from frappe.utils import add_months, cint, flt, get_first_day, getdate, nowdate

from bwm_logistics.api._perm import ANY_STAFF, require


@frappe.whitelist()
def get_reports(months=6):
	require(*ANY_STAFF)
	months = min(max(cint(months) or 6, 3), 24)
	start = get_first_day(add_months(nowdate(), -(months - 1)))

	# ── revenue by month: invoiced vs collected ───────────────────────────────
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

	series = []
	for i in range(months):
		key = _month_key(add_months(start, i))
		series.append(
			{
				"month": key,
				"label": getdate(f"{key}-01").strftime("%b"),
				"invoiced": round(invoiced.get(key, 0), 2),
				"collected": round(collected.get(key, 0), 2),
			}
		)

	# ── top customers by shipment count + charges ─────────────────────────────
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
	top_customers = sorted(
		({"customer": k, **v} for k, v in per_customer.items()),
		key=lambda x: (-x["charges"], -x["count"]),
	)[:10]

	# ── shipment status breakdown ─────────────────────────────────────────────
	status_counts = Counter(
		r.status for r in frappe.get_all("Shipment", fields=["status"], limit_page_length=0)
	)

	return {
		"months": series,
		"top_customers": top_customers,
		"status_breakdown": [
			{"status": s, "count": c} for s, c in sorted(status_counts.items(), key=lambda x: -x[1])
		],
	}


def _month_key(d) -> str:
	d = getdate(d)
	return f"{d.year}-{d.month:02d}"
