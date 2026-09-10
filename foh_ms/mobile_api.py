# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

"""REST API consumed by the FOH-MS Monitor Flutter app.

Session-cookie authenticated (not API key): the same `sid` the app gets back
from :func:`mobile_login` is reused as the Socket.IO handshake credential for
realtime alerts (see foh_ms.realtime), so there's a single auth mechanism for
both REST calls and the live socket.

Two roles:
- "vendor": a Website User linked to exactly one Hotspot Site via its
  `vendor_user` field (same linkage the /vendor-dashboard web page uses).
  Every endpoint below silently scopes to that one site regardless of any
  `site` argument passed in.
- "admin": System Manager / Administrator. Can see every site, and pass an
  explicit `site` argument to drill into one of them.

Website Users have no doctype-level read permission on any of these doctypes
(see each doctype's permissions block) -- exactly like the existing
/vendor-dashboard page, every query here uses ignore_permissions=True after
the code itself has already established which site(s) this user may see.
"""

import frappe
from frappe import _
from frappe.utils import get_first_day, get_last_day, today

from foh_ms.dashboard_utils import get_omada_live_stats, get_revenue, get_revenue_trend


def _is_admin(user=None):
	user = user or frappe.session.user
	return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def _own_site_name():
	site_name = frappe.db.get_value("Hotspot Site", {"vendor_user": frappe.session.user}, "name")
	if not site_name:
		frappe.throw(
			_("No Hotspot Site is linked to your account. Please contact the administrator."),
			frappe.PermissionError,
		)
	return site_name


def _resolve_site(site=None):
	"""Returns the Hotspot Site name a vendor is scoped to, or the admin's
	chosen site (or None, meaning "all sites"). Raises PermissionError if a
	vendor is somehow not linked to any site."""
	if _is_admin():
		if site and not frappe.db.exists("Hotspot Site", site):
			frappe.throw(_("Site not found."))
		return site
	return _own_site_name()


@frappe.whitelist(allow_guest=True)
def mobile_login(usr, pwd):
	"""Authenticate usr/pwd (already merged into frappe.form_dict by Frappe's
	own dispatcher). Also hands back role + site info in the same round trip
	so the app can decide which screen to land on.

	LoginManager's constructor only auto-authenticates usr/pwd from the
	request when cmd == "login" or the path is /api/method/login -- for any
	other endpoint (this one included) it just tries to resume an existing
	session and leaves the user as Guest. So authenticate() and post_login()
	(which does the actual credential check, session creation, and queues
	the sid cookie on the response) are called explicitly instead.
	"""
	from frappe.auth import LoginManager

	login_manager = LoginManager()
	login_manager.authenticate(user=usr, pwd=pwd)
	login_manager.post_login()

	user = frappe.session.user
	if user == "Guest":
		frappe.throw(_("Invalid login."))

	return _profile()


@frappe.whitelist()
def whoami():
	"""Cheap session check the app makes on launch to decide Login vs Home
	without forcing a fresh login every time it's opened."""
	return _profile()


def _profile():
	user = frappe.session.user
	admin = _is_admin(user)

	if admin:
		sites = frappe.get_all(
			"Hotspot Site",
			fields=["name", "vendor_name", "site_name", "is_active"],
			order_by="vendor_name",
			ignore_permissions=True,
		)
		return {"user": user, "role": "admin", "sites": sites}

	site = frappe.db.get_value(
		"Hotspot Site",
		{"vendor_user": user},
		["name", "vendor_name", "site_name", "is_active"],
		as_dict=True,
	)
	if not site:
		frappe.throw(
			_("No Hotspot Site is linked to your account. Please contact the administrator."),
			frappe.PermissionError,
		)
	return {"user": user, "role": "vendor", "sites": [site]}


@frappe.whitelist()
def get_sites():
	"""Admin-only: every site, for the site switcher."""
	if not _is_admin():
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	return frappe.get_all(
		"Hotspot Site",
		fields=["name", "vendor_name", "site_name", "ap_mac", "is_active", "authorization_method"],
		order_by="vendor_name",
		ignore_permissions=True,
	)


def _site_dashboard(site_name):
	"""Same numbers www/vendor_dashboard.py renders for one site, as a dict."""
	site = frappe.db.get_value(
		"Hotspot Site",
		site_name,
		["name", "vendor_name", "site_name", "ap_mac", "is_active"],
		as_dict=True,
	)

	return {
		"site": site,
		"revenue_today": get_revenue(site_name, today(), today()),
		"revenue_month": get_revenue(site_name, get_first_day(today()), get_last_day(today())),
		"revenue_trend": get_revenue_trend(site_name, days=7),
		"active_connections": frappe.db.count("Hotspot Transaction", {"site": site_name, "status": "Paid"}),
		"omada": get_omada_live_stats(site),
		"vouchers_issued": frappe.db.count("Hotspot Voucher", {"site": site_name}),
		"vouchers_redeemed": frappe.db.count("Hotspot Voucher", {"site": site_name, "status": "Used"}),
		"ad_views": frappe.db.count("Hotspot Ad View Log", {"site": site_name}),
	}


def _all_sites_overview():
	"""Admin, no site chosen: totals + a per-site breakdown row. Deliberately
	skips live Omada polling (get_omada_live_stats) here -- pinging every
	site's controller synchronously on one request would be slow and can
	hang on an unreachable controller; that's only fetched for one site at a
	time via _site_dashboard."""
	sites = frappe.get_all(
		"Hotspot Site",
		fields=["name", "vendor_name", "site_name", "is_active"],
		order_by="vendor_name",
		ignore_permissions=True,
	)

	rows = []
	totals = {"revenue_today": 0, "revenue_month": 0, "vouchers_issued": 0, "vouchers_redeemed": 0}

	for site in sites:
		revenue_today = get_revenue(site.name, today(), today())
		revenue_month = get_revenue(site.name, get_first_day(today()), get_last_day(today()))
		vouchers_issued = frappe.db.count("Hotspot Voucher", {"site": site.name})
		vouchers_redeemed = frappe.db.count("Hotspot Voucher", {"site": site.name, "status": "Used"})

		rows.append(
			{
				**site,
				"revenue_today": revenue_today,
				"revenue_month": revenue_month,
				"vouchers_issued": vouchers_issued,
				"vouchers_redeemed": vouchers_redeemed,
			}
		)

		totals["revenue_today"] += revenue_today
		totals["revenue_month"] += revenue_month
		totals["vouchers_issued"] += vouchers_issued
		totals["vouchers_redeemed"] += vouchers_redeemed

	return {"totals": totals, "sites": rows}


@frappe.whitelist()
def get_dashboard(site=None):
	if _is_admin():
		if site:
			if not frappe.db.exists("Hotspot Site", site):
				frappe.throw(_("Site not found."))
			return {"scope": "site", **_site_dashboard(site)}
		return {"scope": "all", **_all_sites_overview()}

	return {"scope": "site", **_site_dashboard(_own_site_name())}


@frappe.whitelist()
def get_transactions(site=None, status=None, limit=50, start=0):
	site_name = _resolve_site(site)

	filters = {}
	if site_name:
		filters["site"] = site_name
	if status:
		filters["status"] = status

	return frappe.get_all(
		"Hotspot Transaction",
		filters=filters,
		fields=[
			"name",
			"site",
			"status",
			"phone_number",
			"package_name",
			"amount",
			"duration_minutes",
			"client_mac",
			"reference_id",
			"creation",
		],
		order_by="creation desc",
		limit_page_length=limit,
		limit_start=start,
		ignore_permissions=True,
	)


@frappe.whitelist()
def get_vouchers(
	site=None,
	status=None,
	batch=None,
	package_name=None,
	search=None,
	date_from=None,
	date_to=None,
	limit=50,
	start=0,
):
	"""The maintainer's voucher list, filterable by status, batch, package,
	a free-text code search, and a generated_on date range. Also returns the
	distinct batches/packages in scope, to populate the app's filter
	dropdowns alongside the page of results."""
	site_name = _resolve_site(site)

	filters = {}
	if site_name:
		filters["site"] = site_name
	if status:
		filters["status"] = status
	if batch:
		filters["batch"] = batch
	if package_name:
		filters["package_name"] = package_name
	if search:
		filters["voucher_code"] = ["like", f"%{search}%"]
	if date_from and date_to:
		filters["generated_on"] = ["between", [date_from, date_to]]
	elif date_from:
		filters["generated_on"] = [">=", date_from]
	elif date_to:
		filters["generated_on"] = ["<=", date_to]

	vouchers = frappe.get_all(
		"Hotspot Voucher",
		filters=filters,
		fields=[
			"name",
			"voucher_code",
			"status",
			"site",
			"batch",
			"package_name",
			"price",
			"duration_minutes",
			"generated_on",
			"expires_on",
			"used_on",
			"used_by_mac",
		],
		order_by="generated_on desc",
		limit_page_length=limit,
		limit_start=start,
		ignore_permissions=True,
	)

	scope_filters = {"site": site_name} if site_name else {}
	batches = frappe.get_all(
		"Hotspot Voucher Batch",
		filters=scope_filters,
		fields=["name", "package_name"],
		order_by="creation desc",
		ignore_permissions=True,
	)
	packages = frappe.get_all(
		"Hotspot Voucher",
		filters=scope_filters,
		fields=["package_name"],
		distinct=True,
		ignore_permissions=True,
	)

	return {
		"vouchers": vouchers,
		"batches": batches,
		"packages": [p.package_name for p in packages],
	}


@frappe.whitelist()
def get_voucher_batches(site=None):
	"""Stock view: quantity vs generated vs how many are still Unused, so the
	maintainer can see at a glance which batches are running low."""
	site_name = _resolve_site(site)

	filters = {"site": site_name} if site_name else {}
	batches = frappe.get_all(
		"Hotspot Voucher Batch",
		filters=filters,
		fields=["name", "site", "package_name", "status", "quantity", "generated_count", "expires_on"],
		order_by="creation desc",
		ignore_permissions=True,
	)

	for batch in batches:
		batch["redeemed_count"] = frappe.db.count(
			"Hotspot Voucher", {"batch": batch.name, "status": "Used"}
		)
		batch["remaining_unused"] = frappe.db.count(
			"Hotspot Voucher", {"batch": batch.name, "status": "Unused"}
		)

	return batches
