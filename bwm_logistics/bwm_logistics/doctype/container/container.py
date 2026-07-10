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
		if self.ata and self.free_days and not self.demurrage_start_date:
			self.demurrage_start_date = add_days(self.ata, int(self.free_days))

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
