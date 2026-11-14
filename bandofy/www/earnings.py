import frappe
from frappe.query_builder.functions import Sum
from frappe.utils import get_first_day, today

from bandofy.utils import get_vendor_site_name

no_cache = 1


def get_context(context):
	context.no_cache = 1

	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/earnings"
		raise frappe.Redirect

	site = get_vendor_site_name()
	if not site:
		frappe.local.flags.redirect_location = "/vendor-dashboard"
		raise frappe.Redirect

	site_doc = frappe.get_doc("Hotspot Site", site)
	context.site = site_doc

	Txn = frappe.qb.DocType("Hotspot Transaction")
	total_earned = (
		frappe.qb.from_(Txn)
		.select(Sum(Txn.amount))
		.where(Txn.site == site)
		.where(Txn.status == "Paid")
		.run()[0][0] or 0
	)

	month_start = get_first_day(today())
	this_month = (
		frappe.qb.from_(Txn)
		.select(Sum(Txn.amount))
		.where(Txn.site == site)
		.where(Txn.status == "Paid")
		.where(Txn.creation >= month_start)
		.run()[0][0] or 0
	)

	Wdl = frappe.qb.DocType("Hotspot Withdrawal")
	total_withdrawn = (
		frappe.qb.from_(Wdl)
		.select(Sum(Wdl.amount))
		.where(Wdl.site == site)
		.where(Wdl.status == "Approved")
		.run()[0][0] or 0
	)

	context.total_earned = frappe.utils.flt(total_earned)
	context.this_month = frappe.utils.flt(this_month)
	context.total_withdrawn = frappe.utils.flt(total_withdrawn)
	context.available_balance = frappe.utils.flt(total_earned) - frappe.utils.flt(total_withdrawn)

	context.withdrawals = frappe.db.get_all(
		"Hotspot Withdrawal",
		filters={"site": site},
		fields=["name", "amount", "phone_number", "network", "status", "requested_on", "processed_on", "notes"],
		order_by="requested_on desc",
		limit=20,
	)
