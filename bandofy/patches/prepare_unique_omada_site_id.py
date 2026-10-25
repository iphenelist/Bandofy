import frappe


def execute():
	"""Hotspot Site.omada_site_id becomes unique, since the captive portal now
	finds the site by it. Before the unique index is added: blanks become NULL
	(MariaDB allows many NULLs but only one ""), and when two sites share an
	ID the newer one is cleared, with a comment and an Error Log entry."""
	if not frappe.db.has_column("Hotspot Site", "omada_site_id"):
		return

	hs = frappe.qb.DocType("Hotspot Site")
	frappe.qb.update(hs).set(hs.omada_site_id, None).where(hs.omada_site_id == "").run()

	rows = (
		frappe.qb.from_(hs)
		.select(hs.name, hs.omada_site_id)
		.where(hs.omada_site_id.isnotnull())
		.orderby(hs.creation)
		.run(as_dict=True)
	)
	seen = {}
	cleared = []
	for row in rows:
		key = row.omada_site_id.strip().lower()
		if key not in seen:
			seen[key] = row.name
			continue
		frappe.qb.update(hs).set(hs.omada_site_id, None).where(hs.name == row.name).run()
		frappe.get_doc("Hotspot Site", seen[key]).add_comment(
			"Comment",
			f"Bandofy: {row.name} had the same Omada Site ID ({row.omada_site_id}); it was cleared there.",
		)
		cleared.append(f"{row.name} (same as {seen[key]})")

	if cleared:
		frappe.log_error(
			title="Bandofy: duplicate Omada Site IDs cleared",
			message="Each Omada site can belong to one Hotspot Site only. Cleared on: " + ", ".join(cleared),
		)
