# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import get_first_day, get_last_day, today

from bandofy.dashboard_utils import get_revenue, get_revenue_trend
from bandofy.utils import site_ap_macs

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
			"omada_site_id",
			"ruijie_ac_name",
			"nas_identifier",
			"is_active",
			"controller_type",
			"portal_logo",
			"portal_tagline",
			"enable_online_payment",
			"subscription_status",
			"subscription_plan",
			"trial_expires_on",
		],
		as_dict=True,
	)

	if not site:
		frappe.throw(
			_("No Hotspot Site is linked to your account. Please contact the administrator."),
			frappe.PermissionError,
		)

	context.site = site
	context.ap_count = len(site_ap_macs(site.name))

	context.total_revenue_today = get_revenue(site.name, today(), today())
	context.total_revenue_month = get_revenue(site.name, get_first_day(today()), get_last_day(today()))

	now = frappe.utils.now_datetime()
	context.active_connections = frappe.db.count(
		"Hotspot Transaction",
		{"site": site.name, "status": "Paid", "authorized_until": [">", now]}
	)
	context.active_sessions = frappe.db.get_all(
		"Hotspot Transaction",
		filters={"site": site.name, "status": "Paid", "authorized_until": [">", now]},
		fields=["client_mac", "package_name", "authorized_until"],
		order_by="authorized_until asc",
		limit=10,
	)
	context.controller_type = "Ruijie"

	# Onboarding completion (needs full doc for child tables)
	site_doc = frappe.get_doc("Hotspot Site", site.name)
	steps_done = 1  # step 1: account always done
	steps_done += 1 if site_doc.devices else 0
	steps_done += 1 if site.nas_identifier else 0
	steps_done += 1 if site_doc.packages else 0
	steps_done += 1 if (site.portal_logo or site.portal_tagline) else 0
	steps_done += 1 if site.enable_online_payment else 0
	context.onboarding_complete = steps_done

	# RADIUS server info for the vendor
	try:
		radius_settings = frappe.get_cached_doc("Hotspot Ruijie Settings")
		vps_hostname = frappe.db.get_single_value("Hotspot Platform Settings", "vps_hostname") or ""
	except Exception:
		radius_settings = None
		vps_hostname = ""
	context.radius_info = {
		"server": f"{vps_hostname}:1812" if vps_hostname else "1812",
		"secret": "••••••••" if radius_settings else "",
		"nas_identifier": site.nas_identifier or "",
		"portal_url": f"https://{frappe.local.site}/landing",
	}

	# Subscription info
	context.subscription_status = site.subscription_status or "Trial"
	context.subscription_plan = site.subscription_plan or ""
	context.trial_expires_on = site.trial_expires_on
	if site.trial_expires_on:
		from frappe.utils import date_diff
		context.trial_days_left = date_diff(site.trial_expires_on, today())
	else:
		context.trial_days_left = 0

	raw_txns = frappe.get_all(
		"Hotspot Transaction",
		filters={"site": site.name, "status": "Paid"},
		fields=[
			"phone_number",
			"package_name",
			"amount",
			"duration_minutes",
			"client_mac",
			"creation",
			"reference_id",
		],
		order_by="creation desc",
		limit_page_length=20,
		ignore_permissions=True,
	)
	# Stringify datetime and Decimal so | tojson works in the template
	for txn in raw_txns:
		txn["creation"] = str(txn.get("creation", ""))
		txn["amount"] = float(txn.get("amount") or 0)
	context.transactions = raw_txns

	context.omada = get_omada_live_stats(site)

	# Daily revenue series for chart — floats so | tojson is safe
	context.daily_revenue_month = [
		{"date": d["date"], "amount": float(d.get("amount") or 0)}
		for d in get_revenue_trend(site.name, days=30)
	]
	context.daily_revenue_week = [
		{"date": d["date"], "amount": float(d.get("amount") or 0)}
		for d in get_revenue_trend(site.name, days=7)
	]

	# Package demand: grouped count per package
	context.package_demand = [
		{"package_name": r.package_name, "count": int(r.count)}
		for r in frappe.db.sql(
			"""
			SELECT package_name, COUNT(*) AS count
			FROM `tabHotspot Transaction`
			WHERE site = %s AND status = 'Paid'
			GROUP BY package_name
			ORDER BY count DESC
			LIMIT 6
			""",
			(site.name,),
			as_dict=True,
		)
	]

	context.vouchers_issued = frappe.db.count("Hotspot Voucher", {"site": site.name})
	context.vouchers_redeemed = frappe.db.count("Hotspot Voucher", {"site": site.name, "status": "Used"})
	context.ad_views = frappe.db.count("Hotspot Ad View Log", {"site": site.name})

	return context
