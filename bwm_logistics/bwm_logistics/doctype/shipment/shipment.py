# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname

# Shipment milestones that flip status (shipment- or container-level).
MILESTONE_STATUS = {
	"Vessel Departed": "In Transit",
	"In Transit": "In Transit",
	"Arrived at Port": "Arrived",
	"Arrived at Destination": "Arrived",
	"Ready for Delivery": "Ready for Delivery",
	"Out for Delivery": "Ready for Delivery",
	"Delivered": "Delivered",
}


class Shipment(Document):
	def autoname(self):
		# The document name IS the customer-facing tracking number:
		# <prefix>-000001, sequential per prefix (Logistics Settings).
		prefix = (frappe.db.get_single_value("Logistics Settings", "tracking_prefix") or "BWM").strip().upper()
		self.name = make_autoname(f"{prefix}-.######")

	def is_trading(self) -> bool:
		# NULL-safe: rows created before shipment_type existed are Customer Cargo.
		return (self.shipment_type or "Customer Cargo") == "Own Goods (Trading)"

	def validate(self):
		self.validate_customer()
		self.compute_totals()
		self.sync_direction_from_container()

	def validate_customer(self):
		if self.is_trading():
			# Own goods: no customer, and nobody external to notify.
			self.notify_customer = 0
			if not self.customer:
				self.customer_name = None
		elif not self.customer:
			frappe.throw(_("Customer is required for Customer Cargo shipments."))
		if not self.customer:
			self.customer_name = None

	def sync_direction_from_container(self):
		if self.container and not self.direction:
			self.direction = frappe.db.get_value("Container", self.container, "direction")

	def compute_totals(self):
		self.total_packages = sum((p.qty or 0) for p in self.packages)
		self.total_weight_kg = sum((p.weight_kg or 0) * (p.qty or 1) for p in self.packages)
		self.total_volume_cbm = sum((p.volume_cbm or 0) * (p.qty or 1) for p in self.packages)
		self.total_declared_value = sum((p.declared_value or 0) for p in self.packages)
		self.total_charges = sum((c.amount or 0) for c in self.charges)

	def apply_milestone(self, milestone: str):
		"""Called by Tracking Event after insert — keeps status fields in sync."""
		updates = {"current_milestone": milestone}
		if milestone in MILESTONE_STATUS:
			updates["status"] = MILESTONE_STATUS[milestone]
		frappe.db.set_value("Shipment", self.name, updates, update_modified=True)

	def make_sales_invoice(self):
		"""One-click Sales Invoice from this shipment's charges."""
		if not self.customer:
			frappe.throw(
				_("This trading shipment has no customer to invoice — raise sales from Billing → New invoice and record costs under Purchases instead.")
			)
		if self.sales_invoice:
			frappe.throw(_("Shipment {0} is already invoiced ({1}).").format(self.name, self.sales_invoice))
		if not self.charges:
			frappe.throw(_("Add at least one charge before invoicing."))

		item_code = _ensure_charge_item()
		invoice = frappe.new_doc("Sales Invoice")
		invoice.customer = self.customer
		# P&L revenue is counted solely via this tag (never via
		# Shipment.sales_invoice — that would double count).
		invoice.bwm_shipment = self.name
		for charge in self.charges:
			invoice.append(
				"items",
				{
					"item_code": item_code,
					"item_name": charge.charge_type,
					"description": f"{charge.charge_type} — Shipment {self.name}",
					"qty": 1,
					"rate": charge.amount,
				},
			)
		invoice.flags.ignore_permissions = True
		invoice.set_missing_values()
		invoice.insert(ignore_permissions=True)
		invoice.submit()
		frappe.db.set_value("Shipment", self.name, "sales_invoice", invoice.name)
		return invoice.name


def _ensure_charge_item() -> str:
	"""A non-stock service Item that carries shipment charge lines on Sales
	Invoices (rate is overridden per line). Created lazily, once per site."""
	code = "Logistics Charge"
	if not frappe.db.exists("Item", code):
		item = frappe.new_doc("Item")
		item.item_code = code
		item.item_name = code
		item.item_group = frappe.db.get_value("Item Group", {"is_group": 0}) or "All Item Groups"
		item.is_stock_item = 0
		item.is_sales_item = 1
		item.stock_uom = "Nos"
		item.flags.ignore_permissions = True
		item.insert(ignore_permissions=True)
	return code
