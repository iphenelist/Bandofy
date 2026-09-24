# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import secrets

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate, nowdate

from bandofy.utils import normalize_mac


class HotspotStaffVoucher(Document):
	def before_insert(self):
		# Runs before naming (autoname is field:voucher_code), and the portal
		# looks codes up stripped + upper-cased -- see bandofy.api.redeem_voucher.
		self.voucher_code = (self.voucher_code or "").strip().upper() or _build_unique_staff_code()

	def validate(self):
		if frappe.db.exists("Hotspot Voucher", self.voucher_code):
			frappe.throw(_("Code {0} is already used by a customer voucher.").format(self.voucher_code))
		if cint(self.session_minutes) <= 0:
			frappe.throw(_("Minutes Per Login must be greater than zero."))

	def check_can_connect(self, client_mac):
		"""Raise if this code may not log ``client_mac`` in right now; returns
		the matching Registered Devices row, or None for a new device."""
		if self.status != "Active":
			frappe.throw(_("This staff voucher has been disabled."))

		if self.valid_until and getdate(self.valid_until) < getdate(nowdate()):
			frappe.throw(_("This staff voucher has expired."))

		target = normalize_mac(client_mac)
		row = next((d for d in self.devices if normalize_mac(d.client_mac) == target), None)

		max_devices = cint(self.max_devices)
		if not row and max_devices and len(self.devices) >= max_devices:
			frappe.throw(
				_("This staff voucher is already in use on {0} device(s). Ask the admin to reset it.").format(
					max_devices
				)
			)

		return row


def _build_unique_staff_code():
	"""8 random digits -- a different length from the 6-digit customer
	voucher codes, so the two can never collide."""
	for _i in range(20):
		code = str(secrets.randbelow(90000000) + 10000000)
		if not frappe.db.exists("Hotspot Staff Voucher", code):
			return code

	frappe.throw(_("Unable to generate a unique voucher code. Please retry."))
