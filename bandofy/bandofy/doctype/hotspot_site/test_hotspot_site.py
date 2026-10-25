# Copyright (c) 2026, Innocent P M and Contributors
# See license.txt

import secrets

import frappe
from frappe.tests import IntegrationTestCase

from bandofy.install import create_default_packages
from bandofy.utils import find_site

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]


def random_omada_site_id():
	return secrets.token_hex(12)


def random_mac():
	return "-".join(secrets.token_hex(1).upper() for _ in range(6))


def make_site(omada_site_id=None, ap_macs=(), is_active=1, **kwargs):
	"""A Hotspot Site with one default package."""
	create_default_packages()
	return frappe.get_doc(
		{
			"doctype": "Hotspot Site",
			"site_name": f"Test Site {secrets.token_hex(3)}",
			"vendor_name": "Test Vendor",
			"is_active": is_active,
			"omada_site_id": omada_site_id,
			"packages": [{"package_name": "Masaa 6"}],
			"devices": [{"ap_mac": mac, "label": mac, "is_active": 1} for mac in ap_macs],
			**kwargs,
		}
	).insert(ignore_permissions=True)


class SiteTestCase(IntegrationTestCase):
	"""Deletes the sites it makes, because the portal API under test commits."""

	def setUp(self):
		self.sites = []

	def tearDown(self):
		for name in self.sites:
			frappe.delete_doc("Hotspot Site", name, ignore_permissions=True, force=True)
		frappe.db.commit()  # nosemgrep

	def site(self, *args, **kwargs):
		doc = make_site(*args, **kwargs)
		self.sites.append(doc.name)
		return doc


class IntegrationTestHotspotSite(SiteTestCase):
	def test_find_site_by_omada_site_id_without_access_points(self):
		omada_id = random_omada_site_id()
		site = self.site(omada_site_id=omada_id)
		self.assertEqual(find_site(omada_id, None).name, site.name)
		self.assertEqual(find_site(omada_id, random_mac()).name, site.name)

	def test_find_site_falls_back_to_ap_mac(self):
		mac = random_mac()
		site = self.site(ap_macs=[mac])
		self.assertEqual(find_site(None, mac).name, site.name)
		self.assertEqual(find_site(random_omada_site_id(), mac).name, site.name)  # unknown ID
		self.assertEqual(find_site("Orion", mac.replace("-", ":").lower()).name, site.name)  # malformed ID

	def test_find_site_respects_active_only(self):
		omada_id = random_omada_site_id()
		site = self.site(omada_site_id=omada_id, is_active=0)
		self.assertIsNone(find_site(omada_id, None))
		self.assertEqual(find_site(omada_id, None, active_only=False).name, site.name)

	def test_find_site_returns_requested_fields(self):
		omada_id = random_omada_site_id()
		site = self.site(omada_site_id=omada_id)
		found = find_site(omada_id, None, fields=["name", "site_name"])
		self.assertEqual(found.site_name, site.site_name)

	def test_malformed_omada_site_id_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.site(omada_site_id="My Shop")

	def test_omada_site_id_is_stripped_and_blank_is_null(self):
		omada_id = random_omada_site_id()
		site = self.site(omada_site_id=f"  {omada_id} ")
		self.assertEqual(site.omada_site_id, omada_id)
		blank = self.site(omada_site_id="")
		self.assertIsNone(frappe.db.get_value("Hotspot Site", blank.name, "omada_site_id"))
		# Many sites without an ID must coexist under the unique index.
		self.site(omada_site_id="")

	def test_duplicate_omada_site_id_is_rejected(self):
		omada_id = random_omada_site_id()
		self.site(omada_site_id=omada_id)
		with self.assertRaises(frappe.ValidationError):
			self.site(omada_site_id=omada_id)
