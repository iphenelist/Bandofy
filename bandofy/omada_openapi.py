# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

"""Client for the TP-Link Omada Open API (the controller's official
northbound API, documented at <controller>/swagger-ui/index.html) -- used to
create sites, adopt devices, and manage SSIDs, portals and hotspot operators
on the central controller configured in Hotspot Omada Settings.

Separate from bandofy.omada_service, which logs in as the hotspot operator to
authorize customers; that account can't manage sites or devices.

Auth is OAuth2 client credentials: POST /openapi/authorize/token returns an
access token (2 h) that every call sends as ``Authorization: AccessToken=...``.
"""

import frappe
import requests
from frappe import _

from bandofy.omada_service import _new_session, _settings

TOKEN_CACHE_KEY = "bandofy:omada_openapi_token"
PAGE_SIZE = 1000
# Open API error codes for an expired (-44112) or invalid (-44113) access token.
TOKEN_ERROR_CODES = {-44112, -44113}


class OmadaApiError(Exception):
	"""The controller rejected an Open API call (or wasn't reachable)."""


def _config():
	settings = frappe.get_cached_doc("Hotspot Omada Settings")
	if not (settings.controller_url and settings.client_id and settings.client_secret):
		raise OmadaApiError(
			_("Set the Controller URL and Open API Client ID/Secret in Hotspot Omada Settings first.")
		)
	return settings


def controller_info(controller_url=None):
	"""The controller's public /api/info (version, omadacId) -- no auth."""
	url = (controller_url or _config().controller_url).rstrip("/")
	try:
		resp = _new_session().get(f"{url}/api/info", timeout=_settings()[0])
		resp.raise_for_status()
		data = resp.json()
	except (requests.RequestException, ValueError) as e:
		raise OmadaApiError(_("Could not reach the Omada Controller at {0}: {1}").format(url, e)) from e
	if data.get("errorCode") not in (0, None):
		raise OmadaApiError(data.get("msg") or str(data))
	return data.get("result") or {}


def _omadac_id(settings):
	if settings.omadac_id:
		return settings.omadac_id
	omadac_id = controller_info(settings.controller_url).get("omadacId")
	if not omadac_id:
		raise OmadaApiError(_("The controller did not report its Controller ID."))
	frappe.db.set_single_value("Hotspot Omada Settings", "omadac_id", omadac_id)
	frappe.clear_document_cache("Hotspot Omada Settings", "Hotspot Omada Settings")
	return omadac_id


def _token(force=False):
	if not force:
		cached = frappe.cache.get_value(TOKEN_CACHE_KEY)
		if cached:
			return cached

	settings = _config()
	try:
		resp = _new_session().post(
			f"{settings.controller_url}/openapi/authorize/token",
			params={"grant_type": "client_credentials"},
			json={
				"omadacId": _omadac_id(settings),
				"client_id": settings.client_id,
				"client_secret": settings.get_password("client_secret"),
			},
			timeout=_settings()[0],
		)
		data = resp.json()
	except (requests.RequestException, ValueError) as e:
		raise OmadaApiError(_("Could not get an Omada Open API token: {0}").format(e)) from e

	result = data.get("result") or {}
	token = result.get("accessToken")
	if data.get("errorCode") != 0 or not token:
		raise OmadaApiError(_("Omada refused the Open API credentials: {0}").format(data.get("msg") or data))
	# Refresh a few minutes before the controller expires it.
	frappe.cache.set_value(
		TOKEN_CACHE_KEY, token, expires_in_sec=max(60, int(result.get("expiresIn") or 7200) - 300)
	)
	return token


def request(method, path, json=None, params=None, _retried=False):
	"""Calls /openapi/v1/{omadacId}{path} and returns its ``result``. Retries
	once with a fresh token if the cached one was rejected."""
	settings = _config()
	url = f"{settings.controller_url}/openapi/v1/{_omadac_id(settings)}{path}"
	try:
		resp = _new_session().request(
			method,
			url,
			json=json,
			params=params,
			headers={"Authorization": f"AccessToken={_token()}"},
			timeout=_settings()[0],
		)
		data = resp.json()
	except (requests.RequestException, ValueError) as e:
		raise OmadaApiError(_("Omada request {0} {1} failed: {2}").format(method, path, e)) from e

	code = data.get("errorCode")
	if (code in TOKEN_ERROR_CODES or resp.status_code == 401) and not _retried:
		frappe.cache.delete_value(TOKEN_CACHE_KEY)
		return request(method, path, json=json, params=params, _retried=True)
	if code != 0:
		raise OmadaApiError(data.get("msg") or f"Omada error {code}")
	return data.get("result")


def _rows(result):
	"""Grid responses wrap rows in {data: [...]}; list responses are bare."""
	if isinstance(result, dict):
		return result.get("data") or []
	return result or []


def _page():
	return {"page": 1, "pageSize": PAGE_SIZE}


# --- Sites -----------------------------------------------------------------


def list_sites():
	return _rows(request("GET", "/sites", params=_page()))


def get_site(site_id):
	return request("GET", f"/sites/{site_id}")


def find_site(name):
	return next((s for s in list_sites() if s.get("name") == name), None)


def list_scenarios():
	return request("GET", "/scenarios") or []


def create_site(name, region, time_zone, scenario, device_username, device_password):
	request(
		"POST",
		"/sites",
		json={
			"name": name,
			"type": 0,
			"region": region,
			"timeZone": time_zone,
			"scenario": scenario,
			"deviceAccountSetting": {"username": device_username, "password": device_password},
			"supportES": False,
			"supportL2": True,
		},
	)
	site = find_site(name)
	if not site:
		raise OmadaApiError(_("Site {0} was created but could not be found afterwards.").format(name))
	return site


# --- Devices ---------------------------------------------------------------


def pending_devices(site_id):
	"""APs the controller has discovered that are waiting to be adopted."""
	return _rows(request("GET", f"/sites/{site_id}/grid/devices/pending", params=_page()))


def site_devices(site_id):
	return _rows(request("GET", f"/sites/{site_id}/devices", params=_page()))


def reboot_device(site_id, mac):
	"""Reboots one adopted device -- disconnects every client on it."""
	return request("POST", f"/sites/{site_id}/devices/{mac}/reboot")


def start_adopt(site_id, mac, username=None, password=None):
	body = {}
	if username:
		body = {"username": username, "password": password or ""}
	return request("POST", f"/sites/{site_id}/devices/{mac}/start-adopt", json=body)


def adopt_result(site_id, mac):
	return request("GET", f"/sites/{site_id}/devices/{mac}/adopt-result") or {}


# --- WLAN groups / SSIDs ---------------------------------------------------


def list_wlans(site_id):
	return _rows(request("GET", f"/sites/{site_id}/wireless-network/wlans"))


def ensure_wlan(site_id, name="Bandofy"):
	"""The site's primary WLAN group (every site has one), else one named
	``name``, created if needed."""
	wlans = list_wlans(site_id)
	wlan = next((w for w in wlans if w.get("primary")), None) or next(
		(w for w in wlans if w.get("name") == name), None
	)
	if wlan:
		return wlan
	request("POST", f"/sites/{site_id}/wireless-network/wlans", json={"name": name, "clone": False})
	wlan = next((w for w in list_wlans(site_id) if w.get("name") == name), None)
	if not wlan:
		raise OmadaApiError(_("WLAN group {0} was created but could not be found afterwards.").format(name))
	return wlan


def list_ssids(site_id, wlan_id):
	return _rows(request("GET", f"/sites/{site_id}/wireless-network/wlans/{wlan_id}/ssids", params=_page()))


def _open_ssid_body(name):
	"""An open (no password) SSID on 2.4 + 5 GHz -- customers get in through
	the captive portal, not a Wi-Fi password."""
	return {
		"name": name,
		"band": 3,
		"guestNetEnable": False,
		"security": 0,
		"broadcast": True,
		"vlanEnable": False,
		"mloEnable": False,
		"pmfMode": 3,
		"enable11r": False,
		"hidePwd": False,
		"prohibitWifiShare": True,
	}


def create_open_ssid(site_id, wlan_id, name):
	request(
		"POST",
		f"/sites/{site_id}/wireless-network/wlans/{wlan_id}/ssids",
		json={**_open_ssid_body(name), "deviceType": 1},
	)
	ssid = next((s for s in list_ssids(site_id, wlan_id) if s.get("name") == name), None)
	if not ssid:
		raise OmadaApiError(_("SSID {0} was created but could not be found afterwards.").format(name))
	return ssid


def rename_open_ssid(site_id, wlan_id, ssid_id, name):
	request(
		"PATCH",
		f"/sites/{site_id}/wireless-network/wlans/{wlan_id}/ssids/{ssid_id}/update-basic-config",
		json=_open_ssid_body(name),
	)


def delete_ssid(site_id, wlan_id, ssid_id):
	request("DELETE", f"/sites/{site_id}/wireless-network/wlans/{wlan_id}/ssids/{ssid_id}")


# --- Portals ---------------------------------------------------------------


def list_portals(site_id):
	return _rows(request("GET", f"/sites/{site_id}/portals"))


def _portal_body(name, ssid_ids, portal_url, timeout_minutes):
	from urllib.parse import urlsplit

	parts = urlsplit(portal_url)
	return {
		"name": name,
		"enable": True,
		"ssidList": ssid_ids,
		"authType": 4,  # External Portal Server
		"authTimeout": {"customTimeout": max(1, int(timeout_minutes)), "customTimeoutUnit": 1},
		"httpsRedirectEnable": True,
		"landingPage": 1,  # back to the original URL
		"externalPortal": {
			"hostType": 2,
			"serverUrlScheme": parts.scheme or "https",
			"serverUrl": (parts.netloc + parts.path).lstrip("/"),
		},
	}


def ensure_portal(site_id, name, ssid_ids, portal_url, timeout_minutes):
	"""An External Portal pointing at Bandofy and bound to ``ssid_ids``;
	updates the existing one of that name instead of duplicating it."""
	body = _portal_body(name, ssid_ids, portal_url, timeout_minutes)
	portal = next((p for p in list_portals(site_id) if p.get("name") == name), None)
	if portal:
		body["ssidList"] = sorted(set(portal.get("ssidList") or []) | set(ssid_ids))
		request("PATCH", f"/sites/{site_id}/portal/{portal['id']}", json=body)
		return {**portal, "ssidList": body["ssidList"]}
	request("POST", f"/sites/{site_id}/portal", json=body)
	portal = next((p for p in list_portals(site_id) if p.get("name") == name), None)
	if not portal:
		raise OmadaApiError(_("Portal {0} was created but could not be found afterwards.").format(name))
	return portal


# --- Hotspot operators -----------------------------------------------------


def find_operator(name):
	"""The hotspot operator ``name`` and a site it can be reached through.
	Operators are controller-wide but the API is site-scoped, so this looks
	through the sites until one lists it."""
	for site in list_sites():
		try:
			operators = _rows(
				request(
					"GET", f"/sites/{site['siteId']}/hotspot/operators", params={**_page(), "searchKey": name}
				)
			)
		except OmadaApiError:
			continue
		operator = next((o for o in operators if o.get("name") == name), None)
		if operator:
			return operator, site["siteId"]
	return None, None


def grant_operator_site(site_id):
	"""Adds ``site_id`` to the configured hotspot operator's Site Privileges
	(creating the operator, scoped to this site, if it doesn't exist yet).
	Omada requires the operator's password on every update."""
	settings = _config()
	name = settings.operator_name
	password = settings.get_password("operator_password", raise_exception=False)
	if not (name and password):
		raise OmadaApiError(_("Set the Hotspot Operator name and password in Hotspot Omada Settings first."))

	operator, via_site = find_operator(name)
	if not operator:
		request(
			"POST",
			f"/sites/{site_id}/hotspot/operators",
			json={"name": name, "password": password, "operatorRoleType": 0, "selectedSites": [site_id]},
		)
		return "created"

	selected = list(operator.get("selectedSites") or [])
	if site_id in selected:
		return "already"
	request(
		"PATCH",
		f"/sites/{via_site}/hotspot/operators/{operator['id']}",
		json={
			"name": name,
			"password": password,
			"note": operator.get("note") or None,
			"operatorRoleType": operator.get("operatorRoleType") or 0,
			"selectedSites": [*selected, site_id],
		},
	)
	return "added"


# --- Connection test -------------------------------------------------------


def test_connection():
	"""Checks reachability, credentials and site access, and fills empty
	new-site defaults (time zone, scenario) from the first existing site."""
	settings = _config()
	info = controller_info(settings.controller_url)
	if info.get("omadacId") and info["omadacId"] != settings.omadac_id:
		frappe.db.set_single_value("Hotspot Omada Settings", "omadac_id", info["omadacId"])
		frappe.clear_document_cache("Hotspot Omada Settings", "Hotspot Omada Settings")

	frappe.cache.delete_value(TOKEN_CACHE_KEY)
	_token(force=True)
	sites = list_sites()

	filled = {}
	settings = frappe.get_doc("Hotspot Omada Settings")
	if sites and not (settings.default_timezone and settings.default_scenario):
		first = get_site(sites[0]["siteId"]) or sites[0]
		for field, key in (
			("default_timezone", "timeZone"),
			("default_scenario", "scenario"),
			("default_region", "region"),
		):
			if not settings.get(field) and first.get(key):
				filled[field] = first[key]
		if filled:
			frappe.db.set_single_value("Hotspot Omada Settings", filled)
			frappe.clear_document_cache("Hotspot Omada Settings", "Hotspot Omada Settings")

	operator = None
	if settings.operator_name:
		op, _site = find_operator(settings.operator_name)
		operator = {
			"name": settings.operator_name,
			"found": bool(op),
			"sites": len((op or {}).get("selectedSites") or []),
		}

	return {
		"controller_version": info.get("controllerVer"),
		"omadac_id": info.get("omadacId"),
		"sites": [{"site_id": s.get("siteId"), "name": s.get("name")} for s in sites],
		"defaults_filled": filled,
		"operator": operator,
	}
