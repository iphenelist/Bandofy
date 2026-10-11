import frappe


def execute():
	"""v2.0.0 makes a site's pricing package (Hotspot Package Item) a link to
	Hotspot Package, where v1 stored free text. Create a Hotspot Package for
	every name a site uses that doesn't exist yet -- otherwise those sites
	could no longer be saved. Uses the first site row's type, price and
	duration; existing packages are left untouched."""
	if not frappe.db.table_exists("Hotspot Package Item"):
		return

	rows = frappe.db.sql(
		"""select package_name, package_type, price, duration_minutes
		from `tabHotspot Package Item`
		where parenttype='Hotspot Site' and ifnull(package_name, '') != ''
		order by creation, idx""",
		as_dict=True,
	)
	created = set()
	for row in rows:
		name = row.package_name.strip()
		if name in created or frappe.db.exists("Hotspot Package", name):
			continue
		frappe.get_doc(
			{
				"doctype": "Hotspot Package",
				"package_name": name,
				"package_type": row.package_type or "Unlimited",
				"price": row.price or 0,
				"duration_minutes": row.duration_minutes or 60,
			}
		).insert(ignore_permissions=True)
		created.add(name)
