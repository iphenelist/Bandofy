// Copyright (c) 2026, Innocent P M and contributors
// For license information, please see license.txt

frappe.ui.form.on("Hotspot Omada Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Test Connection"), () => {
			if (frm.is_dirty()) {
				frappe.msgprint(__("Save your changes first."));
				return;
			}
			frappe.call({
				method: "bandofy.bandofy.doctype.hotspot_omada_settings.hotspot_omada_settings.test_connection",
				freeze: true,
				freeze_message: __("Contacting the Omada Controller..."),
				callback: (r) => {
					const m = r.message || {};
					const sites = (m.sites || []).map((s) => frappe.utils.escape_html(s.name)).join(", ");
					const op = m.operator
						? m.operator.found
							? __("Operator {0} found ({1} site(s)).", [m.operator.name, m.operator.sites])
							: __("Operator {0} not found yet -- it will be created with the first site.", [
									m.operator.name,
							  ])
						: "";
					frappe.msgprint({
						title: __("Connected"),
						indicator: "green",
						message: `${__("Controller")} ${m.controller_version || ""}<br>${__(
							"Sites"
						)}: ${sites || "-"}<br>${op}`,
					});
					frm.reload_doc();
				},
			});
		});
	},
});
