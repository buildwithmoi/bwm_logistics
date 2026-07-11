# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class LogisticsSettings(Document):
	def validate(self):
		# The inbound tracking webhook authenticates with this shared secret;
		# generate once, rotate by clearing the field.
		if not self.tracking_webhook_token:
			self.tracking_webhook_token = frappe.generate_hash(length=32)
