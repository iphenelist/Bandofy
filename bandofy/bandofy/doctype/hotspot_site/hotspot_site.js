// Copyright (c) 2026, Innocent P M and contributors
// For license information, please see license.txt

// Central Omada Controller actions -- the same bandofy.mobile_api endpoints
// the mobile app uses (see bandofy.omada_provisioning).
const OMADA = "bandofy.mobile_api.";

frappe.ui.form.on("Hotspot Site", {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(
			frm.doc.omada_site_id ? __("Re-run Omada Setup") : __("Create on Omada"),
			() => bandofy_provision(frm),
			__("Omada")
		);
		if (frm.doc.omada_site_id) {
			frm.add_custom_button(__("Adopt Device"), () => bandofy_adopt(frm), __("Omada"));
			frm.add_custom_button(__("Wi-Fi Networks"), () => bandofy_ssids(frm), __("Omada"));
		}
	},
});

function bandofy_steps_html(steps) {
	return (steps || [])
		.map(
			(s) =>
				`<div style="margin:4px 0">${s.ok ? "✅" : "❌"} <b>${frappe.utils.escape_html(
					s.step
				)}</b>: ${frappe.utils.escape_html(s.detail || "")}</div>`
		)
		.join("");
}

function bandofy_provision(frm) {
	frappe.prompt(
		{
			fieldname: "ssid_name",
			fieldtype: "Data",
			label: __("Hotspot SSID Name"),
			default: frm.doc.hotspot_ssid_name || "Bandofy",
			reqd: 1,
		},
		(values) => {
			frappe.call({
				method: OMADA + "provision_omada_site",
				args: { site: frm.doc.name, ssid_name: values.ssid_name },
				freeze: true,
				freeze_message: __("Setting up the site on the Omada Controller..."),
				callback: (r) => {
					frappe.msgprint({
						title: __("Omada Setup"),
						message: bandofy_steps_html(r.message),
					});
					frm.reload_doc();
				},
			});
		},
		__("Create on Omada"),
		__("Start")
	);
}

function bandofy_adopt(frm) {
	frappe.call({
		method: OMADA + "get_pending_devices",
		args: { site: frm.doc.name },
		freeze: true,
		callback: (r) => {
			const devices = r.message || [];
			if (!devices.length) {
				frappe.msgprint(
					__(
						"No devices are waiting to be adopted. Factory-reset the AP and make sure it can reach the controller (same network, or Controller Inform URL set)."
					)
				);
				return;
			}
			const d = new frappe.ui.Dialog({
				title: __("Adopt Device"),
				fields: [
					{
						fieldname: "mac",
						fieldtype: "Select",
						label: __("Device"),
						reqd: 1,
						options: devices.map((x) => ({
							value: x.mac,
							label: [x.mac, x.model, x.ip].filter(Boolean).join(" · "),
						})),
					},
					{
						fieldtype: "Section Break",
						label: __("Device login (only if not factory default)"),
					},
					{ fieldname: "username", fieldtype: "Data", label: __("Username") },
					{ fieldname: "password", fieldtype: "Password", label: __("Password") },
				],
				primary_action_label: __("Adopt"),
				primary_action(values) {
					d.hide();
					frappe.call({
						method: OMADA + "adopt_omada_device",
						args: { site: frm.doc.name, ...values },
						freeze: true,
						freeze_message: __("Adopting..."),
						callback: (res) => {
							const done = res.message && res.message.status === "adopted";
							frappe.msgprint(
								done
									? __("{0} is adopted and connected.", [res.message.mac])
									: __(
											"{0} is still adopting. It will appear as Connected in a minute.",
											[res.message.mac]
									  )
							);
							frm.reload_doc();
						},
					});
				},
			});
			d.show();
		},
	});
}

function bandofy_ssids(frm) {
	frappe.call({
		method: OMADA + "get_omada_ssids",
		args: { site: frm.doc.name },
		freeze: true,
		callback: (r) => {
			const rows = (r.message || [])
				.map(
					(s) =>
						`<tr><td>${frappe.utils.escape_html(s.name)}</td><td>${
							s.is_hotspot ? __("Hotspot") : ""
						}</td><td>${s.open ? __("Open") : __("Secured")}</td></tr>`
				)
				.join("");
			const d = new frappe.ui.Dialog({
				title: __("Wi-Fi Networks"),
				fields: [
					{
						fieldtype: "HTML",
						options: `<table class="table table-bordered"><thead><tr><th>${__(
							"SSID"
						)}</th><th></th><th></th></tr></thead><tbody>${rows}</tbody></table>`,
					},
					{
						fieldname: "name",
						fieldtype: "Data",
						label: __("Rename hotspot SSID to"),
						default: frm.doc.hotspot_ssid_name,
					},
				],
				primary_action_label: __("Save"),
				primary_action(values) {
					frappe.call({
						method: OMADA + "save_omada_ssid",
						args: {
							site: frm.doc.name,
							name: values.name,
							ssid_id: frm.doc.omada_ssid_id,
						},
						freeze: true,
						callback: () => {
							d.hide();
							frappe.show_alert({ message: __("SSID saved"), indicator: "green" });
							frm.reload_doc();
						},
					});
				},
			});
			d.show();
		},
	});
}
