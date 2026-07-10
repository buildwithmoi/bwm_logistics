# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""P0 smoke verification — run with:

    bench --site local16.6 execute bwm_logistics.p0_verify.run

Checks the P0 exit criteria end-to-end without a browser:
  1. Logistics roles exist (install.py).
  2. Demo users exist (created idempotently): an operations staff user and a
     portal customer (with linked Customer + Contact) — handy for manual login
     tests too. Passwords: see DEMO_PASSWORD below (dev-only).
  3. access.user_perms + login_destinations route each persona correctly.
  4. The public landing (/home) and SPA host (/logistics) pages render, and
     the SPA host resolves the built Vite bundle from the manifest.
"""

import frappe
from frappe.utils import set_request

DEMO_PASSWORD = "bwm-demo-2026"  # dev/demo only — rotate on real sites
OPS_USER = "ops@bwm-demo.test"
CUSTOMER_USER = "customer@bwm-demo.test"


def run():
	out = []

	def check(label, ok, detail=""):
		out.append(f"{'PASS' if ok else 'FAIL'}  {label}" + (f" — {detail}" if detail else ""))
		return ok

	frappe.set_user("Administrator")

	# 1 ── roles exist ────────────────────────────────────────────────────────
	from bwm_logistics.install import LOGISTICS_ROLES, ensure_roles

	ensure_roles()
	missing = [r for r, _, _ in LOGISTICS_ROLES if not frappe.db.exists("Role", r)]
	check("roles created", not missing, f"missing: {missing}" if missing else "all 5 present")

	# 2 ── demo users ─────────────────────────────────────────────────────────
	_ensure_user(OPS_USER, "Odai", "Operations", ["Logistics Operations"], user_type="System User")
	_ensure_user(CUSTOMER_USER, "Ama", "Customer", ["Logistics Customer"], user_type="Website User")
	customer = _ensure_customer_link(CUSTOMER_USER, "Ama Customer")
	check("demo users + customer link", bool(customer), f"customer: {customer}")

	# 3 ── access map + destinations per persona ─────────────────────────────
	from bwm_logistics.api import access

	ops_perms = access.user_perms(OPS_USER)
	check(
		"ops perms = operator pages minus settings",
		set(ops_perms) == access.OPERATOR_KEYS - {"settings"},
		f"got {sorted(ops_perms)}",
	)
	cust_perms = access.user_perms(CUSTOMER_USER)
	check(
		"customer perms = portal pages only",
		set(cust_perms) == access.PORTAL_KEYS,
		f"got {sorted(cust_perms)}",
	)

	frappe.set_user(OPS_USER)
	d = access.login_destinations()
	check(
		"ops destinations → operator only",
		d["has_operator"] and not d["has_customer"] and not d["has_desk"],
		str(d),
	)
	frappe.set_user(CUSTOMER_USER)
	d = access.login_destinations()
	check(
		"customer destinations → portal only",
		d["has_customer"] and not d["has_operator"] and not d["has_desk"],
		str(d),
	)
	frappe.set_user("Administrator")

	# 4 ── website pages render ───────────────────────────────────────────────
	html, status = _render("/home")
	check("/home renders", status == 200 and "port to doorstep" in html.lower(), f"status {status}")

	html, status = _render("/logistics")
	has_bundle = "/assets/bwm_logistics/dist/main/" in html
	check("/logistics renders + bundle resolved", status == 200 and has_bundle, f"status {status}, bundle={has_bundle}")

	html, status = _render("/logistics/portal")  # deep link via website_route_rules
	check("/logistics/<path> route rule works", status == 200, f"status {status}")

	frappe.db.commit()
	print("\n".join(out))
	failed = [line for line in out if line.startswith("FAIL")]
	print(f"\n{len(out) - len(failed)}/{len(out)} checks passed")
	return {"passed": len(out) - len(failed), "failed": len(failed)}


def _ensure_user(email, first_name, last_name, roles, user_type):
	if not frappe.db.exists("User", email):
		user = frappe.new_doc("User")
		user.email = email
		user.first_name = first_name
		user.last_name = last_name
		user.user_type = user_type
		user.send_welcome_email = 0
		user.flags.no_welcome_mail = True
		user.new_password = DEMO_PASSWORD
		user.insert(ignore_permissions=True)
	user = frappe.get_doc("User", email)
	current = {r.role for r in user.roles}
	to_add = [r for r in roles if r not in current]
	if to_add:
		user.add_roles(*to_add)
	return user


def _ensure_customer_link(email, customer_name):
	"""Create a Customer + Contact linked to the portal user (the shape
	_perm.current_customer() resolves)."""
	if not frappe.db.exists("DocType", "Customer"):
		return None  # ERPNext not installed — nothing to link
	if not frappe.db.exists("Customer", {"customer_name": customer_name}):
		c = frappe.new_doc("Customer")
		c.customer_name = customer_name
		c.customer_type = "Individual"
		c.insert(ignore_permissions=True)
	customer = frappe.db.get_value("Customer", {"customer_name": customer_name}, "name")

	contact_name = frappe.db.get_value("Contact", {"user": email}, "name")
	if not contact_name:
		contact = frappe.new_doc("Contact")
		contact.first_name = customer_name
		contact.user = email
		contact.append("email_ids", {"email_id": email, "is_primary": 1})
		contact.insert(ignore_permissions=True)
		contact_name = contact.name
	contact = frappe.get_doc("Contact", contact_name)
	if not any(l.link_doctype == "Customer" and l.link_name == customer for l in contact.links):
		contact.append("links", {"link_doctype": "Customer", "link_name": customer})
		contact.save(ignore_permissions=True)
	return customer


def debug(path="/logistics"):
	"""Call the page's get_context directly so the real traceback surfaces
	(get_response swallows it into a generic 500 page)."""
	import traceback

	from bwm_logistics.www import logistics as page

	frappe.set_user("Guest")
	set_request(method="GET", path=path)
	ctx = frappe._dict()
	try:
		page.get_context(ctx)
		print("get_context OK")
		print("entry_js:", ctx.entry_js)
		print("entry_css:", ctx.entry_css)
		print("boot_json head:", (ctx.boot_json or "")[:120])
	except Exception:
		print("get_context RAISED:")
		traceback.print_exc()
	finally:
		frappe.set_user("Administrator")


def _render(path):
	"""Render a website route the way tests do — no running webserver needed."""
	from frappe.website.serve import get_response

	frappe.set_user("Guest")
	set_request(method="GET", path=path)
	response = get_response()
	frappe.set_user("Administrator")
	html = response.get_data(as_text=True) if hasattr(response, "get_data") else str(response)
	return html, response.status_code
