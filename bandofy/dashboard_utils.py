# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

"""Shared dashboard math used by both the web /vendor-dashboard page and the
mobile monitoring app's REST API, so the two never drift apart.
"""

import frappe


def get_revenue(site_name, start_date, end_date):
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


def get_revenue_trend(site_name, days=7):
	"""Daily Paid revenue totals for the last `days` days (oldest first),
	including days with zero revenue, for the app's trend chart.
	"""
	rows = frappe.db.sql(
		"""
		select date(creation) as day, sum(amount) as total
		from `tabHotspot Transaction`
		where site=%s and status='Paid'
		and date(creation) between date_sub(curdate(), interval %s day) and curdate()
		group by date(creation)
		""",
		(site_name, days - 1),
		as_dict=True,
	)
	by_day = {frappe.utils.getdate(row.day).isoformat(): row.total or 0 for row in rows}

	trend = []
	for offset in range(days - 1, -1, -1):
		day = frappe.utils.add_to_date(frappe.utils.nowdate(), days=-offset, as_string=False)
		day_key = frappe.utils.getdate(day).isoformat()
		trend.append({"date": day_key, "amount": by_day.get(day_key, 0)})

	return trend


def get_omada_live_stats(site):
	"""Fetch live client count / bandwidth usage from the Omada Controller.

	Fails soft: dashboard should still render if the controller is
	unreachable, just marked as disconnected. `site` needs at least `name`.
	"""
	import requests

	stats = {"connected": False, "client_count": 0, "tx_rate": 0, "rx_rate": 0, "error": None}

	try:
		requests.packages.urllib3.disable_warnings()  # noqa: RUF100

		hotspot_site = frappe.get_doc("Hotspot Site", site.name)
		base_url = f"https://{hotspot_site.controller_ip}:{hotspot_site.port}"

		session = requests.Session()
		session.verify = False

		login_resp = session.post(
			f"{base_url}/api/v2/hotspot/login",
			json={
				"username": hotspot_site.omada_username,
				"password": hotspot_site.get_password("omada_password"),
			},
			timeout=5,
		)
		login_resp.raise_for_status()
		token = (login_resp.json().get("result") or {}).get("token")

		if not token:
			raise Exception("No auth token returned by Omada controller")

		clients_resp = session.get(
			f"{base_url}/api/v2/sites/{hotspot_site.site_id}/clients",
			params={"token": token, "currentPage": 1, "currentPageSize": 100},
			headers={"Csrf-Token": token},
			timeout=5,
		)
		clients_resp.raise_for_status()
		result = clients_resp.json().get("result") or {}
		clients = result.get("data") or []

		stats["connected"] = True
		stats["client_count"] = result.get("totalRows", len(clients))
		for client in clients:
			stats["tx_rate"] += client.get("trafficDown", 0) or 0
			stats["rx_rate"] += client.get("trafficUp", 0) or 0

	except Exception as e:
		stats["error"] = str(e)
		frappe.log_error(title="Bandofy Omada Live Stats Fetch Failed", message=frappe.get_traceback())

	return stats
