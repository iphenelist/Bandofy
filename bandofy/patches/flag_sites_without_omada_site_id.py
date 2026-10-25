import frappe

from bandofy.utils import is_omada_site_id


def execute():
	"""The captive portal now finds a Hotspot Site by its Omada Site ID, with
	the AP MAC as fallback. Comment on every active site that has no valid ID
	yet, so the admin can fill it in."""
	hs = frappe.qb.DocType("Hotspot Site")
	rows = frappe.qb.from_(hs).select(hs.name, hs.omada_site_id).where(hs.is_active == 1).run(as_dict=True)
	for row in rows:
		if is_omada_site_id(row.omada_site_id):
			continue
		frappe.get_doc("Hotspot Site", row.name).add_comment(
			"Comment",
			"Bandofy: fill in this site's 24-character Omada Site ID (Details tab). "
			"Customers are matched to the site by it; until then the Access Points table is used.",
		)
