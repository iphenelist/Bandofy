import frappe


def execute():
	"""Snippe has been replaced by Abliner: repoint the saved gateway settings.

	The old Snippe API key / webhook secret must be replaced with the Abliner
	ones (tsl_live_... / whsec_...) before payments will go through.
	"""
	settings = frappe.get_single("Hotspot Payment Settings")
	if settings.gateway_provider == "Abliner":
		return

	settings.db_set(
		{
			"gateway_provider": "Abliner",
			"base_url": "https://abliner.net/api/v1",
		}
	)
