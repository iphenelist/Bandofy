# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import re
from zoneinfo import available_timezones

import frappe
from frappe import _
from frappe.model.document import Document

DEVICE_PASSWORD_SYMBOLS = "!#$%&*@^"


class HotspotOmadaSettings(Document):
	def validate(self):
		if self.controller_url:
			self.controller_url = self.controller_url.strip().rstrip("/")
			if not self.controller_url.startswith(("http://", "https://")):
				self.controller_url = f"https://{self.controller_url}"

		if self.default_timezone:
			self.default_timezone = _normalize_timezone(self.default_timezone)

		password = (
			self.get_password("device_password", raise_exception=False) if self.device_password else None
		)
		if password and not _is_strong_device_password(password):
			frappe.throw(
				_(
					"Device Account Password must be 10-64 characters with upper and lower case letters, "
					"a number and one of {0}."
				).format(DEVICE_PASSWORD_SYMBOLS)
			)


def _normalize_timezone(value):
	"""Omada wants an IANA zone ID (Africa/Nairobi); a bare city name such as
	"Nairobi" is rejected as "Invalid request parameters"."""
	value = value.strip()
	if "/" in value or value.upper().startswith(("UTC", "GMT")):
		return value
	city = value.replace(" ", "_").lower()
	matches = sorted(tz for tz in available_timezones() if tz.lower().endswith(f"/{city}"))
	if len(matches) != 1:
		frappe.throw(
			_("Time Zone must be an ID like Africa/Nairobi, as Omada stores it (got {0}).").format(value)
		)
	return matches[0]


def _is_strong_device_password(password):
	return (
		10 <= len(password) <= 64
		and re.search(r"[a-z]", password)
		and re.search(r"[A-Z]", password)
		and re.search(r"\d", password)
		and any(c in DEVICE_PASSWORD_SYMBOLS for c in password)
	)


@frappe.whitelist()
def test_connection():
	"""Desk "Test Connection" button: fetches the controller ID, an Open API
	token and the site list, and fills in any empty new-site defaults from
	the first existing site."""
	frappe.only_for("System Manager")
	from bandofy.omada_openapi import test_connection as run

	return run()
