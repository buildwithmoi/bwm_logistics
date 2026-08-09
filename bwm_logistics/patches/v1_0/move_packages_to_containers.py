# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Move the manifest from the shipment onto the box that carries it.

Packages used to hang off the Shipment, which only worked while a shipment was
exactly one container. A booking routinely spans several boxes, and a
consolidated box carries several customers — neither is expressible that way.
So contents now live on the Container, each line tagged with whose goods they
are, and a shipment lists the containers it rides in.

This patch is the one-way move of existing data:

  Shipment.packages  ->  Container.contents  (customer = the shipment's customer)
  Shipment.container ->  Shipment.containers[0]

`Shipment.packages` is deliberately **not** deleted. It stays in the doctype and
in the database, unread by the UI, so a mistake here is recoverable and nobody
loses a manifest to a migration. Re-running is safe: a container that already
has contents is left alone.
"""

import frappe

from bwm_logistics.api.items import ITEM_GROUP, _ensure_group, ensure_item


def execute():
	if not frappe.db.exists("DocType", "Container Content"):
		return

	_ensure_group()
	moved = {"contents": 0, "containers": 0, "items": 0}

	for ship in frappe.get_all(
		"Shipment",
		fields=["name", "customer", "container", "shipment_type"],
		limit_page_length=0,
	):
		if not ship.container:
			continue  # loose cargo: nothing to move it onto

		# 1. The manifest, onto the box. This has to happen BEFORE the shipment
		#    is linked to it: saving the shipment runs check_distribution_products(),
		#    which resolves the manifest through its containers — and a booking
		#    that already has distributions recorded would fail that check while
		#    the box is still empty, killing the migrate.
		#    Own goods carry no customer tag: they are ours.
		customer = None if ship.shipment_type == "Own Goods (Trading)" else ship.customer
		packages = frappe.get_all(
			"Shipment Package",
			filters={"parenttype": "Shipment", "parent": ship.name},
			fields=["description", "qty", "unit", "weight_kg", "declared_value"],
			order_by="idx",
		)
		container = frappe.get_doc("Container", ship.container)
		if packages and not container.contents:
			for pkg in packages:
				before = frappe.db.count("Item", {"item_group": ITEM_GROUP})
				item = ensure_item(pkg.description, container.direction)
				if item and frappe.db.count("Item", {"item_group": ITEM_GROUP}) > before:
					moved["items"] += 1
				container.append(
					"contents",
					{
						"item": item,
						"description": pkg.description,
						"qty": pkg.qty or 0,
						"unit": pkg.unit or "Nos",
						"customer": customer,
						"weight_kg": pkg.weight_kg,
						"declared_value": pkg.declared_value,
					},
				)
				moved["contents"] += 1
			container.flags.ignore_permissions = True
			container.save(ignore_permissions=True)

		# 2. Now the container list: adopt the single link as the first row.
		if not frappe.db.exists("Shipment Container", {"parent": ship.name, "container": ship.container}):
			doc = frappe.get_doc("Shipment", ship.name)
			doc.append("containers", {"container": ship.container})
			doc.flags.ignore_permissions = True
			doc.flags.ignore_validate_update_after_submit = True
			doc.save(ignore_permissions=True)
			moved["containers"] += 1

	frappe.db.commit()
	print(
		f"Moved {moved['contents']} package line(s) onto containers, "
		f"linked {moved['containers']} shipment(s) to their box, "
		f"created {moved['items']} catalogue item(s)"
	)


