import frappe
from frappe.query_builder.functions import IfNull

from bandofy.install import create_default_packages


def execute():
	"""Hotspot Package now carries Download/Upload Kbps, which site package
	rows fetch. Create the default packages (existing ones got the column
	default when the field was added, so give them their real bandwidth),
	then copy each package's bandwidth onto the site rows that use it."""
	create_default_packages(set_bandwidth=True)
	pkg = frappe.qb.DocType("Hotspot Package")
	item = frappe.qb.DocType("Hotspot Package Item")
	packages = (
		frappe.qb.from_(pkg)
		.select(pkg.name, pkg.bandwidth_down_kbps, pkg.bandwidth_up_kbps)
		.where((IfNull(pkg.bandwidth_down_kbps, 0) > 0) | (IfNull(pkg.bandwidth_up_kbps, 0) > 0))
	).run(as_dict=True)
	for package in packages:
		(
			frappe.qb.update(item)
			.set(item.bandwidth_down_kbps, package.bandwidth_down_kbps)
			.set(item.bandwidth_up_kbps, package.bandwidth_up_kbps)
			.where(item.package_name == package.name)
		).run()
