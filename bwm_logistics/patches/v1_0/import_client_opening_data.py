# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""Seed JM Containers' opening stock on the first migrate that carries it.

The client's live containers and distributions come from their working Excel.
Rather than have someone copy a spreadsheet onto the server and remember to run
an import, the sheet is frozen into `data/jm_containers_opening.json` (see
`import_jm_excel.extract`) and loaded here — so `bench migrate` after a deploy
brings the site up with real stock.

Frappe runs a patch once per site, and `import_jm_excel.load()` skips records
that already exist, so re-running by hand after a restore is harmless.

A data import must never block an app upgrade: if the load fails, the error is
logged and migrate carries on. Re-run it afterwards with

    bench --site <site> execute bwm_logistics.import_jm_excel.load_opening
"""

import frappe

from bwm_logistics.import_jm_excel import load_opening


def execute():
	try:
		load_opening()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(
			title="Opening data import failed",
			message=frappe.get_traceback(),
		)
		print(
			"WARNING: opening-balance import failed — migrate continued. See the Error Log, then re-run:\n"
			"  bench --site <site> execute bwm_logistics.import_jm_excel.load_opening"
		)
