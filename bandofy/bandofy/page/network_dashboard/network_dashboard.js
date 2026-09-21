// Copyright (c) 2026, Innocent P M and contributors
// For license information, please see license.txt

frappe.pages["network-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Network Dashboard"),
		single_column: true,
	});

	new bandofy.NetworkDashboard(page);
};

frappe.provide("bandofy");

bandofy.NetworkDashboard = class NetworkDashboard {
	constructor(page) {
		this.page = page;
		this.$body = $('<div class="network-dashboard-wrapper" style="padding: 12px 2px;"></div>').appendTo(
			page.body
		);
		this.page.set_primary_action(__("Refresh"), () => this.load(), "refresh");
		this.load();
	}

	load() {
		this.$body.html('<div class="text-muted" style="padding: 20px;">Loading...</div>');
		frappe.call({
			method: "bandofy.bandofy.page.network_dashboard.network_dashboard.get_dashboard_data",
			callback: (r) => {
				if (r.message) this.render(r.message);
			},
		});
	}

	render(data) {
		const kpi = (label, value) => `
			<div class="col-sm-3" style="margin-bottom: 16px;">
				<div style="border: 1px solid var(--border-color); border-radius: 8px; padding: 16px; background: var(--card-bg, #fff);">
					<div style="font-size: 12px; text-transform: uppercase; color: var(--text-muted); font-weight: 600;">${label}</div>
					<div style="font-size: 22px; font-weight: 700; margin-top: 4px;">${value}</div>
				</div>
			</div>`;

		const kpis = `
			<div class="row">
				${kpi(__("Total Sites"), data.total_sites)}
				${kpi(__("Active Sites"), data.active_sites)}
				${kpi(__("Revenue Today"), format_currency(data.total_revenue_today))}
				${kpi(__("Revenue This Month"), format_currency(data.total_revenue_month))}
			</div>`;

		const rows = (data.sites || [])
			.map(
				(s) => `
				<tr>
					<td><a href="/app/hotspot-site/${encodeURIComponent(s.name)}">${frappe.utils.escape_html(s.vendor_name)}</a></td>
					<td>${frappe.utils.escape_html(s.site_name)}</td>
					<td>${s.is_active ? '<span class="indicator green">Active</span>' : '<span class="indicator red">Inactive</span>'}</td>
					<td>${format_currency(s.revenue_today)}</td>
					<td>${format_currency(s.revenue_month)}</td>
					<td>${s.transactions_today}</td>
					<td>${s.vouchers_redeemed} / ${s.vouchers_issued}</td>
				</tr>`
			)
			.join("");

		const table = `
			<div style="overflow-x: auto; margin-top: 8px;">
				<table class="table table-bordered" style="background: var(--card-bg, #fff);">
					<thead>
						<tr>
							<th>${__("Vendor")}</th>
							<th>${__("Site")}</th>
							<th>${__("Status")}</th>
							<th>${__("Revenue Today")}</th>
							<th>${__("Revenue (Month)")}</th>
							<th>${__("Transactions Today")}</th>
							<th>${__("Vouchers Redeemed / Issued")}</th>
						</tr>
					</thead>
					<tbody>
						${rows || `<tr><td colspan="7" class="text-muted text-center">${__("No sites found")}</td></tr>`}
					</tbody>
				</table>
			</div>`;

		this.$body.html(kpis + table);
	}
};
