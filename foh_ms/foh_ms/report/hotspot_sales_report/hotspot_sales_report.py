# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, flt, getdate


def execute(filters=None):
	filters = filters or {}
	from_date = getdate(filters.get("from_date"))
	to_date = getdate(filters.get("to_date"))
	site = filters.get("site")

	conditions = ["t.status = 'Paid'", "date(t.creation) between %(from_date)s and %(to_date)s"]
	params = {"from_date": from_date, "to_date": to_date}

	if site:
		conditions.append("t.site = %(site)s")
		params["site"] = site

	where = " and ".join(conditions)

	rows = frappe.db.sql(
		f"""
		select
			date(t.creation) as date,
			t.site as site,
			s.vendor_name as vendor_name,
			count(t.name) as total_transactions,
			sum(case when t.reference_id like 'VOUCHER:%%' then 1 else 0 end) as voucher_transactions,
			sum(case when t.reference_id like 'VOUCHER:%%' then 0 else 1 end) as mobile_money_transactions,
			sum(t.amount) as total_revenue
		from `tabHotspot Transaction` t
		left join `tabHotspot Site` s on s.name = t.site
		where {where}
		group by date(t.creation), t.site
		order by date desc, total_revenue desc
		""",
		params,
		as_dict=True,
	)

	total_revenue = sum(flt(r.total_revenue) for r in rows)
	total_transactions = sum(r.total_transactions for r in rows)
	days_in_range = max(date_diff(to_date, from_date) + 1, 1)

	report_summary = [
		{"value": total_transactions, "label": _("Total Paid Transactions"), "datatype": "Int", "indicator": "blue"},
		{"value": total_revenue, "label": _("Total Revenue"), "datatype": "Currency", "indicator": "green"},
		{
			"value": round(total_revenue / days_in_range, 2),
			"label": _("Avg Revenue / Day"),
			"datatype": "Currency",
			"indicator": "green",
		},
	]

	date_revenue = {}
	current = from_date
	while current <= to_date:
		date_revenue[str(current)] = 0
		current = add_days(current, 1)

	for r in rows:
		key = str(r.date)
		if key in date_revenue:
			date_revenue[key] += flt(r.total_revenue)

	chart = {
		"data": {
			"labels": list(date_revenue.keys()),
			"datasets": [{"name": _("Revenue"), "values": list(date_revenue.values())}],
		},
		"type": "line",
		"lineOptions": {"regionFill": 1},
		"axisOptions": {"xIsSeries": True},
		"title": _("Daily Revenue Trend"),
	}

	columns = [
		{"fieldname": "date", "label": _("Date"), "fieldtype": "Date", "width": 110},
		{"fieldname": "site", "label": _("Site"), "fieldtype": "Link", "options": "Hotspot Site", "width": 130},
		{"fieldname": "vendor_name", "label": _("Vendor"), "fieldtype": "Data", "width": 160},
		{"fieldname": "total_transactions", "label": _("Transactions"), "fieldtype": "Int", "width": 110},
		{"fieldname": "mobile_money_transactions", "label": _("Mobile Money"), "fieldtype": "Int", "width": 110},
		{"fieldname": "voucher_transactions", "label": _("Vouchers"), "fieldtype": "Int", "width": 100},
		{"fieldname": "total_revenue", "label": _("Revenue"), "fieldtype": "Currency", "width": 130},
	]

	data = [dict(r) for r in rows]
	if data:
		data.append(
			{
				"date": _("TOTAL"),
				"site": "",
				"vendor_name": "",
				"total_transactions": total_transactions,
				"mobile_money_transactions": sum(r.mobile_money_transactions for r in rows),
				"voucher_transactions": sum(r.voucher_transactions for r in rows),
				"total_revenue": total_revenue,
				"bold": 1,
			}
		)

	return columns, data, None, chart, report_summary
