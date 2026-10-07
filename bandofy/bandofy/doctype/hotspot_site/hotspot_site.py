# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from bandofy.utils import normalize_mac


class HotspotSite(Document):
	def validate(self):
		self.validate_devices()
		self.validate_vendor_user_uniqueness()
		self.validate_packages()

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
