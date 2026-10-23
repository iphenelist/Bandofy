# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

"""Shared dashboard math used by both the web /vendor-dashboard page and the
mobile monitoring app's REST API, so the two never drift apart.
"""

import frappe
from frappe.query_builder.functions import CurDate, Date, Sum
from pypika.terms import Interval


def get_revenue(site_name, start_date, end_date):
	t = frappe.qb.DocType("Hotspot Transaction")
	result = (
		frappe.qb.from_(t)
		.select(Sum(t.amount).as_("total"))
		.where((t.site == site_name) & (t.status == "Paid") & Date(t.creation).between(start_date, end_date))
	).run()
	return result[0][0] if result and result[0][0] else 0


def get_revenue_trend(site_name, days=7):
	"""Daily Paid revenue totals for the last `days` days (oldest first),
	including days with zero revenue, for the app's trend chart.
	"""
	t = frappe.qb.DocType("Hotspot Transaction")
	rows = (
		frappe.qb.from_(t)
		.select(Date(t.creation).as_("day"), Sum(t.amount).as_("total"))
		.where(
			(t.site == site_name)
			& (t.status == "Paid")
			& Date(t.creation).between(CurDate() - Interval(days=days - 1), CurDate())
		)
		.groupby(Date(t.creation))
	).run(as_dict=True)
	by_day = {frappe.utils.getdate(row.day).isoformat(): row.total or 0 for row in rows}

	trend = []
	for offset in range(days - 1, -1, -1):
		day = frappe.utils.add_to_date(frappe.utils.nowdate(), days=-offset, as_string=False)
		day_key = frappe.utils.getdate(day).isoformat()
		trend.append({"date": day_key, "amount": by_day.get(day_key, 0)})

	return trend


def get_omada_live_stats(site):
	"""Controller status and live client count / bandwidth usage.

	Fails soft: dashboard should still render if the controller is
	unreachable, just marked as disconnected. `site` needs at least `name`.
	"""
	from bandofy import omada_service

	stats = {"connected": False, "client_count": 0, "tx_rate": 0, "rx_rate": 0, "error": None}

	hotspot_site = frappe.get_doc("Hotspot Site", site.name)
	try:
		stats = omada_service.get_live_stats(**omada_service.site_controller(hotspot_site))
	except Exception as e:
		stats["error"] = str(e)
		frappe.log_error(title="Bandofy Omada Live Stats Fetch Failed", message=frappe.get_traceback())

	return stats
