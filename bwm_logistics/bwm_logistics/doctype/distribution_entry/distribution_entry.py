# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Distribution Entry — the quantity-first outbound ledger for trading
shipments (P8). One entry = "gave N units of product X from shipment Y to
recipient Z" (a truck, a person, or Storage). Money is optional: entries with
a real customer + unit price can be converted to a Sales Invoice
(api/stock.py), which is what feeds the P&L — the ledger itself never does."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, nowdate

QTY_TOLERANCE = 1e-6


def _norm(text) -> str:
	return (text or "").strip().lower()


class DistributionEntry(Document):
	def before_insert(self):
		self.recorded_by = frappe.session.user
		if not self.delivery_date:
			self.delivery_date = nowdate()

	def validate(self):
		if flt(self.qty) <= 0:
			frappe.throw(_("Quantity must be greater than zero."))

		shipment = frappe.db.get_value(
			"Shipment", self.shipment, ["shipment_type", "status"], as_dict=True
		)
		if not shipment:
			frappe.throw(_("Unknown shipment {0}.").format(self.shipment))
		if (shipment.shipment_type or "Customer Cargo") != "Own Goods (Trading)":
			frappe.throw(
				_("Distribution is for Own Goods (Trading) shipments — customer cargo is delivered via Dispatch.")
			)
		if shipment.status == "Cancelled":
			frappe.throw(_("Shipment {0} is cancelled.").format(self.shipment))

		self.validate_against_balance()
		self.amount = round(flt(self.qty) * flt(self.unit_price), 2)

	def validate_against_balance(self):
		"""Line-level guard: total distributed per product never exceeds the
		received qty on the shipment's matching package lines."""
		packages = frappe.get_all(
			"Shipment Package",
			filters={"parenttype": "Shipment", "parent": self.shipment},
			fields=["description", "qty", "unit"],
		)
		matching = [p for p in packages if _norm(p.description) == _norm(self.product)]
		if not matching:
			frappe.throw(
				_("Product {0} is not on shipment {1} — it must match a package description exactly.").format(
					frappe.bold(self.product), self.shipment
				)
			)
		if not self.unit:
			self.unit = matching[0].unit or "PIECES"

		received = sum(flt(p.qty) for p in matching)
		others = sum(
			flt(r.qty)
			for r in frappe.get_all(
				"Distribution Entry",
				filters={"shipment": self.shipment, "name": ("!=", self.name or "")},
				fields=["qty", "product"],
			)
			if _norm(r.product) == _norm(self.product)
		)
		if others + flt(self.qty) > received + QTY_TOLERANCE:
			frappe.throw(
				_("Only {0} {1} of {2} remaining on {3} — you are trying to distribute {4}.").format(
					frappe.format_value(max(received - others, 0), {"fieldtype": "Float"}),
					self.unit or "",
					frappe.bold(self.product),
					self.shipment,
					frappe.format_value(flt(self.qty), {"fieldtype": "Float"}),
				)
			)

	def on_trash(self):
		if self.sales_invoice:
			frappe.throw(
				_("This entry is invoiced ({0}) — cancel or unlink the invoice before deleting it.").format(
					self.sales_invoice
				)
			)
