# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.model.document import Document


class LogisticsRole(Document):
	def validate(self):
		# Keep the pages JSON clean: known operator page keys only.
		from bwm_logistics.api.access import OPERATOR_KEYS

		try:
			pages = json.loads(self.pages or "[]")
		except Exception:
			pages = []
		clean = [p for p in pages if isinstance(p, str) and p in OPERATOR_KEYS and p != "settings"]
		self.pages = json.dumps(sorted(set(clean)))

	def page_keys(self) -> set:
		from bwm_logistics.api.access import OPERATOR_KEYS

		if self.is_admin:
			return set(OPERATOR_KEYS)
		if self.all_pages:
			return OPERATOR_KEYS - {"settings"}
		try:
			return {p for p in json.loads(self.pages or "[]") if p in OPERATOR_KEYS}
		except Exception:
			return set()

	def on_trash(self):
		# Unassign from users so no one points at a dead role.
		for user in frappe.get_all("User", filters={"bwm_logistics_role": self.name}, pluck="name"):
			frappe.db.set_value("User", user, "bwm_logistics_role", None)
