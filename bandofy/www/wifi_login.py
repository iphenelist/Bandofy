# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, nowdate

from bandofy.utils import find_site, has_used_free_trial, is_admin_user, is_omada_site_id, is_sabbath_now

no_cache = 1

# Bundled brand marks for the Tanzanian mobile money networks the captive
# portal accepts payment from. The image files are not part of this change --
# drop the actual logo files (png/jpg/jpeg/webp) named accordingly into
# apps/bandofy/bandofy/public/images/payment_logos/; a name-only text badge is
# shown as a fallback until each file is added.
PAYMENT_PROVIDERS = [
	{"name": "Mixx by Yas", "file": "mixx_by_yas"},
	{"name": "Airtel Money", "file": "airtel_money"},
	{"name": "HaloPesa", "file": "halopesa"},
]


def get_context(context):
	frappe.flags.disable_guest_fallback = True
	context.no_cache = 1

	# Omada redirects use apMac/ap/ap_mac and clientMac/client_mac depending
	# on firmware. Ruijie ACs send the names set by `fmt custom` in their
	# web-auth template (see docs/ruijie.md): wlanapmac, mac, ssid, url,
	# wlanacname, wlanuserip and wlannasip. Accept all of them.
	ap_mac = _param("apMac", "ap", "ap_mac", "wlanapmac")
	client_mac = _param("clientMac", "client_mac", "mac")
	# Where the client was headed before the captive portal.
	orig_url = _param("origUrl", "orig_url", "url")
	# ssidName/radioId are Omada-Controller-managed-site specific -- required
	# by the hotspot/login authorize call in api.authorize_mac_on_omada.
	ssid_name = _param("ssidName", "ssid")
	radio_id = _param("radioId", "radio_id")
	# Ruijie only: the AC's name identifies the site, and the user and NAS
	# IPs may be needed by the AC's login page.
	ac_name = _param("wlanacname", "ac_name")
	user_ip = _param("wlanuserip", "user_ip")
	nas_ip = _param("wlannasip", "nas_ip")
	# Controller-managed sites add the Omada site ID as "site"; it is how the
	# portal finds the Hotspot Site (the AP MAC is the fallback).
	omada_site = (frappe.form_dict.get("site") or "").strip()
	if not is_omada_site_id(omada_site):
		omada_site = ""

	context.ap_mac = ap_mac
	context.client_mac = client_mac
	context.orig_url = orig_url
	context.ssid_name = ssid_name
	context.radio_id = radio_id
	context.omada_site = omada_site
	context.ac_name = ac_name
	context.user_ip = user_ip
	context.nas_ip = nas_ip
	context.controller_type = None
	context.vendor_name = None
	context.site_label = None
	context.support_phone = None
	context.packages = []
	context.site_found = False
	context.ads = []
	context.online_payment_enabled = False
	context.free_trial_enabled = False
	context.free_trial_available = False
	context.free_trial_minutes = 15
	context.sabbath_active = False
	context.lipa_images = []
	context.lipa_default = None
	context.currency = frappe.db.get_single_value("Hotspot Payment Settings", "default_currency") or "TZS"
	context.payment_providers = PAYMENT_PROVIDERS
	context.portal_logo = None
	context.portal_tagline = None

	if ap_mac or omada_site or ac_name:
		site = find_site(
			omada_site,
			ap_mac,
			ac_name=ac_name,
			fields=[
				"name",
				"controller_type",
				"vendor_name",
				"site_name",
				"phone_number",
				"enable_online_payment",
				"enable_free_trial",
				"free_trial_minutes",
				"enable_sabbath_mode",
				"vendor_user",
				"portal_logo",
				"portal_tagline",
				"lipa_namba_image",
			],
		)

		if site:
			context.site_found = True
			context.controller_type = site.controller_type or "Omada"
			context.vendor_name = site.vendor_name
			context.site_label = site.site_name
			context.support_phone = site.phone_number
			context.online_payment_enabled = bool(site.enable_online_payment)
			context.free_trial_minutes = int(site.free_trial_minutes or 15)
			context.free_trial_enabled = bool(site.enable_free_trial)
			context.free_trial_available = context.free_trial_enabled and not has_used_free_trial(
				site.name, client_mac
			)
			context.sabbath_active = is_sabbath_now(site)
			context.portal_logo = site.portal_logo
			context.portal_tagline = site.portal_tagline
			apply_preview_overrides(context, site)
			context.lipa_images, context.lipa_default = get_lipa_images(site.lipa_namba_image)
			context.packages = frappe.get_all(
				"Hotspot Package Item",
				filters={"parent": site.name, "parenttype": "Hotspot Site"},
				fields=[
					"name",
					"idx",
					"package_name",
					"package_type",
					"price",
					"duration_minutes",
					"bandwidth_down_kbps",
					"bandwidth_up_kbps",
				],
				order_by="idx asc",
			)
			for pkg in context.packages:
				pkg["duration_label"] = format_duration(pkg.duration_minutes)
				pkg["price_label"] = "{} {:,.0f}".format(context.currency, pkg.price or 0)
			context.ads = get_active_ads(site.name)
			context.free_trial_ads = free_trial_ads(context.ads)

	context.portal_data = build_portal_data(context)
	return context


def _param(*names):
	"""The first non-empty request parameter among ``names``, stripped."""
	for name in names:
		value = frappe.form_dict.get(name)
		if value:
			return str(value).strip()
	return ""


def build_portal_data(context):
	"""Everything the Vue portal app (public/js/wifi_portal) needs, handed to
	it as a single JSON blob on window.PORTAL."""
	keys = [
		"ap_mac",
		"client_mac",
		"orig_url",
		"ssid_name",
		"radio_id",
		"omada_site",
		"ac_name",
		"user_ip",
		"nas_ip",
		"controller_type",
		"site_found",
		"vendor_name",
		"site_label",
		"support_phone",
		"packages",
		"ads",
		"free_trial_ads",
		"online_payment_enabled",
		"free_trial_enabled",
		"free_trial_available",
		"free_trial_minutes",
		"sabbath_active",
		"lipa_images",
		"lipa_default",
		"currency",
		"payment_providers",
		"portal_logo",
		"portal_tagline",
	]
	return {key: context.get(key) for key in keys}


def apply_preview_overrides(context, site):
	"""Lets the site's own vendor (or an admin) preview unsaved portal
	branding changes on this real template via query params, without ever
	writing drafts to the database -- this is what the mobile app's
	Customize Portal live preview is built on. Only honored for an
	authenticated request that owns this site: a Guest hitting the real
	portal URL with these query params can never spoof another vendor's
	branding, so actual customers are completely unaffected.
	"""
	if frappe.form_dict.get("preview") != "1":
		return
	if frappe.session.user == "Guest":
		return
	if frappe.session.user != site.vendor_user and not is_admin_user():
		return

	if frappe.form_dict.get("preview_tagline") is not None:
		context.portal_tagline = frappe.form_dict.get("preview_tagline") or None
	if frappe.form_dict.get("preview_logo"):
		context.portal_logo = frappe.form_dict.get("preview_logo")


def format_duration(minutes):
	"""Human-friendly Swahili label for a package's duration, e.g. 180 -> 'Saa 3'."""
	minutes = int(minutes or 0)
	if minutes and minutes % 1440 == 0:
		return f"Siku {minutes // 1440}"
	if minutes and minutes % 60 == 0:
		return f"Saa {minutes // 60}"
	return f"Dakika {minutes}"


def get_lipa_images(lipa_namba_image):
	"""The Lipa Namba (pay-by-QR/till-number) picture as (images, default):
	the site's attached image, or the bundled one if none is set. Kept as a
	one-item list so the portal's Lipa widget works unchanged."""
	image = {
		"label": "Lipa Namba",
		"image": lipa_namba_image or "/assets/bandofy/images/lipanamba/lipa_namba.jpeg",
		"is_default": 1,
	}
	return [image], image


def get_active_ads(site_name):
	"""Ads scoped to this site plus any global (site-blank) ads, active and in schedule."""
	today = getdate(nowdate())
	ads = frappe.get_all(
		"Hotspot Ad",
		filters={"is_active": 1, "site": ["in", [site_name, ""]]},
		fields=[
			"name",
			"title",
			"image",
			"target_url",
			"description",
			"phone_number",
			"show_before_free_trial",
			"fullscreen_image",
			"video",
		],
		order_by="display_order asc, creation asc",
	)

	visible = []
	for ad in ads:
		row = frappe.db.get_value("Hotspot Ad", ad.name, ["start_date", "end_date"], as_dict=True)
		if row.start_date and getdate(row.start_date) > today:
			continue
		if row.end_date and getdate(row.end_date) < today:
			continue
		ad["marquee_text"] = build_ad_marquee_text(ad)
		# Roughly a fixed reading speed, clamped so very short or very long
		# blurbs don't scroll unreadably fast/slow.
		ad["marquee_duration"] = max(10, min(28, round(len(ad["marquee_text"]) * 0.32, 1)))
		visible.append(ad)

	return visible


def free_trial_ads(ads):
	"""The ads a customer must watch (one of, full screen) before a free
	trial connects. See api.claim_free_trial, which enforces it."""
	return [ad for ad in ads if ad.get("show_before_free_trial")]


def build_ad_marquee_text(ad):
	"""Short scrolling caption under the ad banner: description + phone, or
	just the ad title if neither of those optional fields is set."""
	parts = []
	if ad.get("description"):
		parts.append(ad["description"])
	if ad.get("phone_number"):
		parts.append(f"\U0001f4de {ad['phone_number']}")
	return "   •   ".join(parts) if parts else (ad.get("title") or "")
