import frappe

from bandofy.utils import normalize_mac


def execute():
	"""Hotspot Site: every AP now lives in one Access Points table (`devices`)
	instead of a primary `ap_mac` field plus `additional_devices`, and Lipa
	Namba is one attached image instead of a table. Runs before Frappe drops
	the orphaned Hotspot Lipa Number doctype, so its rows can still be read."""
	frappe.db.sql(
		"""update `tabHotspot Site Device` set parentfield='devices'
		where parenttype='Hotspot Site' and parentfield='additional_devices'"""
	)

	has_ap_mac = frappe.db.has_column("Hotspot Site", "ap_mac")
	has_lipa = frappe.db.table_exists("Hotspot Lipa Number")

	for site in frappe.get_all("Hotspot Site", fields=["name", "site_name"]):
		if has_ap_mac:
			_move_primary_ap(site)
		if has_lipa:
			_pick_lipa_image(site.name)


def _move_primary_ap(site):
	ap_mac = frappe.db.sql("select ap_mac from `tabHotspot Site` where name=%s", site.name)[0][0]
	rows = frappe.get_all(
		"Hotspot Site Device",
		filters={"parenttype": "Hotspot Site", "parentfield": "devices", "parent": site.name},
		fields=["name", "ap_mac"],
		order_by="idx asc",
	)
	if ap_mac and normalize_mac(ap_mac) not in {normalize_mac(r.ap_mac) for r in rows}:
		doc = frappe.get_doc(
			{
				"doctype": "Hotspot Site Device",
				"parenttype": "Hotspot Site",
				"parentfield": "devices",
				"parent": site.name,
				"ap_mac": ap_mac,
				"label": site.site_name,
				"is_active": 1,
				"idx": 0,
			}
		)
		doc.db_insert()
		rows.insert(0, doc)
	for idx, row in enumerate(rows, start=1):
		frappe.db.set_value("Hotspot Site Device", row.name, "idx", idx, update_modified=False)


def _pick_lipa_image(site_name):
	if frappe.db.get_value("Hotspot Site", site_name, "lipa_namba_image"):
		return
	image = frappe.db.sql(
		"""select image from `tabHotspot Lipa Number`
		where parenttype='Hotspot Site' and parent=%s and ifnull(image, '') != ''
		order by is_default desc, idx asc limit 1""",
		site_name,
	)
	if image:
		frappe.db.set_value("Hotspot Site", site_name, "lipa_namba_image", image[0][0], update_modified=False)
