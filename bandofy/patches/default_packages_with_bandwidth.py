import frappe

from bandofy.install import create_default_packages


def execute():
	"""Hotspot Package now carries Download/Upload Kbps, which site package
	rows fetch. Create the default packages (existing ones got the column
	default when the field was added, so give them their real bandwidth),
	then copy each package's bandwidth onto the site rows that use it."""
	create_default_packages(set_bandwidth=True)
	frappe.db.sql(
		"""update `tabHotspot Package Item` item
		join `tabHotspot Package` pkg on pkg.name = item.package_name
		set item.bandwidth_down_kbps = pkg.bandwidth_down_kbps,
			item.bandwidth_up_kbps = pkg.bandwidth_up_kbps
		where ifnull(pkg.bandwidth_down_kbps, 0) > 0 or ifnull(pkg.bandwidth_up_kbps, 0) > 0"""
	)
