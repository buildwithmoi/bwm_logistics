# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class MilestoneTemplate(Document):
	def validate(self):
		if not self.milestones:
			frappe.throw(_("Add at least one milestone."))
		# Only one default per direction — flip the others off quietly.
		if self.is_default:
			for other in frappe.get_all(
				"Milestone Template",
				filters={"direction": self.direction, "is_default": 1, "name": ("!=", self.name)},
				pluck="name",
			):
				frappe.db.set_value("Milestone Template", other, "is_default", 0)


def get_default(direction: str) -> str | None:
	"""Name of the default template for a direction (or any template of that
	direction as fallback)."""
	name = frappe.db.get_value("Milestone Template", {"direction": direction, "is_default": 1})
	return name or frappe.db.get_value("Milestone Template", {"direction": direction})
