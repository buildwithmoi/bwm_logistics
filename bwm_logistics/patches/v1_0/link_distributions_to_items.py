# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Point existing distribution entries at the catalogue Item they meant.

The ledger recorded its product as free text, matched back to the manifest by
comparing lowercased names. That was the last string join left in the system —
and it meant renaming a manifest line silently detached every entry recorded
against it: the goods stayed gone from the yard, but the balance reported
nothing had left.

Each entry is matched against its own shipment's manifest, by exact name first
and then by the containment rule the opening import used (their sheet shortens
names: "Hen Leg Quarter" for "US Hen Leg Quarter"). An entry that matches
nothing is left alone with its name — `line_key()` still keys those on the name
they were written with, so nothing breaks; they just don't gain the protection.
"""

import frappe

from bwm_logistics.bwm_logistics.doctype.shipment.shipment import manifests_for


def _norm(text) -> str:
	return (text or "").strip().lower()


def execute():
	if not frappe.db.has_column("Distribution Entry", "item"):
		return

	rows = frappe.get_all(
		"Distribution Entry",
		filters={"item": ("is", "not set")},
		fields=["name", "shipment", "product"],
		limit_page_length=0,
	)
	if not rows:
		return

	manifests = manifests_for(sorted({r.shipment for r in rows if r.shipment}))
	linked, unmatched = 0, []
	for row in rows:
		lines = manifests.get(row.shipment) or []
		wanted = _norm(row.product)
		hit = next((line for line in lines if _norm(line["description"]) == wanted), None)
		if not hit:
			hit = next((line for line in lines if wanted and wanted in _norm(line["description"])), None)
		if not hit or not hit.get("item"):
			unmatched.append(f"{row.name} ({row.product})")
			continue
		frappe.db.set_value("Distribution Entry", row.name, "item", hit["item"], update_modified=False)
		linked += 1

	frappe.db.commit()
	print(f"Linked {linked} distribution entr(ies) to their catalogue item")
	if unmatched:
		print(
			f"  {len(unmatched)} still matched by name only (no manifest line to point at): "
			+ ", ".join(unmatched[:10])
			+ ("…" if len(unmatched) > 10 else "")
		)
