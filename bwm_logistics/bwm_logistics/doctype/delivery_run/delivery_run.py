# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class DeliveryRun(Document):
	def validate(self):
		self.hydrate_stops()
		self.compute_totals()

	def hydrate_stops(self):
		"""Fill stop address/contact/COD from the linked shipment or pickup
		request so dispatchers don't retype what the system already knows."""
		for stop in self.stops:
			if stop.stop_type == "Delivery" and stop.shipment:
				ship = frappe.db.get_value(
					"Shipment",
					stop.shipment,
					["consignee_name", "consignee_phone", "delivery_address", "sales_invoice"],
					as_dict=True,
				)
				if not ship:
					frappe.throw(_("Unknown shipment {0} on stop {1}.").format(stop.shipment, stop.idx))
				stop.contact_name = stop.contact_name or ship.consignee_name
				stop.contact_phone = stop.contact_phone or ship.consignee_phone
				stop.address = stop.address or ship.delivery_address
				# Default COD to the invoice outstanding (0 for prepaid shipments).
				if not stop.cod_due and ship.sales_invoice:
					stop.cod_due = (
						frappe.db.get_value("Sales Invoice", ship.sales_invoice, "outstanding_amount") or 0
					)
			elif stop.stop_type == "Pickup" and stop.pickup_request:
				req = frappe.db.get_value(
					"Pickup Request",
					stop.pickup_request,
					["pickup_address", "contact_phone", "customer_name"],
					as_dict=True,
				)
				if not req:
					frappe.throw(_("Unknown pickup request {0} on stop {1}.").format(stop.pickup_request, stop.idx))
				stop.contact_name = stop.contact_name or req.customer_name
				stop.contact_phone = stop.contact_phone or req.contact_phone
				stop.address = stop.address or req.pickup_address

	def compute_totals(self):
		self.total_stops = len(self.stops)
		self.completed_stops = len([s for s in self.stops if s.status == "Completed"])
		self.cod_due_total = sum((s.cod_due or 0) for s in self.stops if s.stop_type == "Delivery")
		self.cod_collected_total = sum((s.cod_collected or 0) for s in self.stops)

	def on_update(self):
		# Keep tagged pickup requests' status in step with scheduling.
		for stop in self.stops:
			if stop.stop_type == "Pickup" and stop.pickup_request and self.status in ("Scheduled", "In Transit"):
				current = frappe.db.get_value("Pickup Request", stop.pickup_request, "status")
				if current == "Requested":
					frappe.db.set_value("Pickup Request", stop.pickup_request, "status", "Scheduled")

	def assert_driver(self, user: str | None = None):
		"""Throw unless `user` is this run's driver (drivers act only on their
		own runs; managers/ops bypass via their own role checks)."""
		user = user or frappe.session.user
		driver_user = frappe.db.get_value("Driver", self.driver, "user")
		if driver_user != user:
			frappe.throw(_("This run is assigned to another driver."), frappe.PermissionError)
