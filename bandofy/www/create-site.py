import frappe
from frappe import _

no_cache = 1


def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/create-site"
        raise frappe.Redirect

    from bandofy.utils import get_vendor_site_name

    # Already has a site — go straight to dashboard
    if get_vendor_site_name():
        frappe.local.flags.redirect_location = "/vendor-dashboard"
        raise frappe.Redirect

    return context
