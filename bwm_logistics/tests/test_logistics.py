# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Core P1 flow tests — run with:

    bench --site <site> run-tests --app bwm_logistics
"""

import frappe

try:
	from frappe.tests import IntegrationTestCase
except ImportError:  # older frappe
	from frappe.tests.utils import FrappeTestCase as IntegrationTestCase


def _make_customer(name):
	if frappe.db.exists("Customer", {"customer_name": name}):
		return frappe.db.get_value("Customer", {"customer_name": name}, "name")
	doc = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": name,
			"customer_type": "Individual",
			# Explicit group/territory — CI sites have no Selling Settings defaults.
			"customer_group": frappe.db.get_value("Customer Group", {"is_group": 0}) or "All Customer Groups",
			"territory": frappe.db.get_value("Territory", {"is_group": 0}) or "All Territories",
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


class TestInstall(IntegrationTestCase):
	def test_roles_created(self):
		from bwm_logistics.install import LOGISTICS_ROLES, ensure_roles

		ensure_roles()
		for role, _desk, _desc in LOGISTICS_ROLES:
			self.assertTrue(frappe.db.exists("Role", role), f"missing role {role}")

	def test_default_milestone_templates_seeded(self):
		from bwm_logistics.install import seed_milestone_templates

		seed_milestone_templates()
		directions = {t.direction for t in frappe.get_all("Milestone Template", fields=["direction"])}
		self.assertTrue({"Import", "Export"} <= directions)


class TestConsolidationFlow(IntegrationTestCase):
	"""Container → tagged shipments → milestone cascade → notification log."""

	def setUp(self):
		frappe.set_user("Administrator")
		from bwm_logistics.install import after_install

		after_install()

	def test_cascade_and_tracking(self):
		container = frappe.get_doc(
			{
				"doctype": "Container",
				"direction": "Import",
				"container_no": "TSTU3054383",
			}
		).insert(ignore_permissions=True)
		self.assertTrue(container.milestone_template, "default template not applied")

		c1 = _make_customer("Test Cascade Customer A")
		c2 = _make_customer("Test Cascade Customer B")
		s1 = frappe.get_doc(
			{
				"doctype": "Shipment",
				"customer": c1,
				"direction": "Import",
				"container": container.name,
				"packages": [{"description": "Box", "qty": 2, "weight_kg": 10}],
			}
		).insert(ignore_permissions=True)
		s2 = frappe.get_doc(
			{
				"doctype": "Shipment",
				"customer": c2,
				"direction": "Import",
				"container": container.name,
				"packages": [{"description": "Barrel", "qty": 1, "weight_kg": 50}],
			}
		).insert(ignore_permissions=True)

		# totals
		self.assertEqual(s1.total_packages, 2)
		self.assertEqual(s1.total_weight_kg, 20)

		# container-wide milestone cascades to both shipments
		event = frappe.get_doc(
			{
				"doctype": "Tracking Event",
				"container": container.name,
				"milestone": "Vessel Departed",
				"location": "Origin Port",
				"notify": 1,
			}
		).insert(ignore_permissions=True)

		for ship in (s1.name, s2.name):
			row = frappe.db.get_value("Shipment", ship, ["status", "current_milestone"], as_dict=True)
			self.assertEqual(row.current_milestone, "Vessel Departed")
			self.assertEqual(row.status, "In Transit")

		# notifications resolved once per tagged customer (send may be Skipped/
		# Failed on sites without email/SMS configured — resolution must be logged)
		from bwm_logistics.notifications import dispatch_for_event

		dispatch_for_event(event.name)
		logs = frappe.get_all(
			"Notification Log Entry", filters={"tracking_event": event.name}, fields=["customer"]
		)
		self.assertEqual({l.customer for l in logs}, {c1, c2})

		# shipment-specific event does not touch the sibling
		frappe.get_doc(
			{
				"doctype": "Tracking Event",
				"shipment": s1.name,
				"milestone": "Out for Delivery",
				"notify": 0,
			}
		).insert(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("Shipment", s1.name, "current_milestone"), "Out for Delivery")
		self.assertEqual(frappe.db.get_value("Shipment", s2.name, "current_milestone"), "Vessel Departed")

		# merged timeline: own + container events, no sibling leakage
		from bwm_logistics.api.shipments import get_timeline

		self.assertEqual(len(get_timeline(s1.name)), 2)
		self.assertEqual(len(get_timeline(s2.name)), 1)

	def test_guest_tracking_has_no_pii(self):
		container = frappe.get_doc(
			{"doctype": "Container", "direction": "Import", "container_no": "TSTU3054383"}
		).insert(ignore_permissions=True)
		customer = _make_customer("Test PII Customer")
		ship = frappe.get_doc(
			{
				"doctype": "Shipment",
				"customer": customer,
				"direction": "Import",
				"container": container.name,
				"consignee_name": "Secret Receiver",
				"packages": [{"description": "Box", "qty": 1}],
			}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "Tracking Event",
				"container": container.name,
				"milestone": "Arrived at Port",
				"notify": 0,
			}
		).insert(ignore_permissions=True)

		from bwm_logistics.api.track import track

		frappe.set_user("Guest")
		try:
			result = track(ship.name)
		finally:
			frappe.set_user("Administrator")

		self.assertTrue(result["found"])
		self.assertEqual(result["current_milestone"], "Arrived at Port")
		flat = frappe.as_json(result)
		self.assertNotIn("Secret Receiver", flat)
		self.assertNotIn(customer, flat)

	def test_invalid_container_no_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{"doctype": "Container", "direction": "Import", "container_no": "NOT-A-NUMBER"}
			).insert(ignore_permissions=True)


class TestAccess(IntegrationTestCase):
	def test_role_page_maps(self):
		from bwm_logistics.api import access

		ops_pages = access.ROLE_PAGES["Logistics Operations"]
		self.assertIn("containers", ops_pages)
		self.assertNotIn("settings", ops_pages)
		self.assertEqual(access.ROLE_PAGES["Logistics Customer"], access.PORTAL_KEYS)


class TestDispatchFlow(IntegrationTestCase):
	"""Pickup request → run with hydrated stops → start → POD complete →
	pickup completed → finish. (COD→Payment Entry needs accounting setup and
	is covered by p2_verify on a configured site, not in CI.)"""

	def setUp(self):
		frappe.set_user("Administrator")
		from bwm_logistics.install import after_install

		after_install()

	def _driver(self, email="test-driver@bwm.test", name="Test Driver"):
		from bwm_logistics.api.dispatch import save_driver

		return save_driver({"full_name": name, "email": email})

	def test_run_lifecycle_with_pod(self):
		customer = _make_customer("Dispatch Test Customer")
		ship = frappe.get_doc(
			{
				"doctype": "Shipment",
				"customer": customer,
				"direction": "Import",
				"consignee_name": "Receiver X",
				"delivery_address": "Test Street 5",
				"packages": [{"description": "Box", "qty": 1}],
			}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{"doctype": "Tracking Event", "shipment": ship.name, "milestone": "Ready for Delivery", "notify": 0}
		).insert(ignore_permissions=True)

		pickup = frappe.get_doc(
			{
				"doctype": "Pickup Request",
				"customer": customer,
				"pickup_address": "Pickup Lane 1",
				"source": "Portal",
			}
		).insert(ignore_permissions=True)

		driver = self._driver()
		from bwm_logistics.api import dispatch as dapi

		run_name = dapi.save_run(
			{
				"driver": driver["name"],
				"run_date": frappe.utils.nowdate(),
				"stops": [
					{"stop_type": "Delivery", "shipment": ship.name},
					{"stop_type": "Pickup", "pickup_request": pickup.name},
				],
			}
		)["name"]

		run = frappe.get_doc("Delivery Run", run_name)
		dstop = next(s for s in run.stops if s.stop_type == "Delivery")
		pstop = next(s for s in run.stops if s.stop_type == "Pickup")
		# hydration
		self.assertEqual(dstop.address, "Test Street 5")
		self.assertEqual(pstop.address, "Pickup Lane 1")
		self.assertEqual(
			frappe.db.get_value("Pickup Request", pickup.name, "status"), "Scheduled"
		)

		dapi.start_run(run_name)
		self.assertEqual(
			frappe.db.get_value("Shipment", ship.name, "current_milestone"), "Out for Delivery"
		)

		dapi.stop_arrived(run_name, dstop.name)
		dapi.stop_complete(run_name, dstop.name, receiver="Receiver X", cod_collected=0)
		dapi.stop_complete(run_name, pstop.name, receiver="Warehouse")
		self.assertEqual(dapi.finish_run(run_name)["status"], "Completed")

		self.assertEqual(frappe.db.get_value("Shipment", ship.name, "status"), "Delivered")
		self.assertEqual(
			frappe.db.get_value("Pickup Request", pickup.name, "status"), "Completed"
		)
		run.reload()
		self.assertEqual(run.completed_stops, 2)
		self.assertEqual(dstop.name and run.stops[0].pod_receiver, "Receiver X")

	def test_driver_scoping(self):
		driver_a = self._driver()
		self._driver(email="test-driver-b@bwm.test", name="Test Driver B")
		customer = _make_customer("Dispatch Scope Customer")
		ship = frappe.get_doc(
			{
				"doctype": "Shipment",
				"customer": customer,
				"direction": "Import",
				"packages": [{"description": "Box", "qty": 1}],
			}
		).insert(ignore_permissions=True)

		from bwm_logistics.api import dispatch as dapi

		run_name = dapi.save_run(
			{
				"driver": driver_a["name"],
				"run_date": frappe.utils.nowdate(),
				"stops": [{"stop_type": "Delivery", "shipment": ship.name}],
			}
		)["name"]

		# driver B must not act on driver A's run
		frappe.set_user("test-driver-b@bwm.test")
		try:
			with self.assertRaises(frappe.PermissionError):
				dapi.start_run(run_name)
			self.assertEqual(dapi.list_runs()["rows"], [])
		finally:
			frappe.set_user("Administrator")
