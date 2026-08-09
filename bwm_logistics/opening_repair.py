# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Bring a deployed site fully onto Model B, whatever state it came from.

The client's site takes its data from one place — the opening spreadsheet
frozen into `data/jm_containers_opening.json` — but *when* a server was first
built decides what shape that data landed in:

  * installed before Model B → goods sit in the retired `Shipment.packages`
  * installed mid-way        → goods moved, but the catalogue was misclassified
  * installed fresh          → correct, unless the import hit an unset-up site
  * never imported at all    → the import failed and only wrote an Error Log

This is the sweep that guarantees the end state, so a deploy does not depend on
which commit the server happened to be sitting on.

**It is wired to `after_migrate`, not only to a patch, and that is deliberate.**
`frappe.installer.install_app()` calls `set_all_patches_as_completed()` *before*
`after_install` runs, so on a freshly installed site every patch is recorded as
done without executing. A patch alone therefore cannot heal a new server — the
one deployment that most needs healing. Running from the migrate hook means the
repair happens on the first `bench migrate` either way, and costs a handful of
counts once the site is healthy.

Four things it repairs, all idempotent:

1. **The Item classification field, created here rather than waited for.**
   `install.ensure_item_fields()` runs on `after_migrate`, which is *after*
   patches — so every catalogue Item created by an import or by
   move_packages_to_containers was written while `bwm_trade_direction` did not
   exist yet, and fell back to the column default "Both". The effect is quiet
   and wrong: an export container is offered import-only goods, which is the
   one thing that field exists to prevent.
2. **Missing opening data.** import_client_opening_data deliberately swallows a
   failed load so a data problem can never block an app upgrade. That leaves a
   site up with no stock and only an Error Log to say so. If the frozen file
   holds containers this site doesn't have, they are loaded now.
3. **Containers with no manifest**, rebuilt from the frozen file — the case
   where a site imported after the shipment stopped carrying packages but
   before the container started carrying contents.
4. **Shipments still pointing at a box through the old single link**, adopted
   into the `containers` table, then every total re-derived from the manifest.

It repairs; it never deletes. If you would rather start the site from nothing,
that is a deliberate, separate act:

    bench --site <site> execute bwm_logistics.reset_demo_data.run
    bench --site <site> execute bwm_logistics.import_jm_excel.load_opening
"""

import frappe

from bwm_logistics.bwm_logistics.doctype.shipment.shipment import refresh_stored_totals

# Doctypes whose existence means somebody has actually worked on this site.
# Finding any is not an error — it only means "repair, and say so loudly",
# because the assumption behind a deploy sweep is that there was nothing to lose.
ACTIVITY = ("Sales Invoice", "Purchase Invoice", "Payment Entry", "Delivery Run", "Pickup Request")


def run():
	"""Idempotent. Safe to run by hand at any time:

	    bench --site <site> execute bwm_logistics.opening_repair.run
	"""
	if not frappe.db.exists("DocType", "Container Content"):
		return

	frappe.flags.mute_emails = True
	report: list[str] = []

	_ensure_item_field(report)

	# Anything touching the catalogue needs ERPNext's Item Group tree and UOMs,
	# which the setup wizard creates. Until then there is nothing to normalise —
	# say so plainly and let the next migrate (or the manual re-run) finish it.
	from bwm_logistics.api.items import catalogue_blocker

	blocker = catalogue_blocker()
	if blocker:
		# Nothing lost: this runs again on the next migrate, and by then the
		# wizard will have built the tree it needs.
		print(f"Opening-data repair deferred — {blocker}. It will retry on the next migrate.")
		return

	data = _opening_data()
	if data:
		_load_missing_containers(data, report)
		_rebuild_empty_manifests(data, report)
	_adopt_single_container_links(report)
	_classify_items_from_their_boxes(report)

	changed = refresh_stored_totals(frappe.get_all("Shipment", pluck="name", limit_page_length=0))
	if changed:
		report.append(f"re-derived totals on {changed} shipment(s)")

	# Only speak up when something was actually changed. A healthy site migrates
	# in silence; a repaired one says what it did, and whether it found more
	# than an import sitting there when it did it.
	if report:
		_note_existing_activity(report)
		frappe.db.commit()
		print("Opening-data repair: " + "; ".join(report))
	return report


# ── 1. the classification field ──────────────────────────────────────────────
def _ensure_item_field(report: list[str]):
	"""Create bwm_trade_direction now, so anything below can set it."""
	from bwm_logistics.install import ensure_item_fields

	existed = frappe.db.has_column("Item", "bwm_trade_direction")
	ensure_item_fields()
	if not existed:
		report.append("created Item.bwm_trade_direction")


# ── 2 & 3. the opening data ──────────────────────────────────────────────────
def _opening_data() -> dict | None:
	import json
	import os

	from bwm_logistics.import_jm_excel import opening_data_path

	path = opening_data_path()
	if not os.path.exists(path):
		return None
	with open(path) as f:
		return json.load(f)


def _existing_container(row: dict) -> str | None:
	return frappe.db.get_value(
		"Container", {"container_no": row.get("container_no"), "bl_no": row.get("bl_no")}, "name"
	)


def _load_missing_containers(data: dict, report: list[str]):
	"""Run the import when the frozen file holds boxes this site has never seen.

	load() skips whatever already exists, so this is a no-op on a site that
	imported cleanly — and the repair for one where the import failed and was
	only written to the Error Log.
	"""
	missing = [row for row in data.get("containers") or [] if not _existing_container(row)]
	if not missing:
		return

	from bwm_logistics.import_jm_excel import load

	try:
		created = load(data)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="Opening data repair failed", message=frappe.get_traceback())
		report.append(f"WARNING: {len(missing)} container(s) still missing — see the Error Log")
		return
	report.append(
		f"imported {created.get('containers', 0)} container(s), "
		f"{created.get('shipments', 0)} shipment(s), {created.get('distributions', 0)} distribution(s)"
	)


def _rebuild_empty_manifests(data: dict, report: list[str]):
	"""Put the goods back on a box that came through with none."""
	from bwm_logistics.api.items import ensure_item

	rebuilt = 0
	for row in data.get("containers") or []:
		name = _existing_container(row)
		if not name or not row.get("packages"):
			continue
		box = frappe.get_doc("Container", name)
		if box.contents:
			continue  # already carries its manifest — leave it alone

		for pkg in row["packages"]:
			box.append(
				"contents",
				{
					"item": ensure_item(pkg.get("description"), box.direction),
					"description": pkg.get("description"),
					"qty": pkg.get("qty") or 0,
					"unit": pkg.get("unit") or "Nos",
					"weight_kg": pkg.get("weight_kg"),
					"declared_value": pkg.get("declared_value"),
				},
			)
		box.flags.ignore_permissions = True
		box.save(ignore_permissions=True)
		rebuilt += 1

	if rebuilt:
		report.append(f"rebuilt the manifest on {rebuilt} container(s)")


# ── 4. shipments and their boxes ─────────────────────────────────────────────
def _adopt_single_container_links(report: list[str]):
	"""A booking that names its box only through the legacy single link gets a
	row in the `containers` table — sync_containers() does the rest."""
	adopted = 0
	for ship in frappe.get_all(
		"Shipment", filters={"container": ("is", "set")}, fields=["name", "container"], limit_page_length=0
	):
		if frappe.db.exists("Shipment Container", {"parent": ship.name, "container": ship.container}):
			continue
		try:
			doc = frappe.get_doc("Shipment", ship.name)
			doc.append("containers", {"container": ship.container})
			doc.flags.ignore_permissions = True
			doc.flags.ignore_validate_update_after_submit = True
			doc.save(ignore_permissions=True)
			adopted += 1
		except Exception:
			# One unhappy legacy row must not abandon the rest of the sweep.
			frappe.db.rollback()
			frappe.log_error(
				title=f"Could not link {ship.name} to its container", message=frappe.get_traceback()
			)

	if adopted:
		report.append(f"linked {adopted} shipment(s) to their box")


# ── 5. the catalogue ─────────────────────────────────────────────────────────
def _classify_items_from_their_boxes(report: list[str]):
	"""Set an item's trade direction from the containers that actually carry it.

	Only touches items still sitting on the "Both" fallback, and only when the
	evidence is unanimous — an item seen in both an import and an export box
	genuinely is Both, and an explicit Import/Export somebody chose is never
	overwritten.
	"""
	from bwm_logistics.api.items import ITEM_GROUP

	directions: dict[str, set] = {}
	for row in frappe.db.sql(
		"""select cc.item, c.direction
		   from `tabContainer Content` cc join `tabContainer` c on c.name = cc.parent
		   where cc.item is not null and cc.item != ''""",
		as_dict=True,
	):
		directions.setdefault(row.item, set()).add(row.direction)

	fixed = 0
	for item, seen in directions.items():
		seen = {d for d in seen if d in ("Import", "Export")}
		if len(seen) != 1:
			continue
		current = frappe.db.get_value("Item", item, ["bwm_trade_direction", "item_group"], as_dict=True)
		if not current or current.item_group != ITEM_GROUP:
			continue
		if current.bwm_trade_direction not in (None, "", "Both"):
			continue  # somebody chose this deliberately
		frappe.db.set_value("Item", item, "bwm_trade_direction", seen.pop(), update_modified=False)
		fixed += 1

	if fixed:
		report.append(f"classified {fixed} catalogue item(s) by the boxes carrying them")


# ── reporting ────────────────────────────────────────────────────────────────
def _note_existing_activity(report: list[str]):
	"""Say so if this site had more than an import on it. Nothing was deleted
	either way — this is here so a surprise shows up in the deploy log."""
	found = {dt: frappe.db.count(dt) for dt in ACTIVITY if frappe.db.exists("DocType", dt)}
	busy = {dt: n for dt, n in found.items() if n}
	if busy:
		report.append("site already had " + ", ".join(f"{n} {dt}" for dt, n in busy.items()))
