# Dashboards, reports and the mobile app

Module: **Bandofy**. Sidebar: top-level **Network Dashboard**; **Reports → Hotspot Sales Report**.

## Who sees what

| User | Gets |
| --- | --- |
| System Manager / Administrator ("admin") | Desk, the Network Dashboard, every site in the mobile app. |
| Website User set as a site's **Vendor User** ("vendor") | `/vendor-dashboard` and the mobile app, limited to their one site. |

`bandofy.api.restrict_desk_access` (a `before_request` hook) redirects users without System Manager who open a `/app…` URL to `/vendor-dashboard`. On v16 the desk lives at `/desk`, which this hook doesn't match. Frappe's own desk check still refuses Website Users there, but with an error page rather than the redirect. On a bench shared with other apps, the hook also bounces those apps' non-System-Manager desk users on `/app` links.

## Revenue rules

Every revenue figure counts Hotspot Transactions with status **Paid**, grouped by the **date of creation**. `bandofy/dashboard_utils.py` holds the shared queries, so the web dashboard, the Desk page and the mobile app agree:

- `get_revenue(site, from, to)`: total Paid amount between two dates, inclusive.
- `get_revenue_trend(site, days)`: daily totals for the last *n* days, with zero for days without sales.

The Sales Report and the mobile app's report screen also exclude staff logins (`STAFF:` references).

## /vendor-dashboard

`bandofy/www/vendor_dashboard.py`. Guests are sent to log in. A user not linked to any site gets a permission error. It shows the vendor's site, AP count, today's and this month's revenue, and recent Paid transactions.

## Network Dashboard (Desk page `network-dashboard`)

System Manager only. One row per site: AP MACs, active flag, revenue today and this month, Paid transactions today, and vouchers issued and redeemed. It also shows totals, and sorts sites by this month's revenue.

## Hotspot Sales Report (Script Report)

| Filter | |
| --- | --- |
| From Date, To Date | Required. |
| Site | Optional. |

There is one row per day and site: Vendor, Transactions, Mobile Money, Vouchers (`VOUCHER:` references) and Revenue, plus a TOTAL row. It also shows a daily revenue line chart and summary cards (total paid transactions, total revenue, average revenue per day over the whole range).

## Mobile app API (`bandofy/mobile_api.py`)

The Bandofy Monitor Flutter app uses session cookies: `mobile_login` returns the role and site in the same call. Every endpoint works out the caller's site itself; a vendor's `site` argument is ignored, and an admin may pass one or leave it out for all sites. Endpoints cover:

- the dashboard, transactions and manual reconciliation;
- vouchers, batches (with PDF cards), staff vouchers and packages;
- site settings, branding, access points (live status from Omada, reboot) and Omada provisioning, adoption and SSIDs;
- ads, chat, the sales report (with revenue by package), and gateway and Omada settings (passwords are never returned).

## Realtime alerts (`bandofy/realtime.py`)

These go to every System Manager and to the site's Vendor User:

| Event | When |
| --- | --- |
| `foh_voucher_used` | A Hotspot Voucher goes from Unused to Used. |
| `foh_payment_received` | A mobile money Hotspot Transaction goes from Pending to Paid. |
| `foh_new_chat_message` | A Guest chat message is inserted. |

`mobile_api.get_activity(since)` returns the same payloads, for when the app has been offline.
