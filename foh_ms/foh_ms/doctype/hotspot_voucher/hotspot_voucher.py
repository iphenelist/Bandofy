# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

from frappe.model.document import Document
from frappe.utils import add_to_date


class HotspotVoucher(Document):
	def validate(self):
		self.set_expiry_from_usage()

	def set_expiry_from_usage(self):
		"""Once redeemed, Expires On reflects when the granted access itself
		runs out (Used On + Duration) rather than the pre-redemption
		code-validity deadline it held before that."""
		if self.used_on and self.has_value_changed("used_on"):
			self.expires_on = add_to_date(self.used_on, minutes=self.duration_minutes or 0)
