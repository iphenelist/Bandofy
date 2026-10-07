import json

import frappe
from frappe.utils import now_datetime

# Hotspot Site fields v2.0.0 removes or moves (old columns are left in the
# database by Frappe, but they're no longer on the form or used).
OLD_SITE_FIELDS = (
	"ap_mac",
	"authorization_method",
	"controller_ip",
	"port",
	"controller_id",
	"site_id",
	"omada_username",
	"radius_client_ip",
	"radius_nas_id",
	"ap_login_url_template",
	"portal_primary_color",
	"portal_secondary_color",
)


def execute():
	"""Before v2.0.0 changes any doctype: save everything it removes or
	reshapes to a private JSON file (Files > bandofy_v1_backup_*.json, System
	Manager only), so nothing from the old version is lost even where v2 has
	no place for it -- e.g. extra Lipa Namba images, whose table Frappe drops
	during this migrate, or the deleted Hotspot RADIUS Settings.

	Passwords are not copied into the file: Frappe keeps them encrypted in
	its __Auth table, which this upgrade doesn't touch."""
	if not frappe.db.table_exists("Hotspot Site"):
		return

	backup = {
		"created": str(now_datetime()),
		"note": "Bandofy v1 data saved before the v2.0.0 upgrade. Passwords stay encrypted in __Auth.",
		"sites": _sites(),
		"site_devices": _rows(
			"Hotspot Site Device", ("parent", "parentfield", "idx", "ap_mac", "label", "is_active")
		),
		"lipa_namba_images": _rows("Hotspot Lipa Number", ("parent", "idx", "label", "image", "is_default")),
		"site_packages": _rows(
			"Hotspot Package Item",
			("parent", "idx", "package_name", "package_type", "price", "duration_minutes"),
		),
		"radius_settings": _single("Hotspot RADIUS Settings"),
		"payment_settings": _single("Hotspot Payment Settings"),
	}

	if not any(backup[k] for k in ("sites", "site_devices", "lipa_namba_images", "radius_settings")):
		return

	name = f"bandofy_v1_backup_{now_datetime():%Y%m%d_%H%M%S}.json"
	frappe.get_doc(
		{
			"doctype": "File",
			"file_name": name,
			"is_private": 1,
			"content": json.dumps(backup, indent=1, default=str),
		}
	).insert(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep -- keep the backup even if a later patch fails


def _sites():
	columns = ["name", "site_name", "vendor_name"] + [
		c for c in OLD_SITE_FIELDS if frappe.db.has_column("Hotspot Site", c)
	]
	return frappe.db.sql(
		f"select {', '.join(f'`{c}`' for c in columns)} from `tabHotspot Site` order by creation",
		as_dict=True,
	)


def _rows(doctype, fields):
	if not frappe.db.table_exists(doctype):
		return []
	columns = [f for f in fields if frappe.db.has_column(doctype, f)]
	return frappe.db.sql(
		f"""select {", ".join(f"`{c}`" for c in columns)} from `tab{doctype}`
		where parenttype='Hotspot Site' order by parent, idx""",
		as_dict=True,
	)


def _single(doctype):
	"""A settings single's stored values, minus anything password-like."""
	rows = frappe.db.sql("select field, value from `tabSingles` where doctype=%s", doctype, as_dict=True)
	return {
		r.field: r.value
		for r in rows
		if not any(word in r.field for word in ("password", "secret", "api_key", "token"))
	}
