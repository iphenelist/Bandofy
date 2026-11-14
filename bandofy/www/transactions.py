import frappe
from frappe import _
from frappe.utils import get_first_day, get_last_day, today

from bandofy.utils import get_vendor_site_name

no_cache = 1


def get_context(context):
    context.no_cache = 1

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/transactions"
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

    txns = frappe.get_all(
        "Hotspot Transaction",
        filters={"site": site.name, "status": "Paid"},
        fields=["name", "phone_number", "package_name", "amount", "duration_minutes", "reference_id", "creation"],
        order_by="creation desc",
        limit_page_length=100,
        ignore_permissions=True,
    )
    for t in txns:
        t["creation"] = str(t.get("creation", ""))
        t["amount"] = float(t.get("amount") or 0)

    context.transactions = txns
    context.total_paid = sum(t["amount"] for t in txns)
    context.total_count = len(txns)
    return context
