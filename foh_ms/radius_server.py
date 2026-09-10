# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

"""Independent local RADIUS authentication server for standalone TP-Link
EAPs that have no Omada Controller.

This is a separate integration path from foh_ms.api.authorize_mac_on_omada
(which calls the Omada Controller's REST API) and does not modify or
replace it. It is only consulted for Hotspot Sites whose
``authorization_method`` is "Local RADIUS Server", and it only answers
Access-Requests while Hotspot RADIUS Settings has "Enable Local RADIUS
Authorization" checked -- while disabled every request is rejected.

On the EAP's Portal page this corresponds to:
    Authentication Type: External RADIUS Server
    RADIUS Server IP:    <this machine's IP>
    RADIUS Port:         1812 (default)
    RADIUS Password:     the site's "RADIUS Shared Secret"
    NAS ID:              the site's "RADIUS NAS Identifier"
    Portal Customization: External Web Portal

Run as a long-lived process, e.g. from the Procfile:

    radius: bench --site <site> execute foh_ms.radius_server.start
"""

import hmac
import os
import time

import frappe
from frappe.utils import get_datetime, now_datetime
from pyrad import packet
from pyrad.dictionary import Dictionary
from pyrad.server import RemoteHost, Server

DICTIONARY_PATH = os.path.join(os.path.dirname(__file__), "radius_dictionary.txt")


class FohRadiusServer(Server):
	def __init__(self, refresh_interval, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.refresh_interval = refresh_interval or 60
		self._last_refresh = 0
		self._enabled = False
		self.refresh_hosts()

	def refresh_hosts(self):
		"""Reload the enabled flag and the RADIUS-mode site/secret map from
		the database, so toggling settings in the Desk takes effect without
		restarting this process."""
		settings = frappe.get_single("Hotspot RADIUS Settings")
		self._enabled = bool(settings.enabled)
		self.refresh_interval = settings.refresh_interval_seconds or 60

		hosts = {}
		if self._enabled:
			sites = frappe.get_all(
				"Hotspot Site",
				filters=[
					["authorization_method", "=", "Local RADIUS Server"],
					["is_active", "=", 1],
					["radius_client_ip", "is", "set"],
					["radius_client_ip", "!=", ""],
				],
				fields=["name", "radius_client_ip"],
			)
			for site in sites:
				secret = frappe.utils.password.get_decrypted_password(
					"Hotspot Site", site.name, "radius_secret", raise_exception=False
				)
				if secret:
					hosts[site.radius_client_ip] = RemoteHost(
						site.radius_client_ip, secret.encode("utf-8"), site.name
					)

		self.hosts = hosts
		self._last_refresh = time.time()

	def _maybe_refresh(self):
		if time.time() - self._last_refresh > self.refresh_interval:
			self.refresh_hosts()

	def HandleAuthPacket(self, pkt):
		self._maybe_refresh()

		reply = self.CreateReplyPacket(pkt)
		reply.code = packet.AccessReject

		if self._enabled:
			try:
				username = (pkt.get("User-Name") or [""])[0]
				raw_password = pkt.PwDecrypt(pkt["User-Password"][0]) if "User-Password" in pkt else ""
				session = validate_session(username, raw_password)
				if session:
					reply.code = packet.AccessAccept
					reply.AddAttribute("Session-Timeout", session["remaining_seconds"])
			except Exception:
				frappe.log_error(
					title="FOH-MS RADIUS: Auth Packet Error", message=frappe.get_traceback()
				)
				frappe.db.commit()  # nosemgrep -- persist the error log; no request cycle to do it for us
				reply.code = packet.AccessReject

		self.SendReplyPacket(pkt.fd, reply)

	def HandleAcctPacket(self, pkt):
		# Accounting isn't wired up to anything yet; just acknowledge so the
		# EAP doesn't keep retrying if "RADIUS Accounting" is enabled on it.
		reply = self.CreateReplyPacket(pkt)
		self.SendReplyPacket(pkt.fd, reply)


def validate_session(username, password):
	"""Check (username, password) against a still-valid, Paid Hotspot
	Transaction. ``username`` is the Hotspot Transaction name and
	``password`` is the one-time token foh_ms.api generates once a
	RADIUS-mode site's transaction is confirmed Paid.
	"""
	if not (username and password):
		return None
	if not frappe.db.exists("Hotspot Transaction", username):
		return None

	txn = frappe.db.get_value(
		"Hotspot Transaction",
		username,
		["status", "radius_token", "authorized_until"],
		as_dict=True,
	)
	if not txn or txn.status != "Paid" or not txn.radius_token:
		return None
	if not hmac.compare_digest(txn.radius_token, password):
		return None
	if not txn.authorized_until:
		return None

	remaining = (get_datetime(txn.authorized_until) - now_datetime()).total_seconds()
	if remaining <= 0:
		return None

	return {"remaining_seconds": int(remaining)}


def start(bind_ip=None, auth_port=None, acct_port=None):
	"""Entrypoint for ``bench execute foh_ms.radius_server.start``."""
	settings = frappe.get_single("Hotspot RADIUS Settings")
	dictionary = Dictionary(DICTIONARY_PATH)

	resolved_bind_ip = bind_ip or settings.bind_ip or "0.0.0.0"
	resolved_auth_port = auth_port or settings.auth_port or 1812
	resolved_acct_port = acct_port or settings.acct_port or 1813

	srv = FohRadiusServer(
		settings.refresh_interval_seconds,
		addresses=[resolved_bind_ip],
		authport=resolved_auth_port,
		acctport=resolved_acct_port,
		dict=dictionary,
	)
	srv.BindToAddress(resolved_bind_ip)

	frappe.logger("foh_ms").info(
		f"FOH-MS RADIUS server listening on {resolved_bind_ip}:{resolved_auth_port} "
		f"(enabled={bool(settings.enabled)})"
	)
	srv.Run()
