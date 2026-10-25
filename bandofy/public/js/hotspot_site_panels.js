// Copyright (c) 2026, Innocent P M and contributors
// For license information, please see license.txt

// Live panels on the Hotspot Site form (loaded via the doctype_js hook). Each
// panel uses the same bandofy.mobile_api endpoints as the Bandofy Monitor app,
// so the Desk form and the app show the same numbers and enforce the same rules.
// Panels load the first time their tab is opened: the Dashboard and Access
// Points panels call the Omada Controller, which can be slow.

/* global bandofy -- namespace created by frappe.provide("bandofy.site_panels") below */

frappe.provide("bandofy.site_panels");

$.extend(bandofy.site_panels, {
	// Tab fieldname -> the HTML fields (panels) it holds.
	TABS: {
		dashboard_tab: ["dashboard_html"],
		omada_tab: ["devices_html"],
		portal_tab: ["ads_html"],
		vouchers_tab: ["voucher_batches_html", "staff_vouchers_html", "vouchers_html"],
		transactions_tab: ["transactions_html"],
		chat_tab: ["chat_html"],
	},
	PAGE_LENGTH: 20,

	setup(frm) {
		frm.__bandofy_loaded = {};
		const fields = Object.values(this.TABS).flat();
		if (frm.is_new()) {
			fields.forEach((f) =>
				this.wrapper(frm, f).html(
					`<p class="text-muted">${__("Save the site first.")}</p>`
				)
			);
			return;
		}
		this.load_active_tab(frm);
	},

	load_active_tab(frm) {
		// Opening a URL with a tab hash fires on_tab_change before refresh;
		// setup() (from refresh) loads the active tab then.
		if (frm.is_new() || !frm.__bandofy_loaded) return;
		const tab = frm.get_active_tab?.()?.df?.fieldname;
		(this.TABS[tab] || []).forEach((field) => {
			if (!frm.__bandofy_loaded[field]) this.load(frm, field);
		});
	},

	load(frm, field) {
		frm.__bandofy_loaded[field] = true;
		const $w = this.wrapper(frm, field).html(`<p class="text-muted">${__("Loading...")}</p>`);
		Promise.resolve(this.renderers[field].call(this, frm, $w)).catch(() => {
			frm.__bandofy_loaded[field] = false;
			$w.html(`<p class="text-danger">${__("Could not load this section.")}</p>`);
		});
	},

	// Reload a panel now if its tab is open, otherwise the next time it is.
	reload(frm, field) {
		frm.__bandofy_loaded[field] = false;
		this.load_active_tab(frm);
	},

	wrapper(frm, field) {
		return frm.fields_dict[field].$wrapper;
	},

	call(method, args) {
		return frappe.xcall("bandofy.mobile_api." + method, args);
	},

	// --- small rendering helpers ----------------------------------------------

	esc(value) {
		return frappe.utils.escape_html(value == null ? "" : String(value));
	},

	date(value) {
		return value ? this.esc(frappe.datetime.str_to_user(value)) : "";
	},

	money(value) {
		return this.esc(format_currency(value || 0));
	},

	pill(label, color) {
		return `<span class="indicator-pill ${color}">${this.esc(__(label))}</span>`;
	},

	button(label, action, cls = "btn-default") {
		return $(`<button class="btn btn-xs ${cls}" style="margin: 0 4px 4px 0"></button>`)
			.text(label)
			.on("click", (e) => {
				e.preventDefault();
				action();
			});
	},

	toolbar(buttons) {
		const $bar = $(`<div style="margin-bottom: 8px"></div>`);
		buttons.forEach((b) => $bar.append(b));
		return $bar;
	},

	// columns: [{label, html(row) -> escaped HTML string or jQuery}]
	table(columns, rows, empty) {
		if (!rows.length) {
			return $(`<p class="text-muted">${this.esc(empty || __("Nothing here yet."))}</p>`);
		}
		const $table = $(
			`<table class="table table-bordered table-sm" style="margin: 0"></table>`
		);
		$table.append(
			`<thead><tr>${columns
				.map((c) => `<th style="white-space: nowrap">${this.esc(c.label)}</th>`)
				.join("")}</tr></thead>`
		);
		const $body = $("<tbody></tbody>").appendTo($table);
		rows.forEach((row) => {
			const $tr = $("<tr></tr>").appendTo($body);
			columns.forEach((c) => $("<td></td>").append(c.html(row)).appendTo($tr));
		});
		return $(`<div class="table-responsive"></div>`).append($table);
	},

	link(doctype, name) {
		return `<a href="/desk/${frappe.router.slug(doctype)}/${encodeURIComponent(
			name
		)}">${this.esc(name)}</a>`;
	},

	// --- panels ----------------------------------------------------------------

	renderers: {
		async dashboard_html(frm, $w) {
			const d = await this.call("get_dashboard", { site: frm.doc.name });
			const omada = d.omada || {};
			const stat = (label, value) =>
				`<div class="col-6 col-md-3" style="margin-bottom: 12px">
					<div class="text-muted small">${this.esc(label)}</div>
					<div style="font-size: 1.25rem; font-weight: 600">${value}</div>
				</div>`;
			$w.empty().append(
				this.toolbar([this.button(__("Refresh"), () => this.load(frm, "dashboard_html"))]),
				`<div class="row">
					${stat(__("Revenue Today"), this.money(d.revenue_today))}
					${stat(__("Revenue This Month"), this.money(d.revenue_month))}
					${stat(__("Paid Connections"), this.esc(d.active_connections))}
					${stat(__("Ad Views"), this.esc(d.ad_views))}
					${stat(__("Vouchers Issued"), this.esc(d.vouchers_issued))}
					${stat(__("Vouchers Redeemed"), this.esc(d.vouchers_redeemed))}
					${stat(__("Access Points"), this.esc(d.site?.device_count))}
					${stat(
						__("Omada Controller"),
						omada.connected
							? `${this.pill("Connected", "green")} <span class="small">${this.esc(
									__("{0} client(s)", [omada.client_count || 0])
							  )}</span>`
							: this.pill("Disconnected", "red")
					)}
				</div>`
			);
			if (omada.error) {
				$w.append(`<p class="text-muted small">${this.esc(omada.error)}</p>`);
			}
			const trend = d.revenue_trend || [];
			if (trend.length) {
				const chart = $(`<div></div>`).appendTo($w);
				new frappe.Chart(chart[0], {
					title: __("Revenue, Last 7 Days"),
					type: "bar",
					height: 220,
					colors: ["#16A34A"],
					data: {
						labels: trend.map((t) => frappe.datetime.str_to_user(t.date)),
						datasets: [{ name: __("Revenue"), values: trend.map((t) => t.amount) }],
					},
				});
			}
		},

		async devices_html(frm, $w) {
			const devices = await this.call("get_site_devices", { site: frm.doc.name });
			// Live status, model, IP and Reboot come from the Omada Open API.
			const open_api = !!(frm.doc.__onload && frm.doc.__onload.open_api);
			const status = (s) =>
				!s || s === "unknown"
					? this.pill("Unknown", "gray")
					: s === "connected"
					? this.pill("Connected", "green")
					: this.pill(s, /offline|disconnect/.test(s) ? "red" : "orange");
			$w.empty().append(
				this.toolbar([
					this.button(__("Refresh"), () => this.load(frm, "devices_html")),
					this.button(__("Check Connection"), () => this.check_connection(frm)),
				]),
				this.table(
					[
						{ label: __("AP MAC"), html: (r) => this.esc(r.ap_mac) },
						{ label: __("Label"), html: (r) => this.esc(r.label) },
						{
							label: __("Active"),
							html: (r) => (r.is_active ? __("Yes") : __("No")),
						},
						...(open_api
							? [
									{ label: __("Status"), html: (r) => status(r.status) },
									{ label: __("Model"), html: (r) => this.esc(r.model) },
									{ label: __("IP"), html: (r) => this.esc(r.ip) },
							  ]
							: []),
						open_api && {
							label: "",
							html: (r) =>
								this.button(__("Reboot"), () =>
									frappe.confirm(
										__(
											"Reboot {0}? Every customer connected to it is disconnected.",
											[this.esc(r.label || r.ap_mac)]
										),
										() =>
											this.call("reboot_site_device", {
												site: frm.doc.name,
												ap_mac: r.ap_mac,
											}).then(() =>
												frappe.show_alert({
													message: __("Reboot started"),
													indicator: "green",
												})
											)
									)
								),
						},
					].filter(Boolean),
					devices,
					open_api
						? __(
								"No access points yet. Add them in the table above, or use Omada > Adopt Device."
						  )
						: __(
								"No access points listed. That's fine: customers are matched by the Omada Site ID. Add APs above only to label them."
						  )
				)
			);
		},

		async ads_html(frm, $w) {
			const ads = await this.call("get_ads", { site: frm.doc.name });
			$w.empty().append(
				this.toolbar([
					this.button(__("New Ad"), () => this.ad_dialog(frm), "btn-primary"),
					this.button(__("Refresh"), () => this.load(frm, "ads_html")),
				]),
				this.table(
					[
						{ label: __("Ad"), html: (r) => this.link("Hotspot Ad", r.name) },
						{ label: __("Title"), html: (r) => this.esc(r.title) },
						{
							label: __("Site"),
							html: (r) =>
								r.site ? this.esc(r.site) : this.pill("All sites", "blue"),
						},
						{
							label: __("Status"),
							html: (r) =>
								r.is_active
									? this.pill("Active", "green")
									: this.pill("Inactive", "gray"),
						},
						{
							label: __("Schedule"),
							html: (r) =>
								r.start_date || r.end_date
									? `${this.date(r.start_date)} – ${this.date(r.end_date)}`
									: "",
						},
						{ label: __("Order"), html: (r) => this.esc(r.display_order) },
						{ label: __("Views"), html: (r) => this.esc(r.views_count) },
						{
							label: "",
							html: (r) =>
								$("<span></span>").append(
									this.button(__("Edit"), () => this.ad_dialog(frm, r)),
									this.button(__("Delete"), () =>
										frappe.confirm(
											__("Delete ad {0}?", [this.esc(r.title).bold()]),
											() =>
												this.call("delete_ad", { name: r.name }).then(() =>
													this.load(frm, "ads_html")
												)
										)
									)
								),
						},
					],
					ads,
					__("No ads for this site.")
				)
			);
		},

		async voucher_batches_html(frm, $w) {
			const batches = await this.call("get_voucher_batches", { site: frm.doc.name });
			$w.empty().append(
				this.toolbar([
					this.button(__("New Batch"), () => this.new_batch(frm), "btn-primary"),
					this.button(__("Refresh"), () => this.load(frm, "voucher_batches_html")),
				]),
				this.table(
					[
						{
							label: __("Batch"),
							html: (r) => this.link("Hotspot Voucher Batch", r.name),
						},
						{ label: __("Package"), html: (r) => this.esc(r.package_name) },
						{ label: __("Quantity"), html: (r) => this.esc(r.quantity) },
						{ label: __("Generated"), html: (r) => this.esc(r.generated_count) },
						{
							label: __("Unused"),
							html: (r) =>
								r.remaining_unused
									? this.esc(r.remaining_unused)
									: this.pill("0", "red"),
						},
						{ label: __("Redeemed"), html: (r) => this.esc(r.redeemed_count) },
						{ label: __("Expires"), html: (r) => this.date(r.expires_on) },
						{
							label: "",
							html: (r) =>
								this.button(__("PDF"), () =>
									window.open(
										"/api/method/bandofy.mobile_api.download_voucher_batch_pdf?batch=" +
											encodeURIComponent(r.name)
									)
								),
						},
					],
					batches,
					__("No voucher batches yet.")
				)
			);
		},

		async staff_vouchers_html(frm, $w) {
			const vouchers = await this.call("get_staff_vouchers", { site: frm.doc.name });
			const act = (method, args, message) =>
				this.call(method, args).then(() => {
					frappe.show_alert({ message, indicator: "green" });
					this.load(frm, "staff_vouchers_html");
				});
			$w.empty().append(
				this.toolbar([
					this.button(
						__("New Staff Voucher"),
						() => this.new_staff_voucher(frm),
						"btn-primary"
					),
					this.button(__("Refresh"), () => this.load(frm, "staff_vouchers_html")),
				]),
				this.table(
					[
						{
							label: __("Code"),
							html: (r) => this.link("Hotspot Staff Voucher", r.name),
						},
						{ label: __("Staff"), html: (r) => this.esc(r.staff_name) },
						{
							label: __("Status"),
							html: (r) =>
								r.status === "Active"
									? this.pill("Active", "green")
									: this.pill("Disabled", "gray"),
						},
						{
							label: __("Devices"),
							html: (r) =>
								this.esc(
									`${r.devices.length} / ${
										r.max_devices ? r.max_devices : __("unlimited")
									}`
								),
						},
						{ label: __("Minutes / Login"), html: (r) => this.esc(r.session_minutes) },
						{ label: __("Valid Until"), html: (r) => this.date(r.valid_until) },
						{ label: __("Last Used"), html: (r) => this.date(r.last_used_on) },
						{
							label: "",
							html: (r) =>
								$("<div></div>").append(
									this.button(
										r.status === "Active" ? __("Disable") : __("Enable"),
										() =>
											act(
												"set_staff_voucher_status",
												{
													name: r.name,
													status:
														r.status === "Active"
															? "Disabled"
															: "Active",
												},
												__("Staff voucher updated")
											)
									),
									r.devices.length
										? this.button(__("Reset Devices"), () =>
												frappe.confirm(
													__("Free all device slots on code {0}?", [
														this.esc(r.name),
													]),
													() =>
														act(
															"reset_staff_voucher_devices",
															{ name: r.name },
															__("Devices reset")
														)
												)
										  )
										: ""
								),
						},
					],
					vouchers,
					__("No staff vouchers yet.")
				)
			);
		},

		async vouchers_html(frm, $w) {
			const state = { status: "", search: "", start: 0, rows: [] };
			const $filters = $(`<div class="row" style="margin-bottom: 8px">
				<div class="col-6 col-md-3"><select class="form-control input-xs"></select></div>
				<div class="col-6 col-md-3"><input class="form-control input-xs" type="search"></div>
			</div>`);
			const $status = $filters.find("select");
			["", "Unused", "Used", "Expired", "Blocked"].forEach((s) =>
				$status.append(
					$("<option></option>")
						.val(s)
						.text(s ? __(s) : __("All statuses"))
				)
			);
			const $search = $filters.find("input").attr("placeholder", __("Search code"));
			const $list = $("<div></div>");
			const $more = this.button(__("Load More"), () => fetch(false));

			const set_status = (r, status) =>
				this.call("set_voucher_status", { name: r.name, status }).then(() => {
					frappe.show_alert({ message: __("Voucher updated"), indicator: "green" });
					fetch(true);
				});
			// A voucher sold outside the portal (e.g. through the ISP router):
			// marking it Used records a Paid transaction at its price.
			const mark_sold = (r) =>
				frappe.confirm(
					__(
						"Mark voucher {0} as sold for {1}? It will be counted in the sales report.",
						[this.esc(r.name).bold(), this.money(r.price)]
					),
					() => set_status(r, "Used")
				);

			const fetch = async (reset) => {
				if (reset) Object.assign(state, { start: 0, rows: [] });
				const res = await this.call("get_vouchers", {
					site: frm.doc.name,
					status: state.status || null,
					search: state.search || null,
					limit: this.PAGE_LENGTH,
					start: state.start,
				});
				state.rows = state.rows.concat(res.vouchers);
				state.start += res.vouchers.length;
				$more.toggle(res.vouchers.length === this.PAGE_LENGTH);
				$list.empty().append(
					this.table(
						[
							{
								label: __("Code"),
								html: (r) => this.link("Hotspot Voucher", r.name),
							},
							{
								label: __("Status"),
								html: (r) =>
									this.pill(
										r.status,
										{ Unused: "blue", Used: "green", Blocked: "red" }[
											r.status
										] || "gray"
									),
							},
							{ label: __("Package"), html: (r) => this.esc(r.package_name) },
							{ label: __("Batch"), html: (r) => this.esc(r.batch) },
							{ label: __("Generated"), html: (r) => this.date(r.generated_on) },
							{ label: __("Expires"), html: (r) => this.date(r.expires_on) },
							{ label: __("Used On"), html: (r) => this.date(r.used_on) },
							{ label: __("Used By"), html: (r) => this.esc(r.used_by_mac) },
							{
								label: "",
								html: (r) =>
									r.status === "Used"
										? ""
										: $("<span></span>").append(
												this.button(__("Mark Sold"), () => mark_sold(r)),
												r.status === "Unused"
													? this.button(__("Block"), () =>
															set_status(r, "Blocked")
													  )
													: r.status === "Blocked"
													? this.button(__("Unblock"), () =>
															set_status(r, "Unused")
													  )
													: ""
										  ),
							},
						],
						state.rows,
						__("No vouchers match.")
					)
				);
			};

			$status.on("change", () => {
				state.status = $status.val();
				fetch(true);
			});
			$search.on(
				"input",
				frappe.utils.debounce(() => {
					state.search = $search.val().trim();
					fetch(true);
				}, 400)
			);
			$w.empty().append($filters, $list, $more);
			await fetch(true);
		},

		async transactions_html(frm, $w) {
			const state = { status: "", start: 0, rows: [] };
			const $status = $(`<select class="form-control input-xs"></select>`);
			["", "Paid", "Pending", "Failed"].forEach((s) =>
				$status.append(
					$("<option></option>")
						.val(s)
						.text(s ? __(s) : __("All statuses"))
				)
			);
			const $filters = $(`<div class="row" style="margin-bottom: 8px">
				<div class="col-6 col-md-3"></div></div>`);
			$filters.find(".col-6").append($status);
			const $list = $("<div></div>");
			const $more = this.button(__("Load More"), () => fetch(false));

			const set_status = (r, status) =>
				frappe.confirm(
					status === "Paid"
						? __(
								"Mark {0} as Paid? The customer's device is authorized as if the payment had been confirmed.",
								[this.esc(r.name)]
						  )
						: __("Mark {0} as Failed?", [this.esc(r.name)]),
					() =>
						this.call("set_transaction_status", { name: r.name, status }).then(() => {
							frappe.show_alert({
								message: __("Transaction updated"),
								indicator: "green",
							});
							frm.__bandofy_loaded.dashboard_html = false;
							fetch(true);
						})
				);

			const fetch = async (reset) => {
				if (reset) Object.assign(state, { start: 0, rows: [] });
				const rows = await this.call("get_transactions", {
					site: frm.doc.name,
					status: state.status || null,
					limit: this.PAGE_LENGTH,
					start: state.start,
				});
				state.rows = state.rows.concat(rows);
				state.start += rows.length;
				$more.toggle(rows.length === this.PAGE_LENGTH);
				$list.empty().append(
					this.table(
						[
							{
								label: __("Transaction"),
								html: (r) => this.link("Hotspot Transaction", r.name),
							},
							{ label: __("Date"), html: (r) => this.date(r.creation) },
							{
								label: __("Status"),
								html: (r) =>
									this.pill(
										r.status,
										{ Paid: "green", Pending: "orange", Failed: "red" }[
											r.status
										] || "gray"
									),
							},
							{ label: __("Phone"), html: (r) => this.esc(r.phone_number) },
							{ label: __("Package"), html: (r) => this.esc(r.package_name) },
							{ label: __("Amount"), html: (r) => this.money(r.amount) },
							{ label: __("Reference"), html: (r) => this.esc(r.reference_id) },
							{ label: __("Client MAC"), html: (r) => this.esc(r.client_mac) },
							{
								label: "",
								html: (r) =>
									r.status === "Pending"
										? $("<div></div>").append(
												this.button(__("Mark Paid"), () =>
													set_status(r, "Paid")
												),
												this.button(__("Mark Failed"), () =>
													set_status(r, "Failed")
												)
										  )
										: "",
							},
						],
						state.rows,
						__("No transactions yet.")
					)
				);
			};

			$status.on("change", () => {
				state.status = $status.val();
				fetch(true);
			});
			$w.empty().append($filters, $list, $more);
			await fetch(true);
		},

		async chat_html(frm, $w) {
			const threads = await this.call("get_chat_threads", { site: frm.doc.name });
			const $layout = $(`<div class="row">
				<div class="col-md-5 bandofy-threads"></div>
				<div class="col-md-7 bandofy-thread"></div>
			</div>`);
			const $threads = $layout.find(".bandofy-threads");
			const $thread = $layout.find(".bandofy-thread");

			if (!threads.length) {
				$threads.html(`<p class="text-muted">${__("No guest messages yet.")}</p>`);
			}
			threads.forEach((t) => {
				$(`<a href="#" class="list-group-item list-group-item-action" style="display: block">
					<div style="display: flex; justify-content: space-between; gap: 8px">
						<b>${this.esc(t.client_mac)}</b>
						${t.unread_count ? this.pill(String(t.unread_count), "red") : ""}
					</div>
					<div class="text-muted small text-truncate">${this.esc(t.last_message)}</div>
					<div class="text-muted small">${this.esc(frappe.datetime.comment_when(t.last_message_at))}</div>
				</a>`)
					.on("click", (e) => {
						e.preventDefault();
						this.open_thread(frm, $thread, t.client_mac);
					})
					.appendTo($threads);
			});

			$w.empty().append(
				this.toolbar([this.button(__("Refresh"), () => this.load(frm, "chat_html"))]),
				$layout
			);
		},
	},

	// --- dialogs and sub-views -------------------------------------------------

	check_connection(frm) {
		this.call("check_omada_connection", { site: frm.doc.name }).then((steps) =>
			frappe.msgprint({
				title: __("Omada Connection"),
				message: (steps || [])
					.map(
						(s) =>
							`<div style="margin: 4px 0">${s.ok ? "✅" : "❌"} <b>${this.esc(
								s.step
							)}</b>: ${this.esc(s.detail)}</div>`
					)
					.join(""),
			})
		);
	},

	// New or edit a captive-portal ad in a popup (bandofy.mobile_api.save_ad).
	ad_dialog(frm, ad) {
		// Portal visitors are guests, so ad media must be public files.
		const upload = { make_attachments_public: 1 };
		const d = new frappe.ui.Dialog({
			title: ad ? __("Edit Ad") : __("New Ad"),
			size: "large",
			fields: [
				{ fieldname: "title", fieldtype: "Data", label: __("Ad Title"), reqd: 1 },
				{ fieldname: "is_active", fieldtype: "Check", label: __("Is Active"), default: 1 },
				{ fieldtype: "Column Break" },
				{
					fieldname: "site",
					fieldtype: "Link",
					options: "Hotspot Site",
					label: __("Hotspot Site (leave blank for all sites)"),
					default: frm.doc.name,
					hidden: !frappe.user.has_role("System Manager"),
				},
				{
					fieldname: "display_order",
					fieldtype: "Int",
					label: __("Display Order"),
					default: 0,
				},
				{ fieldtype: "Section Break", label: __("Creative") },
				{
					fieldname: "image",
					fieldtype: "Attach Image",
					label: __("Banner Image"),
					reqd: 1,
					options: upload,
				},
				{ fieldname: "target_url", fieldtype: "Data", label: __("Target URL (Optional)") },
				{ fieldtype: "Column Break" },
				{
					fieldname: "description",
					fieldtype: "Data",
					label: __("Short Description (Optional)"),
				},
				{
					fieldname: "phone_number",
					fieldtype: "Data",
					options: "Phone",
					label: __("Contact Phone (Optional)"),
				},
				{
					fieldtype: "Section Break",
					label: __("Full-Screen Ad (before Free Internet)"),
					collapsible: !(ad && ad.show_before_free_trial),
				},
				{
					fieldname: "show_before_free_trial",
					fieldtype: "Check",
					label: __("Show Before Free Internet"),
				},
				{
					fieldname: "fullscreen_image",
					fieldtype: "Attach Image",
					label: __("Full-Screen Image (1080 x 1920)"),
					options: upload,
				},
				{ fieldtype: "Column Break" },
				{
					fieldname: "video",
					fieldtype: "Attach",
					label: __("Video (MP4, 720 x 1280)"),
					options: upload,
				},
				{ fieldtype: "Section Break", label: __("Schedule (Optional)") },
				{ fieldname: "start_date", fieldtype: "Date", label: __("Start Date") },
				{ fieldtype: "Column Break" },
				{ fieldname: "end_date", fieldtype: "Date", label: __("End Date") },
			],
			primary_action_label: __("Save"),
			primary_action: (values) => {
				this.call("save_ad", { name: ad ? ad.name : null, values }).then(() => {
					d.hide();
					frappe.show_alert({ message: __("Ad saved"), indicator: "green" });
					this.load(frm, "ads_html");
				});
			},
		});
		if (ad) d.set_values(ad);
		d.show();
	},

	new_batch(frm) {
		const d = new frappe.ui.Dialog({
			title: __("New Voucher Batch"),
			fields: [
				{
					fieldname: "package_name",
					fieldtype: "Link",
					options: "Hotspot Package",
					label: __("Package"),
					reqd: 1,
				},
				{ fieldname: "quantity", fieldtype: "Int", label: __("Quantity"), reqd: 1 },
				{ fieldname: "prefix", fieldtype: "Data", label: __("Voucher Code Prefix") },
				{ fieldname: "expires_on", fieldtype: "Date", label: __("Vouchers Expire On") },
				{ fieldname: "notes", fieldtype: "Small Text", label: __("Notes") },
			],
			primary_action_label: __("Create and Generate"),
			primary_action: (values) => {
				frappe.dom.freeze(__("Generating vouchers..."));
				this.call("create_voucher_batch", { site: frm.doc.name, ...values })
					.then((r) => {
						d.hide();
						frappe.show_alert({
							message: __("{0} voucher(s) generated in {1}", [r.created, r.batch]),
							indicator: "green",
						});
						this.reload(frm, "voucher_batches_html");
						this.reload(frm, "vouchers_html");
					})
					.finally(() => frappe.dom.unfreeze());
			},
		});
		d.show();
	},

	new_staff_voucher(frm) {
		const d = new frappe.ui.Dialog({
			title: __("New Staff Voucher"),
			fields: [
				{ fieldname: "staff_name", fieldtype: "Data", label: __("Staff Name"), reqd: 1 },
				{ fieldname: "phone_number", fieldtype: "Data", label: __("Phone Number") },
				{
					fieldname: "session_minutes",
					fieldtype: "Int",
					label: __("Minutes Per Login"),
					default: 1440,
					reqd: 1,
				},
				{
					fieldname: "max_devices",
					fieldtype: "Int",
					label: __("Max Devices"),
					default: 1,
					description: __("0 = unlimited"),
				},
				{ fieldname: "valid_until", fieldtype: "Date", label: __("Valid Until") },
				{ fieldname: "notes", fieldtype: "Small Text", label: __("Notes") },
			],
			primary_action_label: __("Create"),
			primary_action: (values) => {
				this.call("create_staff_voucher", { site: frm.doc.name, ...values }).then((r) => {
					d.hide();
					frappe.msgprint({
						title: __("Staff Voucher Created"),
						message: __("Code: {0}", [`<b>${this.esc(r.name)}</b>`]),
						indicator: "green",
					});
					this.load(frm, "staff_vouchers_html");
				});
			},
		});
		d.show();
	},

	async open_thread(frm, $thread, client_mac) {
		$thread.html(`<p class="text-muted">${__("Loading...")}</p>`);
		const messages = await this.call("get_chat_thread", { client_mac, site: frm.doc.name });
		const $messages = $(
			`<div style="max-height: 360px; overflow-y: auto; margin-bottom: 8px"></div>`
		);
		messages.forEach((m) => {
			const mine = m.direction === "Admin";
			$messages.append(`<div style="display: flex; justify-content: ${
				mine ? "flex-end" : "flex-start"
			}; margin: 4px 0">
				<div style="max-width: 80%; padding: 6px 10px; border-radius: 8px; background: ${
					mine ? "var(--green-100, #dcfce7)" : "var(--control-bg)"
				}">
					<div style="white-space: pre-wrap">${this.esc(m.message)}</div>
					<div class="text-muted small">${this.esc(frappe.datetime.str_to_user(m.creation))}</div>
				</div>
			</div>`);
		});
		const $reply = $(
			`<textarea class="form-control" rows="2" maxlength="500"></textarea>`
		).attr("placeholder", __("Reply to {0}", [client_mac]));
		const $send = this.button(
			__("Send"),
			() => {
				const message = $reply.val().trim();
				if (!message) return;
				this.call("send_chat_reply", { client_mac, message, site: frm.doc.name }).then(
					() => this.open_thread(frm, $thread, client_mac)
				);
			},
			"btn-primary"
		);
		$thread
			.empty()
			.append(
				`<h6>${this.esc(client_mac)}</h6>`,
				$messages,
				$reply,
				$(`<div style="margin-top: 6px"></div>`).append($send)
			);
		$messages.scrollTop($messages[0].scrollHeight);
	},
});
