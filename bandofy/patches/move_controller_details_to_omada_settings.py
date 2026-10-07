import frappe

from bandofy.omada_service import OMADA_SITE_ID


def execute():
	"""Hotspot Site no longer stores the Omada controller and operator --
	they live once in Hotspot Omada Settings. Carry over what sites already
	had: the first site's controller and operator fill any empty settings,
	and each site's Omada site ID moves to omada_site_id. (The old columns
	stay in the database, unused, as Frappe doesn't drop them.)"""
	columns = ("controller_ip", "port", "controller_id", "site_id", "omada_username", "omada_password")
	if not all(frappe.db.has_column("Hotspot Site", c) for c in columns):
		return

	sites = frappe.db.sql(
		"""select name, controller_ip, port, controller_id, site_id, omada_username, omada_site_id
		from `tabHotspot Site` order by creation""",
		as_dict=True,
	)

	for site in sites:
		# Only real Omada site IDs (24 hex chars); a stored site *name* such as
		# "Orion" is resolved later (omada_service.site_controller) or linked
		# by Create on Omada.
		if site.site_id and not site.omada_site_id and OMADA_SITE_ID.match(site.site_id):
			frappe.db.set_value(
				"Hotspot Site", site.name, "omada_site_id", site.site_id, update_modified=False
			)

	source = next((s for s in sites if s.controller_ip and s.omada_username), None)
	if not source:
		return

	settings = frappe.get_single("Hotspot Omada Settings")
	values = {}
	if not settings.controller_url:
		values["controller_url"] = f"https://{source.controller_ip}:{source.port or 8043}"
	if not settings.omadac_id and source.controller_id:
		values["omadac_id"] = source.controller_id
	if not settings.operator_name:
		values["operator_name"] = source.omada_username
	if values:
		frappe.db.set_single_value("Hotspot Omada Settings", values)

	if not settings.get_password("operator_password", raise_exception=False):
		from frappe.utils.password import get_decrypted_password, set_encrypted_password

		password = get_decrypted_password(
			"Hotspot Site", source.name, "omada_password", raise_exception=False
		)
		if password:
			set_encrypted_password(
				"Hotspot Omada Settings", "Hotspot Omada Settings", password, "operator_password"
			)
