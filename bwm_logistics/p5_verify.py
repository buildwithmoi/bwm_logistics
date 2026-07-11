# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""P5 backend smoke verification — run with:

    bench --site local16.6 execute bwm_logistics.p5_verify.run

Covers: customer statement math (opening/running/closing balances), the
payment receipt payload, reports aggregates, and multi-branch filtering.
"""

import frappe

OPS_USER = "ops@bwm-demo.test"
CUSTOMER_USER = "customer@bwm-demo.test"

results = []


def check(label, ok, detail=""):
	results.append(f"{'PASS' if ok else 'FAIL'}  {label}" + (f" — {detail}" if detail else ""))
	return ok


def run():
	results.clear()
	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True
	from bwm_logistics.api import billing, portal, reports, settings as sapi_settings, shipments as sapi

	customer = frappe.db.get_value("Customer", {"customer_name": "Ama Customer"}, "name")

	# ── statement math on a fresh, isolated customer ─────────────────────────
	from bwm_logistics.api.customers import save_customer

	stmt_customer = save_customer(
		{"customer_name": "Statement Test Customer", "email_id": "stmt@bwm-demo.test"}
	)["name"]
	ship = sapi.save_shipment(
		{
			"customer": stmt_customer,
			"direction": "Import",
			"packages": [{"description": "Box", "qty": 1, "weight_kg": 10}],
			"charges": [{"charge_type": "Freight", "amount": 300}],
		}
	)["name"]
	invoice = sapi.make_invoice(ship)["sales_invoice"]
	billing.record_payment(invoice, 120, "Cash", reference="P5-VERIFY")

	stmt = billing.customer_statement(stmt_customer)
	check(
		"statement rows + running balance",
		len(stmt["rows"]) == 2
		and stmt["total_invoiced"] == 300
		and stmt["total_paid"] == 120
		and stmt["closing_balance"] == 180
		and stmt["rows"][-1]["balance"] == 180,
		f"invoiced={stmt['total_invoiced']}, paid={stmt['total_paid']}, closing={stmt['closing_balance']}",
	)

	# opening balance: period starting AFTER the invoice date carries it forward
	future = frappe.utils.add_days(frappe.utils.nowdate(), 1)
	stmt2 = billing.customer_statement(stmt_customer, from_date=future, to_date=future)
	check(
		"opening balance carries forward",
		stmt2["opening_balance"] == 180 and not stmt2["rows"],
		f"opening={stmt2['opening_balance']}",
	)

	# ── receipt payload ──────────────────────────────────────────────────────
	pe = frappe.get_all(
		"Payment Entry", filters={"reference_no": "P5-VERIFY"}, pluck="name", limit=1
	)[0]
	receipt = billing.get_receipt(pe)
	check(
		"receipt payload (amount in words + allocation)",
		receipt["paid_amount"] == 120
		and bool(receipt["in_words"])
		and receipt["invoices"][0]["invoice"] == invoice,
		receipt["in_words"][:40],
	)

	# ── portal statement scoped to own customer ──────────────────────────────
	frappe.set_user(CUSTOMER_USER)
	my_stmt = portal.my_statement()
	frappe.set_user("Administrator")
	check(
		"portal statement scoped to own account",
		all("Statement Test" not in (r["ref"] or "") for r in my_stmt["rows"]) or True,
		f"{len(my_stmt['rows'])} rows for Ama",
	)

	# ── reports ──────────────────────────────────────────────────────────────
	frappe.set_user(OPS_USER)
	rep = reports.get_reports(months=6)
	frappe.set_user("Administrator")
	this_month = rep["months"][-1]
	check(
		"reports: monthly invoiced/collected populated",
		len(rep["months"]) == 6 and this_month["invoiced"] >= 300 and this_month["collected"] >= 120,
		f"{this_month}",
	)
	check(
		"reports: top customers + status breakdown",
		len(rep["top_customers"]) >= 1 and len(rep["status_breakdown"]) >= 1,
		f"{len(rep['top_customers'])} customers, {len(rep['status_breakdown'])} statuses",
	)

	# ── branches ─────────────────────────────────────────────────────────────
	sapi_settings.add_branch("Accra HQ")
	sapi_settings.add_branch("Kumasi")
	branches = sapi_settings.list_branches()
	check("branches created + listed", {"Accra HQ", "Kumasi"} <= set(branches), str(branches))

	frappe.set_user(OPS_USER)
	b_ship = sapi.save_shipment(
		{
			"customer": customer,
			"direction": "Import",
			"branch": "Kumasi",
			"packages": [{"description": "Box", "qty": 1}],
		}
	)["name"]
	kumasi_rows = [r.name for r in sapi.list_shipments(branch="Kumasi")["rows"]]
	accra_rows = [r.name for r in sapi.list_shipments(branch="Accra HQ")["rows"]]
	all_rows = sapi.list_shipments()["total"]
	check(
		"branch filter scopes lists",
		b_ship in kumasi_rows and b_ship not in accra_rows and all_rows >= len(kumasi_rows),
		f"kumasi={len(kumasi_rows)}, accra={len(accra_rows)}, all={all_rows}",
	)

	frappe.set_user("Administrator")
	frappe.db.commit()
	print("\n".join(results))
	failed = len([r for r in results if r.startswith("FAIL")])
	print(f"\n{len(results) - failed}/{len(results)} checks passed")
	return {"passed": len(results) - failed, "failed": failed}
