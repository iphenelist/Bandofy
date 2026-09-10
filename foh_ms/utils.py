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
	matched against a Hotspot Site record."""
	if not ap_mac:
		return None

	target = normalize_mac(ap_mac)
	filters = {"is_active": 1} if active_only else {}
	fields = list(fields) if fields else ["name"]
	if "ap_mac" not in fields:
		fields = [*fields, "ap_mac"]

	for site in frappe.get_all("Hotspot Site", filters=filters, fields=fields):
		if normalize_mac(site.ap_mac) == target:
			return site

	return None
