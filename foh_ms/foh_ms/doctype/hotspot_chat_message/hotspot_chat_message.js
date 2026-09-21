// Copyright (c) 2026, Innocent P M and contributors
// For license information, please see license.txt

frappe.ui.form.on("Hotspot Chat Message", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.direction === "Guest" && !frm.doc.is_read) {
			frm.set_value("is_read", 1);
			frm.save();
		}

		frm.add_custom_button(__("Reply"), () => {
			const dialog = new frappe.ui.Dialog({
				title: __("Reply to {0}", [frm.doc.client_mac]),
				fields: [
					{
						fieldname: "message",
						fieldtype: "Small Text",
						label: __("Message"),
						reqd: 1,
					},
				],
				primary_action_label: __("Send"),
				primary_action(values) {
					frappe.call({
						method: "frappe.client.insert",
						args: {
							doc: {
								doctype: "Hotspot Chat Message",
								site: frm.doc.site,
								client_mac: frm.doc.client_mac,
								direction: "Admin",
								message: values.message,
							},
						},
						callback() {
							dialog.hide();
							frappe.show_alert({ message: __("Reply sent"), indicator: "green" });
							frappe.set_route("List", "Hotspot Chat Message", {
								client_mac: frm.doc.client_mac,
							});
						},
					});
				},
			});
			dialog.show();
		}, __("Actions")).addClass("btn-primary");
	},
});
