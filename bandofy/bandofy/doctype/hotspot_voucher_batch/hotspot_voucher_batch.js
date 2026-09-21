// Copyright (c) 2026, Innocent P M and contributors
// For license information, please see license.txt

frappe.ui.form.on("Hotspot Voucher Batch", {
	refresh(frm) {
		if (!frm.is_new() && (frm.doc.generated_count || 0) < (frm.doc.quantity || 0)) {
			frm.add_custom_button(__("Generate Vouchers"), () => {
				frappe.call({
					method: "bandofy.bandofy.doctype.hotspot_voucher_batch.hotspot_voucher_batch.generate_vouchers_for_batch",
					args: { batch: frm.doc.name },
					freeze: true,
					freeze_message: __("Generating vouchers..."),
					callback(r) {
						if (r.message) {
							frappe.show_alert({
								message: __("{0} voucher(s) generated.", [r.message.created]),
								indicator: "green",
							});
							frm.reload_doc();
						}
					},
				});
			}).addClass("btn-primary");
		}

		if ((frm.doc.generated_count || 0) > 0) {
			frm.add_custom_button(__("View Vouchers"), () => {
				frappe.set_route("List", "Hotspot Voucher", { batch: frm.doc.name });
			});
		}
	},
});
