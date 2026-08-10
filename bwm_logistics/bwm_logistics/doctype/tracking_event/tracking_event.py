# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


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
		self.supersede_auto_event()
		self.sync_parents()
		if self.notify:
			# Queued so slow SMTP/SMS gateways never block the operator's save.
			frappe.enqueue(
				"bwm_logistics.notifications.dispatch_for_event",
				queue="short",
				event_name=self.name,
				enqueue_after_commit=True,
			)

	def supersede_auto_event(self):
		"""An operator recording what the system already laid down replaces it.

		Entering a date received puts the arrival on the timeline by itself
		(Container.sync_arrival_event). If the operator then records that same
		arrival — to add a location, or to notify the customer — the timeline
		would carry it twice. Theirs wins; the placeholder goes.
		"""
		if self.source == "System" or not self.container:
			return
		for name in frappe.get_all(
			"Tracking Event",
			filters={
				"container": self.container,
				"milestone": self.milestone,
				"source": "System",
				"name": ("!=", self.name),
			},
			pluck="name",
		):
			if getdate(frappe.db.get_value("Tracking Event", name, "event_datetime")) == getdate(
				self.event_datetime
			):
				frappe.delete_doc("Tracking Event", name, ignore_permissions=True, delete_permanently=True)

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
		"""Append-only for the people recording milestones, correctable by a
		manager. The log is the audit trail behind customer notifications, so
		Operations cannot rewrite it — but somebody has to be able to undo a bad
		import or clear a site down to nothing and start entering by hand.

		The doctype permissions say the same thing; this is the backstop for a
		script or an API call that reaches past them.
		"""
		if not (
			frappe.session.user == "Administrator"
			or {"System Manager", "Logistics Manager"} & set(frappe.get_roles())
		):
			frappe.throw(_("Only a manager can delete a tracking event."))

	def after_delete(self):
		"""A deleted event must not leave its milestone behind.

		`apply_milestone()` writes current_milestone and status onto the
		container and the shipment, so removing the event that set them would
		otherwise leave both quoting a milestone with nothing behind it — the
		record would read "Arrived" over an empty timeline.
		"""
		touched = [("Shipment", self.shipment), ("Container", self.container)]
		if self.container and not self.shipment:
			# A container-wide event cascaded to every shipment in the box, so
			# undoing it has to reach all of them too.
			touched += [
				("Shipment", name)
				for name in frappe.get_all("Shipment", filters={"container": self.container}, pluck="name")
			]
		for doctype, name in touched:
			if name and frappe.db.exists(doctype, name):
				resync_from_events(doctype, name)


def resync_from_events(doctype: str, name: str):
	"""Re-derive current_milestone and status from the events that remain.

	A shipment's timeline is the union of its own events and its container's —
	the same rule get_timeline() reads by — so rewinding one has to look at
	both. Reading only the shipment's own events sent a booking back to Open
	while its box still said In Transit.
	"""
	if doctype == "Shipment":
		or_filters = [["shipment", "=", name]]
		box = frappe.db.get_value("Shipment", name, "container")
		if box:
			or_filters.append(["container", "=", box])
	else:
		or_filters = [["container", "=", name]]

	latest = frappe.get_all(
		"Tracking Event",
		or_filters=or_filters,
		fields=["milestone"],
		order_by="event_datetime desc, creation desc",
		limit=1,
	)
	if latest:
		frappe.get_doc(doctype, name).apply_milestone(latest[0].milestone)
		return

	# Nothing left: back to where the record started. Cancelled is a decision
	# somebody made, not a milestone that was recorded — leave it alone.
	updates = {"current_milestone": None}
	if frappe.db.get_value(doctype, name, "status") != "Cancelled":
		updates["status"] = "Active" if doctype == "Container" else "Open"
	frappe.db.set_value(doctype, name, updates, update_modified=False)
