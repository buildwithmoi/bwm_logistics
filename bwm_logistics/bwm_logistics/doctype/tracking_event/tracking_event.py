# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TrackingEvent(Document):
	"""Append-only milestone log. One event links a container OR a shipment
	(or both, when an event is specific to one shipment inside a container).

	Container events cascade logically, not physically: a shipment's timeline
	is the union of its own events and its container's events, and container
	events notify every tagged customer once.
	"""

	def validate(self):
		if not (self.container or self.shipment):
			frappe.throw(_("A tracking event needs a container or a shipment."))
		# Consistency: if both set, the shipment must be tagged to that container.
		if self.container and self.shipment:
			tagged = frappe.db.get_value("Shipment", self.shipment, "container")
			if tagged != self.container:
				frappe.throw(_("Shipment {0} is not tagged to container {1}.").format(self.shipment, self.container))

	def after_insert(self):
		self.sync_parents()
		if self.notify:
			# Queued so slow SMTP/SMS gateways never block the operator's save.
			frappe.enqueue(
				"bwm_logistics.notifications.dispatch_for_event",
				queue="short",
				event_name=self.name,
				enqueue_after_commit=True,
			)

	def sync_parents(self):
		"""Keep current_milestone/status on the linked docs in step."""
		if self.shipment:
			frappe.get_doc("Shipment", self.shipment).apply_milestone(self.milestone)
		if self.container:
			frappe.get_doc("Container", self.container).apply_milestone(self.milestone)
			if not self.shipment:
				# Container-wide event → cascade status to every tagged shipment.
				for name in frappe.get_all(
					"Shipment",
					filters={"container": self.container, "status": ("not in", ["Cancelled"])},
					pluck="name",
				):
					frappe.get_doc("Shipment", name).apply_milestone(self.milestone)

	def on_trash(self):
		# Append-only: events are the audit trail behind customer notifications.
		if not frappe.session.user == "Administrator":
			frappe.throw(_("Tracking events cannot be deleted."))
