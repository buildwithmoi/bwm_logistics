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


class TestCarrierTracking(IntegrationTestCase):
	"""Inbound webhook + tracking-data application (dedupe, ETA updates)."""

	def setUp(self):
		frappe.set_user("Administrator")
		from bwm_logistics.install import after_install

		after_install()

	def _container(self, no="TSTU3054383"):
		return frappe.get_doc(
			{"doctype": "Container", "direction": "Import", "container_no": no}
		).insert(ignore_permissions=True)

	def test_apply_tracking_data_dedupes_and_updates_eta(self):
		from bwm_logistics.carrier_tracking import apply_tracking_data

		container = self._container()
		data = {
			"events": [
				{"milestone": "Vessel Departed", "event_datetime": frappe.utils.now_datetime()},
				{"milestone": "Vessel Departed", "event_datetime": frappe.utils.now_datetime()},
			],
			"eta": frappe.utils.add_days(frappe.utils.nowdate(), 10),
		}
		first = apply_tracking_data(container, data)
		self.assertEqual(first["new_events"], 1)
		self.assertIn("eta", first["updated"])
		# Second pass with the same payload — nothing new.
		container.reload()
		second = apply_tracking_data(container, data)
		self.assertEqual(second["new_events"], 0)
		self.assertEqual(
			frappe.db.get_value("Container", container.name, "current_milestone"), "Vessel Departed"
		)

	def test_webhook_requires_token(self):
		from bwm_logistics.api.carrier_webhook import receive

		settings = frappe.get_doc("Logistics Settings")
		settings.save()  # ensures a webhook token exists
		container = self._container()

		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.PermissionError):
				receive(token="wrong", container_no=container.container_no, event="Arrived at Port")
			result = receive(
				token=frappe.db.get_single_value("Logistics Settings", "tracking_webhook_token"),
				container_no=container.container_no,
				event="Arrived at Port",
				location="Tema",
			)
		finally:
			frappe.set_user("Administrator")
		self.assertTrue(result["ok"])
		self.assertEqual(result["new_events"], 1)


class TestRateCards(IntegrationTestCase):
	"""Charge computation from package totals (FR-PAY-1). CI-safe — no
	invoices/accounting involved."""

	def test_compute_and_apply(self):
		frappe.set_user("Administrator")
		from bwm_logistics.install import after_install

		after_install()
		card = frappe.get_doc(
			{
				"doctype": "Rate Card",
				"card_name": "CI Test Rates",
				"items": [
					{"charge_type": "Freight", "calc_basis": "Per KG", "rate": 5, "minimum": 100},
					{"charge_type": "Handling", "calc_basis": "Per Package", "rate": 20},
					{"charge_type": "Docs", "calc_basis": "Flat", "rate": 50},
				],
			}
		).insert(ignore_permissions=True)

		customer = _make_customer("Rate Card Customer")
		ship = frappe.get_doc(
			{
				"doctype": "Shipment",
				"customer": customer,
				"direction": "Import",
				"packages": [
					{"description": "Barrel", "qty": 2, "weight_kg": 40},
					{"description": "Box", "qty": 1, "weight_kg": 10},
				],
			}
		).insert(ignore_permissions=True)

		charges = card.compute_charges(ship)
		by_type = {c["charge_type"]: c["amount"] for c in charges}
		self.assertEqual(by_type["Freight"], 450)  # 90 kg × 5
		self.assertEqual(by_type["Handling"], 60)  # 3 pkg × 20
		self.assertEqual(by_type["Docs"], 50)

		from bwm_logistics.api.shipments import apply_rate_card

		result = apply_rate_card(ship.name, card.name)
		self.assertEqual(result["total_charges"], 560)

		# minimum enforced on a light shipment
		light = frappe.get_doc(
			{
				"doctype": "Shipment",
				"customer": customer,
				"direction": "Import",
				"packages": [{"description": "Envelope", "qty": 1, "weight_kg": 2}],
			}
		).insert(ignore_permissions=True)
		light_charges = {c["charge_type"]: c["amount"] for c in card.compute_charges(light)}
		self.assertEqual(light_charges["Freight"], 100)


class TestLogisticsRoles(IntegrationTestCase):
	"""Admin-managed role resolution (CI-safe)."""

	def setUp(self):
		frappe.set_user("Administrator")
		from bwm_logistics.install import after_install

		after_install()

	def test_role_resolution_and_gate_sync(self):
		import json

		from bwm_logistics.api import access, staff

		frappe.get_doc(
			{
				"doctype": "Logistics Role",
				"role_name": "CI Test Role",
				"pages": json.dumps(["dashboard", "shipments"]),
			}
		).insert(ignore_permissions=True)

		email = "ci-role-user@bwm.test"
		if not frappe.db.exists("User", email):
			user = frappe.new_doc("User")
			user.email = email
			user.first_name = "CI"
			user.user_type = "Website User"
			user.send_welcome_email = 0
			user.insert(ignore_permissions=True)
		staff.assign_role(email, "CI Test Role")

		perms = access.user_perms(email)
		self.assertEqual(set(perms), {"dashboard", "shipments"})
		self.assertIn("Logistics Operations", frappe.get_roles(email))
		self.assertNotIn("Logistics Accounts", frappe.get_roles(email))

		# billing page unlocks the Accounts gate
		staff.save_role({"role_name": "CI Test Role", "pages": ["dashboard", "shipments", "billing"]})
		self.assertIn("Logistics Accounts", frappe.get_roles(email))
		self.assertIn("billing", access.user_perms(email))

	def test_settings_never_leaks_to_non_admin_role(self):
		import json

		from bwm_logistics.api import access, staff

		# Even if someone force-writes settings into the JSON, validate strips it.
		doc = frappe.get_doc(
			{
				"doctype": "Logistics Role",
				"role_name": "CI Sneaky Role",
				"pages": json.dumps(["settings", "dashboard"]),
			}
		).insert(ignore_permissions=True)
		self.assertNotIn("settings", doc.page_keys())


class TestReportsAndBranches(IntegrationTestCase):
	"""CI-safe P5 checks — no accounting involved."""

	def setUp(self):
		frappe.set_user("Administrator")
		from bwm_logistics.install import after_install

		after_install()

	def test_reports_shape_without_invoices(self):
		customer = _make_customer("Reports Customer")
		frappe.get_doc(
			{
				"doctype": "Shipment",
				"customer": customer,
				"direction": "Import",
				"packages": [{"description": "Box", "qty": 1}],
				"charges": [{"charge_type": "Freight", "amount": 75}],
			}
		).insert(ignore_permissions=True)

		from bwm_logistics.api.reports import get_reports

		rep = get_reports(months=6)
		self.assertEqual(len(rep["months"]), 6)
		self.assertTrue(any(c["customer"] == "Reports Customer" for c in rep["top_customers"]))
		self.assertTrue(any(s["status"] == "Open" for s in rep["status_breakdown"]))

	def test_branch_filtering(self):
		if not frappe.db.exists("Branch", "Test Branch A"):
			frappe.get_doc({"doctype": "Branch", "branch": "Test Branch A"}).insert(ignore_permissions=True)
		customer = _make_customer("Branch Customer")
		ship = frappe.get_doc(
			{
				"doctype": "Shipment",
				"customer": customer,
				"direction": "Import",
				"branch": "Test Branch A",
				"packages": [{"description": "Box", "qty": 1}],
			}
		).insert(ignore_permissions=True)

		from bwm_logistics.api.shipments import list_shipments

		scoped = [r.name for r in list_shipments(branch="Test Branch A")["rows"]]
		self.assertIn(ship.name, scoped)

	def test_statement_empty_customer(self):
		from bwm_logistics.api.billing import build_statement

		customer = _make_customer("Empty Statement Customer")
		stmt = build_statement(customer, "2026-01-01", "2026-01-31")
		self.assertEqual(stmt["opening_balance"], 0)
		self.assertEqual(stmt["rows"], [])
		self.assertEqual(stmt["closing_balance"], 0)


class TestDemurrageAlerts(IntegrationTestCase):
	def test_at_risk_and_digest(self):
		frappe.set_user("Administrator")
		from bwm_logistics import alerts

		frappe.get_doc(
			{
				"doctype": "Container",
				"direction": "Import",
				"container_no": "TSTU3054383",
				"demurrage_start_date": frappe.utils.add_days(frappe.utils.nowdate(), 1),
			}
		).insert(ignore_permissions=True)

		risky = alerts.at_risk_containers()
		self.assertTrue(any(r.days_left <= alerts.RISK_WINDOW_DAYS for r in risky))

		alerts.demurrage_check()
		logs = frappe.get_all(
			"Notification Log Entry",
			filters={"milestone": "Demurrage Alert"},
			fields=["status", "subject"],
		)
		self.assertTrue(logs, "digest not logged")
		# Second call the same day must not double-send.
		before = len(logs)
		alerts.demurrage_check()
		after = frappe.db.count("Notification Log Entry", {"milestone": "Demurrage Alert"})
		self.assertEqual(after, before)
