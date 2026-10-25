# Copyright (c) 2026, Innocent P M and Contributors
# See license.txt

import secrets
from unittest.mock import patch

import frappe
from frappe.utils import add_to_date, now_datetime

from bandofy import api
from bandofy.bandofy.doctype.hotspot_site.test_hotspot_site import SiteTestCase, random_mac
from bandofy.ruijie import check_login
from bandofy.utils import find_site


class TestRuijie(SiteTestCase):
	"""Ruijie sites: found by the AC name, connected through a one-time
	RADIUS login the portal submits to the AC."""

	def setUp(self):
		super().setUp()
		self.cleanup = []

	def tearDown(self):
		for doctype, name in reversed(self.cleanup):
			frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)
		super().tearDown()

	def ruijie_site(self, **kwargs):
		return self.site(controller_type="Ruijie", ruijie_ac_name=f"AC-{secrets.token_hex(4)}", **kwargs)

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

	def redeem(self, site, client_mac):
		code = self.make_voucher(site)
		result = api.redeem_voucher(code, client_mac, ac_name=site.ruijie_ac_name)
		self.cleanup.append(("Hotspot Transaction", result["transaction_id"]))
		return result

	def test_find_site_by_ac_name(self):
		site = self.ruijie_site()
		self.assertEqual(find_site(None, None, ac_name=site.ruijie_ac_name).name, site.name)
		self.assertIsNone(find_site(None, None, ac_name="some-other-ac"))

	def test_ruijie_site_needs_ac_name(self):
		with self.assertRaises(frappe.ValidationError):
			self.site(controller_type="Ruijie")

	@patch("bandofy.api._authorize_on_omada")
	def test_voucher_returns_login_form_without_omada(self, omada):
		site = self.ruijie_site()
		result = self.redeem(site, random_mac())

		omada.assert_not_called()
		login = result["login"]
		self.assertNotIn("redirect_url", result)
		self.assertEqual(login["method"], "POST")
		self.assertEqual(login["fields"]["username"], result["transaction_id"])
		self.assertEqual(len(login["fields"]["password"]), 24)

	def test_check_login_accepts_the_issued_login_once_per_device(self):
		site = self.ruijie_site()
		client_mac = random_mac()
		result = self.redeem(site, client_mac)
		username = result["transaction_id"]
		password = result["login"]["fields"]["password"]

		remaining = check_login(username, password, calling_station_id=client_mac.replace("-", ":"))
		self.assertTrue(350 * 60 < remaining <= 360 * 60)

		self.assertIsNone(check_login(username, "wrong-password"))
		# A login read off another customer's screen is useless elsewhere.
		self.assertIsNone(check_login(username, password, calling_station_id=random_mac()))

	def test_check_login_mac_relogin(self):
		site = self.ruijie_site()
		client_mac = random_mac()
		self.redeem(site, client_mac)

		self.assertTrue(check_login(client_mac.replace("-", "").lower(), "ignored"))
		self.assertIsNone(check_login(client_mac, "ignored", allow_mac_relogin=False))
		self.assertIsNone(check_login(random_mac(), "ignored"))

	def test_check_login_rejects_expired_and_inactive(self):
		site = self.ruijie_site()
		result = self.redeem(site, random_mac())
		username = result["transaction_id"]
		password = result["login"]["fields"]["password"]

		frappe.db.set_value(
			"Hotspot Transaction", username, "authorized_until", add_to_date(now_datetime(), minutes=-1)
		)
		self.assertIsNone(check_login(username, password))

		frappe.db.set_value(
			"Hotspot Transaction", username, "authorized_until", add_to_date(now_datetime(), hours=1)
		)
		frappe.db.set_value("Hotspot Site", site.name, "is_active", 0)
		self.assertIsNone(check_login(username, password))

	def test_status_poll_hands_login_only_to_the_paying_device(self):
		site = self.ruijie_site()
		client_mac = random_mac()
		result = self.redeem(site, client_mac)

		status = api.get_omada_connection_status(result["transaction_id"], client_mac=client_mac)
		self.assertTrue(status["ready"])
		self.assertIn("login", status)
		with self.assertRaises(frappe.ValidationError):
			api.get_omada_connection_status(result["transaction_id"], client_mac=random_mac())
