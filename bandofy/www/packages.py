import frappe
from frappe import _

from bandofy.utils import get_vendor_site_name

no_cache = 1


def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/packages"
        raise frappe.Redirect

    site_name = get_vendor_site_name()
    if not site_name:
        frappe.throw(_("No Hotspot Site linked to your account."), frappe.PermissionError)
    site = frappe.db.get_value(
        "Hotspot Site",
        site_name,
        ["name", "vendor_name", "site_name"],
        as_dict=True,
    )

    context.site = site

    # Packages linked to this site
    site_doc = frappe.get_doc("Hotspot Site", site.name)
    pkg_names = [p.package_name for p in site_doc.packages if p.package_name]

    packages = []
    for pname in pkg_names:
        if not pname:
            continue
        p = frappe.db.get_value(
            "Hotspot Package", pname,
            ["name", "package_name", "package_type", "price", "duration_minutes", "bandwidth_down_kbps", "bandwidth_up_kbps"],
            as_dict=True,
        )
        if p:
            p["price"] = float(p.get("price") or 0)
            p["bandwidth_down_kbps"] = int(p.get("bandwidth_down_kbps") or 0)
            p["bandwidth_up_kbps"] = int(p.get("bandwidth_up_kbps") or 0)
            packages.append(p)

    context.packages = packages
    return context
