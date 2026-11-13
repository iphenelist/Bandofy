# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import frappe

# (name, price, duration minutes, download Kbps, upload Kbps), sized so a
# 40 Mbps line serves ~25-35 customers and no package exceeds 20% of it.
DEFAULT_PACKAGES = [
	("Masaa 6", 300, 360, 2048, 1024),
	("Masaa 12", 500, 720, 3072, 1024),
	("Siku", 1000, 1440, 4096, 1024),
	("Siku 3", 1500, 4320, 5120, 2048),
	("Wiki", 5000, 10080, 6144, 2048),
	("Mwezi", 15000, 43200, 8192, 3072),
]


def after_install():
	setup_roles()
	create_default_packages()


def setup_roles():
	"""Ensure the Bandofy Manager role exists and lands on the vendor dashboard."""
	if not frappe.db.exists("Role", "Bandofy Manager"):
		r = frappe.new_doc("Role")
		r.role_name = "Bandofy Manager"
		r.desk_access = 1
		r.insert(ignore_permissions=True)
	frappe.db.set_value("Role", "Bandofy Manager", "home_page", "/vendor-dashboard")


def create_default_packages(set_bandwidth=False):
	"""Creates the default Hotspot Packages. An existing package keeps its
	price and duration; with ``set_bandwidth`` it also gets the default
	Download/Upload Kbps."""
	for name, price, minutes, down, up in DEFAULT_PACKAGES:
		if not frappe.db.exists("Hotspot Package", name):
			frappe.get_doc(
				{
					"doctype": "Hotspot Package",
					"package_name": name,
					"package_type": "Unlimited",
					"price": price,
					"duration_minutes": minutes,
					"bandwidth_down_kbps": down,
					"bandwidth_up_kbps": up,
				}
			).insert(ignore_permissions=True)
		elif set_bandwidth:
			frappe.db.set_value(
				"Hotspot Package", name, {"bandwidth_down_kbps": down, "bandwidth_up_kbps": up}
			)
