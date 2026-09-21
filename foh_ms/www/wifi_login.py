# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import getdate, nowdate

from foh_ms.utils import find_site_by_ap_mac, has_used_free_trial, is_admin_user

no_cache = 1

# Bundled brand marks for the Tanzanian mobile money networks the captive
# portal accepts payment from. The image files are not part of this change --
# drop the actual logo files (png/jpg/jpeg/webp) named accordingly into
# apps/foh_ms/foh_ms/public/images/payment_logos/; a name-only text badge is
# shown as a fallback until each file is added.
PAYMENT_PROVIDERS = [
	{"name": "Mixx by Yas", "file": "mixx_by_yas"},
	{"name": "Airtel Money", "file": "airtel_money"},
	{"name": "HaloPesa", "file": "halopesa"},
	{"name": "M-Pesa", "file": "mpesa"},
]


def get_context(context):
	frappe.flags.disable_guest_fallback = True
	context.no_cache = 1

	# Standalone EAP "External Web Portal" redirects use apMac/ap/ap_mac and
	# clientMac/client_mac depending on firmware; accept all of them.
	ap_mac = (
		frappe.form_dict.get("apMac")
		or frappe.form_dict.get("ap")
		or frappe.form_dict.get("ap_mac")
		or ""
	)
	client_mac = frappe.form_dict.get("clientMac") or frappe.form_dict.get("client_mac") or ""
	# "target" (host:port to complete a Local RADIUS Server login against) and
	# "origUrl" (where to send the client once authorized) are standalone-EAP
	# specific and only meaningful for that flow; pass them through as-is.
	target = frappe.form_dict.get("target") or ""
	orig_url = frappe.form_dict.get("origUrl") or frappe.form_dict.get("orig_url") or ""
	# ssidName/radioId are Omada-Controller-managed-site specific -- required
	# by the hotspot/login authorize call in api.authorize_mac_on_omada.
	ssid_name = frappe.form_dict.get("ssidName") or frappe.form_dict.get("ssid") or ""
	radio_id = frappe.form_dict.get("radioId") or frappe.form_dict.get("radio_id") or ""

	context.ap_mac = ap_mac
	context.client_mac = client_mac
	context.target = target
	context.orig_url = orig_url
	context.ssid_name = ssid_name
	context.radio_id = radio_id
	context.vendor_name = None
	context.site_label = None
	context.support_phone = None
	context.packages = []
	context.site_found = False
	context.ads = []
	context.authorization_method = None
	context.online_payment_enabled = False
	context.free_trial_enabled = False
	context.free_trial_available = False
	context.free_trial_minutes = 15
	context.lipa_images = []
	context.lipa_default = None
	context.currency = frappe.db.get_single_value("Hotspot Payment Settings", "default_currency") or "TZS"
	context.payment_providers = PAYMENT_PROVIDERS
	context.portal_logo = None
	context.portal_tagline = None
	context.portal_primary_color = "#ec4899"
	context.portal_secondary_color = "#6366f1"
	context.portal_mid_color = _mix_colors("#ec4899", "#6366f1")

	if ap_mac:
		site = find_site_by_ap_mac(
			ap_mac,
			fields=[
				"name",
				"vendor_name",
				"site_name",
				"authorization_method",
				"phone_number",
				"enable_online_payment",
				"enable_free_trial",
				"free_trial_minutes",
				"vendor_user",
				"portal_logo",
				"portal_tagline",
				"portal_primary_color",
				"portal_secondary_color",
			],
		)

		if site:
			context.site_found = True
			context.vendor_name = site.vendor_name
			context.site_label = site.site_name
			context.authorization_method = site.authorization_method
			context.support_phone = site.phone_number
			context.online_payment_enabled = bool(site.enable_online_payment)
			context.free_trial_minutes = int(site.free_trial_minutes or 15)
			context.free_trial_enabled = bool(site.enable_free_trial)
			context.free_trial_available = context.free_trial_enabled and not has_used_free_trial(
				site.name, client_mac
			)
			context.portal_logo = site.portal_logo
			context.portal_tagline = site.portal_tagline
			context.portal_primary_color = site.portal_primary_color or context.portal_primary_color
			context.portal_secondary_color = site.portal_secondary_color or context.portal_secondary_color
			apply_preview_overrides(context, site)
			context.portal_mid_color = _mix_colors(context.portal_primary_color, context.portal_secondary_color)
			context.lipa_images, context.lipa_default = get_lipa_images(site.name)
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
			context.ads = get_active_ads(site.name)

	return context


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

	if frappe.form_dict.get("preview_primary_color"):
		context.portal_primary_color = frappe.form_dict.get("preview_primary_color")
	if frappe.form_dict.get("preview_secondary_color"):
		context.portal_secondary_color = frappe.form_dict.get("preview_secondary_color")
	if frappe.form_dict.get("preview_tagline") is not None:
		context.portal_tagline = frappe.form_dict.get("preview_tagline") or None
	if frappe.form_dict.get("preview_logo"):
		context.portal_logo = frappe.form_dict.get("preview_logo")


def _mix_colors(hex_a, hex_b):
	"""Simple RGB average of two '#rrggbb' colors, for the body gradient's
	middle stop."""

	def to_rgb(hex_color):
		hex_color = (hex_color or "").lstrip("#")
		if len(hex_color) != 6:
			return (124, 58, 237)  # falls back to the original mid-purple
		return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))

	a, b = to_rgb(hex_a), to_rgb(hex_b)
	mixed = tuple((a[i] + b[i]) // 2 for i in range(3))
	return "#{:02x}{:02x}{:02x}".format(*mixed)


def format_duration(minutes):
	"""Human-friendly Swahili label for a package's duration, e.g. 180 -> 'Saa 3'."""
	minutes = int(minutes or 0)
	if minutes and minutes % 1440 == 0:
		return f"Siku {minutes // 1440}"
	if minutes and minutes % 60 == 0:
		return f"Saa {minutes // 60}"
	return f"Dakika {minutes}"


def get_lipa_images(site_name):
	"""Manual pay-by-QR/till-number images for the Lipa Namba button.

	Returns (images, default_image). Sites that haven't populated the
	Lipa Namba Images table yet fall back to the original static image so
	their captive portal keeps working exactly as before this table existed.
	"""
	rows = frappe.get_all(
		"Hotspot Lipa Number",
		filters={"parent": site_name, "parenttype": "Hotspot Site"},
		fields=["label", "image", "is_default"],
		order_by="idx asc",
	)
	if not rows:
		fallback = {
			"label": "Lipa Namba",
			"image": "/assets/foh_ms/images/lipanamba/lipa_namba.jpeg",
			"is_default": 1,
		}
		return [fallback], fallback

	default_row = next((row for row in rows if row.is_default), rows[0])
	return rows, default_row


def get_active_ads(site_name):
	"""Ads scoped to this site plus any global (site-blank) ads, active and in schedule."""
	today = getdate(nowdate())
	ads = frappe.get_all(
		"Hotspot Ad",
		filters={"is_active": 1, "site": ["in", [site_name, ""]]},
		fields=["name", "title", "image", "target_url", "description", "phone_number"],
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


def build_ad_marquee_text(ad):
	"""Short scrolling caption under the ad banner: description + phone, or
	just the ad title if neither of those optional fields is set."""
	parts = []
	if ad.get("description"):
		parts.append(ad["description"])
	if ad.get("phone_number"):
		parts.append(f"\U0001f4de {ad['phone_number']}")
	return "   •   ".join(parts) if parts else (ad.get("title") or "")
