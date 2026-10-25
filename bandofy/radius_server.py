# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

"""Bandofy's RADIUS server for Ruijie sites (see bandofy.ruijie).

A Ruijie AC sends the one-time login the portal page submitted to it (or,
for a returning device, its MAC) as an Access-Request. This server asks
:func:`bandofy.ruijie.check_login` and answers Access-Accept with a
Session-Timeout of the remaining paid time, or Access-Reject. Omada sites
never use it.

It is a separate long-running process. Run it next to the bench, e.g. as a
supervisor program or a Procfile line:

    radius: bench --site <site> execute bandofy.radius_server.start

and open UDP 1812 (and 1813 for accounting) to the controllers. Settings
live in Hotspot Ruijie Settings; changes are picked up within a minute.

Controllers are admitted by the shared secret, not by IP: sites behind
mobile-network NAT have changing, shared addresses.
"""

import os
import time

import frappe
from pyrad import packet
from pyrad.dictionary import Dictionary
from pyrad.server import RemoteHost, Server

DICTIONARY_PATH = os.path.join(os.path.dirname(__file__), "radius_dictionary.txt")
REFRESH_SECONDS = 60
ANY_HOST = "0.0.0.0"


class BandofyRadiusServer(Server):
	def __init__(self, site, *args, **kwargs):
		self.site = site
		self.enabled = False
		self.allow_mac_relogin = True
		self._last_refresh = 0
		super().__init__(*args, **kwargs)
		self.refresh()

	def refresh(self):
		"""Reload Hotspot Ruijie Settings, so toggling them in the Desk takes
		effect without restarting this process."""
		self._fresh_transaction()
		settings = frappe.get_doc("Hotspot Ruijie Settings")
		secret = settings.get_password("shared_secret", raise_exception=False)
		self.enabled = bool(settings.enabled and secret)
		self.allow_mac_relogin = bool(settings.allow_mac_relogin)
		# Without a secret there is no way to read the password or sign the
		# reply, so packets are dropped (pyrad: "unknown host").
		self.hosts = {ANY_HOST: RemoteHost(ANY_HOST, secret.encode(), "ruijie")} if secret else {}
		self._last_refresh = time.monotonic()

	def _fresh_transaction(self):
		"""Each request must see the latest payments: end the previous
		database transaction (REPEATABLE READ would otherwise keep showing
		the snapshot from when it began), reconnecting if the connection
		was dropped while idle."""
		try:
			frappe.db.rollback()
			frappe.db.sql("select 1")
		except Exception:
			frappe.destroy()
			frappe.init(site=self.site)
			frappe.connect()

	def _ProcessInput(self, fd):
		if time.monotonic() - self._last_refresh > REFRESH_SECONDS:
			try:
				self.refresh()
			except Exception:
				frappe.logger("bandofy").exception("RADIUS: could not reload settings")
		super()._ProcessInput(fd)

	def HandleAuthPacket(self, pkt):
		reply = self.CreateReplyPacket(pkt)
		reply.code = packet.AccessReject

		if self.enabled:
			try:
				self._fresh_transaction()
				from bandofy.ruijie import check_login

				username = _first(pkt, "User-Name")
				password = pkt.PwDecrypt(pkt["User-Password"][0]) if "User-Password" in pkt else ""
				remaining = check_login(
					username,
					password,
					calling_station_id=_first(pkt, "Calling-Station-Id"),
					allow_mac_relogin=self.allow_mac_relogin,
				)
				if remaining:
					reply.code = packet.AccessAccept
					reply.AddAttribute("Session-Timeout", remaining)
			except Exception:
				reply.code = packet.AccessReject
				frappe.log_error(title="Bandofy RADIUS: Auth Packet Error", message=frappe.get_traceback())
				frappe.db.commit()  # nosemgrep -- persist the error log; there is no request cycle to do it

		self.SendReplyPacket(pkt.fd, reply)

	def HandleAcctPacket(self, pkt):
		# Sessions are timed by Session-Timeout; accounting is acknowledged
		# so the AC doesn't keep retrying.
		self.SendReplyPacket(pkt.fd, self.CreateReplyPacket(pkt))


def _first(pkt, attribute):
	values = pkt.get(attribute) or []
	value = values[0] if values else ""
	return value.decode(errors="replace") if isinstance(value, bytes) else str(value)


def start():
	"""Entrypoint for ``bench --site <site> execute bandofy.radius_server.start``."""
	settings = frappe.get_doc("Hotspot Ruijie Settings")
	bind_ip = settings.bind_ip or "0.0.0.0"
	auth_port = settings.auth_port or 1812
	acct_port = settings.acct_port or 1813

	server = BandofyRadiusServer(
		frappe.local.site,
		authport=auth_port,
		acctport=acct_port,
		dict=Dictionary(DICTIONARY_PATH),
	)
	server.BindToAddress(bind_ip)
	frappe.logger("bandofy").info(
		f"Bandofy RADIUS server listening on {bind_ip}:{auth_port}/{acct_port} (enabled={server.enabled})"
	)
	print(f"Bandofy RADIUS server listening on {bind_ip}:{auth_port}/{acct_port} (enabled={server.enabled})")
	server.Run()
