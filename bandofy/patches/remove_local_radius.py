import frappe


def execute():
	"""Local RADIUS authorization was removed (Omada Controller API only), and
	Hotspot RADIUS Settings was replaced by Hotspot Omada Settings."""
	if frappe.db.exists("DocType", "Hotspot RADIUS Settings"):
		frappe.delete_doc("DocType", "Hotspot RADIUS Settings", force=True, ignore_missing=True)

	radius_sites = (
		frappe.db.sql(
			"select name from `tabHotspot Site` where authorization_method = 'Local RADIUS Server'",
			pluck=True,
		)
		if frappe.db.has_column("Hotspot Site", "authorization_method")
		else []
	)
	if radius_sites:
		frappe.log_error(
			title="Bandofy: Local RADIUS sites need Omada settings",
			message="These sites used Local RADIUS, which no longer exists. Fill in their Omada "
			"Controller details: " + ", ".join(radius_sites),
		)
