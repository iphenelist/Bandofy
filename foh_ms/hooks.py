app_name = "foh_ms"
app_title = "FOH-MS"
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
# 		"name": "foh_ms",
# 		"logo": "/assets/foh_ms/logo.png",
# 		"title": "FOH-MS",
# 		"route": "/foh_ms",
# 		"has_permission": "foh_ms.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/foh_ms/css/foh_ms.css"
# app_include_js = "/assets/foh_ms/js/foh_ms.js"

# include js, css files in header of web template
# web_include_css = "/assets/foh_ms/css/foh_ms.css"
# web_include_js = "/assets/foh_ms/js/foh_ms.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "foh_ms/public/scss/website"

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
# app_include_icons = "foh_ms/public/icons.svg"

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
# 	"methods": "foh_ms.utils.jinja_methods",
# 	"filters": "foh_ms.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "foh_ms.install.before_install"
# after_install = "foh_ms.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "foh_ms.uninstall.before_uninstall"
# after_uninstall = "foh_ms.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "foh_ms.utils.before_app_install"
# after_app_install = "foh_ms.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "foh_ms.utils.before_app_uninstall"
# after_app_uninstall = "foh_ms.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "foh_ms.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "foh_ms.notifications.get_notification_config"

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

# Instant alerts for the FOH-MS Monitor mobile app (see foh_ms.realtime) --
# delivered over Frappe's realtime socket the moment a voucher is redeemed
# or a Mobile Money payment completes.
doc_events = {
	"Hotspot Voucher": {"on_update": "foh_ms.realtime.notify_voucher_used"},
	"Hotspot Transaction": {"on_update": "foh_ms.realtime.notify_transaction_paid"},
	"Hotspot Chat Message": {"after_insert": "foh_ms.realtime.notify_new_chat_message"},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		"*/5 * * * *": ["foh_ms.api.sync_pending_payments"],
	},
}

# scheduler_events = {
# 	"all": [
# 		"foh_ms.tasks.all"
# 	],
# 	"daily": [
# 		"foh_ms.tasks.daily"
# 	],
# 	"hourly": [
# 		"foh_ms.tasks.hourly"
# 	],
# 	"weekly": [
# 		"foh_ms.tasks.weekly"
# 	],
# 	"monthly": [
# 		"foh_ms.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "foh_ms.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "foh_ms.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "foh_ms.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "foh_ms.task.get_dashboard_data"
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
before_request = ["foh_ms.api.restrict_desk_access"]
# after_request = ["foh_ms.utils.after_request"]

# Job Events
# ----------
# before_job = ["foh_ms.utils.before_job"]
# after_job = ["foh_ms.utils.after_job"]

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
# 	"foh_ms.auth.validate"
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

