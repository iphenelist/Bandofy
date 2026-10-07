from collections import Counter

import frappe

CONTROLLER_COLUMNS = ("controller_ip", "port", "controller_id", "site_id", "omada_username")


def execute():
	"""Hotspot Site no longer stores the Omada controller and operator --
	they live once in Hotspot Omada Settings. Carry over what sites had:

	- each site's old Omada site ID moves to omada_site_id. A stored site
	  *name* (e.g. "Orion") is kept too: omada_service.site_controller turns
	  it into the real ID on first use;
	- the controller most sites used, and its operator login, fill any empty
	  Hotspot Omada Settings fields;
	- a site that used a *different* controller can't keep working on the
	  central one, so it gets a comment on its record and an Error Log entry
	  instead of failing silently.

	The old columns and encrypted passwords stay in the database (Frappe
	drops neither), and v2_backup_v1_data saved a copy of the values."""
	columns = [c for c in CONTROLLER_COLUMNS if frappe.db.has_column("Hotspot Site", c)]
	if not columns:
		return

	sites = frappe.db.sql(
		f"""select name, site_name, omada_site_id, {", ".join(f"`{c}`" for c in columns)}
		from `tabHotspot Site` order by creation""",
		as_dict=True,
	)

	for site in sites:
		if site.get("site_id") and not site.omada_site_id:
			frappe.db.set_value(
				"Hotspot Site", site.name, "omada_site_id", site.site_id, update_modified=False
			)

	configured = [s for s in sites if s.get("controller_ip")]
	if not configured:
		return

	def controller(s):
		return (s.controller_ip.strip().lower(), str(s.get("port") or 8043))

	central = Counter(controller(s) for s in configured).most_common(1)[0][0]
	same = [s for s in configured if controller(s) == central]
	source = next((s for s in same if s.get("omada_username")), same[0])
	_fill_settings(source, central)

	elsewhere = [s for s in configured if controller(s) != central]
	for site in elsewhere:
		frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Comment",
				"reference_doctype": "Hotspot Site",
				"reference_name": site.name,
				"content": (
					f"Bandofy v2 upgrade: this site used the Omada Controller "
					f"{site.controller_ip}:{site.get('port') or 8043}, but v2 manages every site on one "
					f"central controller ({central[0]}:{central[1]}). Customers won't be authorized until "
					"this site is moved to the central controller (adopt its APs there, then Omada > "
					"Create on Omada). Its old settings are kept in the v1 backup file."
				),
			}
		).insert(ignore_permissions=True)
	if elsewhere:
		frappe.log_error(
			title="Bandofy v2: sites on another Omada Controller",
			message="\n".join(
				f"{s.name} ({s.site_name}): {s.controller_ip}:{s.get('port') or 8043}" for s in elsewhere
			),
		)


def _fill_settings(source, central):
	settings = frappe.get_single("Hotspot Omada Settings")
	values = {}
	if not settings.controller_url:
		host, port = central
		values["controller_url"] = (
			host if host.startswith(("http://", "https://")) else f"https://{host}:{port}"
		)
	if not settings.omadac_id and source.get("controller_id"):
		values["omadac_id"] = source.controller_id
	if not settings.operator_name and source.get("omada_username"):
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
