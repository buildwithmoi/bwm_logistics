# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Run the Model B normalisation sweep on an existing site.

The sweep itself lives in `bwm_logistics.opening_repair` because a patch cannot
carry it alone: a freshly installed site has every patch marked complete before
`after_install` even runs, so this file would never execute on the deployment
that most needs it. `hooks.after_migrate` calls the same function.

This patch exists so a server that is *upgraded* gets the repair inside the
migrate that carries the change, rather than one hook later.
"""

import frappe

from bwm_logistics.opening_repair import run


def execute():
	try:
		run()
	except Exception:
		# A data repair must never block an app upgrade — after_migrate will
		# try again on the next deploy.
		frappe.db.rollback()
		frappe.log_error(title="Model B normalisation failed", message=frappe.get_traceback())
		print("WARNING: opening-data repair failed — migrate continued. See the Error Log.")
