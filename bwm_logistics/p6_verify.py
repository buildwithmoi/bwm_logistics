# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""P6 backend smoke verification — run with:

    bench --site local16.6 execute bwm_logistics.p6_verify.run

Covers the admin-managed role structure: seeded roles, staff creation with
role assignment, page resolution per role, Frappe-gate syncing (billing pages
unlock the Accounts APIs), role editing rippling to members, and the expanded
reports sections.
"""

import frappe

results = []


def check(label, ok, detail=""):
	results.append(f"{'PASS' if ok else 'FAIL'}  {label}" + (f" — {detail}" if detail else ""))
	return ok


def run():
	results.clear()
	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True
	from bwm_logistics.install import after_install

	after_install()
	from bwm_logistics.api import access, staff

	# ── seeded roles ─────────────────────────────────────────────────────────
	catalog = staff.list_roles()
	names = {r["role_name"] for r in catalog["roles"]}
	check("default roles seeded", {"Admin", "Manager", "Operations", "Accounts"} <= names, str(sorted(names)))

	# ── custom role + staff member ───────────────────────────────────────────
	staff.save_role(
		{"role_name": "Front Desk", "pages": ["dashboard", "shipments", "customers", "scan"]}
	)
	user_email = "frontdesk@bwm-demo.test"
	staff.create_staff("Efua FrontDesk", user_email, logistics_role="Front Desk")

	perms = access.user_perms(user_email)
	check(
		"role pages resolve exactly",
		set(perms) == {"dashboard", "shipments", "customers", "scan"},
		str(sorted(perms)),
	)
	froles = set(frappe.get_roles(user_email))
	check(
		"frappe gates synced (ops yes, accounts no)",
		"Logistics Operations" in froles and "Logistics Accounts" not in froles,
		str(sorted(froles & {"Logistics Operations", "Logistics Accounts", "Logistics Manager"})),
	)

	# ── role edit ripples to members ─────────────────────────────────────────
	staff.save_role(
		{"role_name": "Front Desk", "pages": ["dashboard", "shipments", "customers", "scan", "billing"]}
	)
	perms2 = access.user_perms(user_email)
	froles2 = set(frappe.get_roles(user_email))
	check(
		"adding billing page unlocks Accounts gate",
		"billing" in perms2 and "Logistics Accounts" in froles2,
		str(sorted(froles2 & {"Logistics Accounts"})),
	)

	# ── admin role gets settings + manager gate ──────────────────────────────
	staff.assign_role(user_email, "Admin")
	perms3 = access.user_perms(user_email)
	froles3 = set(frappe.get_roles(user_email))
	check(
		"admin role → settings page + Manager gate",
		"settings" in perms3 and "Logistics Manager" in froles3,
		f"{len(perms3)} pages",
	)

	# back to Front Desk for future runs’ determinism
	staff.assign_role(user_email, "Front Desk")

	# ── legacy fallback (users without an app role keep working) ─────────────
	ops_perms = access.user_perms("ops@bwm-demo.test")
	check(
		"fallback: staff w/o app role use static map",
		"containers" in ops_perms and "settings" not in ops_perms,
		f"{len(ops_perms)} pages",
	)

	# ── non-manager blocked from role management ─────────────────────────────
	frappe.set_user(user_email)
	try:
		staff.save_role({"role_name": "Sneaky", "pages": ["settings"]})
		blocked = False
	except frappe.PermissionError:
		blocked = True
	finally:
		frappe.set_user("Administrator")
	check("non-manager blocked from role management", blocked)

	# ── reports sections ─────────────────────────────────────────────────────
	frappe.set_user("ops@bwm-demo.test")
	from bwm_logistics.api.reports import get_reports

	rep = get_reports(months=6)
	frappe.set_user("Administrator")
	check(
		"reports sections present",
		all(k in rep for k in ("months", "shipment_months", "containers", "deliveries", "messaging")),
		f"messaging total={rep['messaging']['total']}, deliveries runs={rep['deliveries']['runs_total']}",
	)

	frappe.db.commit()
	print("\n".join(results))
	failed = len([r for r in results if r.startswith("FAIL")])
	print(f"\n{len(results) - failed}/{len(results)} checks passed")
	return {"passed": len(results) - failed, "failed": failed}
