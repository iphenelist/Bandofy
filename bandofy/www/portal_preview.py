# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from bandofy.utils import get_vendor_site_name

no_cache = 1


def get_context(context):
	context.no_cache = 1

	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/portal-preview"
		raise frappe.Redirect

	site_name = get_vendor_site_name()
	if not site_name:
		frappe.local.flags.redirect_location = "/vendor-dashboard"
		raise frappe.Redirect

	site = frappe.db.get_value(
		"Hotspot Site",
		site_name,
		["name", "vendor_name", "portal_theme", "portal_primary_color", "portal_logo", "portal_tagline"],
		as_dict=True,
	)

	packages = frappe.db.get_all(
		"Hotspot Package Item",
		filters={"parent": site_name, "parenttype": "Hotspot Site"},
		fields=["package_name", "price", "duration_minutes"],
		order_by="price asc",
		limit=3,
	)
	context.site = site
	context.current_theme = site.portal_theme or "Default"
	context.preview_packages = packages
