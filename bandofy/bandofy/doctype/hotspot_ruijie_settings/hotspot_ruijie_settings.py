# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document


class HotspotRuijieSettings(Document):
	def validate(self):
		if self.extra_fields and self.extra_fields.strip():
			try:
				extra = json.loads(self.extra_fields)
			except ValueError:
				frappe.throw(_('Extra Fields must be a JSON object, e.g. {"userip": "{user_ip}"}.'))
			if not isinstance(extra, dict):
				frappe.throw(_('Extra Fields must be a JSON object, e.g. {"userip": "{user_ip}"}.'))

		if self.enabled and not self.get_password("shared_secret", raise_exception=False):
			frappe.throw(_("Set the RADIUS Shared Secret before enabling."))
