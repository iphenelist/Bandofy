import frappe
from frappe import _
from frappe.utils import get_first_day, get_last_day, today

no_cache = 1


def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/vouchers"
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

    # Voucher batches for this site
    context.batches = frappe.get_all(
        "Hotspot Voucher Batch",
        filters={"site": site.name},
        fields=["name", "creation", "quantity", "package_name", "status"],
        order_by="creation desc",
        limit_page_length=50,
        ignore_permissions=True,
    )
    for b in context.batches:
        b["creation"] = str(b.get("creation", ""))
        # Get price from the linked package
        pkg_price = frappe.db.get_value("Hotspot Package", b.get("package_name"), "price") or 0
        b["price_per_voucher"] = float(pkg_price)
        b["used"] = frappe.db.count("Hotspot Voucher", {"batch": b["name"], "status": "Used"})
        b["unused"] = frappe.db.count("Hotspot Voucher", {"batch": b["name"], "status": "Unused"})

    # Available packages for this site
    site_doc = frappe.get_doc("Hotspot Site", site.name)
    context.packages = [
        {"name": p.package_name, "price": float(p.price or 0), "duration_minutes": p.duration_minutes, "package_type": p.package_type}
        for p in site_doc.packages
    ]

    context.total_vouchers = frappe.db.count("Hotspot Voucher", {"site": site.name})
    context.used_vouchers  = frappe.db.count("Hotspot Voucher", {"site": site.name, "status": "Used"})
    context.unused_vouchers = frappe.db.count("Hotspot Voucher", {"site": site.name, "status": "Unused"})

    return context
