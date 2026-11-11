# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

"""Shared dashboard math used by both the web /vendor-dashboard page and the
mobile monitoring app's REST API, so the two never drift apart.
"""

import frappe
from frappe.query_builder.functions import CurDate, Date, Sum
from pypika.terms import Interval

import bandofy.omada_service as omada_service
from bandofy.omada_auth import OmadaAuthError, get_live_stats


def get_omada_live_stats(site):
	"""Live Omada controller stats for one Hotspot Site doc.

	Returns a dict with connected, client_count, tx_rate, rx_rate, and error.
	Fails soft on Ruijie sites or when Omada credentials are not configured.
	"""
	_UNAVAILABLE = {"connected": False, "client_count": 0, "tx_rate": 0, "rx_rate": 0, "error": None}

	if getattr(site, "controller_type", None) == "Ruijie":
		return {**_UNAVAILABLE, "error": "Live stats not available for Ruijie sites."}

	try:
		ctrl = omada_service.site_controller(site)
	except OmadaAuthError as e:
		return {**_UNAVAILABLE, "error": str(e)}

	try:
		return get_live_stats(**ctrl)
	except OmadaAuthError as e:
		return {**_UNAVAILABLE, "error": str(e)}
	except Exception:
		frappe.log_error(title="Bandofy: get_omada_live_stats failed", message=frappe.get_traceback())
		return {**_UNAVAILABLE, "error": "Could not reach the Omada Controller."}


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


