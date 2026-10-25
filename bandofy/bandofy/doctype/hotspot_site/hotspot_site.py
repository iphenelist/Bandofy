# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from bandofy.utils import is_omada_site_id, normalize_mac


class HotspotSite(Document):
	def onload(self):
		# The Omada menu and live AP panels need the Open API; the form hides
		# them when it isn't configured.
		self.set_onload("open_api", self.controller_type != "Ruijie" and open_api_configured())

	def validate(self):
		self.sync_names_from_site_name()
		self.validate_omada_site_id()
		self.validate_ruijie_ac_name()
		self.validate_devices()
		self.validate_vendor_user_uniqueness()
		self.validate_packages()

	def sync_names_from_site_name(self):
		"""Site Name is the one name a site has: it is also the vendor name
		shown on the portal and the hotspot Wi-Fi (SSID) name, so the other
		two fields are kept as copies rather than typed separately."""
		self.site_name = (self.site_name or "").strip()
		if (
			self.controller_type != "Ruijie"
			and self.has_value_changed("site_name")
			and len(self.site_name) > 32
		):
			frappe.throw(_("Site Name is also the Wi-Fi name, so it must be 32 characters or fewer."))
		self.vendor_name = self.site_name
		self.hotspot_ssid_name = self.site_name

	def validate_omada_site_id(self):
		"""The captive portal finds the site by this ID, so a typo would only
		show up when a customer tries to pay. Uniqueness is enforced by the
		field itself."""
		if not self.omada_site_id:
			self.omada_site_id = None  # NULL, not "", so the unique index allows many blanks
			return
		self.omada_site_id = self.omada_site_id.strip()
		# Sites from v1 may still hold an Omada site *name* here, which
		# omada_service resolves through the Open API; only check new values.
		if self.has_value_changed("omada_site_id") and not is_omada_site_id(self.omada_site_id):
			frappe.throw(
				_(
					"Omada Site ID must be the 24-character ID from the Omada Controller "
					"(for example 6538a1f0c3e2b14d2a9f0e77), not the site name."
				)
			)

	def validate_ruijie_ac_name(self):
		"""Ruijie sites are matched by the AC name the controller sends as
		``wlanacname``; blank is stored as NULL so the unique index allows
		many Omada sites without one."""
		self.ruijie_ac_name = (self.ruijie_ac_name or "").strip() or None
		if self.controller_type == "Ruijie" and not self.ruijie_ac_name:
			frappe.throw(_("Enter the Ruijie AC Name: the controller's name as it sends it (wlanacname)."))

	def validate_devices(self):
		"""An AP belongs to exactly one site: no MAC twice in this site's
		Access Points, and none already registered on another site (the
		captive portal finds the site by the AP a customer connects through).
		MACs are compared ignoring ':' vs '-' and case."""
		seen = {}
		for row in self.devices:
			mac = normalize_mac(row.ap_mac)
			if mac in seen:
				frappe.throw(_("Access point {0} is listed twice.").format(frappe.bold(row.ap_mac)))
			seen[mac] = row.ap_mac

		if not seen:
			return
		others = frappe.get_all(
			"Hotspot Site Device",
			filters={"parenttype": "Hotspot Site", "parentfield": "devices", "parent": ["!=", self.name]},
			fields=["parent", "ap_mac"],
		)
		for row in others:
			if normalize_mac(row.ap_mac) in seen:
				frappe.throw(
					_("Access point {0} already belongs to Hotspot Site {1}.").format(
						frappe.bold(seen[normalize_mac(row.ap_mac)]), row.parent
					)
				)

	def validate_vendor_user_uniqueness(self):
		if not self.vendor_user:
			return
		existing = frappe.db.get_value(
			"Hotspot Site", {"vendor_user": self.vendor_user, "name": ["!=", self.name]}, "name"
		)
		if existing:
			frappe.throw(
				_("User {0} is already linked to Hotspot Site {1}").format(
					frappe.bold(self.vendor_user), existing
				)
			)

	def validate_packages(self):
		if not self.packages:
			frappe.throw(_("Please add at least one pricing package."))


def open_api_configured():
	"""Whether Hotspot Omada Settings has Open API keys, which site creation,
	AP adoption, SSID editing, AP status/reboot and bandwidth caps need."""
	return bool(frappe.db.get_single_value("Hotspot Omada Settings", "client_id"))
