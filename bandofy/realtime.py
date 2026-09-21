# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

"""Instant, no-FCM-required alerts for the mobile monitoring app.

Delivered over Frappe's built-in Socket.IO realtime (Redis pub/sub under the
hood) straight to the affected vendor's session and every System Manager's
session, so the app hears about a redeemed voucher / completed payment the
moment it happens instead of having to poll.
"""

import frappe


def _admin_users():
	"""Every user with the System Manager role, plus Administrator, so the
	admin app hears about activity on every site."""
	users = set(
		frappe.get_all(
			"Has Role",
			filters={"role": "System Manager", "parenttype": "User"},
			pluck="parent",
		)
	)
	users.add("Administrator")
	return users


def _notify(event, payload, extra_user=None):
	targets = _admin_users()
	if extra_user:
		targets.add(extra_user)

	for user in targets:
		frappe.publish_realtime(event=event, message=payload, user=user)


def notify_voucher_used(doc, method=None):
	"""doc_event: Hotspot Voucher on_update. Fires only on the actual
	Unused -> Used transition, not on every save of the voucher."""
	if not doc.has_value_changed("status") or doc.status != "Used":
		return

	try:
		site = frappe.db.get_value(
			"Hotspot Site", doc.site, ["vendor_user", "vendor_name", "site_name"], as_dict=True
		)
		payload = {
			"site": doc.site,
			"site_name": site.site_name if site else doc.site,
			"vendor_name": site.vendor_name if site else None,
			"voucher_code": doc.name,
			"package_name": doc.package_name,
			"price": doc.price,
			"duration_minutes": doc.duration_minutes,
			"used_on": frappe.utils.get_datetime_str(doc.used_on) if doc.used_on else None,
			"used_by_mac": doc.used_by_mac,
		}
		_notify("foh_voucher_used", payload, extra_user=site.vendor_user if site else None)
	except Exception:
		frappe.log_error(title="Bandofy Realtime: notify_voucher_used failed", message=frappe.get_traceback())


def notify_transaction_paid(doc, method=None):
	"""doc_event: Hotspot Transaction on_update. Fires only on the Pending ->
	Paid transition for Mobile Money (STK Push) payments. Voucher redemptions
	insert their transaction already Paid (on_update never fires for that
	insert) and are covered by notify_voucher_used instead, so they don't
	double-notify."""
	if doc.phone_number == "Voucher":
		return
	if not doc.has_value_changed("status") or doc.status != "Paid":
		return

	try:
		site = frappe.db.get_value(
			"Hotspot Site", doc.site, ["vendor_user", "vendor_name", "site_name"], as_dict=True
		)
		payload = {
			"site": doc.site,
			"site_name": site.site_name if site else doc.site,
			"vendor_name": site.vendor_name if site else None,
			"transaction": doc.name,
			"phone_number": doc.phone_number,
			"package_name": doc.package_name,
			"amount": doc.amount,
			"duration_minutes": doc.duration_minutes,
		}
		_notify("foh_payment_received", payload, extra_user=site.vendor_user if site else None)
	except Exception:
		frappe.log_error(
			title="Bandofy Realtime: notify_transaction_paid failed", message=frappe.get_traceback()
		)


def notify_new_chat_message(doc, method=None):
	"""doc_event: Hotspot Chat Message after_insert. Only guest-authored
	messages need to reach the admin -- an admin's own reply obviously
	doesn't need to notify anyone back."""
	if doc.direction != "Guest":
		return

	try:
		site = frappe.db.get_value(
			"Hotspot Site", doc.site, ["vendor_user", "vendor_name", "site_name"], as_dict=True
		)
		payload = {
			"site": doc.site,
			"site_name": site.site_name if site else doc.site,
			"vendor_name": site.vendor_name if site else None,
			"client_mac": doc.client_mac,
			"message": doc.message,
			"creation": frappe.utils.get_datetime_str(doc.creation),
		}
		_notify("foh_new_chat_message", payload, extra_user=site.vendor_user if site else None)
	except Exception:
		frappe.log_error(
			title="Bandofy Realtime: notify_new_chat_message failed", message=frappe.get_traceback()
		)
