# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days

# ISO 6346: 3 owner letters + category letter (U/J/Z) + 6 digits + check digit.
CONTAINER_NO_PATTERN = re.compile(r"^[A-Z]{3}[UJZ]\d{7}$")

# Recording one of these milestones flips the container to Completed.
TERMINAL_MILESTONES = {"Delivered"}


class Container(Document):
	def validate(self):
		self.validate_container_no()
		self.set_default_template()
		self.set_demurrage_start()
		self.compute_contents()
		self.check_distributed_contents()

	def on_update(self):
		self.refresh_shipment_totals()

	def compute_contents(self):
		self.total_qty = sum((c.qty or 0) for c in self.contents)

	def shipments(self) -> list[str]:
		"""Every booking riding in this box."""
		names = frappe.get_all(
			"Shipment Container", filters={"parenttype": "Shipment", "parent": ("is", "set"), "container": self.name},
			pluck="parent",
		)
		# Anything still linked the old single-field way counts too.
		names += frappe.get_all("Shipment", filters={"container": self.name}, pluck="name")
		return sorted(set(names))

	def refresh_shipment_totals(self):
		"""The manifest lives here, but the totals are cached on the shipment —
		so editing a box has to re-derive them. Without this, correcting a
		quantity leaves every booking in the box (and the customer's portal)
		quoting the number it had before the correction."""
		from bwm_logistics.bwm_logistics.doctype.shipment.shipment import refresh_stored_totals

		refresh_stored_totals(self.shipments())

	def check_distributed_contents(self):
		"""Goods that have already gone out cannot be taken off the manifest.

		Renaming is free — the ledger points at the catalogue Item, so the name
		follows. What this blocks is removing a line, or cutting its quantity
		below what has already been distributed from it, either of which would
		make real movements unaccountable.

		Only what *this* save takes away is objected to: a box whose numbers
		already disagreed stays editable, or it could never be corrected.
		"""
		if self.is_new() or not frappe.db.exists("DocType", "Distribution Entry"):
			return
		before = self.get_doc_before_save()
		if not before:
			return

		bookings = self.shipments()
		if not bookings:
			return

		from bwm_logistics.bwm_logistics.doctype.distribution_entry.distribution_entry import line_key

		gone_out: dict[str, float] = {}
		labels: dict[str, str] = {}
		for row in frappe.get_all(
			"Distribution Entry",
			filters={"shipment": ("in", bookings)},
			fields=["item", "product", "qty"],
		):
			key = line_key(row.item, row.product)
			gone_out[key] = gone_out.get(key, 0) + (row.qty or 0)
			labels.setdefault(key, row.product or row.item)
		if not gone_out:
			return

		def held(rows) -> dict[str, float]:
			out: dict[str, float] = {}
			for row in rows:
				key = line_key(row.item, row.description)
				out[key] = out.get(key, 0) + (row.qty or 0)
			return out

		was, now = held(before.contents), held(self.contents)
		short = []
		for key, distributed in gone_out.items():
			available = now.get(key, 0)
			if available >= distributed or available >= was.get(key, 0):
				continue  # still covered, or this save didn't reduce it
			short.append(
				_("{0} — {1} distributed, {2} left on the manifest").format(
					frappe.bold(labels.get(key, key)), distributed, available
				)
			)
		if short:
			frappe.throw(
				_("These goods have already been distributed out of this container:<br>{0}<br><br>Delete those distribution entries first, or put the quantity back.").format(
					"<br>".join(short)
				)
			)

	def customers(self) -> list[str]:
		"""Every customer with goods in this box, in manifest order.

		Untagged lines are ours, so they contribute nobody — which is what makes
		a consolidated box notify three customers and not four.
		"""
		seen: dict[str, None] = {}
		for row in self.contents:
			if row.customer:
				seen.setdefault(row.customer, None)
		return list(seen)

	def contents_for(self, customer: str) -> list[dict]:
		"""One customer's lines, for a notification that names their goods."""
		return [
			{"item": r.item, "description": r.description or r.item, "qty": r.qty, "unit": r.unit}
			for r in self.contents
			if r.customer == customer
		]

	def validate_container_no(self):
		if not self.container_no:
			return
		self.container_no = self.container_no.replace(" ", "").upper()
		if not CONTAINER_NO_PATTERN.match(self.container_no):
			frappe.throw(
				_("Container number {0} is not a valid ISO number (4 letters + 7 digits, e.g. MSCU1234567).").format(
					self.container_no
				)
			)

	def set_default_template(self):
		if self.milestone_template or not self.direction:
			return
		from bwm_logistics.bwm_logistics.doctype.milestone_template.milestone_template import get_default

		self.milestone_template = get_default(self.direction)

	def set_demurrage_start(self):
		"""Free days run from the day the box landed, so a corrected arrival
		date has to move the clock with it — the booking can now set ATA (as
		"date received"), which makes a stale demurrage date easy to create."""
		if not (self.ata and self.free_days):
			return
		expected = add_days(self.ata, int(self.free_days))
		before = self.get_doc_before_save()
		if not self.demurrage_start_date or (before and before.ata != self.ata):
			self.demurrage_start_date = expected

	def milestone_options(self) -> list[dict]:
		"""The template's milestone rows (for the record-milestone UI)."""
		if not self.milestone_template:
			return []
		template = frappe.get_cached_doc("Milestone Template", self.milestone_template)
		return [
			{"milestone": m.milestone, "notify_customer": m.notify_customer, "description": m.description}
			for m in template.milestones
		]

	def apply_milestone(self, milestone: str):
		"""Called by Tracking Event after insert — keeps status fields in sync."""
		updates = {"current_milestone": milestone}
		if milestone in TERMINAL_MILESTONES:
			updates["status"] = "Completed"
		frappe.db.set_value("Container", self.name, updates, update_modified=True)
