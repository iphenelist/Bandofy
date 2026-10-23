import frappe
from frappe.query_builder.functions import IfNull


def execute():
	"""v2.0.0 makes a site's pricing package (Hotspot Package Item) a link to
	Hotspot Package, where v1 stored free text. Create a Hotspot Package for
	every name a site uses that doesn't exist yet -- otherwise those sites
	could no longer be saved. Uses the first site row's type, price and
	duration; existing packages are left untouched."""
	if not frappe.db.table_exists("Hotspot Package Item"):
		return

	item = frappe.qb.DocType("Hotspot Package Item")
	rows = (
		frappe.qb.from_(item)
		.select(item.package_name, item.package_type, item.price, item.duration_minutes)
		.where((item.parenttype == "Hotspot Site") & (IfNull(item.package_name, "") != ""))
		.orderby(item.creation)
		.orderby(item.idx)
	).run(as_dict=True)
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
