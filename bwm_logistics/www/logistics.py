# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

import json
import os

import frappe
# Explicit import — `frappe.sessions` is only attached to the frappe module
# during HTTP request handling; direct imports keep this page renderable in
# tests/`bench execute` too.
from frappe.sessions import get as get_bootinfo
from frappe.sessions import get_csrf_token

# The SPA mounts at /logistics. `no_cache = 1` so each page load re-emits a
# fresh CSRF token (set in get_context) — otherwise stale tokens float around
# after logout/login.
no_cache = 1
# The SPA renders its own branded login screen for Guests — we don't redirect
# to Frappe's /login. Keeping the page reachable for unauthenticated users
# lets the SPA show the login UI instantly without a full reload.
allow_guest = True


def get_context(context):
	"""Inject the asset URLs + bootinfo into the Vue mount template.

	Vite emits hashed entry chunks under `bwm_logistics/public/dist/main/`.
	We read its `manifest.json` to find the right filenames so the template
	doesn't break every rebuild. In dev (no manifest), the developer is
	hitting Vite directly on :8080 — they shouldn't be on /logistics then.
	"""
	try:
		context.csrf_token = get_csrf_token()
	except AttributeError:
		# Non-request contexts (tests / `bench execute`) have no session_obj to
		# stamp a token into. Real HTTP requests always do.
		context.csrf_token = ""
	# frappe.as_json (not stdlib json.dumps) — the boot payload contains
	# datetime values the stdlib encoder can't serialize.
	context.boot_json = frappe.as_json(get_bootinfo())
	context.is_guest = frappe.session.user == "Guest"

	context.entry_js, context.entry_css = _resolve_assets("dist/main")


def _resolve_assets(subdir):
	"""Return ('/assets/bwm_logistics/<subdir>/<entry-hash>.js', css_url_or_None).

	Manifest schema (Vite with `manifest: true`): keys are source paths
	relative to the project root (e.g. "src/main.ts"); each value has
	`file` plus optional `css` array.
	"""
	asset_root = frappe.get_app_path("bwm_logistics", "public", subdir)
	manifest_path = os.path.join(asset_root, ".vite", "manifest.json")
	if not os.path.exists(manifest_path):
		# Fallback for when the bundle hasn't been built yet — clearer than a
		# 500. The page renders a hint so the developer knows to build.
		return None, None

	with open(manifest_path, encoding="utf-8") as f:
		manifest = json.load(f)

	entry = manifest.get("src/main.ts") or next((v for v in manifest.values() if v.get("isEntry")), None)
	if not entry:
		return None, None

	asset_prefix = f"/assets/bwm_logistics/{subdir}/"
	js = asset_prefix + entry["file"]
	css = None
	css_files = entry.get("css") or []
	if css_files:
		css = asset_prefix + css_files[0]
	return js, css
