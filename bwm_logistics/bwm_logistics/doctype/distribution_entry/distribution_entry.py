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


def line_key(item, description) -> str:
	"""What identifies a product in the ledger.

	The catalogue Item where there is one, so renaming a manifest line carries
	through instead of orphaning every entry that named it. Entries recorded
	before the catalogue existed still key on the name they were written with.
	"""
	return f"item:{item}" if item else f"name:{_norm(description)}"


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
		received qty on the shipment's matching manifest lines."""
		from bwm_logistics.bwm_logistics.doctype.shipment.shipment import shipment_manifest

		lines = shipment_manifest(self.shipment)
		# Prefer the catalogue item; fall back to the name for an entry (or a
		# manifest) written before the catalogue existed.
		matching = [line for line in lines if self.item and line["item"] == self.item]
		if not matching:
			matching = [line for line in lines if _norm(line["description"]) == _norm(self.product)]
		if not matching:
			frappe.throw(
				_("Product {0} is not in shipment {1}'s containers — it must match a manifest line.").format(
					frappe.bold(self.product or self.item), self.shipment
				)
			)
		if not self.item:
			self.item = matching[0]["item"]
		if not self.product:
			self.product = matching[0]["description"]
		if not self.unit:
			self.unit = matching[0]["unit"] or "PIECES"

		mine = line_key(self.item, self.product)
		received = sum(flt(line["qty"]) for line in matching)
		others = sum(
			flt(r.qty)
			for r in frappe.get_all(
				"Distribution Entry",
				filters={"shipment": self.shipment, "name": ("!=", self.name or "")},
				fields=["qty", "product", "item"],
			)
			if line_key(r.item, r.product) == mine
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
