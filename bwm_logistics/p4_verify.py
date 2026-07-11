# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""P4 backend smoke verification — run with:

    bench --site local16.6 execute bwm_logistics.p4_verify.run

Covers the billing workspace: rate card CRUD + charge computation from
package totals, uninvoiced list → invoice, partial then settling manual
payments, overview aggregates, and charge-lock after invoicing.
"""

import frappe

OPS_USER = "ops@bwm-demo.test"

results = []


def check(label, ok, detail=""):
	results.append(f"{'PASS' if ok else 'FAIL'}  {label}" + (f" — {detail}" if detail else ""))
	return ok


def run():
	results.clear()
	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True
	from bwm_logistics.api import billing, shipments as sapi

	# ── rate card CRUD + math ────────────────────────────────────────────────
	if frappe.db.exists("Rate Card", "Standard Import Rates"):
		frappe.delete_doc("Rate Card", "Standard Import Rates", force=True)
	card = billing.save_rate_card(
		{
			"card_name": "Standard Import Rates",
			"direction": "Import",
			"is_default": 1,
			"items": [
				{"charge_type": "Freight", "calc_basis": "Per KG", "rate": 5, "minimum": 100},
				{"charge_type": "Handling", "calc_basis": "Per Package", "rate": 20},
				{"charge_type": "Documentation", "calc_basis": "Flat", "rate": 50},
			],
		}
	)["name"]
	cards = billing.list_rate_cards()
	check("rate card saved + listed", any(c["name"] == card for c in cards), card)

	customer = frappe.db.get_value("Customer", {"customer_name": "Ama Customer"}, "name")
	frappe.set_user(OPS_USER)
	ship = sapi.save_shipment(
		{
			"customer": customer,
			"direction": "Import",
			"destination": "Accra",
			"packages": [
				{"description": "Barrel", "qty": 2, "weight_kg": 40},  # 80kg total
				{"description": "Box", "qty": 1, "weight_kg": 10},
			],
		}
	)["name"]
	applied = sapi.apply_rate_card(ship, card)
	# Freight: 90kg × 5 = 450; Handling: 3 pkg × 20 = 60; Documentation: 50 → 560
	check(
		"rate card charges computed (per-kg, per-package, flat)",
		applied["total_charges"] == 560,
		str(applied),
	)

	# minimum kicks in on a light shipment
	light = sapi.save_shipment(
		{
			"customer": customer,
			"direction": "Import",
			"packages": [{"description": "Envelope", "qty": 1, "weight_kg": 2}],
		}
	)["name"]
	applied_light = sapi.apply_rate_card(light, card)
	freight = next(c for c in applied_light["charges"] if c["charge_type"] == "Freight")
	check("minimum charge enforced", freight["amount"] == 100, str(applied_light["charges"]))

	# ── uninvoiced → invoice → payments ──────────────────────────────────────
	uninv = [r.name for r in billing.uninvoiced_shipments()]
	check("shipment appears in uninvoiced list", ship in uninv, f"{len(uninv)} uninvoiced")

	frappe.set_user("Administrator")
	invoice = sapi.make_invoice(ship)["sales_invoice"]
	uninv_after = [r.name for r in billing.uninvoiced_shipments()]
	check("invoiced shipment leaves uninvoiced list", ship not in uninv_after)

	# charges locked after invoicing
	try:
		sapi.apply_rate_card(ship, card)
		check("charges locked after invoicing", False, "no exception")
	except Exception:
		check("charges locked after invoicing", True)

	# partial then settling payment
	p1 = billing.record_payment(invoice, 200, "Cash", reference="P4-VERIFY")
	check("partial payment recorded", p1["outstanding"] == 360, str(p1))
	p2 = billing.record_payment(invoice, 360, "Cash")
	check("invoice settled", p2["outstanding"] == 0, str(p2))
	try:
		billing.record_payment(invoice, 10, "Cash")
		check("overpayment rejected", False, "no exception")
	except Exception:
		check("overpayment rejected", True)

	# ── invoice list + overview ──────────────────────────────────────────────
	frappe.set_user(OPS_USER)
	rows = billing.list_invoices(search=None)["rows"]
	hit = next((r for r in rows if r.name == invoice), None)
	check("invoice list links shipment", bool(hit) and hit.get("shipment") == ship, str(hit and hit.get("shipment")))
	ov = billing.overview()
	check(
		"overview aggregates",
		ov["collected_this_month"] >= 560 and "unpaid_total" in ov,
		f"collected={ov['collected_this_month']}, unpaid={ov['unpaid_total']}",
	)

	frappe.set_user("Administrator")
	frappe.db.commit()
	print("\n".join(results))
	failed = len([r for r in results if r.startswith("FAIL")])
	print(f"\n{len(results) - failed}/{len(results)} checks passed")
	return {"passed": len(results) - failed, "failed": failed}
