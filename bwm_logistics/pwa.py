# Copyright (c) 2026, Build With Moi and contributors
# For license information, please see license.txt

"""PWA plumbing (P8): serves the built service worker and web manifest at
/logistics/* URLs.

Why this exists: the Vite build emits sw.js under
/assets/bwm_logistics/dist/main/, but a service worker's scope is capped at
the directory it is served FROM — an /assets worker can never control
/logistics. This custom page renderer (hooks.py `page_renderer`) intercepts
/logistics/sw.js (+ workbox chunk + manifest) BEFORE the website_route_rules
catch-all and streams the built file with `Service-Worker-Allowed: /logistics`
so main.ts can register it with scope "/logistics".

Note: renderers receive the post-route-rule endpoint ("logistics"), so we
match on the raw request path instead."""

import json
import mimetypes
import os
import re

import frappe
from werkzeug.wrappers import Response

from frappe.website.page_renderers.base_renderer import BaseRenderer

# Whitelist — exact filenames only, no user-controlled path segments.
_PWA_FILE = re.compile(r"^logistics/(sw\.js|workbox-[\w.-]+\.js|manifest\.webmanifest)$")
_CONTENT_TYPES = {
	".js": "text/javascript",
	".webmanifest": "application/manifest+json",
}


class PWARenderer(BaseRenderer):
	def __init__(self, path=None, http_status_code=None):
		super().__init__(path=path, http_status_code=http_status_code)
		raw = (
			getattr(getattr(frappe.local, "request", None), "path", None)
			or getattr(frappe.local, "path", "")
			or ""
		)
		match = _PWA_FILE.match(raw.strip("/ "))
		self.filename = match.group(1) if match else None

	def can_render(self):
		return bool(self.filename) and os.path.exists(self._file_path())

	def _file_path(self):
		return frappe.get_app_path("bwm_logistics", "public", "dist", "main", self.filename)

	def render(self):
		with open(self._file_path(), "rb") as f:
			data = f.read()
		if self.filename == "manifest.webmanifest":
			data = self._brand(data)
		ext = os.path.splitext(self.filename)[1]
		content_type = _CONTENT_TYPES.get(ext) or mimetypes.guess_type(self.filename)[0] or "application/octet-stream"
		response = Response(data, status=200, content_type=content_type)
		# Browsers revalidate SWs anyway; no-cache keeps updates instant.
		response.headers["Cache-Control"] = "no-cache, must-revalidate"
		if self.filename.endswith(".js"):
			# The requested scope (/logistics) is broader than the SW's own URL
			# directory (/logistics/) — this header authorises it.
			response.headers["Service-Worker-Allowed"] = "/logistics"
		return response

	def _brand(self, data: bytes) -> bytes:
		"""Stamp the tenant's own name onto the installed app.

		The manifest is generated at build time, so it carries whatever name the
		bundle was built with — which is how an installed PWA ends up on a
		client's phone under our name. It is served through here rather than as
		a static asset, so the name can come from Logistics Settings instead.
		"""
		try:
			from bwm_logistics.api.settings import business_name

			manifest = json.loads(data)
			name = business_name()
			manifest["name"] = name
			manifest["short_name"] = name[:12]
			return json.dumps(manifest).encode()
		except Exception:
			# Branding is never worth a broken manifest — serve what was built.
			return data
