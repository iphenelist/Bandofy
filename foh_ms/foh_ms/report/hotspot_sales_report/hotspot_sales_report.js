// Copyright (c) 2026, Innocent P M and contributors
// For license information, please see license.txt

frappe.query_reports["Hotspot Sales Report"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), -30),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "site",
			label: __("Hotspot Site"),
			fieldtype: "Link",
			options: "Hotspot Site",
		},
	],
};
