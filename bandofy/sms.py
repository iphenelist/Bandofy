import frappe


def send_sms(phone, message):
	"""Send SMS via NextSMS API if enabled in platform settings."""
	try:
		settings = frappe.get_single("Hotspot Platform Settings")
		if not settings.sms_enabled or not settings.sms_api_key:
			return
		if not phone or phone in ("Free Trial", "Staff", "Voucher"):
			return

		import base64
		import requests

		token = base64.b64encode(f"{settings.sms_api_key}:".encode()).decode()
		requests.post(
			"https://messaging.nextsms.co.tz/api/sms/v1/text/single",
			headers={
				"Authorization": f"Basic {token}",
				"Content-Type": "application/json",
			},
			json={
				"from": settings.sms_sender_id or "BANDOFY",
				"to": phone,
				"text": message,
			},
			timeout=8,
		)
	except Exception:
		frappe.log_error("SMS send failed", "Bandofy SMS")
