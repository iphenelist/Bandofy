# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import hashlib
import hmac
import json

import frappe
import requests
from frappe import _
from frappe.utils import add_to_date, get_url, getdate, now_datetime, nowdate

from foh_ms.omada_service import authorize_client
from foh_ms.utils import find_site_by_ap_mac

DEFAULT_SUCCESS_REDIRECT_URL = "https://www.google.com"
PAYMENT_POLL_GRACE_SECONDS = 90  # give the webhook this long to arrive before polling
PAYMENT_POLL_MAX_AGE_MINUTES = 60  # transactions still Pending after this are given up on


@frappe.whitelist(allow_guest=True)
def initiate_payment(phone, package_idx, client_mac, ap_mac, ssid_name=None, radio_id=None):
	"""Create a Pending Hotspot Transaction and kick off the STK push.

	Called by the captive portal (wifi_login.html) once a customer picks a
	plan and enters their Mobile Money number.
	"""
	if not (phone and package_idx and client_mac and ap_mac):
		frappe.throw(_("Missing required parameters."))

	found = find_site_by_ap_mac(ap_mac)
	if not found:
		frappe.throw(_("This access point is not registered or is currently inactive."))

	site = frappe.get_doc("Hotspot Site", found.name)

	if not site.enable_online_payment:
		frappe.throw(_("Mfumo wa kulipa kwa pesa upo katika matengenezo."))

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
		frappe.log_error(
			title=f"FOH-MS STK Push Failed: {txn.name}", message=frappe.get_traceback()
		)
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
		frappe.logger("foh_ms").info(
			f"Payment gateway disabled/unconfigured; STK push stub for {phone} "
			f"amount={amount} txn={transaction_id}"
		)
		return {
			"reference_id": None,
			"message": _("STK push sent. Please check your phone to complete the payment."),
		}

	base_url = (settings.base_url or "https://api.snippe.sh").strip().rstrip("/")
	timeout = max(5, min(int(settings.request_timeout or 30), 120))
	currency = (settings.default_currency or "TZS").strip().upper()

	payload = {
		"payment_type": "mobile",
		"details": {"amount": int(round(amount)), "currency": currency},
		"customer": {
			"firstname": "Hotspot",
			"lastname": "Customer",
			"email": "noreply@foh-ms.local",
		},
		"phone_number": phone,
		"webhook_url": get_url("/api/method/foh_ms.api.payment_callback"),
		"metadata": {"transaction_id": transaction_id},
	}

	response = requests.post(
		f"{base_url}/v1/payments",
		headers={
			"Authorization": f"Bearer {api_key}",
			"Content-Type": "application/json",
			"Idempotency-Key": transaction_id,
		},
		json=payload,
		timeout=timeout,
	)
	response.raise_for_status()
	body = response.json()

	if body.get("status") == "error":
		frappe.throw(body.get("message") or _("Payment gateway returned an error."))

	data = body.get("data") or {}
	reference = data.get("reference") or data.get("id")

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

	webhook_secret = (settings.get_password("webhook_secret") or "").strip()
	if webhook_secret and not _verify_webhook_signature(webhook_secret, raw_body):
		frappe.local.response["http_status_code"] = 401
		return {"status": "error", "message": "Invalid webhook signature"}

	try:
		payload = json.loads(raw_body) if raw_body else dict(frappe.local.form_dict)
	except json.JSONDecodeError:
		frappe.local.response["http_status_code"] = 400
		return {"status": "error", "message": "Invalid JSON payload"}

	event_type = (payload.get("type") or frappe.get_request_header("X-Webhook-Event") or "").strip().lower()
	data = payload.get("data") or payload
	metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}

	transaction_id = (metadata.get("transaction_id") or data.get("transaction_id") or "").strip()
	reference_id = (data.get("reference") or data.get("id") or data.get("reference_id") or "").strip()
	gateway_status = str(data.get("status") or "").strip().lower()

	txn_name = None
	if transaction_id and frappe.db.exists("Hotspot Transaction", transaction_id):
		txn_name = transaction_id
	elif reference_id:
		txn_name = frappe.db.get_value("Hotspot Transaction", {"reference_id": reference_id})

	if not txn_name:
		frappe.log_error(
			title="FOH-MS Payment Callback: Transaction Not Found", message=frappe.as_json(payload)
		)
		frappe.local.response["http_status_code"] = 404
		return {"status": "error", "message": "Transaction not found"}

	txn = frappe.get_doc("Hotspot Transaction", txn_name)

	if txn.status != "Pending":
		# Already processed by an earlier delivery of this event, or by the
		# fallback poller — avoid double-authorizing the client.
		return {"status": "ok", "message": "Already processed"}

	if event_type == "payment.completed" or gateway_status in ("completed", "success", "successful", "paid"):
		_mark_transaction_paid(txn, reference_id, settings)
		return {"status": "success"}

	if event_type == "payment.failed" or gateway_status in ("failed", "voided", "expired", "cancelled"):
		txn.status = "Failed"
		txn.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep
		return {"status": "failed"}

	return {"status": "pending"}


def _mark_transaction_paid(txn, reference_id, settings):
	txn.status = "Paid"
	if reference_id:
		txn.reference_id = reference_id

	authorization_method = frappe.db.get_value("Hotspot Site", txn.site, "authorization_method")
	if authorization_method == "Local RADIUS Server":
		_issue_radius_token(txn)

	txn.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep

	if authorization_method == "Local RADIUS Server":
		# Independent of the Omada Controller path below: the EAP itself
		# authorizes the client once its browser completes RADIUS login via
		# the credentials from get_radius_credentials(). See radius_server.py.
		return

	if settings.auto_authorize_on_payment:
		frappe.enqueue(
			"foh_ms.api.authorize_mac_on_omada",
			queue="short",
			enqueue_after_commit=True,
			transaction_id=txn.name,
		)


def _issue_radius_token(txn):
	"""Generate the one-time credential a 'Local RADIUS Server' site's
	client browser will submit back through the EAP. Read by
	foh_ms.radius_server.validate_session; unused for Omada-Controller-API
	sites.
	"""
	txn.radius_token = frappe.generate_hash(length=20)
	txn.authorized_until = add_to_date(now_datetime(), minutes=txn.duration_minutes or 0)


def _extract_signature(signature_header):
	signature = (signature_header or "").strip()
	if not signature:
		return ""
	if "," in signature:
		for part in signature.split(","):
			token = part.strip()
			if token.startswith("v1="):
				return token.split("=", 1)[1].strip()
	if "=" in signature:
		return signature.split("=", 1)[1].strip()
	return signature


def _verify_webhook_signature(webhook_secret, raw_body):
	signature = _extract_signature(frappe.get_request_header("X-Webhook-Signature") or "")
	if not signature:
		return False

	timestamp = (frappe.get_request_header("X-Webhook-Timestamp") or "").strip()
	if timestamp:
		signed_payload = f"{timestamp}.{raw_body}".encode()
		expected = hmac.new(webhook_secret.encode(), signed_payload, hashlib.sha256).hexdigest()
		if hmac.compare_digest(expected, signature):
			return True

	# Fallback for gateways that sign the raw body without a timestamp.
	expected_legacy = hmac.new(webhook_secret.encode(), raw_body.encode(), hashlib.sha256).hexdigest()
	return hmac.compare_digest(expected_legacy, signature)


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

	base_url = (settings.base_url or "https://api.snippe.sh").strip().rstrip("/")
	timeout = max(5, min(int(settings.request_timeout or 30), 120))

	for row in pending:
		if not row.reference_id:
			if row.creation <= cutoff_old:
				frappe.db.set_value("Hotspot Transaction", row.name, "status", "Failed")
			continue

		try:
			response = requests.get(
				f"{base_url}/v1/payments/{row.reference_id}",
				headers={"Authorization": f"Bearer {api_key}"},
				timeout=timeout,
			)
			response.raise_for_status()
			data = (response.json() or {}).get("data") or {}
			gateway_status = str(data.get("status") or "").strip().lower()
		except Exception:
			frappe.log_error(
				title=f"FOH-MS Payment Poll Failed: {row.name}", message=frappe.get_traceback()
			)
			continue

		if gateway_status in ("completed", "success", "successful", "paid"):
			txn = frappe.get_doc("Hotspot Transaction", row.name)
			_mark_transaction_paid(txn, row.reference_id, settings)
		elif gateway_status in ("failed", "voided", "expired", "cancelled"):
			frappe.db.set_value("Hotspot Transaction", row.name, "status", "Failed")
		elif row.creation <= cutoff_old:
			frappe.db.set_value("Hotspot Transaction", row.name, "status", "Failed")

	frappe.db.commit()  # nosemgrep


@frappe.whitelist(allow_guest=True)
def redeem_voucher(voucher_code, client_mac, ap_mac, ssid_name=None, radio_id=None):
	"""Redeem a pre-generated Hotspot Voucher in place of an STK Push payment."""
	if not (voucher_code and client_mac and ap_mac):
		frappe.throw(_("Missing required parameters."))

	found = find_site_by_ap_mac(ap_mac)
	if not found:
		frappe.throw(_("This access point is not registered or is currently inactive."))
	site_name = found.name

	voucher_code = voucher_code.strip().upper()

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

	authorization_method = frappe.db.get_value("Hotspot Site", site_name, "authorization_method")

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
	if authorization_method == "Local RADIUS Server":
		_issue_radius_token(txn)
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

	if authorization_method != "Local RADIUS Server":
		# Voucher redemption is already a synchronous, immediate-response
		# flow (unlike payment, which waits on a webhook) -- authorize now so
		# we can hand the portal page a redirect_url in this same response.
		# On failure, fall back to the async retry queue instead of leaving
		# an already-consumed voucher stuck with no authorization attempt.
		site = frappe.get_doc("Hotspot Site", site_name)
		try:
			_authorize_transaction_on_omada(txn, site)
			result["redirect_url"] = site.success_redirect_url or DEFAULT_SUCCESS_REDIRECT_URL
		except Exception:
			frappe.log_error(
				title=f"FOH-MS Omada Authorization Failed: {txn.name}",
				message=frappe.get_traceback(),
			)
			frappe.enqueue(
				"foh_ms.api.authorize_mac_on_omada",
				queue="short",
				enqueue_after_commit=True,
				transaction_id=txn.name,
			)

	return result


@frappe.whitelist(allow_guest=True)
def get_radius_credentials(transaction_id):
	"""For 'Local RADIUS Server' sites: hand the portal page the one-time
	username/password it must submit back through the EAP so it completes
	RADIUS login. Independent of authorize_mac_on_omada -- unused for
	'Omada Controller API' sites.
	"""
	txn = frappe.db.get_value(
		"Hotspot Transaction",
		transaction_id,
		["status", "radius_token", "site", "client_mac", "ap_mac"],
		as_dict=True,
	)
	if not txn or txn.status != "Paid" or not txn.radius_token:
		frappe.throw(_("Transaction is not ready yet."))

	site = frappe.db.get_value(
		"Hotspot Site", txn.site, ["authorization_method", "ap_login_url_template"], as_dict=True
	)
	if not site or site.authorization_method != "Local RADIUS Server":
		frappe.throw(_("This access point does not use local RADIUS authorization."))

	login_url = None
	if site.ap_login_url_template:
		login_url = (
			site.ap_login_url_template.replace("{username}", transaction_id)
			.replace("{password}", txn.radius_token)
			.replace("{client_mac}", txn.client_mac or "")
			.replace("{ap_mac}", txn.ap_mac or "")
		)

	return {
		"username": transaction_id,
		"password": txn.radius_token,
		"login_url": login_url,
	}


@frappe.whitelist(allow_guest=True)
def log_ad_view(ad, ap_mac=None, client_mac=None):
	"""Record an ad impression on the captive portal and bump its view count."""
	if not ad or not frappe.db.exists("Hotspot Ad", ad):
		return {"ok": False}

	site_name = None
	if ap_mac:
		found = find_site_by_ap_mac(ap_mac, active_only=False)
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


def _authorize_transaction_on_omada(txn, site):
	"""Call omada_service.authorize_client for this transaction/site and, on
	success, flag the transaction so the portal page's status poll (see
	get_omada_connection_status) knows it can redirect the browser out of
	the captive portal. Raises OmadaAuthError/Exception on failure -- callers
	decide whether to retry synchronously or via the queue.
	"""
	authorize_client(
		omada_host=f"https://{site.controller_ip}:{site.port}",
		controller_id=site.controller_id,
		operator_username=site.omada_username,
		operator_password=site.get_password("omada_password"),
		client_mac=txn.client_mac,
		ap_mac=txn.ap_mac,
		ssid_name=txn.ssid_name,
		site_name=site.site_id,
		duration_minutes=txn.duration_minutes,
		radio_id=txn.radio_id,
	)
	txn.db_set("omada_authorized", 1, commit=True)


def authorize_mac_on_omada(transaction_id):
	"""Authorize a paying client's MAC address on its site's Omada controller.

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
		_authorize_transaction_on_omada(txn, site)
		frappe.logger("foh_ms").info(f"Authorized {txn.client_mac} on {site.name} ({transaction_id})")
	except Exception:
		frappe.log_error(
			title=f"FOH-MS Omada Authorization Failed: {transaction_id}",
			message=frappe.get_traceback(),
		)


@frappe.whitelist(allow_guest=True)
def get_omada_connection_status(transaction_id):
	"""Polled by the portal page for 'Omada Controller API' sites: reports
	whether authorize_mac_on_omada has completed for this transaction yet,
	and the URL to send the browser to once it has, to break it out of the
	captive portal. Independent of get_radius_credentials, which serves the
	equivalent purpose for 'Local RADIUS Server' sites.
	"""
	txn = frappe.db.get_value(
		"Hotspot Transaction",
		transaction_id,
		["status", "omada_authorized", "site"],
		as_dict=True,
	)
	if not txn:
		frappe.throw(_("Transaction not found."))

	if txn.status == "Failed":
		return {"ready": False, "failed": True}

	if not txn.omada_authorized:
		return {"ready": False}

	redirect_url = frappe.db.get_value("Hotspot Site", txn.site, "success_redirect_url")
	return {"ready": True, "redirect_url": redirect_url or DEFAULT_SUCCESS_REDIRECT_URL}


def restrict_desk_access():
	"""before_request hook: bounce non-System Manager users away from /app.

	Vendors only ever have access to the /vendor-dashboard portal page; they
	must never reach the Frappe Desk backend.
	"""
	request = getattr(frappe.local, "request", None)
	if not request or not request.path.startswith("/app"):
		return

	if frappe.session.user == "Guest":
		return

	if "System Manager" in frappe.get_roles(frappe.session.user):
		return

	frappe.local.flags.redirect_location = "/vendor-dashboard"
	raise frappe.Redirect
