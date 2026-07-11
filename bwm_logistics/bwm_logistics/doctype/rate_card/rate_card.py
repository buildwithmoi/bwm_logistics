# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class RateCard(Document):
	def validate(self):
		if not self.items:
			frappe.throw(_("Add at least one charge line."))
		# One default per direction (blank direction = global default).
		if self.is_default:
			for other in frappe.get_all(
				"Rate Card",
				filters={"direction": self.direction or "", "is_default": 1, "name": ("!=", self.name)},
				pluck="name",
			):
				frappe.db.set_value("Rate Card", other, "is_default", 0)

	def compute_charges(self, shipment) -> list[dict]:
		"""Charge lines for a shipment from its package totals (FR-PAY-1)."""
		basis_values = {
			"Flat": 1,
			"Per KG": flt(shipment.total_weight_kg),
			"Per CBM": flt(shipment.total_volume_cbm),
			"Per Package": flt(shipment.total_packages),
		}
		charges = []
		for item in self.items:
			quantity = basis_values.get(item.calc_basis, 1)
			amount = flt(item.rate) * quantity
			if item.minimum and amount < flt(item.minimum):
				amount = flt(item.minimum)
			if amount > 0:
				charges.append({"charge_type": item.charge_type, "amount": round(amount, 2)})
		return charges
