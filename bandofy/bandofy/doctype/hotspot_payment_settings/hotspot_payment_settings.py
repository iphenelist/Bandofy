# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import get_url


class HotspotPaymentSettings(Document):
	def validate(self):
		self.webhook_url_preview = get_url("/api/method/bandofy.api.payment_callback")


def get_settings():
	return frappe.get_single("Hotspot Payment Settings")
