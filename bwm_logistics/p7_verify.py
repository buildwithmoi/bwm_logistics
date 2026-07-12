# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""P7 backend smoke verification — run with:

    bench --site local16.6 execute bwm_logistics.p7_verify.run

Covers the billing revamp: trading shipments (customer optional, invoice
blocked, notifications skipped), purchasing (supplier + Purchase Invoice +
supplier payment), free-form sales invoicing, per-shipment P&L math with role
gating, the branded print format + PDF smoke, the executive dashboard's
server-side profit gate, and the advanced reports (aging invariants, gated
profitability, filters).
"""

import frappe
from frappe.utils import flt

results = []

OPS_USER = "ops@bwm-demo.test"


def check(label, ok, detail=""):
	results.append(f"{'PASS' if ok else 'FAIL'}  {label}" + (f" — {detail}" if detail else ""))
	return ok


def _make_customer(name):
	existing = frappe.db.get_value("Customer", {"customer_name": name}, "name")
	if existing:
		return existing
	doc = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": name,
			"customer_type": "Individual",
			"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}) or "All Customer Groups",
			"territory": frappe.db.get_value("Territory", {"is_group": 0}) or "All Territories",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def run():
	results.clear()
	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True
	from bwm_logistics.install import after_install

	after_install()

	from bwm_logistics.api import billing, purchasing
	from bwm_logistics.api.dashboard import get_overview
	from bwm_logistics.api.reports import get_reports

	# ── schema: custom fields ────────────────────────────────────────────────
	check(
		"bwm_shipment custom fields exist (SI + PI)",
		bool(frappe.db.exists("Custom Field", "Sales Invoice-bwm_shipment"))
		and bool(frappe.db.exists("Custom Field", "Purchase Invoice-bwm_shipment")),
	)

	# ── trading shipment: customer optional, notify forced off ──────────────
	container = frappe.get_doc(
		{"doctype": "Container", "direction": "Import", "container_no": "MSKU2733680"}
	).insert(ignore_permissions=True)

	trading = frappe.get_doc(
		{
			"doctype": "Shipment",
			"shipment_type": "Own Goods (Trading)",
			"direction": "Import",
			"container": container.name,
			"notify_customer": 1,  # must be forced back to 0
			"packages": [{"description": "Chicken wings (frozen)", "qty": 1200, "weight_kg": 10}],
		}
	).insert(ignore_permissions=True)
	check(
		"trading shipment saves without customer, notify forced off",
		not trading.customer and trading.notify_customer == 0,
		trading.name,
	)

	# ── customer cargo still requires a customer ─────────────────────────────
	try:
		frappe.get_doc(
			{
				"doctype": "Shipment",
				"direction": "Import",
				"packages": [{"description": "Box", "qty": 1}],
			}
		).insert(ignore_permissions=True)
		blocked = False
	except frappe.ValidationError:
		blocked = True
	check("customer cargo without customer is blocked", blocked)

	# ── make_sales_invoice refuses trading shipments ─────────────────────────
	try:
		trading.make_sales_invoice()
		blocked = False
	except frappe.ValidationError:
		blocked = True
	check("make_sales_invoice blocked for trading shipment", blocked)

	# ── notifications skip customer-less shipments ───────────────────────────
	customer = _make_customer("P7 Cargo Customer")
	cargo = frappe.get_doc(
		{
			"doctype": "Shipment",
			"customer": customer,
			"direction": "Import",
			"container": container.name,
			"notify_customer": 1,
			"packages": [{"description": "Box", "qty": 2}],
			"charges": [{"charge_type": "Freight", "amount": 400}],
		}
	).insert(ignore_permissions=True)

	from bwm_logistics.notifications import _target_shipments

	targets = {s.name for s in _target_shipments(frappe._dict(shipment=None, container=container.name))}
	check(
		"notification targets: cargo in, trading out",
		cargo.name in targets and trading.name not in targets,
		str(sorted(targets)),
	)

	# ── freight invoice tags bwm_shipment ────────────────────────────────────
	si_name = cargo.make_sales_invoice()
	check(
		"freight invoice tagged bwm_shipment",
		frappe.db.get_value("Sales Invoice", si_name, "bwm_shipment") == cargo.name,
		si_name,
	)

	# ── purchasing: supplier + purchase invoice ──────────────────────────────
	supplier = purchasing.create_supplier("P7 Clearing Agent", phone="0244000000")["name"]
	check("supplier created", bool(frappe.db.exists("Supplier", supplier)), supplier)

	purchase = purchasing.record_purchase(
		{
			"supplier": supplier,
			"shipment": trading.name,
			"reference": "BILL-P7-001",
			"lines": [
				{"description": "Goods — chicken wings", "amount": 5000},
				{"description": "Duties & taxes", "amount": 1250},
				{"description": "Clearing & handling", "amount": 350},
			],
		}
	)
	pi_name = purchase["purchase_invoice"]
	pi = frappe.get_doc("Purchase Invoice", pi_name)
	expense_ok = all(row.expense_account for row in pi.items)
	check(
		"purchase invoice submitted, tagged, expense accounts set",
		pi.docstatus == 1 and pi.bwm_shipment == trading.name and expense_ok and flt(pi.grand_total) == 6600,
		f"{pi_name} total={pi.grand_total}",
	)

	# ── free-form sales invoice against the trading shipment ────────────────
	buyer = _make_customer("P7 Wholesale Buyer")
	sale = billing.new_invoice(
		{
			"customer": buyer,
			"shipment": trading.name,
			"lines": [{"description": "Chicken wings — 600 cartons", "qty": 600, "rate": 14}],
		}
	)
	check(
		"free-form invoice submitted + tagged",
		frappe.db.get_value("Sales Invoice", sale["sales_invoice"], "bwm_shipment") == trading.name
		and flt(sale["grand_total"]) == 8400,
		f"{sale['sales_invoice']} total={sale['grand_total']}",
	)

	# ── P&L math ─────────────────────────────────────────────────────────────
	pnl = billing.shipment_pnl(trading.name)
	check(
		"shipment P&L math (8400 − 6600 = 1800 @ 21.4%)",
		flt(pnl["revenue"]) == 8400
		and flt(pnl["cost"]) == 6600
		and flt(pnl["profit"]) == 1800
		and pnl["margin_pct"] == 21.4
		and len(pnl["sales"]) == 1
		and len(pnl["purchases"]) == 1,
		f"rev={pnl['revenue']} cost={pnl['cost']} profit={pnl['profit']} margin={pnl['margin_pct']}",
	)

	# ── pay the supplier (partial, then check outstanding) ───────────────────
	pay = purchasing.pay_supplier(pi_name, 2600, "Cash")
	check(
		"supplier payment settles against PI",
		flt(pay["outstanding"]) == 4000,
		f"pe={pay['payment_entry']} outstanding={pay['outstanding']}",
	)

	# ── role gates: Operations blocked from money endpoints ──────────────────
	frappe.set_user(OPS_USER)
	blocked_calls = 0
	for fn, args in (
		(billing.shipment_pnl, (trading.name,)),
		(purchasing.record_purchase, ({"supplier": supplier, "lines": [{"description": "x", "amount": 1}]},)),
		(purchasing.pay_supplier, (pi_name, 1)),
	):
		try:
			fn(*args)
		except frappe.PermissionError:
			blocked_calls += 1
	ops_dash = get_overview()
	ops_reports = get_reports(months=6)
	frappe.set_user("Administrator")
	check("Operations blocked from P&L/purchase/pay APIs", blocked_calls == 3, f"{blocked_calls}/3 blocked")
	check(
		"profit hidden from Operations (dashboard + reports)",
		"profit_mtd" not in ops_dash and "profitability" not in ops_reports,
	)

	# ── executive dashboard payload (admin sees profit) ──────────────────────
	dash = get_overview()
	core_keys = {
		"revenue_mtd", "collected_mtd", "outstanding_total", "overdue_count",
		"containers_active", "shipments_active", "pipeline", "demurrage_risk",
		"cod_unreconciled", "arriving_week", "top_customers", "recent_payments",
		"revenue_months", "shipment_months", "recent_events",
	}
	check(
		"dashboard payload complete + profit visible to admin",
		core_keys <= set(dash) and "profit_mtd" in dash and len(dash["revenue_months"]) == 12,
		f"profit_mtd={dash.get('profit_mtd')}",
	)

	# ── advanced reports: aging invariants + profitability + filters ────────
	rep = get_reports(months=6)
	aging = rep["aging"]
	buckets_sum = round(sum(aging["buckets"].values()), 2)
	outstanding_sum = round(
		sum(
			flt(r.outstanding_amount)
			for r in frappe.get_all(
				"Sales Invoice",
				filters={"docstatus": 1, "outstanding_amount": (">", 0)},
				fields=["outstanding_amount"],
			)
		),
		2,
	)
	check(
		"aging buckets sum to total outstanding",
		buckets_sum == aging["total"] == outstanding_sum,
		f"buckets={buckets_sum} total={aging['total']} ledger={outstanding_sum}",
	)

	prof = rep.get("profitability") or {}
	row = next((r for r in prof.get("rows", []) if r["shipment"] == trading.name), None)
	check(
		"reports profitability row matches P&L",
		bool(row) and flt(row["profit"]) == 1800 and row["type"] == "Own Goods (Trading)",
		str(row and {k: row[k] for k in ("revenue", "cost", "profit")}),
	)

	rep_range = get_reports(from_date="2026-01-01", to_date="2026-12-31", direction="Export")
	check(
		"custom range + direction filter accepted",
		rep_range["window"] == {"from": "2026-01-01", "to": "2026-12-31"}
		and all(m["imports"] == 0 for m in rep_range["shipment_months"]),
		rep_range["window"]["from"] + " → " + rep_range["window"]["to"],
	)
	check("collection rate present", "rate_pct" in rep["collection"], str(rep["collection"]))

	# ── print format: exists, default, renders a PDF ─────────────────────────
	fmt_exists = bool(frappe.db.exists("Print Format", "BWM Invoice"))
	default_fmt = frappe.db.get_value(
		"Property Setter",
		{"doc_type": "Sales Invoice", "property": "default_print_format"},
		"value",
	)
	check("BWM Invoice print format installed + default", fmt_exists and default_fmt == "BWM Invoice", str(default_fmt))

	pdf_ok, pdf_detail = False, ""
	try:
		pdf = frappe.get_print("Sales Invoice", si_name, print_format="BWM Invoice", as_pdf=True)
		pdf_ok = bool(pdf) and pdf[:4] == b"%PDF"
		pdf_detail = f"{len(pdf)} bytes"
	except Exception as e:  # env-conditioned (wkhtmltopdf missing) — report it
		pdf_detail = str(e)[:120]
	check("branded invoice renders to PDF", pdf_ok, pdf_detail)

	frappe.db.commit()
	print("\n".join(results))
	failed = len([r for r in results if r.startswith("FAIL")])
	print(f"\n{len(results) - failed}/{len(results)} checks passed")
	return {"passed": len(results) - failed, "failed": failed}


def set_demo_passwords():
	"""Dev convenience for the HTTP e2e: demo staff/customer users are created
	without passwords (welcome emails muted on this site). Also ensures an
	Accounts-role demo user for testing the billing-side endpoints."""
	from frappe.utils.password import update_password

	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True
	accounts_user = "accounts@bwm-demo.test"
	if not frappe.db.exists("User", accounts_user):
		from bwm_logistics.api.staff import create_staff

		create_staff("Ama Accounts", accounts_user, logistics_role="Accounts")
	for user in (OPS_USER, "customer@bwm-demo.test", accounts_user):
		if frappe.db.exists("User", user):
			update_password(user, "bwm-demo-2026")
	frappe.db.commit()
	print("demo passwords set")
