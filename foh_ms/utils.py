# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import re

import frappe


def normalize_mac(mac):
	"""Compare MACs on hex digits only -- EAPs/controllers are inconsistent
	about ':' vs '-' separators and upper/lower case."""
	return re.sub(r"[^0-9a-fA-F]", "", mac or "").lower()


def find_site_by_ap_mac(ap_mac, fields=None, active_only=True):
	"""Look up a Hotspot Site by AP MAC, tolerant of ':' vs '-' separators
	and case -- used everywhere a captive portal redirect's MAC needs to be
	matched against a Hotspot Site record. Matches either a site's primary
	`ap_mac` field or any MAC registered in its `additional_devices` child
	table (see Hotspot Site Device)."""
	if not ap_mac:
		return None

	target = normalize_mac(ap_mac)
	filters = {"is_active": 1} if active_only else {}
	fields = list(fields) if fields else ["name"]
	if "ap_mac" not in fields:
		fields = [*fields, "ap_mac"]

	sites = frappe.get_all("Hotspot Site", filters=filters, fields=fields)
	for site in sites:
		if normalize_mac(site.ap_mac) == target:
			return site

	device_rows = frappe.get_all(
		"Hotspot Site Device", filters={"is_active": 1}, fields=["parent", "ap_mac"]
	)
	matched_parent = next(
		(row.parent for row in device_rows if normalize_mac(row.ap_mac) == target), None
	)
	if not matched_parent:
		return None

	for site in sites:
		if site.name == matched_parent:
			return site

	# The matching device's site wasn't in the active-sites fetch above (e.g.
	# active_only excluded an inactive site) -- fetch it directly instead.
	if not active_only:
		return frappe.db.get_value("Hotspot Site", matched_parent, fields, as_dict=True)

	return None


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
	the admin/vendor role split foh_ms.mobile_api and the captive portal's
	branding preview override both check against."""
	user = user or frappe.session.user
	return user == "Administrator" or "System Manager" in frappe.get_roles(user)
