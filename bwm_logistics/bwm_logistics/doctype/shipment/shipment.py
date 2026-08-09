# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import make_autoname

# Shipment milestones that flip status (shipment- or container-level).
# "Delayed" is deliberately absent: it marks current_milestone (red chip in
# the UI) without disturbing the logistics status.
MILESTONE_STATUS = {
	"Vessel Departed": "In Transit",
	"In Transit": "In Transit",
	"Arrived at Port": "Arrived",
	"Arrived at Destination": "Arrived",
	"Offloaded": "Arrived",
	"Ready for Delivery": "Ready for Delivery",
	"Out for Delivery": "Ready for Delivery",
	"Delivered": "Delivered",
}

TRADING = "Own Goods (Trading)"

MANIFEST_FIELDS = [
	"parent",
	"idx",
	"item",
	"description",
	"qty",
	"unit",
	"weight_kg",
	"declared_value",
	"customer",
	"customer_name",
]


# ─── The manifest ────────────────────────────────────────────────────────────
# Model B keeps the packing list on the box, not the booking. So "what is this
# shipment carrying" is a question about its containers, narrowed to whose
# booking it is — and these three functions are the only place that answers it.
# Totals, stock balances, the distribution guard and the portal all come
# through here, which is what stops them drifting apart the way they did while
# each read `Shipment.packages` for itself.


def manifest_lines(containers: list[str], customer: str | None = None) -> list[dict]:
	"""The goods one party has inside the given boxes.

	`customer=None` means ours — the untagged lines. Pass a customer and you
	get theirs and nobody else's, which is the whole reason the tag exists:
	billing one customer out of a consolidated box is this same call with a
	different argument, and the portal is this call with the session's customer.
	"""
	containers = [c for c in containers if c]
	if not containers:
		return []

	filters = {"parenttype": "Container", "parent": ("in", containers)}
	# An untagged line is ours. "" and NULL both occur — a Link cleared in the
	# UI stores "", one never set stores NULL — so match on unset, not on "".
	filters["customer"] = customer if customer else ("is", "not set")

	rows = frappe.get_all(
		"Container Content", filters=filters, fields=MANIFEST_FIELDS, order_by="parent asc, idx asc"
	)
	numbers = dict(
		frappe.get_all(
			"Container",
			filters={"name": ("in", containers)},
			fields=["name", "container_no"],
			as_list=True,
		)
	)
	# Hold the order the shipment lists its boxes in, not alphabetical name order.
	position = {name: i for i, name in enumerate(containers)}
	rows.sort(key=lambda r: (position.get(r.parent, 0), r.idx or 0))
	for row in rows:
		row["container"] = row.parent
		row["container_no"] = numbers.get(row.parent)
		row["description"] = row.description or row.item
	return rows


def shipment_boxes(shipment: str) -> list[str]:
	"""The containers a booking rides in, in the order they were added."""
	return frappe.get_all(
		"Shipment Container",
		filters={"parenttype": "Shipment", "parent": shipment},
		pluck="container",
		order_by="idx asc",
	)


def shipment_manifest(shipment: str) -> list[dict]:
	"""What one booking is carrying, resolved from its boxes."""
	info = frappe.db.get_value("Shipment", shipment, ["shipment_type", "customer"], as_dict=True)
	if not info:
		return []
	owner = None if (info.shipment_type or "Customer Cargo") == TRADING else info.customer
	return manifest_lines(shipment_boxes(shipment), owner)


def manifests_for(shipments: list[str]) -> dict[str, list[dict]]:
	"""Every booking's manifest in a fixed number of queries.

	The Stock page asks for all trading bookings at once; resolving them one at
	a time is three queries each. Same answer as shipment_manifest(), batched.
	"""
	shipments = [s for s in shipments if s]
	if not shipments:
		return {}

	owners = {
		s.name: (None if (s.shipment_type or "Customer Cargo") == TRADING else s.customer)
		for s in frappe.get_all(
			"Shipment",
			filters={"name": ("in", shipments)},
			fields=["name", "shipment_type", "customer"],
		)
	}
	boxes: dict[str, list[str]] = {s: [] for s in shipments}
	for row in frappe.get_all(
		"Shipment Container",
		filters={"parenttype": "Shipment", "parent": ("in", shipments)},
		fields=["parent", "container"],
		order_by="parent asc, idx asc",
	):
		if row.container:
			boxes[row.parent].append(row.container)

	every_box = sorted({c for names in boxes.values() for c in names})
	if not every_box:
		return {s: [] for s in shipments}

	by_container: dict[str, list[dict]] = {c: [] for c in every_box}
	numbers = dict(
		frappe.get_all(
			"Container", filters={"name": ("in", every_box)}, fields=["name", "container_no"], as_list=True
		)
	)
	for row in frappe.get_all(
		"Container Content",
		filters={"parenttype": "Container", "parent": ("in", every_box)},
		fields=MANIFEST_FIELDS,
		order_by="parent asc, idx asc",
	):
		row["container"] = row.parent
		row["container_no"] = numbers.get(row.parent)
		row["description"] = row.description or row.item
		by_container[row.parent].append(row)

	out = {}
	for name in shipments:
		owner = owners.get(name)
		out[name] = [
			row
			for box in boxes[name]
			for row in by_container.get(box, [])
			if (row.customer or None) == (owner or None)
		]
	return out


class Shipment(Document):
	def autoname(self):
		# The document name IS the customer-facing tracking number:
		# <prefix>-000001, sequential per prefix (Logistics Settings).
		prefix = (frappe.db.get_single_value("Logistics Settings", "tracking_prefix") or "BWM").strip().upper()
		self.name = make_autoname(f"{prefix}-.######")

	def is_trading(self) -> bool:
		# NULL-safe: rows created before shipment_type existed are Customer Cargo.
		return (self.shipment_type or "Customer Cargo") == TRADING

	def manifest(self) -> list[dict]:
		"""The goods this booking carries — its boxes' lines, narrowed to whose
		booking it is. Reads the in-memory container rows so it is correct
		during validate(), before the table has been written."""
		owner = None if self.is_trading() else self.customer
		return manifest_lines([r.container for r in self.containers if r.container], owner)

	def validate(self):
		self.validate_customer()
		self.sync_containers()
		self.compute_totals()
		self.sync_direction_from_container()
		self.check_distribution_products()

	def sync_containers(self):
		"""Keep the single `container` link in step with the `containers` table.

		A booking can span several boxes, so the table is the truth. The old
		single link stays as "the primary box" because tracking events, the
		portal and every existing query still read it — this keeps both correct
		rather than rewriting all of them at once.
		"""
		rows = [r.container for r in self.containers if r.container]
		# De-duplicate but hold order: the first box listed is the primary one.
		seen: dict[str, None] = {}
		for name in rows:
			seen.setdefault(name, None)
		ordered = list(seen)
		if len(ordered) != len(self.containers):
			self.set("containers", [{"container": name} for name in ordered])

		if ordered:
			self.container = ordered[0]
		elif self.container:
			# Set the old way (or by an import): adopt it as the first row.
			self.append("containers", {"container": self.container})

	def validate_customer(self):
		if self.is_trading():
			# Own goods: no customer, and nobody external to notify.
			self.notify_customer = 0
			if not self.customer:
				self.customer_name = None
		elif not self.customer:
			frappe.throw(_("Customer is required for Customer Cargo shipments."))
		if not self.customer:
			self.customer_name = None

	def sync_direction_from_container(self):
		if self.container and not self.direction:
			self.direction = frappe.db.get_value("Container", self.container, "direction")

	def check_distribution_products(self):
		"""Distribution Entries name a product off the manifest — block
		detaching the box whose goods already have distributions recorded."""
		if self.is_new() or not frappe.db.exists("DocType", "Distribution Entry"):
			return
		products = frappe.get_all(
			"Distribution Entry", filters={"shipment": self.name}, pluck="product", distinct=True
		)
		if not products:
			return
		have = {(line["description"] or "").strip().lower() for line in self.manifest()}
		missing = sorted({p for p in products if (p or "").strip().lower() not in have})
		if missing:
			frappe.throw(
				_(
					"These goods have distributions recorded but are no longer on this shipment's containers: {0}. Put the container back, or delete those distribution entries first."
				).format(", ".join(missing))
			)

	def compute_totals(self):
		# Off the manifest, not off `packages` — that table is retired (kept
		# only so move_packages_to_containers stays reversible) and reading it
		# here is what left every new booking showing "0 packages".
		lines = self.manifest()
		self.total_packages = sum((line["qty"] or 0) for line in lines)
		self.total_weight_kg = sum((line["weight_kg"] or 0) * (line["qty"] or 1) for line in lines)
		self.total_declared_value = sum((line["declared_value"] or 0) for line in lines)
		# total_volume_cbm has no source on a container line and nothing renders
		# it — left untouched rather than zeroed over historical data.
		self.total_charges = sum((c.amount or 0) for c in self.charges)

	def apply_milestone(self, milestone: str):
		"""Called by Tracking Event after insert — keeps status fields in sync."""
		updates = {"current_milestone": milestone}
		if milestone in MILESTONE_STATUS:
			updates["status"] = MILESTONE_STATUS[milestone]
		frappe.db.set_value("Shipment", self.name, updates, update_modified=True)

	def make_sales_invoice(self):
		"""One-click Sales Invoice from this shipment's charges."""
		if not self.customer:
			frappe.throw(
				_("This trading shipment has no customer to invoice — raise sales from Billing → New invoice and record costs under Purchases instead.")
			)
		if self.sales_invoice:
			frappe.throw(_("Shipment {0} is already invoiced ({1}).").format(self.name, self.sales_invoice))
		if not self.charges:
			frappe.throw(_("Add at least one charge before invoicing."))

		item_code = _ensure_charge_item()
		invoice = frappe.new_doc("Sales Invoice")
		invoice.customer = self.customer
		# P&L revenue is counted solely via this tag (never via
		# Shipment.sales_invoice — that would double count).
		invoice.bwm_shipment = self.name
		for charge in self.charges:
			invoice.append(
				"items",
				{
					"item_code": item_code,
					"item_name": charge.charge_type,
					"description": f"{charge.charge_type} — Shipment {self.name}",
					"qty": 1,
					"rate": charge.amount,
				},
			)
		invoice.flags.ignore_permissions = True
		invoice.set_missing_values()
		invoice.insert(ignore_permissions=True)
		invoice.submit()
		frappe.db.set_value("Shipment", self.name, "sales_invoice", invoice.name)
		return invoice.name


def _ensure_charge_item() -> str:
	"""A non-stock service Item that carries shipment charge lines on Sales
	Invoices (rate is overridden per line). Created lazily, once per site."""
	code = "Logistics Charge"
	if not frappe.db.exists("Item", code):
		item = frappe.new_doc("Item")
		item.item_code = code
		item.item_name = code
		item.item_group = frappe.db.get_value("Item Group", {"is_group": 0}) or "All Item Groups"
		item.is_stock_item = 0
		item.is_sales_item = 1
		item.stock_uom = "Nos"
		item.flags.ignore_permissions = True
		item.insert(ignore_permissions=True)
	return code
