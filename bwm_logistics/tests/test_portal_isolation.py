# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""One customer must never reach another's records — nor our costs.

This is the multi-tenant equivalent of a permission flight: the portal endpoints
all take a document name straight from the URL, so each one is asked for a
record belonging to somebody else and has to refuse. Written once, run on every
change.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from bwm_logistics.api import portal

# Keys that describe what a shipment cost *us*. A customer paying a freight bill
# has no business seeing any of them, whatever the frontend does with them.
FORBIDDEN_KEYS = {
	"cost",
	"margin",
	"margin_pct",
	"profit",
	"supplier",
	"supplier_name",
	"purchase_total",
	"purchases",
	"spent_mtd",
}


def _customer(name: str) -> str:
	if not frappe.db.exists("Customer", {"customer_name": name}):
		doc = frappe.new_doc("Customer")
		doc.customer_name = name
		doc.customer_type = "Individual"
		doc.insert(ignore_permissions=True)
	return frappe.db.get_value("Customer", {"customer_name": name}, "name")


def _portal_user(email: str, customer: str) -> str:
	if not frappe.db.exists("User", email):
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = email.split("@")[0]
		user.user_type = "Website User"
		user.send_welcome_email = 0
		user.insert(ignore_permissions=True)
	user = frappe.get_doc("User", email)
	if not any(r.role == "Logistics Customer" for r in user.roles):
		user.append("roles", {"role": "Logistics Customer"})
		user.save(ignore_permissions=True)

	contact_name = frappe.db.get_value("Contact", {"user": email}, "name")
	if not contact_name:
		contact = frappe.new_doc("Contact")
		contact.first_name = email.split("@")[0]
		contact.user = email
		contact.append("email_ids", {"email_id": email, "is_primary": 1})
		contact.insert(ignore_permissions=True)
		contact_name = contact.name
	contact = frappe.get_doc("Contact", contact_name)
	if not any(l.link_doctype == "Customer" and l.link_name == customer for l in contact.links):
		contact.append("links", {"link_doctype": "Customer", "link_name": customer})
		contact.save(ignore_permissions=True)
	return email


class TestPortalIsolation(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		frappe.flags.mute_emails = True

		cls.cust_a = _customer("Isolation Test A")
		cls.cust_b = _customer("Isolation Test B")
		cls.user_a = _portal_user("isolation-a@bwm-test.invalid", cls.cust_a)
		cls.user_b = _portal_user("isolation-b@bwm-test.invalid", cls.cust_b)

		# One shipment each, so "somebody else's record" is a real name.
		cls.ship_a = cls._shipment(cls.cust_a)
		cls.ship_b = cls._shipment(cls.cust_b)
		frappe.db.commit()

	@classmethod
	def _shipment(cls, customer: str) -> str:
		doc = frappe.get_doc(
			{
				"doctype": "Shipment",
				"shipment_type": "Customer Cargo",
				"direction": "Import",
				"customer": customer,
				"packages": [{"description": "Isolation test carton", "qty": 1, "unit": "CARTONS"}],
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
		return doc.name

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_cannot_open_another_customers_shipment(self):
		"""B asks for A's tracking number by name and is refused."""
		frappe.set_user(self.user_b)
		with self.assertRaises(frappe.DoesNotExistError):
			portal.shipment_detail(self.ship_a)

	def test_own_shipment_still_opens(self):
		"""The refusal above must be about ownership, not a broken endpoint."""
		frappe.set_user(self.user_b)
		out = portal.shipment_detail(self.ship_b)
		self.assertEqual(out["name"], self.ship_b)

	def test_list_endpoints_are_scoped(self):
		"""Nothing of A's appears in B's lists."""
		frappe.set_user(self.user_b)
		names = {r["name"] for r in portal.my_shipments()["rows"]}
		self.assertNotIn(self.ship_a, names)

	def test_portal_payloads_carry_no_cost_of_ours(self):
		"""No portal endpoint returns a key describing our own cost or margin."""
		frappe.set_user(self.user_b)
		payloads = {
			"overview": portal.overview(),
			"my_shipments": portal.my_shipments(),
			"my_invoices": portal.my_invoices(),
			"my_pickups": portal.my_pickups(),
			"shipment_detail": portal.shipment_detail(self.ship_b),
		}
		for label, payload in payloads.items():
			for key in _walk_keys(payload):
				self.assertNotIn(
					key.lower(),
					FORBIDDEN_KEYS,
					msg=f"portal.{label} returned '{key}' — that is our cost, not the customer's",
				)


def _walk_keys(value, depth: int = 0):
	"""Every dict key anywhere in a nested payload."""
	if depth > 6:
		return
	if isinstance(value, dict):
		for k, v in value.items():
			yield k
			yield from _walk_keys(v, depth + 1)
	elif isinstance(value, list):
		for item in value:
			yield from _walk_keys(item, depth + 1)
