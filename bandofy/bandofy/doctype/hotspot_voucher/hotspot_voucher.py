# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_to_date, now_datetime

# client_mac of a voucher sold by hand (marked Used without being redeemed on
# the captive portal), e.g. internet sold through the ISP router.
MANUAL_SALE = "Manual Sale"


class HotspotVoucher(Document):
	def validate(self):
		self.record_manual_sale()
		self.set_expiry_from_usage()

	def record_manual_sale(self):
		"""A voucher marked Used by hand gets the same Paid Hotspot
		Transaction a portal redemption creates (api.redeem_voucher), so the
		sale shows in the Sales Report and dashboards at the voucher's price.
		Portal redemptions already carry their transaction and are skipped."""
		if self.status != "Used" or self.transaction or not self.has_value_changed("status"):
			return
		self.used_on = self.used_on or now_datetime()
		self.used_by_mac = self.used_by_mac or MANUAL_SALE
		txn = frappe.get_doc(
			{
				"doctype": "Hotspot Transaction",
				"site": self.site,
				"phone_number": "Voucher",
				"client_mac": MANUAL_SALE,
				"package_name": self.package_name,
				"amount": self.price,
				"duration_minutes": self.duration_minutes,
				"status": "Paid",
				"reference_id": f"VOUCHER:{self.name}",
			}
		).insert(ignore_permissions=True)
		self.transaction = txn.name

	def set_expiry_from_usage(self):
		"""Once redeemed, Expires On reflects when the granted access itself
		runs out (Used On + Duration) rather than the pre-redemption
		code-validity deadline it held before that."""
		if self.used_on and self.has_value_changed("used_on"):
			self.expires_on = add_to_date(self.used_on, minutes=self.duration_minutes or 0)
