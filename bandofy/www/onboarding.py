import frappe
from frappe.utils import date_diff, today

from bandofy.radius_auth import RADIUS_CONTROLLER_TYPES

no_cache = 1


def _integration_done(site_doc):
	ct = site_doc.controller_type or "Omada"
	if ct in RADIUS_CONTROLLER_TYPES:
		return bool(site_doc.nas_identifier)
	return bool(site_doc.omada_site_id)


def get_context(context):
	context.no_cache = 1

	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/onboarding"
		raise frappe.Redirect

	site = frappe.db.get_value("Hotspot Site", {"vendor_user": frappe.session.user}, "name")
	if not site:
		frappe.local.flags.redirect_location = "/vendor-dashboard"
		raise frappe.Redirect

	site_doc = frappe.get_doc("Hotspot Site", site)
	context.site = site_doc

	steps = [
		{
			"title": "Account & site created",
			"done": True,
			"description": "Your account and hotspot site have been set up.",
			"action_url": None,
		},
		{
			"title": "Add access points",
			"done": bool(site_doc.devices),
			"description": "Register your Omada or Ruijie access points by MAC address.",
			"action_url": "/devices",
		},
		{
			"title": "Configure integration",
			"done": _integration_done(site_doc),
			"description": "Connect Bandofy with your hardware: set your Omada Site ID, Ruijie AC Name, or point your AP at the RADIUS server.",
			"action_url": "/site-settings",
		},
		{
			"title": "Build your packages",
			"done": bool(site_doc.packages),
			"description": "Create hourly, daily, or weekly packages with your pricing.",
			"action_url": "/packages",
		},
		{
			"title": "Brand your portal",
			"done": bool(site_doc.portal_logo or site_doc.portal_tagline),
			"description": "Upload your logo and set a tagline for a professional look.",
			"action_url": "/site-settings",
		},
		{
			"title": "Enable payments",
			"done": bool(site_doc.enable_online_payment),
			"description": "Turn on mobile money payments so guests can pay instantly.",
			"action_url": "/site-settings",
		},
	]

	context.steps = steps
	context.steps_done = sum(1 for s in steps if s["done"])
	context.total_steps = len(steps)
	context.all_done = context.steps_done == context.total_steps

	context.subscription_status = site_doc.subscription_status or "Trial"
	if site_doc.trial_expires_on:
		context.trial_days_left = date_diff(site_doc.trial_expires_on, today())
	else:
		context.trial_days_left = 7
