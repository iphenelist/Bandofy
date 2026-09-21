app_name = "bandofy"
app_title = "Bandofy"
app_publisher = "Innocent P M"
app_description = "Frappe Omada Hotspot Management System, this is the Frappe custom app that helps hotspot vending in the tp-link Omada access points without use of microtik devices."
app_email = "innocentphenelist@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "bandofy",
# 		"logo": "/assets/bandofy/logo.png",
# 		"title": "Bandofy",
# 		"route": "/bandofy",
# 		"has_permission": "bandofy.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/bandofy/css/bandofy.css"
# app_include_js = "/assets/bandofy/js/bandofy.js"

# include js, css files in header of web template
# web_include_css = "/assets/bandofy/css/bandofy.css"
# web_include_js = "/assets/bandofy/js/bandofy.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "bandofy/public/scss/website"

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
# app_include_icons = "bandofy/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
role_home_page = {
	"System Manager": "app",
}

# Website Route Rules
# --------------------
# Maps friendly public URLs to the underlying www page controllers.

website_route_rules = [
	{"from_route": "/wifi_login", "to_route": "wifi_login"},
	{"from_route": "/vendor-dashboard", "to_route": "vendor_dashboard"},
]

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
# 	"methods": "bandofy.utils.jinja_methods",
# 	"filters": "bandofy.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "bandofy.install.before_install"
# after_install = "bandofy.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "bandofy.uninstall.before_uninstall"
# after_uninstall = "bandofy.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "bandofy.utils.before_app_install"
# after_app_install = "bandofy.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "bandofy.utils.before_app_uninstall"
# after_app_uninstall = "bandofy.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "bandofy.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "bandofy.notifications.get_notification_config"

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

# Instant alerts for the Bandofy Monitor mobile app (see bandofy.realtime) --
# delivered over Frappe's realtime socket the moment a voucher is redeemed
# or a Mobile Money payment completes.
doc_events = {
	"Hotspot Voucher": {"on_update": "bandofy.realtime.notify_voucher_used"},
	"Hotspot Transaction": {"on_update": "bandofy.realtime.notify_transaction_paid"},
	"Hotspot Chat Message": {"after_insert": "bandofy.realtime.notify_new_chat_message"},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		"*/5 * * * *": ["bandofy.api.sync_pending_payments"],
	},
}

# scheduler_events = {
# 	"all": [
# 		"bandofy.tasks.all"
# 	],
# 	"daily": [
# 		"bandofy.tasks.daily"
# 	],
# 	"hourly": [
# 		"bandofy.tasks.hourly"
# 	],
# 	"weekly": [
# 		"bandofy.tasks.weekly"
# 	],
# 	"monthly": [
# 		"bandofy.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "bandofy.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "bandofy.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "bandofy.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "bandofy.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# Non-System Manager users (vendors) must never reach the Desk backend;
# bounce them to their web portal dashboard instead.
before_request = ["bandofy.api.restrict_desk_access"]
# after_request = ["bandofy.utils.after_request"]

# Job Events
# ----------
# before_job = ["bandofy.utils.before_job"]
# after_job = ["bandofy.utils.after_job"]

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
# 	"bandofy.auth.validate"
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

