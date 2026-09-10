# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import get_first_day, get_last_day, today

from foh_ms.dashboard_utils import get_omada_live_stats, get_revenue

no_cache = 1


def get_context(context):
	context.no_cache = 1

	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/vendor-dashboard"
		raise frappe.Redirect

	site = frappe.db.get_value(
		"Hotspot Site",
		{"vendor_user": frappe.session.user},
		[
			"name",
			"vendor_name",
			"site_name",
			"ap_mac",
			"controller_ip",
			"port",
			"site_id",
			"omada_username",
			"is_active",
		],
		as_dict=True,
	)

	if not site:
		frappe.throw(
			_("No Hotspot Site is linked to your account. Please contact the administrator."),
			frappe.PermissionError,
		)

	context.site = site

	context.total_revenue_today = get_revenue(site.name, today(), today())
	context.total_revenue_month = get_revenue(site.name, get_first_day(today()), get_last_day(today()))

	context.active_connections = frappe.db.count("Hotspot Transaction", {"site": site.name, "status": "Paid"})

	context.transactions = frappe.get_all(
		"Hotspot Transaction",
		filters={"site": site.name, "status": "Paid"},
		fields=["phone_number", "package_name", "amount", "duration_minutes", "client_mac", "creation", "reference_id"],
		order_by="creation desc",
		limit_page_length=20,
		ignore_permissions=True,
	)

	context.omada = get_omada_live_stats(site)

	context.vouchers_issued = frappe.db.count("Hotspot Voucher", {"site": site.name})
	context.vouchers_redeemed = frappe.db.count("Hotspot Voucher", {"site": site.name, "status": "Used"})
	context.ad_views = frappe.db.count("Hotspot Ad View Log", {"site": site.name})

	return context
