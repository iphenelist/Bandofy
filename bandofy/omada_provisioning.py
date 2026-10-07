# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

"""Sets a Hotspot Site up on the central Omada Controller through the Open
API (bandofy.omada_openapi): the Omada site, its open hotspot SSID, an
External Portal pointing at Bandofy, and the hotspot operator's access to the
site. The Hotspot Site keeps only the resulting Omada IDs; the controller and
operator themselves live in Hotspot Omada Settings (see
bandofy.omada_service.site_controller). Also adopts devices and manages a
site's SSIDs.

Every step checks what already exists first, so provisioning can be re-run
safely to finish a partly-done setup, and an existing Omada site with the
same name (e.g. one created by hand) is linked rather than duplicated.
"""

import time

import frappe
from frappe import _
from frappe.utils import cint, get_url

from bandofy import omada_openapi as api
from bandofy.omada_openapi import OmadaApiError
from bandofy.utils import normalize_mac

PORTAL_NAME = "Bandofy Portal"
ADOPT_WAIT_SECONDS = 30
DEVICE_CONNECTED = 1  # DeviceInfo.status
ADOPT_ERRORS = {
	-39002: "The device doesn't respond to adopt commands.",
	-39003: "The device username or password is incorrect.",
	-39004: "The controller could not adopt the device.",
	-39005: "The device is not connected to the controller.",
	-39329: "The device could not link to its uplink AP.",
}


def _settings():
	return frappe.get_doc("Hotspot Omada Settings")


def _omada_mac(mac):
	"""Omada's MAC format: AA-BB-CC-DD-EE-FF."""
	digits = normalize_mac(mac).upper()
	if len(digits) != 12:
		frappe.throw(_("{0} is not a valid MAC address.").format(mac))
	return "-".join(digits[i : i + 2] for i in range(0, 12, 2))


def _require_provisioned(site):
	if not site.omada_site_id:
		frappe.throw(_("Create this site on the Omada Controller first (Create on Omada)."))


def _portal_url(settings):
	return settings.portal_url or get_url("/wifi_login")


def _auth_timeout_minutes(site):
	"""Omada ends the portal session after this; Bandofy's own transaction
	duration is what the hotspot operator authorizes, so this just needs to
	be at least the longest package."""
	return max([cint(p.duration_minutes) for p in site.packages] + [1440])


def provision_site(site_name, ssid_name=None):
	"""Runs every setup step for one Hotspot Site and returns a report:
	[{step, ok, detail}]. Stops at the first failing step, keeping whatever
	was already done (and saved) so a re-run picks up from there."""
	site = frappe.get_doc("Hotspot Site", site_name)
	settings = _settings()
	steps = []

	def add(step, ok, detail):
		steps.append({"step": step, "ok": bool(ok), "detail": detail})

	ssid_name = (ssid_name or site.hotspot_ssid_name or settings.default_ssid_name or "Bandofy").strip()

	try:
		# 1. Omada site
		omada_site = None
		if site.omada_site_id:
			omada_site = next((s for s in api.list_sites() if s.get("siteId") == site.omada_site_id), None)
		if not omada_site:
			omada_site = api.find_site(site.site_name)
			if omada_site:
				add(_("Omada site"), True, _("Linked existing site {0}").format(site.site_name))
			else:
				missing = [
					label
					for label, value in (
						(_("Time Zone"), settings.default_timezone),
						(_("Application Scenario"), settings.default_scenario),
						(_("Device Account Password"), settings.device_password),
					)
					if not value
				]
				if missing:
					raise OmadaApiError(
						_("Fill in {0} in Hotspot Omada Settings (Test Connection can fill the first two).").format(
							", ".join(missing)
						)
					)
				omada_site = api.create_site(
					name=site.site_name,
					region=settings.default_region or "Tanzania",
					time_zone=settings.default_timezone,
					scenario=settings.default_scenario,
					device_username=settings.device_username or "admin",
					device_password=settings.get_password("device_password"),
				)
				add(_("Omada site"), True, _("Created site {0}").format(site.site_name))
		else:
			add(_("Omada site"), True, _("Already set up"))
		site_id = omada_site["siteId"]
		site.omada_site_id = site_id
		site.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep

		# 2. Hotspot SSID
		wlan = api.ensure_wlan(site_id)
		ssids = api.list_ssids(site_id, wlan["wlanId"])
		ssid = next((s for s in ssids if site.omada_ssid_id and s.get("ssidId") == site.omada_ssid_id), None)
		if ssid and ssid.get("name") != ssid_name:
			api.rename_open_ssid(site_id, wlan["wlanId"], ssid["ssidId"], ssid_name)
			add(_("Hotspot SSID"), True, _("Renamed to {0}").format(ssid_name))
		elif ssid:
			add(_("Hotspot SSID"), True, _("Already set up: {0}").format(ssid_name))
		else:
			ssid = next((s for s in ssids if s.get("name") == ssid_name), None)
			if ssid:
				add(_("Hotspot SSID"), True, _("Using existing SSID {0}").format(ssid_name))
			else:
				ssid = api.create_open_ssid(site_id, wlan["wlanId"], ssid_name)
				add(_("Hotspot SSID"), True, _("Created open SSID {0}").format(ssid_name))
		site.omada_wlan_id = wlan["wlanId"]
		site.omada_ssid_id = ssid["ssidId"]
		site.hotspot_ssid_name = ssid_name
		site.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep

		# 3. External portal -> Bandofy
		portal = api.ensure_portal(
			site_id, PORTAL_NAME, [ssid["ssidId"]], _portal_url(settings), _auth_timeout_minutes(site)
		)
		site.omada_portal_id = portal.get("id")
		site.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep
		add(_("Portal"), True, _("External portal to {0}").format(_portal_url(settings)))

		# 4. Hotspot operator site privilege
		result = api.grant_operator_site(site_id)
		add(
			_("Hotspot operator"),
			True,
			{
				"created": _("Created operator {0} for this site"),
				"added": _("Added this site to {0}"),
				"already": _("{0} already has this site"),
			}[result].format(settings.operator_name),
		)
	except OmadaApiError as e:
		add(steps and _("Next step") or _("Omada site"), False, str(e))
	except Exception as e:
		frappe.log_error(title=f"Bandofy Omada provisioning failed: {site.name}", message=frappe.get_traceback())
		add(_("Unexpected error"), False, str(e))

	return steps


# --- Devices ---------------------------------------------------------------


def list_pending_devices(site_name):
	site = frappe.get_doc("Hotspot Site", site_name)
	_require_provisioned(site)
	return [
		{
			"mac": d.get("mac"),
			"name": d.get("name"),
			"model": d.get("modelName") or d.get("model"),
			"ip": d.get("ip"),
			"firmware": d.get("firmwareVersion"),
		}
		for d in api.pending_devices(site.omada_site_id)
	]


def adopt_device(site_name, mac, username=None, password=None):
	"""Starts adopting ``mac`` into the site, registers it as the site's AP
	(primary if none yet, else an additional device), and waits briefly for
	the controller to confirm. Returns {status: adopted|adopting, mac}."""
	site = frappe.get_doc("Hotspot Site", site_name)
	_require_provisioned(site)
	mac = _omada_mac(mac)

	settings = _settings()
	username = username or settings.adopt_username
	password = password or (settings.get_password("adopt_password", raise_exception=False) if username else None)
	pending = next(
		(d for d in api.pending_devices(site.omada_site_id) if normalize_mac(d.get("mac")) == normalize_mac(mac)), {}
	)
	api.start_adopt(site.omada_site_id, mac, username, password)

	_register_device(site, mac, pending.get("name") or pending.get("modelName"))

	deadline = time.monotonic() + ADOPT_WAIT_SECONDS
	while time.monotonic() < deadline:
		time.sleep(3)
		code = api.adopt_result(site.omada_site_id, mac).get("adoptErrorCode")
		if code not in (None, 0):
			raise OmadaApiError(
				_("Adoption failed: {0}").format(_(ADOPT_ERRORS.get(code, f"Omada error {code}.")))
			)
		device = next(
			(d for d in api.site_devices(site.omada_site_id) if normalize_mac(d.get("mac")) == normalize_mac(mac)),
			None,
		)
		if device and cint(device.get("status")) == DEVICE_CONNECTED:
			return {"status": "adopted", "mac": mac}
	return {"status": "adopting", "mac": mac}


def _register_device(site, mac, label=None):
	"""Adds the adopted AP to the site's Access Points table (once)."""
	if any(normalize_mac(d.ap_mac) == normalize_mac(mac) for d in site.devices):
		return
	site.append("devices", {"ap_mac": mac, "label": label or mac, "is_active": 1})
	site.save(ignore_permissions=True)
	frappe.db.commit()  # nosemgrep


# --- SSIDs -----------------------------------------------------------------


def list_ssids(site_name):
	site = frappe.get_doc("Hotspot Site", site_name)
	_require_provisioned(site)
	wlan = api.ensure_wlan(site.omada_site_id)
	return [
		{
			"ssid_id": s.get("ssidId"),
			"name": s.get("name"),
			"open": s.get("security") == 0,
			"is_hotspot": s.get("ssidId") == site.omada_ssid_id,
		}
		for s in api.list_ssids(site.omada_site_id, wlan["wlanId"])
	]


def save_ssid(site_name, name, ssid_id=None):
	"""Renames an SSID, or creates a new open one bound to the Bandofy
	portal. Renaming the hotspot SSID keeps the Hotspot Site in step."""
	site = frappe.get_doc("Hotspot Site", site_name)
	_require_provisioned(site)
	name = (name or "").strip()
	if not 1 <= len(name) <= 32:
		frappe.throw(_("SSID name must be 1 to 32 characters."))

	wlan = api.ensure_wlan(site.omada_site_id)
	if ssid_id:
		api.rename_open_ssid(site.omada_site_id, wlan["wlanId"], ssid_id, name)
	else:
		ssid = api.create_open_ssid(site.omada_site_id, wlan["wlanId"], name)
		ssid_id = ssid["ssidId"]
		api.ensure_portal(
			site.omada_site_id, PORTAL_NAME, [ssid_id], _portal_url(_settings()), _auth_timeout_minutes(site)
		)

	if ssid_id == site.omada_ssid_id:
		site.db_set("hotspot_ssid_name", name, commit=True)
	return list_ssids(site_name)


def delete_ssid(site_name, ssid_id):
	site = frappe.get_doc("Hotspot Site", site_name)
	_require_provisioned(site)
	if ssid_id == site.omada_ssid_id:
		frappe.throw(_("This is the site's hotspot SSID; rename it instead of deleting it."))
	wlan = api.ensure_wlan(site.omada_site_id)
	api.delete_ssid(site.omada_site_id, wlan["wlanId"], ssid_id)
	return list_ssids(site_name)
