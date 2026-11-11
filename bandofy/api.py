# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import hashlib
import hmac
import json
import time

import frappe
import requests
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime_str, get_url, getdate, now_datetime, nowdate

from bandofy.omada_openapi import set_client_rate_limit
from bandofy.omada_auth import authorize_client, site_controller
from bandofy.utils import find_site, has_used_free_trial, is_sabbath_now, normalize_mac

DEFAULT_SUCCESS_REDIRECT_URL = "https://www.youtube.com"
PAYMENT_POLL_GRACE_SECONDS = 90  # give the webhook this long to arrive before polling
PAYMENT_POLL_MAX_AGE_MINUTES = 60  # transactions still Pending after this are given up on
CHAT_MESSAGE_MAX_LENGTH = 500
DEFAULT_GATEWAY_BASE_URL = "https://abliner.net/api/v1"
WEBHOOK_MAX_AGE_SECONDS = 300  # Abliner: reject webhook timestamps older than 5 minutes
SABBATH_MESSAGE = (
	"Ni Sabato — hatupokei malipo wala vocha hadi Jumamosi saa 12 jioni. "
	"/ It is the Sabbath — payments and vouchers resume Saturday 18:00."
)


@frappe.whitelist(allow_guest=True)
def initiate_payment(
	phone, package_idx, client_mac, ap_mac=None, ssid_name=None, radio_id=None, omada_site=None, ac_name=None
):
	"""Create a Pending Hotspot Transaction and kick off the STK push.

	Called by the captive portal (wifi_login.html) once a customer picks a
	plan and enters their Mobile Money number.
	"""
	if not (phone and package_idx and client_mac and (ap_mac or ac_name)):
		frappe.throw(_("Missing required parameters."))

	found = find_site(omada_site, ap_mac, ac_name=ac_name)
	if not found:
		frappe.throw(_("This access point is not registered or is currently inactive."))

	site = frappe.get_doc("Hotspot Site", found.name)
	_require_ap_mac(site, ap_mac)

	if not site.enable_online_payment:
		frappe.throw(_("Mfumo wa kulipa kwa pesa upo katika matengenezo."))

	if is_sabbath_now(site):
		frappe.throw(_(SABBATH_MESSAGE))

	package = None
	for row in site.packages:
		if str(row.idx) == str(package_idx) or row.name == package_idx:
			package = row
			break

	if not package:
		frappe.throw(_("The selected package could not be found."))

	txn = frappe.get_doc(
		{
			"doctype": "Hotspot Transaction",
			"site": site.name,
			"phone_number": phone,
			"client_mac": client_mac,
			"ap_mac": ap_mac,
			"ssid_name": ssid_name,
			"radio_id": radio_id,
			"package_name": package.package_name,
			"amount": package.price,
			"duration_minutes": package.duration_minutes,
			"status": "Pending",
		}
	)
	txn.insert(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	try:
		stk_result = trigger_stk_push(phone=phone, amount=package.price, transaction_id=txn.name)
	except Exception:
		frappe.log_error(title=f"Bandofy STK Push Failed: {txn.name}", message=frappe.get_traceback())
		txn.db_set("status", "Failed", commit=True)
		frappe.throw(_("Could not reach the payment gateway. Please try again in a moment."))

	if stk_result.get("reference_id"):
		txn.db_set("reference_id", stk_result.get("reference_id"), commit=True)

	return {
		"transaction_id": txn.name,
		"status": txn.status,
		"message": stk_result.get(
			"message", _("STK push sent. Please check your phone to complete the payment.")
		),
	}


def trigger_stk_push(phone, amount, transaction_id):
	"""Trigger a Mobile Money STK push via the configured payment gateway.

	Reads gateway credentials from the ``Hotspot Payment Settings`` single.
	While the gateway is disabled (or unconfigured) this falls back to a
	logging-only stub so the captive portal keeps working in development.
	Returns a dict with ``reference_id`` (the gateway's tracking id, stored
	on the transaction) and ``message`` (shown to the customer).
	"""
	settings = frappe.get_single("Hotspot Payment Settings")
	api_key = (settings.get_password("api_key") or "").strip() if settings.enabled else ""

	if not settings.enabled or not api_key:
		frappe.logger("bandofy").info(
			f"Payment gateway disabled/unconfigured; STK push stub for {phone} "
			f"amount={amount} txn={transaction_id}"
		)
		return {
			"reference_id": None,
			"message": _("STK push sent. Please check your phone to complete the payment."),
		}

	base_url = _gateway_base_url(settings)
	timeout = max(5, min(int(settings.request_timeout or 30), 120))
	currency = (settings.default_currency or "TZS").strip().upper()

	# Abliner echoes `reference` back as `customer_reference` on the deposit,
	# the webhook and the transactions lookup — that's how we find the txn.
	body = json.dumps(
		{
			"amount": round(amount),
			"method": "mobile",
			"currency": currency,
			"phone": phone,
			"reference": transaction_id,
			"callback_url": get_url("/api/method/bandofy.api.payment_callback"),
		},
		separators=(",", ":"),
	)
	headers = {
		"Authorization": f"Bearer {api_key}",
		"Content-Type": "application/json",
		"Idempotency-Key": transaction_id,
	}

	# API keys created from 5 Oct 2026 must sign deposits with the whsec_
	# secret: HMAC-SHA256 of "<timestamp>.<raw body>".
	signing_secret = (settings.get_password("webhook_secret", raise_exception=False) or "").strip()
	if signing_secret:
		timestamp = str(int(time.time()))
		headers["x-abliner-timestamp"] = timestamp
		headers["x-abliner-signature"] = hmac.new(
			signing_secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256
		).hexdigest()

	response = requests.post(f"{base_url}/deposits", headers=headers, data=body, timeout=timeout)
	try:
		result = response.json() or {}
	except ValueError:
		result = {}

	if not response.ok or result.get("status") == "error":
		raise Exception(
			f"Abliner deposit failed (HTTP {response.status_code}): "
			f"{result.get('code') or ''} {result.get('message') or response.text[:500]}"
		)

	data = result.get("data") or {}
	reference = data.get("id")

	return {
		"reference_id": reference,
		"message": _("STK push sent. Please check your phone to complete the payment."),
	}


@frappe.whitelist(allow_guest=True)
def payment_callback():
	"""Webhook invoked by the payment gateway when a payment resolves.

	Verifies the HMAC signature (when a webhook secret is configured), then
	moves the matching Hotspot Transaction to Paid/Failed and, on success,
	automatically enqueues Omada MAC authorization. Idempotent: a duplicate
	delivery of an already-processed event is a no-op.
	"""
	settings = frappe.get_single("Hotspot Payment Settings")
	raw_body = frappe.request.get_data(as_text=True) or ""

	webhook_secret = (settings.get_password("webhook_secret", raise_exception=False) or "").strip()
	if webhook_secret and not _verify_webhook_signature(webhook_secret, raw_body):
		frappe.local.response["http_status_code"] = 401
		return {"status": "error", "message": "Invalid webhook signature"}

	try:
		payload = json.loads(raw_body) if raw_body else dict(frappe.local.form_dict)
	except json.JSONDecodeError:
		frappe.local.response["http_status_code"] = 400
		return {"status": "error", "message": "Invalid JSON payload"}

	# Abliner events: transaction.completed / transaction.failed (deposits).
	event_type = str(payload.get("event") or "").strip().lower()
	data = payload.get("data") or {}

	transaction_id = str(data.get("customer_reference") or "").strip()
	reference_id = str(data.get("id") or "").strip()
	gateway_status = str(data.get("status") or "").strip().lower()

	txn_name = None
	if transaction_id and frappe.db.exists("Hotspot Transaction", transaction_id):
		txn_name = transaction_id
	elif reference_id:
		txn_name = frappe.db.get_value("Hotspot Transaction", {"reference_id": reference_id})

	if not txn_name:
		frappe.log_error(
			title="Bandofy Payment Callback: Transaction Not Found", message=frappe.as_json(payload)
		)
		frappe.local.response["http_status_code"] = 404
		return {"status": "error", "message": "Transaction not found"}

	txn = frappe.get_doc("Hotspot Transaction", txn_name)

	if txn.status != "Pending":
		# Already processed by an earlier delivery of this event, or by the
		# fallback poller — avoid double-authorizing the client.
		return {"status": "ok", "message": "Already processed"}

	if event_type == "transaction.completed" or gateway_status == "completed":
		_mark_transaction_paid(txn, reference_id, settings)
		return {"status": "success"}

	if event_type == "transaction.failed" or gateway_status == "failed":
		txn.status = "Failed"
		txn.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep
		return {"status": "failed"}

	return {"status": "pending"}


def _mark_transaction_paid(txn, reference_id, settings):
	txn.status = "Paid"
	if reference_id:
		txn.reference_id = reference_id

	txn.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	if settings.auto_authorize_on_payment:
		frappe.enqueue(
			"bandofy.api.authorize_mac_on_omada",
			queue="short",
			enqueue_after_commit=True,
			transaction_id=txn.name,
		)


def _success_redirect_url(site_url):
	"""Where to send a connected customer: the site's own URL, else the
	default from Hotspot Omada Settings."""
	return (
		site_url
		or frappe.db.get_single_value("Hotspot Omada Settings", "default_success_redirect_url")
		or DEFAULT_SUCCESS_REDIRECT_URL
	)


def _gateway_base_url(settings):
	return (settings.base_url or DEFAULT_GATEWAY_BASE_URL).strip().rstrip("/")


def _verify_webhook_signature(webhook_secret, raw_body):
	"""Abliner signs webhooks as hex HMAC-SHA256 of "<timestamp>.<raw body>"."""
	signature = (frappe.get_request_header("X-Webhook-Signature") or "").strip()
	timestamp = (frappe.get_request_header("X-Webhook-Timestamp") or "").strip()
	if not (signature and timestamp.isdigit()):
		return False

	if abs(time.time() - int(timestamp)) > WEBHOOK_MAX_AGE_SECONDS:
		return False

	signed_payload = f"{timestamp}.{raw_body}".encode()
	expected = hmac.new(webhook_secret.encode(), signed_payload, hashlib.sha256).hexdigest()
	return hmac.compare_digest(expected, signature)


@frappe.whitelist()
def sync_pending_payments():
	"""Fallback poller: check the gateway for transactions the webhook missed.

	Runs every 5 minutes (see hooks.py scheduler_events). Skips gateways
	that are disabled, and skips brand-new transactions to give the webhook
	a chance to arrive first. Transactions still Pending well past
	PAYMENT_POLL_MAX_AGE_MINUTES are given up on and marked Failed.
	"""
	settings = frappe.get_single("Hotspot Payment Settings")
	api_key = (settings.get_password("api_key") or "").strip() if settings.enabled else ""
	if not settings.enabled or not settings.poll_pending_payments or not api_key:
		return

	cutoff_recent = add_to_date(now_datetime(), seconds=-PAYMENT_POLL_GRACE_SECONDS)
	cutoff_old = add_to_date(now_datetime(), minutes=-PAYMENT_POLL_MAX_AGE_MINUTES)

	pending = frappe.get_all(
		"Hotspot Transaction",
		filters={"status": "Pending", "creation": ["<=", cutoff_recent]},
		fields=["name", "reference_id", "creation"],
		limit_page_length=200,
	)

	base_url = _gateway_base_url(settings)
	timeout = max(5, min(int(settings.request_timeout or 30), 120))

	for row in pending:
		# Look up by Abliner's id when we have it, otherwise by the reference
		# we sent (the txn name) — covers a deposit whose response was lost.
		params = {"id": row.reference_id} if row.reference_id else {"customer_reference": row.name}
		try:
			response = requests.get(
				f"{base_url}/transactions",
				headers={"Authorization": f"Bearer {api_key}"},
				params=params,
				timeout=timeout,
			)
			response.raise_for_status()
			matches = (response.json() or {}).get("data") or []
			match = matches[0] if matches else {}
			gateway_status = str(match.get("status") or "").strip().lower()
			reference_id = row.reference_id or str(match.get("id") or "")
		except Exception:
			frappe.log_error(title=f"Bandofy Payment Poll Failed: {row.name}", message=frappe.get_traceback())
			continue

		if gateway_status == "completed":
			txn = frappe.get_doc("Hotspot Transaction", row.name)
			_mark_transaction_paid(txn, reference_id, settings)
		elif gateway_status == "failed":
			frappe.db.set_value("Hotspot Transaction", row.name, "status", "Failed")
		elif row.creation <= cutoff_old:
			frappe.db.set_value("Hotspot Transaction", row.name, "status", "Failed")

	frappe.db.commit()  # nosemgrep


@frappe.whitelist(allow_guest=True)
def redeem_voucher(
	voucher_code, client_mac, ap_mac=None, ssid_name=None, radio_id=None, omada_site=None, ac_name=None
):
	"""Redeem a pre-generated Hotspot Voucher in place of an STK Push payment."""
	if not (voucher_code and client_mac and (ap_mac or ac_name)):
		frappe.throw(_("Missing required parameters."))

	found = find_site(omada_site, ap_mac, ac_name=ac_name, fields=["name", "controller_type"])
	if not found:
		frappe.throw(_("This access point is not registered or is currently inactive."))
	_require_ap_mac(found, ap_mac)
	site_name = found.name

	voucher_code = voucher_code.strip().upper()

	if frappe.db.exists("Hotspot Staff Voucher", voucher_code):
		return _redeem_staff_voucher(voucher_code, site_name, client_mac, ap_mac, ssid_name, radio_id)

	# Staff vouchers (free access) stay usable; customer vouchers wait
	# until the Sabbath ends and remain Unused meanwhile.
	if is_sabbath_now(site_name):
		frappe.throw(_(SABBATH_MESSAGE))

	if not frappe.db.exists("Hotspot Voucher", voucher_code):
		frappe.throw(_("Invalid voucher code."))

	voucher = frappe.get_doc("Hotspot Voucher", voucher_code)

	if voucher.site != site_name:
		frappe.throw(_("This voucher is not valid for this access point."))

	if voucher.status != "Unused":
		frappe.throw(_("This voucher has already been {0}.").format(voucher.status.lower()))

	if voucher.expires_on and getdate(voucher.expires_on) < getdate(nowdate()):
		voucher.db_set("status", "Expired", commit=True)
		frappe.throw(_("This voucher has expired."))

	txn = frappe.get_doc(
		{
			"doctype": "Hotspot Transaction",
			"site": site_name,
			"phone_number": "Voucher",
			"client_mac": client_mac,
			"ap_mac": ap_mac,
			"ssid_name": ssid_name,
			"radio_id": radio_id,
			"package_name": voucher.package_name,
			"amount": voucher.price,
			"duration_minutes": voucher.duration_minutes,
			"status": "Paid",
			"reference_id": f"VOUCHER:{voucher.name}",
		}
	)
	txn.insert(ignore_permissions=True)

	voucher.status = "Used"
	voucher.used_on = now_datetime()
	voucher.used_by_mac = client_mac
	voucher.ap_mac = ap_mac
	voucher.transaction = txn.name
	voucher.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	result = {
		"transaction_id": txn.name,
		"status": "Paid",
		"message": _("Voucher accepted. You are now being connected."),
	}

	# Voucher redemption is already a synchronous, immediate-response
	# flow (unlike payment, which waits on a webhook) -- authorize now so
	# we can hand the portal page a redirect_url in this same response.
	# On failure, fall back to the async retry queue instead of leaving
	# an already-consumed voucher stuck with no authorization attempt.
	site = frappe.get_doc("Hotspot Site", site_name)
	try:
		_authorize_transaction(txn, site)
		result.update(_connect_details(txn, site))
	except Exception:
		frappe.log_error(
			title=f"Bandofy Omada Authorization Failed: {txn.name}",
			message=frappe.get_traceback(),
		)
		frappe.enqueue(
			"bandofy.api.authorize_mac_on_omada",
			queue="short",
			enqueue_after_commit=True,
			transaction_id=txn.name,
		)

	return result


def _redeem_staff_voucher(voucher_code, site_name, client_mac, ap_mac, ssid_name=None, radio_id=None):
	"""Free, reusable staff access: unlike a customer Hotspot Voucher the code
	is never consumed -- each redemption logs the device in for the staff
	voucher's ``session_minutes`` at zero cost, up to ``max_devices``
	distinct devices. The zero-amount Hotspot Transaction
	(phone_number="Staff") is what Omada authorizes against."""
	staff_voucher = frappe.get_doc("Hotspot Staff Voucher", voucher_code)

	if staff_voucher.site != site_name:
		frappe.throw(_("This voucher is not valid for this access point."))

	device = staff_voucher.check_can_connect(client_mac)
	site = frappe.get_doc("Hotspot Site", site_name)

	txn = frappe.get_doc(
		{
			"doctype": "Hotspot Transaction",
			"site": site_name,
			"phone_number": "Staff",
			"client_mac": client_mac,
			"ap_mac": ap_mac,
			"ssid_name": ssid_name,
			"radio_id": radio_id,
			"package_name": "Staff Access",
			"amount": 0,
			"duration_minutes": cint(staff_voucher.session_minutes),
			"status": "Paid",
			"reference_id": f"STAFF:{staff_voucher.name}",
		}
	)
	txn.insert(ignore_permissions=True)

	now = now_datetime()
	if not device:
		device = staff_voucher.append("devices", {"client_mac": client_mac, "first_used_on": now})
	device.last_used_on = now
	staff_voucher.last_used_on = now
	staff_voucher.use_count = cint(staff_voucher.use_count) + 1
	staff_voucher.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	result = {
		"transaction_id": txn.name,
		"status": "Paid",
		"message": _("Welcome {0}. You are now being connected.").format(staff_voucher.staff_name),
	}

	# Same synchronous-authorize-now shortcut redeem_voucher uses.
	try:
		_authorize_transaction(txn, site)
		result.update(_connect_details(txn, site))
	except Exception:
		frappe.log_error(
			title=f"Bandofy Staff Omada Authorization Failed: {txn.name}",
			message=frappe.get_traceback(),
		)
		frappe.enqueue(
			"bandofy.api.authorize_mac_on_omada",
			queue="short",
			enqueue_after_commit=True,
			transaction_id=txn.name,
		)

	return result


FREE_TRIAL_AD_SECONDS = 5
# How long a watched ad stays valid for claiming the free trial.
FREE_TRIAL_AD_WINDOW_MINUTES = 15


def _watched_free_trial_ad(site_name, client_mac):
	"""True when the site has no full-screen ads, or this device's portal
	logged a view of one at least FREE_TRIAL_AD_SECONDS ago (the portal
	logs the view when the ad appears and claims when its countdown ends)."""
	from bandofy.www.landing import free_trial_ads, get_active_ads

	ads = [ad.name for ad in free_trial_ads(get_active_ads(site_name))]
	if not ads:
		return True
	now = now_datetime()
	return bool(
		frappe.db.exists(
			"Hotspot Ad View Log",
			{
				"ad": ["in", ads],
				"client_mac": client_mac,
				# 1 s slack for the gap between the browser's timer and the
				# log row's own timestamp.
				"viewed_on": [
					"between",
					[
						add_to_date(now, minutes=-FREE_TRIAL_AD_WINDOW_MINUTES),
						add_to_date(now, seconds=-(FREE_TRIAL_AD_SECONDS - 1)),
					],
				],
			},
		)
	)


@frappe.whitelist(allow_guest=True)
def claim_free_trial(
	ap_mac=None, client_mac=None, ssid_name=None, radio_id=None, omada_site=None, ac_name=None
):
	"""One-time free-trial connection: authorizes a brand-new device for
	``Hotspot Site.free_trial_minutes`` (default 15), same as a paid voucher
	but at zero cost and with no code to enter. The resulting Hotspot
	Transaction (phone_number="Free Trial") doubles as the device's
	registration -- :func:`bandofy.utils.has_used_free_trial` checks it to
	block a second claim from the same MAC, and the portal itself won't
	render the button again once that check fails.
	"""
	if not (client_mac and (ap_mac or ac_name)):
		frappe.throw(_("Missing required parameters."))

	found = find_site(omada_site, ap_mac, ac_name=ac_name)
	if not found:
		frappe.throw(_("This access point is not registered or is currently inactive."))

	site = frappe.get_doc("Hotspot Site", found.name)
	_require_ap_mac(site, ap_mac)

	if not site.enable_free_trial:
		frappe.throw(_("Free trial is not available on this network."))

	if has_used_free_trial(site.name, client_mac):
		frappe.throw(_("This device has already used its free trial on this network."))

	if not _watched_free_trial_ad(site.name, client_mac):
		frappe.throw(_("Please watch the short ad to get your free internet."))

	duration_minutes = cint(site.free_trial_minutes) or 15

	txn = frappe.get_doc(
		{
			"doctype": "Hotspot Transaction",
			"site": site.name,
			"phone_number": "Free Trial",
			"client_mac": client_mac,
			"ap_mac": ap_mac,
			"ssid_name": ssid_name,
			"radio_id": radio_id,
			"package_name": "Free Trial",
			"amount": 0,
			"duration_minutes": duration_minutes,
			"status": "Paid",
			"reference_id": f"FREE_TRIAL:{client_mac}",
		}
	)
	txn.insert(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	result = {
		"transaction_id": txn.name,
		"status": "Paid",
		"duration_minutes": duration_minutes,
		"message": _("Free trial activated. You are now being connected."),
	}

	# Same synchronous-authorize-now shortcut redeem_voucher uses: this
	# is an immediate-response flow, not a payment waiting on a webhook,
	# so authorize right away and hand back a redirect_url directly.
	try:
		_authorize_transaction(txn, site)
		result.update(_connect_details(txn, site))
	except Exception:
		frappe.log_error(
			title=f"Bandofy Free Trial Omada Authorization Failed: {txn.name}",
			message=frappe.get_traceback(),
		)
		frappe.enqueue(
			"bandofy.api.authorize_mac_on_omada",
			queue="short",
			enqueue_after_commit=True,
			transaction_id=txn.name,
		)

	return result


@frappe.whitelist(allow_guest=True)
def log_ad_view(ad, ap_mac=None, client_mac=None, omada_site=None, ac_name=None):
	"""Record an ad impression on the captive portal and bump its view count."""
	if not ad or not frappe.db.exists("Hotspot Ad", ad):
		return {"ok": False}

	site_name = None
	if ap_mac or omada_site or ac_name:
		found = find_site(omada_site, ap_mac, active_only=False, ac_name=ac_name)
		site_name = found.name if found else None

	frappe.get_doc(
		{
			"doctype": "Hotspot Ad View Log",
			"ad": ad,
			"site": site_name,
			"ap_mac": ap_mac,
			"client_mac": client_mac,
		}
	).insert(ignore_permissions=True)

	frappe.db.set_value("Hotspot Ad", ad, "views_count", frappe.db.count("Hotspot Ad View Log", {"ad": ad}))
	frappe.db.commit()  # nosemgrep

	return {"ok": True}


@frappe.whitelist(allow_guest=True)
def send_chat_message(ap_mac=None, client_mac=None, message=None, omada_site=None, ac_name=None):
	"""Guest sends a chat message to the site's admin from the captive portal.

	Guests are anonymous -- the thread is keyed on (site, client_mac), the
	same identity every other guest-facing record in this app uses.
	"""
	if not (client_mac and message and (ap_mac or ac_name)):
		frappe.throw(_("Missing required parameters."))

	message = message.strip()
	if not message:
		frappe.throw(_("Message cannot be empty."))
	message = message[:CHAT_MESSAGE_MAX_LENGTH]

	found = find_site(omada_site, ap_mac, active_only=False, ac_name=ac_name)
	if not found:
		frappe.throw(_("This access point is not registered or is currently inactive."))

	doc = frappe.get_doc(
		{
			"doctype": "Hotspot Chat Message",
			"site": found.name,
			"client_mac": client_mac,
			"direction": "Guest",
			"message": message,
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	return {"name": doc.name, "creation": get_datetime_str(doc.creation)}


@frappe.whitelist(allow_guest=True)
def get_chat_messages(ap_mac=None, client_mac=None, after=None, omada_site=None, ac_name=None):
	"""Guest polls this to load/refresh their chat thread with the admin.

	``after`` (a previously-seen message's name) limits the response to
	messages created strictly after it, for cheap incremental polling once
	the initial history has been loaded.
	"""
	if not (client_mac and (ap_mac or ac_name)):
		frappe.throw(_("Missing required parameters."))

	found = find_site(omada_site, ap_mac, active_only=False, ac_name=ac_name)
	if not found:
		return {"messages": []}

	filters = {"site": found.name, "client_mac": client_mac}
	if after and frappe.db.exists("Hotspot Chat Message", after):
		filters["creation"] = [">", frappe.db.get_value("Hotspot Chat Message", after, "creation")]

	rows = frappe.get_all(
		"Hotspot Chat Message",
		filters=filters,
		fields=["name", "direction", "message", "creation"],
		order_by="creation asc",
		limit_page_length=200,
	)
	for row in rows:
		row["creation"] = get_datetime_str(row["creation"])

	return {"messages": rows}


def _require_ap_mac(site, ap_mac):
	if not ap_mac:
		frappe.throw(_("Missing required parameters."))


def _authorize_transaction(txn, site):
	"""Let this Paid transaction's device online, then flag the transaction
	so the portal page's status poll (see get_omada_connection_status) knows
	it can move on.

	Omada sites: authorize the client's MAC on the Omada Controller.
	Ruijie sites: set authorized_until (the AC handles the redirect itself).
	"""
	if site.get("controller_type") == "Ruijie":
		from frappe.utils import add_to_date
		until = add_to_date(now_datetime(), minutes=max(int(txn.duration_minutes or 0), 1))
		txn.db_set({"authorized_until": until, "omada_authorized": 1}, commit=True)
		return

	_authorize_on_omada(txn, site)
	txn.db_set("omada_authorized", 1, commit=True)
	_apply_package_bandwidth(txn, site)


def _connect_details(txn, site):
	"""What the portal page needs to finish connecting an authorized device:
	the redirect URL to send the browser to once authorized."""
	return {"redirect_url": _success_redirect_url(site.get("success_redirect_url"))}


def _authorize_on_omada(txn, site):
	"""Call omada_service.authorize_client for this transaction/site."""
	controller = site_controller(site)
	authorize_client(
		omada_host=controller["omada_host"],
		controller_id=controller["controller_id"],
		operator_username=controller["operator_username"],
		operator_password=controller["operator_password"],
		client_mac=txn.client_mac,
		ap_mac=txn.ap_mac,
		ssid_name=txn.ssid_name,
		site_name=controller["site_id"],
		duration_minutes=txn.duration_minutes,
		radio_id=txn.radio_id,
	)


def _apply_package_bandwidth(txn, site):
	"""When the site enforces package bandwidth, caps the client on Omada to
	its package's Download/Upload Kbps (found by package name; Free Trial,
	Staff Access etc. have no package row, so any earlier cap is removed).
	Never fails the authorization -- the customer is already online."""
	if not (site.get("enforce_bandwidth_limits") and site.omada_site_id):
		return
	# Rate limits are set through the Open API; without its keys there is
	# nothing to call (and every authorization would log an error).
	if not frappe.db.get_single_value("Hotspot Omada Settings", "client_id"):
		return
	package = next((p for p in site.packages if p.package_name == txn.package_name), None)
	digits = normalize_mac(txn.client_mac).upper()
	try:
		set_client_rate_limit(
			site.omada_site_id,
			"-".join(digits[i : i + 2] for i in range(0, 12, 2)),
			package.bandwidth_down_kbps if package else 0,
			package.bandwidth_up_kbps if package else 0,
		)
	except Exception:
		frappe.log_error(title=f"Bandofy bandwidth limit failed: {txn.name}", message=frappe.get_traceback())


def authorize_mac_on_omada(transaction_id):
	"""Get a paying client online: authorize its MAC on the Omada controller
	(Omada sites) or record authorized_until (Ruijie sites).

	Enqueued from :func:`payment_callback`/:func:`sync_pending_payments` once
	a transaction is marked Paid, and as a retry fallback when the
	synchronous attempt in :func:`redeem_voucher` fails. Endpoints/payload
	per TP-Link's official "API and Code Sample for External Portal Server
	(Omada Controller 5.0.15 or above)":
	https://support.omadanetworks.com/us/document/13080/
	"""
	txn = frappe.get_doc("Hotspot Transaction", transaction_id)
	site = frappe.get_doc("Hotspot Site", txn.site)

	try:
		_authorize_transaction(txn, site)
		frappe.logger("bandofy").info(f"Authorized {txn.client_mac} on {site.name} ({transaction_id})")
	except Exception:
		frappe.log_error(
			title=f"Bandofy Omada Authorization Failed: {transaction_id}",
			message=frappe.get_traceback(),
		)


@frappe.whitelist(allow_guest=True)
def get_omada_connection_status(transaction_id, client_mac=None):
	"""Polled by the portal page: reports whether authorize_mac_on_omada
	has completed for this transaction yet and, once it has, the redirect URL
	to send the browser to.
	"""
	txn = frappe.db.get_value(
		"Hotspot Transaction",
		transaction_id,
		["name", "status", "omada_authorized", "site", "client_mac"],
		as_dict=True,
	)
	if not txn:
		frappe.throw(_("Transaction not found."))

	if txn.status == "Failed":
		return {"ready": False, "failed": True}

	if not txn.omada_authorized:
		return {"ready": False}

	site = frappe.db.get_value(
		"Hotspot Site", txn.site, ["controller_type", "success_redirect_url"], as_dict=True
	)
	return {"ready": True, **_connect_details(txn, site)}


def restrict_desk_access():
	"""before_request hook: bounce non-System Manager users away from /app."""
	request = getattr(frappe.local, "request", None)
	if not request or not request.path.startswith("/app"):
		return

	if frappe.session.user == "Guest":
		return

	roles = frappe.get_roles(frappe.session.user)

	if "System Manager" in roles:
		return

	if "Occasion Manager" in roles and request.path.startswith("/app/occasion"):
		return

	frappe.local.flags.redirect_location = "/vendor-dashboard"
	raise frappe.Redirect


@frappe.whitelist()
def update_site_settings(site, site_name=None, phone_number=None, portal_tagline=None,
                          mobile_money_account=None, enable_online_payment=0,
                          enable_free_trial=0, free_trial_minutes=10, portal_primary_color=None):
	"""Update basic site settings from the /site-settings web page."""
	site_doc = frappe.get_doc("Hotspot Site", site)
	if site_doc.vendor_user != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not authorised."), frappe.PermissionError)

	if site_name:
		site_doc.site_name = site_name.strip()
	if phone_number is not None:
		site_doc.phone_number = phone_number
	if portal_tagline is not None:
		site_doc.portal_tagline = portal_tagline
	if mobile_money_account is not None:
		site_doc.mobile_money_account = mobile_money_account
	if portal_primary_color is not None:
		site_doc.portal_primary_color = portal_primary_color
	site_doc.enable_online_payment = int(enable_online_payment or 0)
	site_doc.enable_free_trial = int(enable_free_trial or 0)
	site_doc.free_trial_minutes = int(free_trial_minutes or 10)
	site_doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"updated": site}


@frappe.whitelist()
def add_package(site, package_name, package_type, price, duration_minutes, bandwidth_down_kbps=0, bandwidth_up_kbps=0, device_limit=0, data_limit_mb=0):
	"""Create a Hotspot Package and add it to the site's packages list."""
	site_doc = frappe.get_doc("Hotspot Site", site)
	if site_doc.vendor_user != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not authorised."), frappe.PermissionError)

	pkg = frappe.new_doc("Hotspot Package")
	pkg.package_name = package_name
	pkg.package_type = package_type
	pkg.price = float(price)
	pkg.duration_minutes = int(duration_minutes)
	pkg.bandwidth_down_kbps = int(bandwidth_down_kbps or 0)
	pkg.bandwidth_up_kbps = int(bandwidth_up_kbps or 0)
	pkg.device_limit = cint(device_limit)
	pkg.data_limit_mb = cint(data_limit_mb)
	pkg.insert(ignore_permissions=True)

	site_doc.append("packages", {
		"package_name": pkg.name,
		"package_type": pkg.package_type,
		"price": pkg.price,
		"duration_minutes": pkg.duration_minutes,
		"bandwidth_down_kbps": pkg.bandwidth_down_kbps,
		"bandwidth_up_kbps": pkg.bandwidth_up_kbps,
		"device_limit": pkg.device_limit,
		"data_limit_mb": pkg.data_limit_mb,
	})
	site_doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"package": pkg.name}


@frappe.whitelist()
def remove_package(site, package_name):
	"""Remove a package from the site's packages list."""
	site_doc = frappe.get_doc("Hotspot Site", site)
	if site_doc.vendor_user != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not authorised."), frappe.PermissionError)

	site_doc.packages = [p for p in site_doc.packages if p.package_name != package_name]
	if not site_doc.packages:
		frappe.throw(_("Cannot remove the last package. A site must have at least one package."))
	site_doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"removed": package_name}


@frappe.whitelist()
def add_device(site, ap_mac, label="", controller_type="Omada", ac_name=""):
	"""Add an Access Point to the site's devices child table."""
	site_doc = frappe.get_doc("Hotspot Site", site)
	if site_doc.vendor_user != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not authorised."), frappe.PermissionError)

	ap_mac = ap_mac.strip().upper()
	if not ap_mac:
		frappe.throw(_("AP MAC Address is required."))

	if controller_type not in ("Omada", "Ruijie"):
		frappe.throw(_("Invalid integration type."))

	if controller_type == "Ruijie" and not ac_name.strip():
		frappe.throw(_("AC Name is required for Ruijie integration."))

	for row in site_doc.devices:
		if row.ap_mac.upper() == ap_mac:
			frappe.throw(_("This MAC address is already registered."))

	site_doc.append("devices", {
		"ap_mac": ap_mac,
		"label": label.strip(),
		"controller_type": controller_type,
		"ac_name": ac_name.strip(),
		"is_active": 1,
	})
	site_doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"added": ap_mac}


@frappe.whitelist()
def remove_device(site, ap_mac):
	"""Remove an Access Point from the site's devices child table."""
	site_doc = frappe.get_doc("Hotspot Site", site)
	if site_doc.vendor_user != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not authorised."), frappe.PermissionError)

	ap_mac = ap_mac.strip().upper()
	site_doc.devices = [row for row in site_doc.devices if row.ap_mac.upper() != ap_mac]
	site_doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"removed": ap_mac}


@frappe.whitelist()
def toggle_device(site, ap_mac, is_active):
	"""Toggle active/inactive status of an Access Point."""
	site_doc = frappe.get_doc("Hotspot Site", site)
	if site_doc.vendor_user != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not authorised."), frappe.PermissionError)

	ap_mac = ap_mac.strip().upper()
	for row in site_doc.devices:
		if row.ap_mac.upper() == ap_mac:
			row.is_active = int(is_active)
			break
	site_doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {"toggled": ap_mac, "is_active": int(is_active)}


@frappe.whitelist()
def create_voucher_batch(site, package_name, quantity):
	"""Create a Hotspot Voucher Batch and generate individual vouchers for it.
	Called from /vouchers page by Bandofy Manager users.
	"""
	quantity = int(quantity or 0)
	if quantity < 1 or quantity > 500:
		frappe.throw(_("Quantity must be between 1 and 500."))

	site_doc = frappe.get_doc("Hotspot Site", site)
	if site_doc.vendor_user != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not authorised."), frappe.PermissionError)

	# Fetch package details
	pkg = frappe.get_doc("Hotspot Package", package_name)

	batch = frappe.new_doc("Hotspot Voucher Batch")
	batch.site = site
	batch.package_name = package_name
	batch.quantity = quantity
	batch.insert(ignore_permissions=True)

	# Generate individual vouchers
	import random, string
	for _ in range(quantity):
		code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
		v = frappe.new_doc("Hotspot Voucher")
		v.voucher_code = code
		v.site = site
		v.batch = batch.name
		v.package_name = package_name
		v.price = pkg.price
		v.duration_minutes = pkg.duration_minutes
		v.status = "Unused"
		v.insert(ignore_permissions=True)

	frappe.db.commit()
	return {"batch": batch.name, "count": quantity}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def register_manager(full_name, email, password, phone, site_name):
	"""Public signup: create a User + Hotspot Site, assign Bandofy Manager role,
	log the user in, and return a redirect to /vendor-dashboard.
	"""
	email = (email or "").strip().lower()
	full_name = (full_name or "").strip()
	site_name = (site_name or "").strip()
	phone = (phone or "").strip()

	# ── Validate ────────────────────────────────────────────────────────
	if not email or not full_name or not password or not site_name:
		frappe.throw(_("All fields are required."))

	if frappe.db.exists("User", email):
		frappe.throw(_("An account with this email already exists."))

	if frappe.db.exists("Hotspot Site", {"site_name": site_name}):
		frappe.throw(_("A hotspot site with that name already exists. Please choose a different name."))

	if len(password) < 8:
		frappe.throw(_("Password must be at least 8 characters."))

	# ── Create User ─────────────────────────────────────────────────────
	names = full_name.split(" ", 1)
	user = frappe.new_doc("User")
	user.email = email
	user.first_name = names[0]
	user.last_name = names[1] if len(names) > 1 else ""
	user.phone = phone
	user.mobile_no = phone
	user.send_welcome_email = 0
	user.append("roles", {"role": "Bandofy Manager"})
	user.insert(ignore_permissions=True)
	frappe.utils.password.update_password(email, password)

	# ── Read platform defaults ───────────────────────────────────────────
	try:
		ps = frappe.get_single("Hotspot Platform Settings")
		pkg_name = ps.default_pkg_name or "1 Hour"
		pkg_price = ps.default_pkg_price or 500
		pkg_duration = ps.default_pkg_duration or 60
		trial_days = ps.trial_days or 7
	except Exception:
		pkg_name = "1 Hour"
		pkg_price = 500
		pkg_duration = 60
		trial_days = 7

	# ── Create Hotspot Site ──────────────────────────────────────────────
	# Create a default package first
	pkg = frappe.new_doc("Hotspot Package")
	pkg.package_name = pkg_name
	pkg.package_type = "Unlimited"
	pkg.price = pkg_price
	pkg.duration_minutes = pkg_duration
	pkg.insert(ignore_permissions=True)

	site = frappe.new_doc("Hotspot Site")
	site.site_name = site_name
	site.vendor_name = site_name
	site.vendor_user = email
	site.phone_number = phone
	site.is_active = 1
	site.controller_type = "Omada"
	site.subscription_status = "Trial"
	site.trial_expires_on = frappe.utils.add_days(frappe.utils.today(), trial_days)
	site.append("packages", {
		"package_name": pkg.name,
		"package_type": pkg.package_type,
		"price": pkg.price,
		"duration_minutes": pkg.duration_minutes,
	})
	site.insert(ignore_permissions=True)
	site.db_set("nas_identifier", f"bdy-{site.name}")

	frappe.db.commit()

	# ── Log the user in ──────────────────────────────────────────────────
	frappe.local.login_manager.login_as(email)

	return {"redirect": "/onboarding"}


@frappe.whitelist()
def get_device_statuses(site):
	"""Return device list with online status for the Devices page."""
	site_doc = frappe.get_doc("Hotspot Site", site)
	if frappe.session.user != site_doc.vendor_user and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not permitted"), frappe.PermissionError)
	return [
		{
			"ap_mac": d.ap_mac,
			"label": d.label,
			"controller_type": d.controller_type,
			"is_active": d.is_active,
			"online": None,
		}
		for d in site_doc.devices
	]


@frappe.whitelist()
def request_withdrawal(site, amount, phone_number, network):
	"""Submit a withdrawal request against the site's available earnings balance."""
	site_doc = frappe.get_doc("Hotspot Site", site)
	if frappe.session.user != site_doc.vendor_user and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	amount = frappe.utils.flt(amount)
	if amount <= 0:
		frappe.throw(_("Amount must be greater than zero"))

	total_earned = frappe.db.get_value(
		"Hotspot Transaction",
		{"site": site, "status": "Paid"},
		"sum(amount)",
	) or 0
	total_withdrawn = frappe.db.get_value(
		"Hotspot Withdrawal",
		{"site": site, "status": "Approved"},
		"sum(amount)",
	) or 0
	available = frappe.utils.flt(total_earned) - frappe.utils.flt(total_withdrawn)
	if amount > available:
		frappe.throw(_(f"Amount exceeds available balance of TZS {available:,.0f}"))

	doc = frappe.new_doc("Hotspot Withdrawal")
	doc.site = site
	doc.amount = amount
	doc.phone_number = phone_number
	doc.network = network
	doc.status = "Pending"
	doc.requested_on = frappe.utils.now()
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name
