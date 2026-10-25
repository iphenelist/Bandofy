import frappe


def execute():
	"""Vendor Name is now a copy of Site Name (HotspotSite.sync_names_from_site_name).
	Copy it on existing sites so the portal and reports show one name. The
	hotspot SSID name is left alone: it is the live Wi-Fi name on the Omada
	Controller and changes when the site is next saved or Omada Setup is re-run."""
	hs = frappe.qb.DocType("Hotspot Site")
	frappe.qb.update(hs).set(hs.vendor_name, hs.site_name).run()
