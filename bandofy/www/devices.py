import frappe
from frappe import _

no_cache = 1


def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/devices"
        raise frappe.Redirect

    site = frappe.db.get_value(
        "Hotspot Site",
        {"vendor_user": frappe.session.user},
        ["name", "vendor_name", "site_name"],
        as_dict=True,
    )
    if not site:
        frappe.throw(_("No Hotspot Site linked to your account."), frappe.PermissionError)

    context.site = site

    site_doc = frappe.get_doc("Hotspot Site", site.name)
    context.devices = [
        {
            "ap_mac": row.ap_mac,
            "label": row.label or "",
            "controller_type": row.controller_type or "Omada",
            "ac_name": row.ac_name or "",
            "is_active": int(row.is_active or 0),
        }
        for row in site_doc.devices
    ]

    return context
