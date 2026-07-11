# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Operator alerts (PRD FR-CTR-6): demurrage risk.

Daily scheduler job (hooks.scheduler_events). A container is "at risk" when
its demurrage clock starts within the next N days (or already started) and it
isn't Completed/Cancelled. Managers get one digest email per day, and the
digest is logged so the Notifications page shows it.
"""

import frappe
from frappe.utils import add_days, date_diff, nowdate

RISK_WINDOW_DAYS = 3


def at_risk_containers() -> list[dict]:
	rows = frappe.get_all(
		"Container",
		filters={
			"status": "Active",
			"demurrage_start_date": ("<=", add_days(nowdate(), RISK_WINDOW_DAYS)),
		},
		fields=["name", "container_no", "demurrage_start_date", "customs_status", "port_of_discharge"],
		order_by="demurrage_start_date asc",
	)
	for r in rows:
		r["days_left"] = date_diff(r.demurrage_start_date, nowdate())
	return rows


def demurrage_check():
	"""Daily digest to Logistics Managers — only when something is at risk,
	and only once per day."""
	rows = at_risk_containers()
	if not rows:
		return
	already = frappe.get_all(
		"Notification Log Entry",
		filters={"milestone": "Demurrage Alert", "creation": (">=", nowdate())},
		limit=1,
	)
	if already:
		return

	managers = frappe.get_all(
		"Has Role",
		filters={"role": "Logistics Manager", "parenttype": "User"},
		pluck="parent",
	)
	recipients = [
		u
		for u in set(managers)
		if frappe.db.get_value("User", u, "enabled") and u not in ("Administrator", "Guest")
	]

	lines = [
		f"- {r.container_no or r.name}: demurrage {'starts in ' + str(r.days_left) + ' day(s)' if r.days_left > 0 else 'RUNNING since ' + str(r.demurrage_start_date)}"
		f" (customs: {r.customs_status or 'Pending'})"
		for r in rows
	]
	subject = f"Demurrage risk: {len(rows)} container(s) need attention"
	body = "The following containers are at demurrage risk:\n\n" + "\n".join(lines)

	status, error = "Sent", None
	try:
		if recipients:
			frappe.sendmail(recipients=recipients, subject=subject, message=body.replace("\n", "<br>"))
		else:
			status, error = "Skipped", "No Logistics Manager users to notify"
	except Exception as e:
		status, error = "Failed", str(e)[:500]

	frappe.get_doc(
		{
			"doctype": "Notification Log Entry",
			"channel": "Email",
			"status": status,
			"recipient": ", ".join(recipients) or "-",
			"milestone": "Demurrage Alert",
			"subject": subject,
			"message": body,
			"error": error,
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()
