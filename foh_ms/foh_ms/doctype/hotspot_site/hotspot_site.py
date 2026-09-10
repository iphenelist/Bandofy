# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class HotspotSite(Document):
	def validate(self):
		self.validate_ap_mac_uniqueness()
		self.validate_vendor_user_uniqueness()
		self.validate_packages()

	def validate_ap_mac_uniqueness(self):
		if not self.ap_mac:
			return
		existing = frappe.db.get_value(
			"Hotspot Site", {"ap_mac": self.ap_mac, "name": ["!=", self.name]}, "name"
		)
		if existing:
			frappe.throw(
				_("Access Point MAC {0} is already assigned to Hotspot Site {1}").format(
					frappe.bold(self.ap_mac), existing
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
