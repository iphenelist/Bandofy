import frappe
from frappe import _

no_cache = 1


def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/site_settings"
        raise frappe.Redirect

    site = frappe.db.get_value(
        "Hotspot Site",
        {"vendor_user": frappe.session.user},
        ["name", "vendor_name", "site_name", "phone_number", "mobile_money_account",
         "enable_online_payment", "enable_free_trial", "free_trial_minutes", "portal_tagline"],
        as_dict=True,
    )
    if not site:
        frappe.throw(_("No Hotspot Site linked to your account."), frappe.PermissionError)

    context.site = site
    context.enable_online_payment = int(site.get("enable_online_payment") or 0)
    context.enable_free_trial = int(site.get("enable_free_trial") or 0)
    context.free_trial_minutes = int(site.get("free_trial_minutes") or 10)
    return context
