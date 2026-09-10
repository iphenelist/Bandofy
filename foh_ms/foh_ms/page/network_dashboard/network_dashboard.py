# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import get_first_day, get_last_day, today


@frappe.whitelist()
def get_dashboard_data():
	frappe.only_for("System Manager")

	sites = frappe.get_all(
		"Hotspot Site",
		fields=["name", "vendor_name", "site_name", "ap_mac", "is_active"],
		order_by="vendor_name asc",
	)

	month_start = get_first_day(today())
	month_end = get_last_day(today())

	site_rows = []
	total_revenue_today = 0
	total_revenue_month = 0
	total_transactions_today = 0

	for site in sites:
		revenue_today = _revenue(site.name, today(), today())
		revenue_month = _revenue(site.name, month_start, month_end)
		txns_today = frappe.db.count(
			"Hotspot Transaction",
			{"site": site.name, "status": "Paid", "creation": ["between", [today(), today()]]},
		)

		total_revenue_today += revenue_today
		total_revenue_month += revenue_month
		total_transactions_today += txns_today

		site_rows.append(
			{
				"name": site.name,
				"vendor_name": site.vendor_name,
				"site_name": site.site_name,
				"ap_mac": site.ap_mac,
				"is_active": site.is_active,
				"revenue_today": revenue_today,
				"revenue_month": revenue_month,
				"transactions_today": txns_today,
				"vouchers_issued": frappe.db.count("Hotspot Voucher", {"site": site.name}),
				"vouchers_redeemed": frappe.db.count("Hotspot Voucher", {"site": site.name, "status": "Used"}),
			}
		)

	site_rows.sort(key=lambda r: r["revenue_month"], reverse=True)

	return {
		"total_sites": len(sites),
		"active_sites": len([s for s in sites if s.is_active]),
		"total_revenue_today": total_revenue_today,
		"total_revenue_month": total_revenue_month,
		"total_transactions_today": total_transactions_today,
		"sites": site_rows,
	}


def _revenue(site_name, start_date, end_date):
	result = frappe.db.sql(
		"""
		select sum(amount) as total
		from `tabHotspot Transaction`
		where site=%s and status='Paid'
		and date(creation) between %s and %s
		""",
		(site_name, start_date, end_date),
	)
	return result[0][0] if result and result[0][0] else 0
