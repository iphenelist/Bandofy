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
from bandofy.utils import normalize_mac, site_ap_macs


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
	"""`realtime_site` is this Frappe site's name: Frappe's Socket.IO server
	only delivers events on the `/<site name>` namespace, so the app needs
	it to connect (see the app's RealtimeService)."""
	user = frappe.session.user
	admin = _is_admin(user)

	if admin:
		sites = frappe.get_all(
			"Hotspot Site",
			fields=["name", "vendor_name", "site_name", "is_active"],
			order_by="vendor_name",
			ignore_permissions=True,
		)
		return {"user": user, "role": "admin", "sites": sites, "realtime_site": frappe.local.site}

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
	return {"user": user, "role": "vendor", "sites": [site], "realtime_site": frappe.local.site}


@frappe.whitelist()
def get_sites():
	"""Admin-only: every site, for the site switcher."""
	if not _is_admin():
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	sites = frappe.get_all(
		"Hotspot Site",
		fields=["name", "vendor_name", "site_name", "is_active"],
		order_by="vendor_name",
		ignore_permissions=True,
	)
	return [_with_device_info(site) for site in sites]


def _with_device_info(site):
	"""Adds the site's AP count and first AP (the app builds the portal
	preview link from it) -- a site's APs live in its Access Points table."""
	macs = site_ap_macs(site["name"])
	return {**site, "device_count": len(macs), "first_ap_mac": macs[0] if macs else None}


def _site_dashboard(site_name):
	"""Same numbers www/vendor_dashboard.py renders for one site, as a dict."""
	site = frappe.db.get_value(
		"Hotspot Site",
		site_name,
		["name", "vendor_name", "site_name", "is_active"],
		as_dict=True,
	)

	return {
		"site": _with_device_info(site),
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


VOUCHER_FIELDS = [
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
]

# Statuses the app may set by hand. "Used" is only ever set by an actual
# redemption (api.redeem_voucher), which also creates the Paid transaction
# and fires the voucher-used alert.
MANUAL_VOUCHER_STATUSES = ("Unused", "Blocked", "Expired")


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
		fields=VOUCHER_FIELDS,
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
def set_voucher_status(name, status, expires_on=None):
	"""Block, unblock, or expire a single voucher -- e.g. block a code that
	was lost or sold by mistake. A Used voucher is a record of access already
	granted and can't be changed, so it can never be made redeemable again.
	``expires_on`` (a date, or "" for none) is applied first, so a voucher
	whose old expiry has passed can be made Unused in the same call."""
	if status not in MANUAL_VOUCHER_STATUSES:
		frappe.throw(_("Invalid status."))

	if not name or not frappe.db.exists("Hotspot Voucher", name):
		frappe.throw(_("Voucher not found."))

	doc = frappe.get_doc("Hotspot Voucher", name)
	if not _is_admin() and doc.site != _own_site_name():
		frappe.throw(_("Voucher not found."), frappe.PermissionError)

	if doc.status == "Used":
		frappe.throw(_("This voucher has already been used, so its status can't be changed."))

	if expires_on is not None:
		doc.expires_on = _blank_to_none(expires_on)

	if (
		status == "Unused"
		and doc.expires_on
		and frappe.utils.getdate(doc.expires_on) < frappe.utils.getdate(today())
	):
		frappe.throw(
			_("This voucher's expiry date has passed. Choose a new expiry date to make it usable again.")
		)

	doc.status = status
	doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return {field: doc.get(field) for field in VOUCHER_FIELDS}


@frappe.whitelist()
def get_voucher_batches(site=None):
	"""Stock view: quantity vs generated vs how many are still Unused, so the
	maintainer can see at a glance which batches are running low."""
	site_name = _resolve_site(site)

	filters = {"site": site_name} if site_name else {}
	batches = frappe.get_all(
		"Hotspot Voucher Batch",
		filters=filters,
		fields=[
			"name",
			"site",
			"package_name",
			"status",
			"quantity",
			"generated_count",
			"expires_on",
			"notes",
		],
		order_by="creation desc",
		ignore_permissions=True,
	)

	for batch in batches:
		batch["redeemed_count"] = frappe.db.count("Hotspot Voucher", {"batch": batch.name, "status": "Used"})
		batch["remaining_unused"] = frappe.db.count(
			"Hotspot Voucher", {"batch": batch.name, "status": "Unused"}
		)

	return batches


VOUCHER_BATCH_PRINT_FORMAT = "Hotspot Voucher Batch Cards"


@frappe.whitelist()
def download_voucher_batch_pdf(batch):
	"""The batch's printable voucher cards (the "Hotspot Voucher Batch Cards"
	print format) as a PDF download, for the app's Batch Stock tab. A vendor
	can only download batches of their own site."""
	site = frappe.db.get_value("Hotspot Voucher Batch", batch, "site")
	if not site or (not _is_admin() and site != _own_site_name()):
		frappe.throw(_("Voucher batch not found."), frappe.PermissionError)

	# Website Users have no print permission on the doctype; access was
	# checked above, exactly like every other endpoint in this module.
	frappe.flags.ignore_print_permissions = True
	try:
		pdf = frappe.get_print(
			"Hotspot Voucher Batch", batch, print_format=VOUCHER_BATCH_PRINT_FORMAT, as_pdf=True
		)
	except OSError:
		# pdfkit raises OSError when the wkhtmltopdf binary isn't installed on
		# the server -- its raw message is meaningless to a vendor.
		frappe.log_error(
			title="Bandofy Mobile: voucher PDF generation failed", message=frappe.get_traceback()
		)
		frappe.throw(
			_(
				"The server can't create PDFs yet because wkhtmltopdf isn't installed on it. "
				"Please ask the server administrator to install it."
			)
		)
	finally:
		frappe.flags.ignore_print_permissions = False

	frappe.local.response.filename = f"{batch}.pdf"
	frappe.local.response.filecontent = pdf
	frappe.local.response.type = "pdf"


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
	devices=None,
	phone_number=None,
	mobile_money_account=None,
	enable_online_payment=0,
	enable_free_trial=1,
	free_trial_minutes=15,
	success_redirect_url=None,
	packages=None,
	provision_on_omada=1,
	hotspot_ssid_name=None,
):
	"""Admin-only: create a new Hotspot Site from the app. Field validation
	is left to the doctype's own rules, surfaced through the same
	error-message plumbing as any other failure.

	``packages`` is a JSON-encoded list of {package_name, package_type,
	price, duration_minutes} -- the site's own captive-portal pricing plans
	(Hotspot Package Item child rows), unrelated to the global Hotspot
	Package doctype vouchers are generated from. HotspotSite.validate()
	requires at least one, same as creating the site from Desk would.

	Unless ``provision_on_omada`` is 0, the site is also created on the
	central Omada Controller right away (see bandofy.omada_provisioning) and
	the step report is returned as ``provisioning``. ``devices`` is an
	optional JSON list of AP MACs; usually APs are added later by adopting
	them."""
	if not _is_admin():
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	doc = frappe.get_doc(
		{
			"doctype": "Hotspot Site",
			"vendor_name": vendor_name,
			"vendor_user": vendor_user,
			"site_name": site_name,
			"phone_number": phone_number,
			"mobile_money_account": mobile_money_account,
			"is_active": 1,
			"enable_online_payment": enable_online_payment,
			"enable_free_trial": enable_free_trial,
			"free_trial_minutes": free_trial_minutes,
			"success_redirect_url": success_redirect_url,
			"hotspot_ssid_name": hotspot_ssid_name,
		}
	)

	for mac in _json_arg(devices, []) or []:
		if (mac or "").strip():
			doc.append("devices", {"ap_mac": mac.strip(), "label": mac.strip(), "is_active": 1})

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

	result = {"name": doc.name, "site_name": doc.site_name, "vendor_name": doc.vendor_name}
	if frappe.utils.cint(provision_on_omada):
		from bandofy.omada_provisioning import provision_site

		result["provisioning"] = provision_site(doc.name, hotspot_ssid_name)
	return result


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
	"""Every AP in the site's Access Points table, merged with live Omada
	status (online/offline/model/ip) by MAC. Fails soft to status "unknown" if the controller can't be
	reached, same as get_omada_live_stats."""
	site_name = _resolve_site(site)
	if not site_name:
		frappe.throw(_("Please choose a site."))

	doc = frappe.get_doc("Hotspot Site", site_name)

	devices = [
		{"ap_mac": row.ap_mac, "label": row.label, "is_active": bool(row.is_active)} for row in doc.devices
	]
	if not devices:
		return devices

	try:
		live = omada_service.list_devices(**omada_service.site_controller(doc))
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
	doc.append("devices", {"ap_mac": ap_mac.strip(), "label": label, "is_active": 1})
	doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return {"ok": True}


@frappe.whitelist()
def remove_site_device(site, ap_mac):
	site_name = _resolve_site_for_write(site)
	target = normalize_mac(ap_mac)

	doc = frappe.get_doc("Hotspot Site", site_name)
	remaining = [row for row in doc.devices if normalize_mac(row.ap_mac) != target]
	if len(remaining) == len(doc.devices):
		frappe.throw(_("Device not found on this site."))

	doc.set("devices", remaining)
	doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return {"ok": True}


@frappe.whitelist()
def reboot_site_device(site, ap_mac):
	"""Reboots one Omada-adopted device. Disconnects every client currently
	on it -- the app requires an explicit confirmation before calling this."""
	site_name = _resolve_site_for_write(site)
	doc = frappe.get_doc("Hotspot Site", site_name)

	try:
		omada_service.reboot_device(**omada_service.site_controller(doc), device_mac=ap_mac)
	except omada_service.OmadaAuthError as e:
		frappe.throw(str(e), title=_("Omada Controller"))

	return {"ok": True}


@frappe.whitelist()
def check_omada_connection(site=None):
	"""Step-by-step Omada Controller check run from the server (reachability,
	Controller ID, operator login, client and device lists), so a vendor who
	can't open the controller UI can still see exactly what works. Read-only."""
	site_name = _resolve_site_for_write(site)
	doc = frappe.get_doc("Hotspot Site", site_name)

	try:
		controller = omada_service.site_controller(doc)
	except omada_service.OmadaAuthError as e:
		return [{"step": _("Omada settings"), "ok": False, "detail": str(e)}]
	return omada_service.diagnose(**controller)


def _resolve_chat_site(site, client_mac):
	"""The site a chat thread belongs to: a vendor's own site; for an admin
	the given site, or -- when browsing "All sites" -- the site this guest
	device last messaged."""
	if not _is_admin():
		return _own_site_name()
	if site:
		if not frappe.db.exists("Hotspot Site", site):
			frappe.throw(_("Site not found."))
		return site
	found = frappe.db.get_value(
		"Hotspot Chat Message", {"client_mac": client_mac}, "site", order_by="creation desc"
	)
	if not found:
		frappe.throw(_("Conversation not found."))
	return found


@frappe.whitelist()
def get_chat_threads(site=None):
	"""One row per guest device (per site) that's messaged, newest activity
	first, with the last message preview and how many Guest messages are
	still unread. An admin with no site chosen gets every site's threads."""
	site_name = _resolve_site(site)

	threads = frappe.db.sql(
		f"""
		select m.site, s.site_name, m.client_mac,
			max(m.creation) as last_message_at,
			sum(case when m.direction='Guest' and m.is_read=0 then 1 else 0 end) as unread_count
		from `tabHotspot Chat Message` m
		left join `tabHotspot Site` s on s.name = m.site
		{"where m.site=%(site)s" if site_name else ""}
		group by m.site, s.site_name, m.client_mac
		order by last_message_at desc
		""",
		{"site": site_name},
		as_dict=True,
	)

	for thread in threads:
		last = frappe.db.get_value(
			"Hotspot Chat Message",
			{"site": thread.site, "client_mac": thread.client_mac},
			["message", "direction"],
			order_by="creation desc",
			as_dict=True,
		)
		thread["last_message"] = last.message if last else None
		thread["last_direction"] = last.direction if last else None

	return threads


@frappe.whitelist()
def get_chat_thread(client_mac, site=None):
	"""Full message history with one guest device. Viewing a thread marks
	its unread Guest messages read, mirroring what opening the equivalent
	Desk form already does in hotspot_chat_message.js."""
	site_name = _resolve_chat_site(site, client_mac)

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
def send_chat_reply(client_mac, message, site=None):
	"""Admin/vendor reply to a guest's captive-portal chat thread -- same
	shape the existing Desk "Reply" custom button produces via
	frappe.client.insert (see hotspot_chat_message.js), as a properly
	site-scoped endpoint a vendor (barred from Desk) can actually reach."""
	site_name = _resolve_chat_site(site, client_mac)

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
	one of the site's AP MACs as ``ap_mac`` -- the live preview needs it to
	build the real wifi_login URL (see www/wifi_login.py's
	apply_preview_overrides). None if the site has no APs yet."""
	site_name = _resolve_site(site)
	if not site_name:
		frappe.throw(_("Please choose a site."))

	branding = frappe.db.get_value("Hotspot Site", site_name, ["portal_logo", "portal_tagline"], as_dict=True)
	macs = site_ap_macs(site_name)
	return {**branding, "ap_mac": macs[0] if macs else None}


@frappe.whitelist()
def update_site_branding(
	site=None,
	portal_tagline=None,
	portal_logo=None,
):
	"""Saves the captive portal's branding. Uses targeted db.set_value calls
	rather than a full doc.save() -- these fields are purely cosmetic and
	shouldn't trip HotspotSite.validate()'s unrelated business rules (e.g.
	requiring at least one pricing package)."""
	site_name = _resolve_site_for_write(site)

	values = {
		"portal_tagline": portal_tagline,
		"portal_logo": portal_logo,
	}
	for fieldname, value in values.items():
		if value is not None:
			frappe.db.set_value("Hotspot Site", site_name, fieldname, value)
	frappe.db.commit()  # nosemgrep

	return {"ok": True}


# ---------------------------------------------------------------------------
# Full record editing -- everything a System Manager can edit in Desk, with
# vendors limited to their own site's business settings. Every write goes
# through doc.save() so each doctype's own validate() rules still apply.
# ---------------------------------------------------------------------------


def _json_arg(value, default=None):
	"""Lists/dicts arrive JSON-encoded from the app's form-encoded POST."""
	if value is None or value == "":
		return default
	return json.loads(value) if isinstance(value, str) else value


def _blank_to_none(value):
	return None if value in ("", None) else value


def _require_admin():
	if not _is_admin():
		frappe.throw(_("Not permitted."), frappe.PermissionError)


# What a vendor may change on their own Hotspot Site. Everything else on the
# site (hardware credentials, linkage, activation) is admin-only.
SITE_VENDOR_FIELDS = [
	"vendor_name",
	"site_name",
	"phone_number",
	"mobile_money_account",
	"enable_online_payment",
	"enable_free_trial",
	"free_trial_minutes",
	"enable_sabbath_mode",
	"success_redirect_url",
	"lipa_namba_image",
]
SITE_ADMIN_FIELDS = [
	*SITE_VENDOR_FIELDS,
	"vendor_user",
	"is_active",
]
SITE_READ_ONLY_FOR_VENDOR = ["is_active"]
# Shown to everyone; changed only through the Omada endpoints below.
SITE_OMADA_INFO = ["hotspot_ssid_name", "omada_site_id"]
PACKAGE_ITEM_FIELDS = [
	"package_name",
	"package_type",
	"price",
	"duration_minutes",
	"bandwidth_down_kbps",
	"bandwidth_up_kbps",
]


def _site_settings_dict(doc):
	admin = _is_admin()
	fields = SITE_ADMIN_FIELDS if admin else [*SITE_VENDOR_FIELDS, *SITE_READ_ONLY_FOR_VENDOR]
	data = {"name": doc.name, "can_edit_admin_fields": admin}
	data.update({field: doc.get(field) for field in [*fields, *SITE_OMADA_INFO]})
	data["device_count"] = len(doc.devices)
	data["packages"] = [{field: row.get(field) for field in PACKAGE_ITEM_FIELDS} for row in doc.packages]
	return data


@frappe.whitelist()
def get_site_settings(site=None):
	"""Every editable Hotspot Site setting the caller is allowed to see,
	with its Pricing Packages and Lipa Namba Images tables."""
	site_name = _resolve_site_for_write(site)
	return _site_settings_dict(frappe.get_doc("Hotspot Site", site_name))


@frappe.whitelist()
def update_site_settings(site=None, values=None, packages=None):
	"""Saves site settings. ``values`` is a JSON object of fieldname ->
	value; ``packages`` (JSON list), when passed, replaces the Pricing
	Packages table."""
	site_name = _resolve_site_for_write(site)
	admin = _is_admin()
	allowed = SITE_ADMIN_FIELDS if admin else SITE_VENDOR_FIELDS

	doc = frappe.get_doc("Hotspot Site", site_name)

	for fieldname, value in (_json_arg(values, {}) or {}).items():
		if fieldname in allowed:
			doc.set(fieldname, value)
		else:
			frappe.throw(_("You are not allowed to change {0}.").format(fieldname), frappe.PermissionError)

	package_rows = _json_arg(packages)
	if package_rows is not None:
		doc.set("packages", [])
		for row in package_rows:
			if not (row.get("package_name") or "").strip():
				frappe.throw(_("Every package needs a name."))
			doc.append(
				"packages",
				{
					"package_name": row["package_name"].strip(),
					"package_type": row.get("package_type") or "Unlimited",
					"price": row.get("price") or 0,
					"duration_minutes": row.get("duration_minutes") or 0,
					"bandwidth_down_kbps": row.get("bandwidth_down_kbps") or 0,
					"bandwidth_up_kbps": row.get("bandwidth_up_kbps") or 0,
				},
			)

	doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return _site_settings_dict(doc)


@frappe.whitelist()
def update_site_device(site, ap_mac, label=None, is_active=None):
	"""Rename or (de)activate one of the site's access points."""
	site_name = _resolve_site_for_write(site)
	target = normalize_mac(ap_mac)

	doc = frappe.get_doc("Hotspot Site", site_name)
	row = next((r for r in doc.devices if normalize_mac(r.ap_mac) == target), None)
	if not row:
		frappe.throw(_("Device not found on this site."))

	if label is not None:
		row.label = label
	if is_active is not None:
		row.is_active = frappe.utils.cint(is_active)
	doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return {"ok": True}


# --- Global voucher packages (admin) ---------------------------------------


@frappe.whitelist()
def save_package(package_name, package_type, price, duration_minutes, name=None):
	"""Create a Hotspot Package, or update an existing one (``name``). The
	package name is the record's ID, so it can't be renamed here."""
	_require_admin()

	if name:
		doc = frappe.get_doc("Hotspot Package", name)
	else:
		doc = frappe.new_doc("Hotspot Package")
		doc.package_name = (package_name or "").strip()

	doc.package_type = package_type
	doc.price = frappe.utils.flt(price)
	doc.duration_minutes = frappe.utils.cint(duration_minutes)
	doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return {
		"name": doc.name,
		"package_type": doc.package_type,
		"price": doc.price,
		"duration_minutes": doc.duration_minutes,
	}


@frappe.whitelist()
def delete_package(name):
	"""Fails with Frappe's own message if vouchers or batches still use it."""
	_require_admin()
	frappe.delete_doc("Hotspot Package", name, ignore_permissions=True)
	frappe.db.commit()  # nosemgrep
	return {"ok": True}


# --- Portal ads -------------------------------------------------------------

AD_FIELDS = [
	"name",
	"title",
	"is_active",
	"site",
	"display_order",
	"image",
	"target_url",
	"description",
	"phone_number",
	"start_date",
	"end_date",
	"views_count",
]
AD_EDITABLE_FIELDS = [f for f in AD_FIELDS if f not in ("name", "views_count")]


def _get_own_ad(name):
	if not name or not frappe.db.exists("Hotspot Ad", name):
		frappe.throw(_("Ad not found."))
	doc = frappe.get_doc("Hotspot Ad", name)
	if not _is_admin() and doc.site != _own_site_name():
		frappe.throw(_("Ad not found."), frappe.PermissionError)
	return doc


@frappe.whitelist()
def get_ads(site=None):
	"""Captive-portal ads. A vendor sees their own site's ads; an admin sees
	the chosen site's ads plus global ones (no site), or every ad."""
	site_name = _resolve_site(site)
	filters = {"site": ["in", [site_name, ""]]} if site_name else {}
	if not _is_admin():
		filters = {"site": site_name}

	ads = frappe.get_all(
		"Hotspot Ad",
		filters=filters,
		fields=AD_FIELDS,
		order_by="display_order asc, creation asc",
		ignore_permissions=True,
	)
	for ad in ads:
		ad["views_count"] = frappe.db.count("Hotspot Ad View Log", {"ad": ad.name})
	return ads


@frappe.whitelist()
def save_ad(values, name=None):
	"""Create or update an ad from a JSON object of its fields. A vendor's ad
	is always pinned to their own site; only an admin can make a global ad
	(blank site) or place one on another site."""
	data = _json_arg(values, {}) or {}
	doc = _get_own_ad(name) if name else frappe.new_doc("Hotspot Ad")

	for fieldname in AD_EDITABLE_FIELDS:
		if fieldname in data:
			value = data[fieldname]
			doc.set(
				fieldname, _blank_to_none(value) if fieldname in ("start_date", "end_date", "site") else value
			)

	if not _is_admin():
		doc.site = _own_site_name()
	elif doc.site and not frappe.db.exists("Hotspot Site", doc.site):
		frappe.throw(_("Site not found."))

	doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return {field: doc.get(field) for field in AD_FIELDS}


@frappe.whitelist()
def delete_ad(name):
	doc = _get_own_ad(name)
	frappe.db.delete("Hotspot Ad View Log", {"ad": doc.name})
	frappe.delete_doc("Hotspot Ad", doc.name, ignore_permissions=True)
	frappe.db.commit()  # nosemgrep
	return {"ok": True}


# --- Staff vouchers, vouchers, batches --------------------------------------


@frappe.whitelist()
def update_staff_voucher(
	name,
	staff_name=None,
	phone_number=None,
	session_minutes=None,
	max_devices=None,
	valid_until=None,
	notes=None,
):
	"""Edit a staff voucher's details. An empty string clears an optional
	field (the app can't send null)."""
	doc = _get_own_staff_voucher(name)

	if staff_name is not None:
		if not staff_name.strip():
			frappe.throw(_("Staff name is required."))
		doc.staff_name = staff_name.strip()
	if phone_number is not None:
		doc.phone_number = phone_number
	if session_minutes is not None:
		doc.session_minutes = frappe.utils.cint(session_minutes)
	if max_devices is not None:
		doc.max_devices = frappe.utils.cint(max_devices)
	if valid_until is not None:
		doc.valid_until = _blank_to_none(valid_until)
	if notes is not None:
		doc.notes = notes

	doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return _staff_voucher_dict(doc)


@frappe.whitelist()
def set_voucher_expiry(name, expires_on=None):
	"""Change (or clear, with "") one unused voucher's expiry date."""
	if not name or not frappe.db.exists("Hotspot Voucher", name):
		frappe.throw(_("Voucher not found."))

	doc = frappe.get_doc("Hotspot Voucher", name)
	if not _is_admin() and doc.site != _own_site_name():
		frappe.throw(_("Voucher not found."), frappe.PermissionError)
	if doc.status == "Used":
		frappe.throw(_("This voucher has already been used, so it can't be changed."))

	doc.expires_on = _blank_to_none(expires_on)
	doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return {field: doc.get(field) for field in VOUCHER_FIELDS}


@frappe.whitelist()
def update_voucher_batch(name, notes=None, expires_on=None):
	"""Edit a batch's notes and expiry date. A new expiry date is also
	applied to the batch's still-Unused vouchers -- they were generated with
	the old one, and the portal checks each voucher's own date."""
	site = frappe.db.get_value("Hotspot Voucher Batch", name, "site")
	if not site or (not _is_admin() and site != _own_site_name()):
		frappe.throw(_("Voucher batch not found."), frappe.PermissionError)

	doc = frappe.get_doc("Hotspot Voucher Batch", name)
	if notes is not None:
		doc.notes = notes
	if expires_on is not None:
		doc.expires_on = _blank_to_none(expires_on)
		frappe.db.set_value(
			"Hotspot Voucher", {"batch": doc.name, "status": "Unused"}, "expires_on", doc.expires_on
		)
	doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return {"name": doc.name, "notes": doc.notes, "expires_on": doc.expires_on}


# --- Transactions -----------------------------------------------------------

TRANSACTION_DETAIL_FIELDS = [
	"name",
	"site",
	"status",
	"reference_id",
	"phone_number",
	"client_mac",
	"ap_mac",
	"ssid_name",
	"package_name",
	"amount",
	"duration_minutes",
	"omada_authorized",
	"creation",
	"modified",
]


@frappe.whitelist()
def get_transaction(name):
	site = frappe.db.get_value("Hotspot Transaction", name, "site")
	if not site or (not _is_admin() and site != _own_site_name()):
		frappe.throw(_("Transaction not found."), frappe.PermissionError)
	return frappe.db.get_value("Hotspot Transaction", name, TRANSACTION_DETAIL_FIELDS, as_dict=True)


@frappe.whitelist()
def set_transaction_status(name, status):
	"""Admin-only manual reconciliation of a stuck Pending transaction.
	Marking it Paid goes through the same path as a confirmed payment, so
	the customer's device is authorized too."""
	_require_admin()
	if status not in ("Paid", "Failed"):
		frappe.throw(_("Invalid status."))

	txn = frappe.get_doc("Hotspot Transaction", name)
	if txn.status != "Pending":
		frappe.throw(_("Only Pending transactions can be changed."))

	if status == "Paid":
		from bandofy.api import _mark_transaction_paid

		_mark_transaction_paid(txn, txn.reference_id, frappe.get_single("Hotspot Payment Settings"))
	else:
		txn.status = "Failed"
		txn.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep

	return get_transaction(name)


# --- Global settings singles (admin) ----------------------------------------

SETTINGS_DOCTYPES = {
	"payment": "Hotspot Payment Settings",
	"omada": "Hotspot Omada Settings",
}
SETTINGS_SKIP_TYPES = ("Section Break", "Column Break", "Tab Break", "HTML", "Button")


def _settings_dict(doctype):
	meta = frappe.get_meta(doctype)
	doc = frappe.get_single(doctype)
	fields = []
	for df in meta.fields:
		if df.fieldtype in SETTINGS_SKIP_TYPES:
			continue
		is_password = df.fieldtype == "Password"
		fields.append(
			{
				"fieldname": df.fieldname,
				"label": df.label,
				"fieldtype": df.fieldtype,
				"options": df.options,
				"description": df.description,
				"read_only": bool(df.read_only),
				"value": None if is_password else doc.get(df.fieldname),
				"is_set": bool(doc.get(df.fieldname)) if is_password else None,
			}
		)
	return {"doctype": doctype, "fields": fields}


@frappe.whitelist()
def get_settings(kind):
	"""Payment gateway or Omada controller settings, with field metadata so the
	app can render the form. Passwords are never sent back."""
	_require_admin()
	if kind not in SETTINGS_DOCTYPES:
		frappe.throw(_("Unknown settings."))
	return _settings_dict(SETTINGS_DOCTYPES[kind])


@frappe.whitelist()
def update_settings(kind, values):
	"""A blank Password value leaves the stored secret unchanged."""
	_require_admin()
	if kind not in SETTINGS_DOCTYPES:
		frappe.throw(_("Unknown settings."))

	doctype = SETTINGS_DOCTYPES[kind]
	meta = frappe.get_meta(doctype)
	doc = frappe.get_single(doctype)
	for fieldname, value in (_json_arg(values, {}) or {}).items():
		df = meta.get_field(fieldname)
		if not df or df.read_only or df.fieldtype in SETTINGS_SKIP_TYPES:
			continue
		if df.fieldtype == "Password" and not value:
			continue
		doc.set(fieldname, value)
	doc.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return _settings_dict(doctype)


# --- Reports ----------------------------------------------------------------


@frappe.whitelist()
def get_sales_report(site=None, from_date=None, to_date=None):
	"""The Desk "Hotspot Sales Report" (same numbers, same rules: Paid only,
	staff logins excluded) plus a revenue-by-package breakdown, shaped for
	the app's report screen. A vendor always gets their own site."""
	from bandofy.bandofy.report.hotspot_sales_report.hotspot_sales_report import execute

	site_name = _resolve_site(site)
	to_date = to_date or today()
	from_date = from_date or frappe.utils.add_days(to_date, -29)

	_columns, data, _message, chart, summary = execute(
		{"from_date": from_date, "to_date": to_date, "site": site_name}
	)

	rows = [r for r in data if not r.get("bold")]
	totals = {
		"transactions": sum(frappe.utils.cint(r.get("total_transactions")) for r in rows),
		"mobile_money": sum(frappe.utils.cint(r.get("mobile_money_transactions")) for r in rows),
		"vouchers": sum(frappe.utils.cint(r.get("voucher_transactions")) for r in rows),
		"revenue": sum(frappe.utils.flt(r.get("total_revenue")) for r in rows),
	}
	totals["avg_per_day"] = next((s["value"] for s in summary if s.get("label") == _("Avg Revenue / Day")), 0)

	by_package = frappe.db.sql(
		f"""
		select coalesce(package_name, '') as package_name, count(name) as transactions, sum(amount) as revenue
		from `tabHotspot Transaction`
		where status = 'Paid'
			and coalesce(reference_id, '') not like 'STAFF:%%'
			and date(creation) between %(from_date)s and %(to_date)s
			{"and site = %(site)s" if site_name else ""}
		group by package_name
		order by revenue desc
		""",
		{"from_date": from_date, "to_date": to_date, "site": site_name},
		as_dict=True,
	)

	labels = chart["data"]["labels"]
	values = chart["data"]["datasets"][0]["values"]

	return {
		"from_date": str(from_date),
		"to_date": str(to_date),
		"site": site_name,
		"totals": totals,
		"trend": [{"date": d, "revenue": v} for d, v in zip(labels, values, strict=False)],
		"rows": [
			{
				"date": str(r.get("date")),
				"site": r.get("site"),
				"vendor_name": r.get("vendor_name"),
				"transactions": r.get("total_transactions"),
				"mobile_money": r.get("mobile_money_transactions"),
				"vouchers": r.get("voucher_transactions"),
				"revenue": r.get("total_revenue"),
			}
			for r in rows
		],
		"by_package": by_package,
	}


# --- Alert catch-up feed ----------------------------------------------------

ACTIVITY_MAX_AGE_HOURS = 24


@frappe.whitelist()
def get_activity(since=None, limit=50):
	"""Voucher redemptions, mobile money payments and guest chat messages
	after ``since`` (server-time datetime string), oldest first -- the same
	payloads the realtime socket pushes (see bandofy.realtime), so the app's
	background service can catch up on anything it missed while it was
	disconnected. Never looks back more than ACTIVITY_MAX_AGE_HOURS."""
	from bandofy.realtime import chat_message_payload, payment_received_payload, voucher_used_payload

	site_name = _resolve_site(site=None)
	floor = frappe.utils.add_to_date(frappe.utils.now_datetime(), hours=-ACTIVITY_MAX_AGE_HOURS)
	since = max(frappe.utils.get_datetime(since), floor) if since else floor
	limit = min(frappe.utils.cint(limit) or 50, 200)
	scope = {"site": site_name} if site_name else {}

	events = []
	for name in frappe.get_all(
		"Hotspot Voucher",
		filters={**scope, "status": "Used", "used_on": [">", since]},
		pluck="name",
		order_by="used_on desc",
		limit_page_length=limit,
		ignore_permissions=True,
	):
		events.append(
			{"type": "voucherUsed", "payload": voucher_used_payload(frappe.get_doc("Hotspot Voucher", name))}
		)

	for name in frappe.get_all(
		"Hotspot Transaction",
		filters={
			**scope,
			"status": "Paid",
			"modified": [">", since],
			"phone_number": ["not in", ["Voucher", "Staff", "Free Trial"]],
		},
		pluck="name",
		order_by="modified desc",
		limit_page_length=limit,
		ignore_permissions=True,
	):
		events.append(
			{
				"type": "paymentReceived",
				"payload": payment_received_payload(frappe.get_doc("Hotspot Transaction", name)),
			}
		)

	for name in frappe.get_all(
		"Hotspot Chat Message",
		filters={**scope, "direction": "Guest", "creation": [">", since]},
		pluck="name",
		order_by="creation desc",
		limit_page_length=limit,
		ignore_permissions=True,
	):
		events.append(
			{
				"type": "newChatMessage",
				"payload": chat_message_payload(frappe.get_doc("Hotspot Chat Message", name)),
			}
		)

	events.sort(key=lambda e: e["payload"]["timestamp"] or "")
	return {
		"server_time": frappe.utils.get_datetime_str(frappe.utils.now_datetime()),
		"events": events[-limit:],
	}


# --- Central Omada Controller (bandofy.omada_provisioning) -----------------
# Admins create/link sites on the controller; a vendor can adopt devices and
# manage SSIDs on their own site.


def _omada_call(fn, *args, **kwargs):
	"""Runs an Omada operation, turning controller errors into a normal
	user-facing error message."""
	from bandofy.omada_openapi import OmadaApiError

	try:
		return fn(*args, **kwargs)
	except OmadaApiError as e:
		frappe.throw(str(e), title=_("Omada Controller"))


@frappe.whitelist()
def test_omada_connection():
	_require_admin()
	from bandofy.omada_openapi import test_connection

	return _omada_call(test_connection)


@frappe.whitelist()
def provision_omada_site(site=None, ssid_name=None):
	"""Creates (or links and completes) the site on the central controller:
	site, open hotspot SSID, Bandofy portal, operator access. Returns the
	step report [{step, ok, detail}]."""
	_require_admin()
	site_name = _resolve_site_for_write(site)
	from bandofy.omada_provisioning import provision_site

	return provision_site(site_name, ssid_name)


@frappe.whitelist()
def get_pending_devices(site=None):
	"""APs the controller has found that are waiting to be adopted."""
	from bandofy.omada_provisioning import list_pending_devices

	return _omada_call(list_pending_devices, _resolve_site_for_write(site))


@frappe.whitelist()
def adopt_omada_device(mac, site=None, username=None, password=None):
	from bandofy.omada_provisioning import adopt_device

	return _omada_call(adopt_device, _resolve_site_for_write(site), mac, username or None, password or None)


@frappe.whitelist()
def get_omada_ssids(site=None):
	from bandofy.omada_provisioning import list_ssids

	return _omada_call(list_ssids, _resolve_site_for_write(site))


@frappe.whitelist()
def save_omada_ssid(name, site=None, ssid_id=None):
	"""Renames an SSID (``ssid_id``) or creates a new open one on the
	Bandofy portal."""
	from bandofy.omada_provisioning import save_ssid

	return _omada_call(save_ssid, _resolve_site_for_write(site), name, ssid_id or None)


@frappe.whitelist()
def delete_omada_ssid(ssid_id, site=None):
	from bandofy.omada_provisioning import delete_ssid

	return _omada_call(delete_ssid, _resolve_site_for_write(site), ssid_id)
