# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import re

import frappe
from frappe.utils import now_datetime

SABBATH_START_HOUR = 18  # Friday 18:00 ...
SABBATH_END_HOUR = 18  # ... to Saturday 18:00, system timezone


def normalize_mac(mac):
	"""Compare MACs on hex digits only -- EAPs/controllers are inconsistent
	about ':' vs '-' separators and upper/lower case."""
	return re.sub(r"[^0-9a-fA-F]", "", mac or "").lower()


def find_site_by_ap_mac(ap_mac, fields=None, active_only=True):
	"""Look up the Hotspot Site an AP belongs to, tolerant of ':' vs '-'
	separators and case -- used everywhere a captive portal redirect's MAC
	needs to be matched to a site. Matches any active row of a site's Access
	Points table (Hotspot Site Device, parentfield ``devices``)."""
	if not ap_mac:
		return None

	target = normalize_mac(ap_mac)
	device_rows = frappe.get_all(
		"Hotspot Site Device",
		filters={"parenttype": "Hotspot Site", "parentfield": "devices", "is_active": 1},
		fields=["parent", "ap_mac"],
	)
	site_name = next((row.parent for row in device_rows if normalize_mac(row.ap_mac) == target), None)
	if not site_name:
		return None

	filters = {"name": site_name}
	if active_only:
		filters["is_active"] = 1
	return frappe.db.get_value("Hotspot Site", filters, list(fields) if fields else ["name"], as_dict=True)


def site_ap_macs(site_name, active_only=True):
	"""The MACs in a site's Access Points table, in table order."""
	filters = {"parenttype": "Hotspot Site", "parentfield": "devices", "parent": site_name}
	if active_only:
		filters["is_active"] = 1
	return frappe.get_all("Hotspot Site Device", filters=filters, pluck="ap_mac", order_by="idx asc")


def has_used_free_trial(site_name, client_mac):
	"""Whether this device (by MAC, tolerant of ':' vs '-' and case) has
	already claimed the one-time free trial on this site. The free trial's
	own Hotspot Transaction record (phone_number="Free Trial") *is* the
	registration -- no separate tracking doctype needed."""
	if not client_mac:
		return False

	target = normalize_mac(client_mac)
	macs = frappe.get_all(
		"Hotspot Transaction",
		filters={"site": site_name, "phone_number": "Free Trial"},
		pluck="client_mac",
	)
	return any(normalize_mac(mac) == target for mac in macs)


def is_admin_user(user=None):
	"""True for Administrator or any user with the System Manager role --
	the admin/vendor role split bandofy.mobile_api and the captive portal's
	branding preview override both check against."""
	user = user or frappe.session.user
	return user == "Administrator" or "System Manager" in frappe.get_roles(user)


def is_sabbath_now(site, now=None):
	"""Whether purchases are paused for the weekly Sabbath on this site:
	``enable_sabbath_mode`` is ticked and it is Friday 18:00 - Saturday
	18:00 (system timezone). Only new sales are blocked -- devices already
	authorized keep their remaining time. ``site`` is a Hotspot Site name,
	doc or dict carrying ``enable_sabbath_mode``."""
	if isinstance(site, str):
		enabled = frappe.db.get_value("Hotspot Site", site, "enable_sabbath_mode")
	else:
		enabled = site.get("enable_sabbath_mode")
	if not enabled:
		return False

	now = now or now_datetime()
	weekday = now.weekday()  # Monday=0 ... Friday=4, Saturday=5
	return (weekday == 4 and now.hour >= SABBATH_START_HOUR) or (weekday == 5 and now.hour < SABBATH_END_HOUR)
