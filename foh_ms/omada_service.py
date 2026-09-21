# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

"""Two-step TP-Link Omada SDN Controller "External Portal Server" auth.

Per TP-Link's official "API and Code Sample for External Portal Server
(Omada Controller 5.0.15 or above)": https://support.omadanetworks.com/us/document/13080/

    1. Operator login -- POST {host}/{controller_id}/api/v2/hotspot/login
       with {"name": ..., "password": ...} to get a Csrf-Token (and session
       cookie) for the Hotspot Operator account.
    2. Client authorization -- POST {host}/{controller_id}/api/v2/hotspot/extPortal/auth
       with the Csrf-Token header (and cookie) plus the client's MAC/AP/SSID
       to actually let it onto the network.

Both calls must go to the right endpoint or the controller rejects them --
sending credentials to extPortal/auth or the client payload to login always
fails.
"""

import requests
import urllib3

OMADA_AUTH_TYPE_MAC = 4


class OmadaAuthError(Exception):
	"""Raised when the Omada Controller rejects the login or client
	authorization call, or the response doesn't have the expected shape."""


def _operator_login(base_url, operator_username, operator_password, timeout=10):
	"""Log in as an Omada Hotspot Operator. Returns (session, csrf_token) for
	the caller to make further authenticated calls with -- shared by
	authorize_client, list_devices, and reboot_device. Raises OmadaAuthError
	on any failure."""
	session = requests.Session()
	session.verify = False
	urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

	try:
		login_resp = session.post(
			f"{base_url}/api/v2/hotspot/login",
			json={"name": operator_username, "password": operator_password},
			timeout=timeout,
		)
		login_resp.raise_for_status()
	except requests.RequestException as e:
		raise OmadaAuthError(f"Omada operator login request failed: {e}") from e

	login_data = login_resp.json()
	if login_data.get("errorCode") not in (0, None):
		raise OmadaAuthError(f"Omada operator login failed: {login_data}")

	token = (login_data.get("result") or {}).get("token")
	if not token:
		raise OmadaAuthError(f"Omada login did not return a Csrf-Token: {login_data}")

	return session, token


def authorize_client(
	omada_host,
	controller_id,
	operator_username,
	operator_password,
	client_mac,
	ap_mac,
	ssid_name,
	site_name,
	duration_minutes,
	radio_id=0,
	timeout=10,
):
	"""Log in as an Omada Hotspot Operator and authorize a client's MAC.

	Returns the parsed JSON body of the extPortal/auth response on success
	(errorCode 0). Raises OmadaAuthError on any failure.
	"""
	base_url = f"{omada_host.rstrip('/')}/{controller_id}"
	session, token = _operator_login(base_url, operator_username, operator_password, timeout)

	try:
		auth_resp = session.post(
			f"{base_url}/api/v2/hotspot/extPortal/auth",
			headers={"Csrf-Token": token},
			json={
				"clientMac": client_mac,
				"apMac": ap_mac,
				"ssidName": ssid_name,
				"radioId": int(radio_id or 0),
				"site": site_name,
				"time": int(duration_minutes or 0) * 60 * 1000,
				"authType": OMADA_AUTH_TYPE_MAC,
			},
			timeout=timeout,
		)
		auth_resp.raise_for_status()
	except requests.RequestException as e:
		raise OmadaAuthError(f"Omada client authorization request failed: {e}") from e

	auth_data = auth_resp.json()
	if auth_data.get("errorCode") not in (0, None):
		raise OmadaAuthError(f"Omada client authorization failed: {auth_data}")

	return auth_data


def list_devices(
	omada_host, controller_id, operator_username, operator_password, site_id, timeout=10
):
	"""List the Access Points/switches/gateways adopted under an Omada site.

	NOTE: unlike authorize_client and its extPortal/login endpoints (which
	are TP-Link's officially documented External Portal Server API), this
	endpoint pattern (`GET .../api/v2/sites/{siteId}/devices`) is inferred
	from the same internal Omada Controller API family and hasn't been
	exercised against a live controller in this project. Verify it against
	your controller version before relying on it.

	Returns a list of {mac, name, type, status, model, ip} dicts. Raises
	OmadaAuthError on failure.
	"""
	base_url = f"{omada_host.rstrip('/')}/{controller_id}"
	session, token = _operator_login(base_url, operator_username, operator_password, timeout)

	try:
		resp = session.get(
			f"{base_url}/api/v2/sites/{site_id}/devices",
			params={"token": token},
			headers={"Csrf-Token": token},
			timeout=timeout,
		)
		resp.raise_for_status()
	except requests.RequestException as e:
		raise OmadaAuthError(f"Omada device list request failed: {e}") from e

	data = resp.json()
	if data.get("errorCode") not in (0, None):
		raise OmadaAuthError(f"Omada device list failed: {data}")

	result = data.get("result")
	devices = result if isinstance(result, list) else (result or {}).get("data") or []

	return [
		{
			"mac": device.get("mac"),
			"name": device.get("name"),
			"type": device.get("type"),
			"status": device.get("status"),
			"model": device.get("model") or device.get("showModel"),
			"ip": device.get("ip"),
		}
		for device in devices
	]


def reboot_device(
	omada_host, controller_id, operator_username, operator_password, site_id, device_mac, timeout=10
):
	"""Reboot a single adopted device by MAC. Disconnects every client
	currently on it -- callers should confirm with the operator before
	calling this.

	NOTE: same caveat as list_devices -- this endpoint pattern
	(`POST .../api/v2/sites/{siteId}/devices/{mac}/reboot`) hasn't been
	verified against a live controller in this project. Test it against a
	device with no active customers before relying on it in production.

	Raises OmadaAuthError on failure.
	"""
	base_url = f"{omada_host.rstrip('/')}/{controller_id}"
	session, token = _operator_login(base_url, operator_username, operator_password, timeout)

	try:
		resp = session.post(
			f"{base_url}/api/v2/sites/{site_id}/devices/{device_mac}/reboot",
			headers={"Csrf-Token": token},
			timeout=timeout,
		)
		resp.raise_for_status()
	except requests.RequestException as e:
		raise OmadaAuthError(f"Omada device reboot request failed: {e}") from e

	data = resp.json()
	if data.get("errorCode") not in (0, None):
		raise OmadaAuthError(f"Omada device reboot failed: {data}")

	return True
