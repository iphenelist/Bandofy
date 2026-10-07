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

import frappe
import requests
import urllib3
from frappe.utils import cint

OMADA_AUTH_TYPE_MAC = 4
DEFAULT_TIMEOUT = 10


class OmadaAuthError(Exception):
	"""Raised when the Omada Controller rejects the login or client
	authorization call, or the response doesn't have the expected shape."""


def _settings():
	"""(request timeout, verify SSL) from Hotspot Omada Settings, falling
	back to the old hard-coded behaviour if the single isn't there yet."""
	try:
		settings = frappe.get_cached_doc("Hotspot Omada Settings")
		return cint(settings.request_timeout) or DEFAULT_TIMEOUT, bool(settings.verify_ssl)
	except Exception:
		return DEFAULT_TIMEOUT, False


def site_controller(site):
	"""Connection arguments for one Hotspot Site's Omada calls: the central
	controller and hotspot operator from Hotspot Omada Settings, plus this
	site's own Omada site ID. ``site`` is a Hotspot Site doc or dict."""
	settings = frappe.get_cached_doc("Hotspot Omada Settings")
	password = settings.get_password("operator_password", raise_exception=False)
	if not (settings.controller_url and settings.operator_name and password):
		raise OmadaAuthError("Set the Controller URL and Hotspot Operator in Hotspot Omada Settings first.")
	site_id = site.get("omada_site_id")
	if not site_id:
		raise OmadaAuthError(
			f"{site.get('site_name') or site.get('name')} isn't set up on the Omada Controller yet."
		)

	controller_id = settings.omadac_id
	if not controller_id:
		session = _new_session()
		try:
			controller_id = (
				session.get(f"{settings.controller_url}/api/info", timeout=_settings()[0])
				.json()
				.get("result")
				or {}
			).get("omadacId")
		except (requests.RequestException, ValueError) as e:
			raise OmadaAuthError(f"Could not reach the Omada Controller: {e}") from e
		if not controller_id:
			raise OmadaAuthError("The Omada Controller did not report its Controller ID.")
		frappe.db.set_single_value("Hotspot Omada Settings", "omadac_id", controller_id)
		frappe.clear_document_cache("Hotspot Omada Settings", "Hotspot Omada Settings")

	return {
		"omada_host": settings.controller_url,
		"controller_id": controller_id,
		"operator_username": settings.operator_name,
		"operator_password": password,
		"site_id": site_id,
	}


def _new_session():
	"""Controllers usually present self-signed certificates, so verification
	is off unless Hotspot Omada Settings turns it on."""
	session = requests.Session()
	session.verify = _settings()[1]
	if not session.verify:
		urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
	return session


def _operator_login(base_url, operator_username, operator_password, timeout=None):
	"""Log in as an Omada Hotspot Operator. Returns (session, csrf_token) for
	the caller to make further authenticated calls with -- shared by
	authorize_client, list_devices, and reboot_device. Raises OmadaAuthError
	on any failure."""
	timeout = timeout or _settings()[0]
	session = _new_session()

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
	timeout=None,
):
	"""Log in as an Omada Hotspot Operator and authorize a client's MAC.

	Returns the parsed JSON body of the extPortal/auth response on success
	(errorCode 0). Raises OmadaAuthError on any failure.
	"""
	timeout = timeout or _settings()[0]
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


def list_devices(omada_host, controller_id, operator_username, operator_password, site_id, timeout=None):
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
	timeout = timeout or _settings()[0]
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
	omada_host, controller_id, operator_username, operator_password, site_id, device_mac, timeout=None
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
	timeout = timeout or _settings()[0]
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


def get_live_stats(omada_host, controller_id, operator_username, operator_password, site_id, timeout=5):
	"""Controller status plus best-effort live client/traffic numbers for the
	dashboards.

	`connected` means the Hotspot Operator login succeeded -- the same login
	authorize_client depends on, so it matches whether customers can actually
	get online. The client list is fetched from the Hotspot Manager API
	(`.../api/v2/hotspot/sites/{siteId}/clients`), which is not part of
	TP-Link's documented External Portal API; if it fails, `connected` stays
	True and `error` explains why the numbers are missing.

	Raises OmadaAuthError if the login itself fails.
	"""
	timeout = timeout or _settings()[0]
	base_url = f"{omada_host.rstrip('/')}/{controller_id}"
	session, token = _operator_login(base_url, operator_username, operator_password, timeout)

	stats = {"connected": True, "client_count": 0, "tx_rate": 0, "rx_rate": 0, "error": None}
	try:
		resp = session.get(
			f"{base_url}/api/v2/hotspot/sites/{site_id}/clients",
			params={"currentPage": 1, "currentPageSize": 100},
			headers={"Csrf-Token": token},
			timeout=timeout,
		)
		resp.raise_for_status()
		data = resp.json()
		if data.get("errorCode") not in (0, None):
			raise OmadaAuthError(data.get("msg") or f"errorCode {data.get('errorCode')}")

		result = data.get("result") or {}
		clients = result.get("data") or []
		stats["client_count"] = result.get("totalRows", len(clients))
		for client in clients:
			stats["tx_rate"] += client.get("trafficDown", 0) or 0
			stats["rx_rate"] += client.get("trafficUp", 0) or 0
	except (requests.RequestException, ValueError, OmadaAuthError) as e:
		stats["error"] = f"Live traffic unavailable: {e}"

	return stats


def _probe(session, method, url, **kwargs):
	"""One diagnostic request -> (ok, detail, json body or None). Never raises."""
	try:
		resp = session.request(method, url, **kwargs)
	except requests.RequestException as e:
		return False, f"Request failed: {e}", None

	try:
		data = resp.json()
	except ValueError:
		return False, f"HTTP {resp.status_code}, not a JSON response: {resp.text[:160]!r}", None

	error_code = data.get("errorCode")
	ok = resp.ok and error_code in (0, None)
	detail = f"HTTP {resp.status_code}, errorCode {error_code}"
	if data.get("msg"):
		detail += f": {data['msg']}"
	return ok, detail, data


def diagnose(omada_host, controller_id, operator_username, operator_password, site_id, timeout=8):
	"""Step-by-step connectivity check against a site's Omada Controller, for
	operators who can't open the controller UI themselves. Read-only -- it
	never authorizes a client or reboots anything.

	Returns a list of {"step", "ok", "detail"} dicts. Credentials are never
	included in the output.
	"""
	steps = []

	def add(step, ok, detail):
		steps.append({"step": step, "ok": bool(ok), "detail": detail})

	host = omada_host.rstrip("/")
	session = _new_session()

	# 1. Reachability + the controller's real Omadac ID, from its public info endpoint.
	ok, detail, data = _probe(session, "GET", f"{host}/api/info", timeout=timeout)
	if data is None:
		add("Reach controller", False, f"{host}: {detail}")
		return steps

	info = data.get("result") or {}
	real_id = info.get("omadacId")
	version = info.get("controllerVer")
	add("Reach controller", True, f"{host} answered (controller version {version or 'unknown'})")

	if real_id:
		if real_id == controller_id:
			add("Controller ID", True, "Matches the controller")
		else:
			add(
				"Controller ID",
				False,
				f"Settings have '{controller_id}' but the controller reports '{real_id}'. Run Test Connection in Hotspot Omada Settings.",
			)
			controller_id = real_id

	base_url = f"{host}/{controller_id}"

	# 2. Hotspot Operator login -- what client authorization depends on.
	try:
		session, token = _operator_login(base_url, operator_username, operator_password, timeout)
	except OmadaAuthError as e:
		add("Operator login", False, str(e))
		return steps
	add("Operator login", True, f"Logged in as '{operator_username}'")

	headers = {"Csrf-Token": token}

	# 3. Live client list (dashboard traffic numbers).
	ok, detail, _ = _probe(
		session,
		"GET",
		f"{base_url}/api/v2/hotspot/sites/{site_id}/clients",
		params={"currentPage": 1, "currentPageSize": 1},
		headers=headers,
		timeout=timeout,
	)
	add(f"Client list (site '{site_id}')", ok, detail)

	# 4. Device list (Devices screen status, and what reboot relies on).
	ok, detail, _ = _probe(
		session,
		"GET",
		f"{base_url}/api/v2/sites/{site_id}/devices",
		params={"token": token},
		headers=headers,
		timeout=timeout,
	)
	add("Device list", ok, detail)

	return steps
