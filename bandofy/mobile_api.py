# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

"""REST API consumed by the Bandofy Monitor Flutter app.

Session-cookie authenticated (not API key): the same `sid` the app gets back
from :func:`mobile_login` is reused as the Socket.IO handshake credential for
realtime alerts (see bandofy.realtime), so there's a single auth mechanism for
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

import json

import frappe
from frappe import _
from frappe.utils import get_first_day, get_last_day, today

from bandofy import omada_service
from bandofy.dashboard_utils import get_omada_live_stats, get_revenue, get_revenue_trend
from bandofy.utils import is_admin_user as _is_admin
from bandofy.utils import normalize_mac


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


def _resolve_site_for_write(site=None):
	"""Like _resolve_site, but for actions that always need exactly one
	concrete site -- a vendor is forced to their own regardless of `site`;
	an admin must pass one explicitly (there's no "all sites" write)."""
	if not _is_admin():
		return _own_site_name()
	if not site:
		frappe.throw(_("Please choose a site."))
	if not frappe.db.exists("Hotspot Site", site):
		frappe.throw(_("Site not found."))
	return site


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


@frappe.whitelist()
def get_packages():
	"""Every Hotspot Package, for the voucher-creation form's picker."""
	return frappe.get_all(
		"Hotspot Package",
		fields=["name", "package_type", "price", "duration_minutes"],
		order_by="name",
		ignore_permissions=True,
	)


@frappe.whitelist()
def create_site(
	vendor_name,
	vendor_user,
	site_name,
	ap_mac,
	authorization_method="Omada Controller API",
	phone_number=None,
	mobile_money_account=None,
	enable_online_payment=0,
	enable_free_trial=1,
	free_trial_minutes=15,
	controller_ip=None,
	port=8043,
	controller_id=None,
	site_id="default",
	omada_username=None,
	omada_password=None,
	success_redirect_url=None,
	radius_client_ip=None,
	radius_nas_id=None,
	radius_secret=None,
	ap_login_url_template=None,
	packages=None,
):
	"""Admin-only: create a new Hotspot Site from the app. Field validation
	(e.g. Omada credentials required when authorization_method is "Omada
	Controller API") is left to the doctype's own mandatory_depends_on
	rules, surfaced through the same error-message plumbing as any other
	failure.

	``packages`` is a JSON-encoded list of {package_name, package_type,
	price, duration_minutes} -- the site's own captive-portal pricing plans
	(Hotspot Package Item child rows), unrelated to the global Hotspot
	Package doctype vouchers are generated from. HotspotSite.validate()
	requires at least one, same as creating the site from Desk would."""
	if not _is_admin():
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	doc = frappe.get_doc(
		{
			"doctype": "Hotspot Site",
			"vendor_name": vendor_name,
			"vendor_user": vendor_user,
			"site_name": site_name,
			"ap_mac": ap_mac,
			"authorization_method": authorization_method,
			"phone_number": phone_number,
			"mobile_money_account": mobile_money_account,
			"is_active": 1,
			"enable_online_payment": enable_online_payment,
			"enable_free_trial": enable_free_trial,
			"free_trial_minutes": free_trial_minutes,
			"controller_ip": controller_ip,
			"port": port,
			"controller_id": controller_id,
			"site_id": site_id,
			"omada_username": omada_username,
			"omada_password": omada_password,
			"success_redirect_url": success_redirect_url,
			"radius_client_ip": radius_client_ip,
			"radius_nas_id": radius_nas_id,
			"radius_secret": radius_secret,
			"ap_login_url_template": ap_login_url_template,
		}
	)

	package_rows = json.loads(packages) if isinstance(packages, str) else (packages or [])
	for row in package_rows:
		doc.append(
			"packages",
			{
				"package_name": row.get("package_name"),
				"package_type": row.get("package_type") or "Unlimited",
				"price": row.get("price"),
				"duration_minutes": row.get("duration_minutes"),
			},
		)

	doc.insert(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return {"name": doc.name, "site_name": doc.site_name, "vendor_name": doc.vendor_name}


@frappe.whitelist()
def create_voucher_batch(site, package_name, quantity, prefix=None, expires_on=None, notes=None):
	"""Creates a Hotspot Voucher Batch and immediately generates its vouchers
	-- calls HotspotVoucherBatch.generate_vouchers() directly (see
	bandofy.bandofy.doctype.hotspot_voucher_batch.hotspot_voucher_batch) rather
	than the Desk-only generate_vouchers_for_batch wrapper, which requires a
	"write" permission Website Users don't have; site ownership is already
	verified by _resolve_site_for_write below."""
	site_name = _resolve_site_for_write(site)

	if not package_name or not frappe.db.exists("Hotspot Package", package_name):
		frappe.throw(_("Please choose a valid package."))

	quantity = frappe.utils.cint(quantity)
	if quantity <= 0:
		frappe.throw(_("Quantity must be at least 1."))

	batch = frappe.get_doc(
		{
			"doctype": "Hotspot Voucher Batch",
			"site": site_name,
			"package_name": package_name,
			"quantity": quantity,
			"prefix": prefix,
			"expires_on": expires_on,
			"notes": notes,
		}
	)
	batch.insert(ignore_permissions=True)
	created = batch.generate_vouchers()  # saves + commits internally

	return {"batch": batch.name, "created": created}


STAFF_VOUCHER_FIELDS = [
	"name",
	"staff_name",
	"phone_number",
	"site",
	"status",
	"valid_until",
	"session_minutes",
	"max_devices",
	"use_count",
	"last_used_on",
	"notes",
]


def _get_own_staff_voucher(name):
	"""Loads a Hotspot Staff Voucher, refusing one outside the caller's site."""
	if not name or not frappe.db.exists("Hotspot Staff Voucher", name):
		frappe.throw(_("Staff voucher not found."))

	doc = frappe.get_doc("Hotspot Staff Voucher", name)
	if not _is_admin() and doc.site != _own_site_name():
		frappe.throw(_("Staff voucher not found."), frappe.PermissionError)
	return doc


def _staff_voucher_dict(doc):
	data = {field: doc.get(field) for field in STAFF_VOUCHER_FIELDS}
	data["devices"] = [
		{"client_mac": d.client_mac, "first_used_on": d.first_used_on, "last_used_on": d.last_used_on}
		for d in doc.devices
	]
	return data


@frappe.whitelist()
def get_staff_vouchers(site=None):
	"""Free, reusable staff access codes (see Hotspot Staff Voucher), with
	the devices each one has logged in."""
	site_name = _resolve_site(site)

	names = frappe.get_all(
		"Hotspot Staff Voucher",
		filters={"site": site_name} if site_name else {},
		order_by="staff_name asc",
		pluck="name",
		ignore_permissions=True,
	)
	return [_staff_voucher_dict(frappe.get_doc("Hotspot Staff Voucher", name)) for name in names]


@frappe.whitelist()
def create_staff_voucher(
	site,
	staff_name,
	phone_number=None,
	session_minutes=1440,
	max_devices=1,
	valid_until=None,
	notes=None,
):
	site_name = _resolve_site_for_write(site)
	if not staff_name or not staff_name.strip():
		frappe.throw(_("Staff name is required."))

	doc = frappe.get_doc(
		{
			"doctype": "Hotspot Staff Voucher",
			"site": site_name,
			"staff_name": staff_name.strip(),
			"phone_number": phone_number,
			"session_minutes": frappe.utils.cint(session_minutes),
			"max_devices": frappe.utils.cint(max_devices),
			"valid_until": valid_until,
			"notes": notes,
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return _staff_voucher_dict(doc)


@frappe.whitelist()
def set_staff_voucher_status(name, status):
	if status not in ("Active", "Disabled"):
		frappe.throw(_("Invalid status."))

	doc = _get_own_staff_voucher(name)
	doc.status = status
	doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return _staff_voucher_dict(doc)


@frappe.whitelist()
def reset_staff_voucher_devices(name):
	"""Clears Registered Devices so the code can be used on new phones --
	e.g. when a staff member changes their device."""
	doc = _get_own_staff_voucher(name)
	doc.set("devices", [])
	doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return _staff_voucher_dict(doc)


@frappe.whitelist()
def delete_staff_voucher(name):
	doc = _get_own_staff_voucher(name)
	frappe.delete_doc("Hotspot Staff Voucher", doc.name, ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return {"ok": True}


@frappe.whitelist()
def get_site_devices(site=None):
	"""The site's primary AP plus any additional_devices, merged with live
	Omada status (online/offline/model/ip) by MAC when the site is
	Omada-managed. Fails soft to status "unknown" if the controller can't be
	reached, same as get_omada_live_stats."""
	site_name = _resolve_site(site)
	if not site_name:
		frappe.throw(_("Please choose a site."))

	doc = frappe.get_doc("Hotspot Site", site_name)

	devices = [{"ap_mac": doc.ap_mac, "label": doc.site_name, "is_primary": True, "is_active": True}]
	for row in doc.additional_devices:
		devices.append(
			{
				"ap_mac": row.ap_mac,
				"label": row.label,
				"is_primary": False,
				"is_active": bool(row.is_active),
			}
		)

	if doc.authorization_method == "Omada Controller API":
		try:
			live = omada_service.list_devices(
				omada_host=f"https://{doc.controller_ip}:{doc.port}",
				controller_id=doc.controller_id,
				operator_username=doc.omada_username,
				operator_password=doc.get_password("omada_password"),
				site_id=doc.site_id,
			)
			live_by_mac = {normalize_mac(d["mac"]): d for d in live if d.get("mac")}
			for device in devices:
				match = live_by_mac.get(normalize_mac(device["ap_mac"]))
				if match:
					device.update(
						{"status": match.get("status"), "model": match.get("model"), "ip": match.get("ip")}
					)
				else:
					device["status"] = "unknown"
		except Exception:
			frappe.log_error(
				title="Bandofy Mobile: get_site_devices Omada fetch failed", message=frappe.get_traceback()
			)
			for device in devices:
				device["status"] = "unknown"
	else:
		for device in devices:
			device["status"] = "unknown"

	return devices


@frappe.whitelist()
def add_site_device(site, ap_mac, label=None):
	"""Registers another AP's MAC against this site -- its captive-portal
	traffic/voucher redemptions then roll into this site's dashboard. The
	physical AP still needs to be adopted into the Omada Controller itself
	the normal way; this only teaches bandofy to recognize it."""
	site_name = _resolve_site_for_write(site)
	if not ap_mac or not ap_mac.strip():
		frappe.throw(_("AP MAC Address is required."))

	doc = frappe.get_doc("Hotspot Site", site_name)
	doc.append("additional_devices", {"ap_mac": ap_mac.strip(), "label": label, "is_active": 1})
	doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return {"ok": True}


@frappe.whitelist()
def remove_site_device(site, ap_mac):
	site_name = _resolve_site_for_write(site)
	target = normalize_mac(ap_mac)

	doc = frappe.get_doc("Hotspot Site", site_name)
	remaining = [row for row in doc.additional_devices if normalize_mac(row.ap_mac) != target]
	if len(remaining) == len(doc.additional_devices):
		frappe.throw(_("Device not found on this site."))

	doc.set("additional_devices", remaining)
	doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return {"ok": True}


@frappe.whitelist()
def reboot_site_device(site, ap_mac):
	"""Reboots one Omada-adopted device. Disconnects every client currently
	on it -- the app requires an explicit confirmation before calling this."""
	site_name = _resolve_site_for_write(site)
	doc = frappe.get_doc("Hotspot Site", site_name)

	if doc.authorization_method != "Omada Controller API":
		frappe.throw(_("Device reboot is only available for sites using the Omada Controller API."))

	omada_service.reboot_device(
		omada_host=f"https://{doc.controller_ip}:{doc.port}",
		controller_id=doc.controller_id,
		operator_username=doc.omada_username,
		operator_password=doc.get_password("omada_password"),
		site_id=doc.site_id,
		device_mac=ap_mac,
	)

	return {"ok": True}


@frappe.whitelist()
def get_chat_threads(site=None):
	"""One row per guest device that's messaged this site, newest activity
	first, with the last message preview and how many Guest messages are
	still unread."""
	site_name = _resolve_site(site)
	if not site_name:
		frappe.throw(_("Please choose a site."))

	threads = frappe.db.sql(
		"""
		select client_mac,
			max(creation) as last_message_at,
			sum(case when direction='Guest' and is_read=0 then 1 else 0 end) as unread_count
		from `tabHotspot Chat Message`
		where site=%s
		group by client_mac
		order by last_message_at desc
		""",
		(site_name,),
		as_dict=True,
	)

	for thread in threads:
		last = frappe.db.get_value(
			"Hotspot Chat Message",
			{"site": site_name, "client_mac": thread.client_mac},
			["message", "direction"],
			order_by="creation desc",
			as_dict=True,
		)
		thread["last_message"] = last.message if last else None
		thread["last_direction"] = last.direction if last else None

	return threads


@frappe.whitelist()
def get_chat_thread(site, client_mac):
	"""Full message history with one guest device. Viewing a thread marks
	its unread Guest messages read, mirroring what opening the equivalent
	Desk form already does in hotspot_chat_message.js."""
	site_name = _resolve_site_for_write(site)

	messages = frappe.get_all(
		"Hotspot Chat Message",
		filters={"site": site_name, "client_mac": client_mac},
		fields=["name", "direction", "message", "is_read", "creation"],
		order_by="creation asc",
		ignore_permissions=True,
	)

	unread_names = [m.name for m in messages if m.direction == "Guest" and not m.is_read]
	if unread_names:
		frappe.db.sql(
			"update `tabHotspot Chat Message` set is_read=1 where name in %(names)s",
			{"names": unread_names},
		)
		frappe.db.commit()  # nosemgrep

	return messages


@frappe.whitelist()
def send_chat_reply(site, client_mac, message):
	"""Admin/vendor reply to a guest's captive-portal chat thread -- same
	shape the existing Desk "Reply" custom button produces via
	frappe.client.insert (see hotspot_chat_message.js), as a properly
	site-scoped endpoint a vendor (barred from Desk) can actually reach."""
	site_name = _resolve_site_for_write(site)

	message = (message or "").strip()
	if not message:
		frappe.throw(_("Message cannot be empty."))

	doc = frappe.get_doc(
		{
			"doctype": "Hotspot Chat Message",
			"site": site_name,
			"client_mac": client_mac,
			"direction": "Admin",
			"is_read": 1,
			"message": message[:500],
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return {"name": doc.name, "creation": frappe.utils.get_datetime_str(doc.creation)}


@frappe.whitelist()
def get_site_branding(site=None):
	"""Current captive-portal branding for the Customize Portal screen, plus
	the site's ap_mac -- the live preview needs it to build the real
	wifi_login URL (see www/wifi_login.py's apply_preview_overrides)."""
	site_name = _resolve_site(site)
	if not site_name:
		frappe.throw(_("Please choose a site."))

	return frappe.db.get_value(
		"Hotspot Site",
		site_name,
		["ap_mac", "portal_logo", "portal_tagline", "portal_primary_color", "portal_secondary_color"],
		as_dict=True,
	)


@frappe.whitelist()
def update_site_branding(
	site=None,
	portal_primary_color=None,
	portal_secondary_color=None,
	portal_tagline=None,
	portal_logo=None,
):
	"""Saves the captive portal's branding. Uses targeted db.set_value calls
	rather than a full doc.save() -- these fields are purely cosmetic and
	shouldn't trip HotspotSite.validate()'s unrelated business rules (e.g.
	requiring at least one pricing package)."""
	site_name = _resolve_site_for_write(site)

	values = {
		"portal_primary_color": portal_primary_color,
		"portal_secondary_color": portal_secondary_color,
		"portal_tagline": portal_tagline,
		"portal_logo": portal_logo,
	}
	for fieldname, value in values.items():
		if value is not None:
			frappe.db.set_value("Hotspot Site", site_name, fieldname, value)
	frappe.db.commit()  # nosemgrep

	return {"ok": True}
