app_name = "bwm_logistics"
app_title = "Bwm Logistics"
app_publisher = "Build With Moi"
app_description = "Logistics"
app_email = "buildwithmoinow@gmail.com"
app_license = "mit"

# Apps
# ------------------

# Customer, Sales Invoice, Payment Request etc. come from ERPNext.
required_apps = ["erpnext"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "bwm_logistics",
# 		"logo": "/assets/bwm_logistics/logo.png",
# 		"title": "Bwm Logistics",
# 		"route": "/bwm_logistics",
# 		"has_permission": "bwm_logistics.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/bwm_logistics/css/bwm_logistics.css"
# app_include_js = "/assets/bwm_logistics/js/bwm_logistics.js"

# include js, css files in header of web template
# web_include_css = "/assets/bwm_logistics/css/bwm_logistics.css"
# web_include_js = "/assets/bwm_logistics/js/bwm_logistics.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "bwm_logistics/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "bwm_logistics/public/icons.svg"

# Home Pages
# ----------

# Public marketing landing page (www/home.html). Customers reach the portal
# login from here; making it the website home overrides Website Settings.
home_page = "home"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "bwm_logistics.utils.jinja_methods",
# 	"filters": "bwm_logistics.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "bwm_logistics.install.before_install"
# Idempotent role setup; also wired to after_migrate so deployments self-heal.
after_install = "bwm_logistics.install.after_install"
after_migrate = ["bwm_logistics.install.after_install"]

# Uninstallation
# ------------

# before_uninstall = "bwm_logistics.uninstall.before_uninstall"
# after_uninstall = "bwm_logistics.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "bwm_logistics.utils.before_app_install"
# after_app_install = "bwm_logistics.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "bwm_logistics.utils.before_app_uninstall"
# after_app_uninstall = "bwm_logistics.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "bwm_logistics.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "bwm_logistics.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
	"hourly": [
		# Carrier-API container sync — no-op until a provider is configured.
		"bwm_logistics.carrier_tracking.sync_all_active",
	],
	"daily": [
		# Demurrage-risk digest to Logistics Managers.
		"bwm_logistics.alerts.demurrage_check",
	],
}

# Testing
# -------

# Completes the ERPNext setup wizard on bare test sites (CI) so master data
# (Company, Customer Group/Territory trees, accounts) exists for the suite.
before_tests = "bwm_logistics.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "bwm_logistics.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "bwm_logistics.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "bwm_logistics.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["bwm_logistics.utils.before_request"]
# after_request = ["bwm_logistics.utils.after_request"]

# Job Events
# ----------
# before_job = ["bwm_logistics.utils.before_job"]
# after_job = ["bwm_logistics.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"bwm_logistics.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


website_route_rules = [{'from_route': '/logistics/<path:app_path>', 'to_route': 'logistics'},]

# PWA (P8): serves /logistics/sw.js + /logistics/manifest.webmanifest from the
# built bundle with the Service-Worker-Allowed header (see bwm_logistics/pwa.py).
page_renderer = ["bwm_logistics.pwa.PWARenderer"]