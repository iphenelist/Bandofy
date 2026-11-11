# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

"""One-time RADIUS logins for Ruijie, generic RADIUS, and Omada RADIUS sites.

Any AP brand that supports RADIUS (Ruijie, Mikrotik, UniFi, Omada RADIUS,
or any generic RADIUS controller) uses this module. The flow:

1. The AP redirects a new client to /landing with its own parameters.
2. Once the customer has paid (or redeemed a voucher, or taken the free
   trial), :func:`issue_login` gives the transaction a one-time password
   valid for the package's duration. The username is the transaction ID.
3. The portal page submits that username and password to the AP's own
   login server, as described by :func:`login_form` and Hotspot Ruijie Settings.
4. The AP asks Bandofy's RADIUS server (bandofy.radius_server), which
   accepts the login with a Session-Timeout of the remaining paid time.
"""

import hmac
import json
import re

import frappe
from frappe.utils import add_to_date, get_datetime, now_datetime
from frappe.utils.password import get_decrypted_password, set_encrypted_password

from bandofy.utils import normalize_mac

PASSWORD_LENGTH = 24


RADIUS_CONTROLLER_TYPES = ("Ruijie", "RADIUS", "Omada RADIUS")


def uses_radius(site):
	"""True for any controller type that authenticates clients via RADIUS.
	``site`` is a Hotspot Site doc or dict."""
	return (site.get("controller_type") or "Omada") in RADIUS_CONTROLLER_TYPES


def is_ruijie(site):
	"""Deprecated alias for uses_radius(). Use uses_radius() for new code."""
	return uses_radius(site)


def issue_login(txn):
	"""Give a Paid transaction its one-time RADIUS password, accepted until
	the package's time runs out. Idempotent: a login already issued keeps
	its password and expiry, so a retried authorization doesn't change the
	credentials a portal page may already be submitting."""
	if txn.get("authorized_until") and get_decrypted_password(
		"Hotspot Transaction", txn.name, "radius_password", raise_exception=False
	):
		return

	password = frappe.generate_hash(length=PASSWORD_LENGTH)
	set_encrypted_password("Hotspot Transaction", txn.name, password, "radius_password")
	until = add_to_date(now_datetime(), minutes=max(int(txn.duration_minutes or 0), 1))
	txn.db_set({"radius_password": "*" * PASSWORD_LENGTH, "authorized_until": until})


def login_form(txn, success_url):
	"""What the portal page submits to the AC's login server for this
	transaction: {action, method, fields}. {username}, {password} and
	{success_url} are filled in here; {user_ip}, {user_mac}, {ac_name},
	{nas_ip}, {ap_mac}, {ssid} and {url} come from the AC's redirect and are
	filled in by the portal page (public/js/wifi_portal/login.js)."""
	settings = frappe.get_cached_doc("Hotspot Ruijie Settings")
	password = get_decrypted_password("Hotspot Transaction", txn.name, "radius_password")

	fields = {
		(settings.username_field or "username"): "{username}",
		(settings.password_field or "password"): "{password}",
	}
	if settings.extra_fields and settings.extra_fields.strip():
		fields.update({str(k): str(v) for k, v in json.loads(settings.extra_fields).items()})

	known = {"{username}": txn.name, "{password}": password, "{success_url}": success_url or ""}

	def fill(value):
		for placeholder, real in known.items():
			value = value.replace(placeholder, real)
		return value

	return {
		"action": fill(settings.login_url or "http://1.1.1.1:8082/login"),
		"method": (settings.login_method or "POST").upper(),
		"fields": {name: fill(value) for name, value in fields.items()},
	}


def check_login(username, password, calling_station_id=None, allow_mac_relogin=True):
	"""The RADIUS server's decision for one Access-Request: the remaining
	seconds of paid time to grant, or None to reject.

	- ``username`` is a transaction ID and ``password`` its one-time
	  password: accepted while the transaction is Paid, its time hasn't run
	  out and its site is an active Ruijie site. When the AC sends the
	  client's MAC (Calling-Station-Id), it must be the transaction's, so a
	  login read off another customer's portal can't be used elsewhere.
	- ``username`` is a MAC address (the AC's dot1x-mab re-login): accepted
	  while that device has unexpired paid time on a Ruijie site, if
	  ``allow_mac_relogin``.
	"""
	username = (username or "").strip()
	if not username:
		return None

	if frappe.db.exists("Hotspot Transaction", username):
		txn = frappe.db.get_value(
			"Hotspot Transaction",
			username,
			["name", "status", "site", "client_mac", "authorized_until"],
			as_dict=True,
		)
		stored = get_decrypted_password(
			"Hotspot Transaction", txn.name, "radius_password", raise_exception=False
		)
		if not (stored and password and hmac.compare_digest(stored, password)):
			return None
		if calling_station_id and txn.client_mac:
			if normalize_mac(calling_station_id) != normalize_mac(txn.client_mac):
				return None
		return _remaining_seconds(txn)

	mac = _as_mac(username)
	if allow_mac_relogin and mac:
		if calling_station_id and normalize_mac(calling_station_id) != mac:
			return None
		candidates = frappe.get_all(
			"Hotspot Transaction",
			filters={"status": "Paid", "authorized_until": [">", now_datetime()]},
			fields=["name", "status", "site", "client_mac", "authorized_until"],
			order_by="authorized_until desc",
			limit_page_length=500,
		)
		for txn in candidates:
			if normalize_mac(txn.client_mac) == mac:
				remaining = _remaining_seconds(txn)
				if remaining:
					return remaining
	return None


def _as_mac(value):
	"""``value`` as 12 lowercase hex digits if it is a MAC address written
	with or without ':', '-' or '.' separators, else None."""
	digits = re.sub(r"[-:.]", "", value or "")
	return digits.lower() if re.fullmatch(r"[0-9A-Fa-f]{12}", digits) else None


def _remaining_seconds(txn):
	if txn.status != "Paid" or not txn.authorized_until:
		return None
	site = frappe.db.get_value("Hotspot Site", txn.site, ["is_active", "controller_type"], as_dict=True)
	if not site or not site.is_active or not uses_radius(site):
		return None
	remaining = int((get_datetime(txn.authorized_until) - now_datetime()).total_seconds())
	return remaining if remaining > 0 else None
