# Copyright (c) 2026, Innocent P M and Contributors
# See license.txt

import secrets
from unittest.mock import patch

import frappe

from bandofy import api
from bandofy.bandofy.doctype.hotspot_site.test_hotspot_site import (
	SiteTestCase,
	random_mac,
	random_omada_site_id,
)


class TestPortalApiOmadaSite(SiteTestCase):
	"""The captive portal finds the Hotspot Site from the `site` (Omada site
	ID) the controller adds to its redirect, so a site needs no Access Points
	rows for customers to connect."""

	def setUp(self):
		super().setUp()
		self.cleanup = []

	def tearDown(self):
		for doctype, name in reversed(self.cleanup):
			frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)
		super().tearDown()

	def make_voucher(self, site):
		code = str(secrets.randbelow(900000) + 100000)
		frappe.get_doc(
			{
				"doctype": "Hotspot Voucher",
				"voucher_code": code,
				"status": "Unused",
				"site": site.name,
				"package_name": "Masaa 6",
				"duration_minutes": 360,
			}
		).insert(ignore_permissions=True)
		self.cleanup.append(("Hotspot Voucher", code))
		return code

	@patch("bandofy.api._authorize_on_omada")
	def test_redeem_voucher_with_only_omada_site(self, authorize):
		omada_id = random_omada_site_id()
		site = self.site(omada_site_id=omada_id)  # no Access Points rows
		code = self.make_voucher(site)

		result = api.redeem_voucher(code, random_mac(), random_mac(), omada_site=omada_id)
		self.cleanup.append(("Hotspot Transaction", result["transaction_id"]))

		self.assertEqual(result["status"], "Paid")
		self.assertEqual(frappe.db.get_value("Hotspot Voucher", code, "status"), "Used")
		self.assertEqual(
			frappe.db.get_value("Hotspot Transaction", result["transaction_id"], "site"), site.name
		)
		authorize.assert_called_once()
		self.assertEqual(authorize.call_args.args[1].name, site.name)

	@patch("bandofy.api._authorize_on_omada")
	def test_voucher_is_refused_on_another_vendors_site(self, authorize):
		mine = self.site(omada_site_id=random_omada_site_id())
		other_id = random_omada_site_id()
		self.site(omada_site_id=other_id)
		code = self.make_voucher(mine)

		with self.assertRaises(frappe.ValidationError):
			api.redeem_voucher(code, random_mac(), random_mac(), omada_site=other_id)
		self.assertEqual(frappe.db.get_value("Hotspot Voucher", code, "status"), "Unused")
		authorize.assert_not_called()

	def test_unknown_site_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			api.redeem_voucher("123456", random_mac(), random_mac(), omada_site=random_omada_site_id())
