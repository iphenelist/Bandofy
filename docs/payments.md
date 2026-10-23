# Payments

Module: **Bandofy**. Sidebar: top-level **Hotspot Transaction**; **Settings → Hotspot Payment Settings**.

Customers pay by mobile money STK push through **Abliner** (`https://abliner.net/api/v1`). The gateway code is in `bandofy/api.py`.

## Hotspot Payment Settings (single)

System Manager only.

| Field | Notes |
| --- | --- |
| Enabled | While off, payments fall back to a logging-only stub so the portal still works in development. |
| Gateway Provider | `Abliner` (the only option). |
| Default Currency | `TZS`. |
| Base URL, Request Timeout | Default `https://abliner.net/api/v1`, 30 seconds. |
| API Key | `tsl_live_…`, sent as the Bearer token. |
| Webhook Secret | `whsec_…`. Signs outgoing deposit requests and checks incoming webhooks. |
| Webhook URL to Register With Gateway | Read-only. The address to paste into Abliner. |
| Auto-Authorize On Payment | Authorize the device on Omada as soon as payment is confirmed (default on). |
| Poll Pending Payments | The 5-minute fallback poll (default on). |

## Hotspot Transaction

Named `HTX-#####`. One row per paid, pending or failed connection.

| Field | Notes |
| --- | --- |
| Site, Status | Status is `Pending`, `Paid` or `Failed`. |
| Payment Reference ID | The gateway's ID for mobile money, or a prefix for non-cash access (below). |
| Phone Number | The mobile money number, or `Voucher`, `Staff` or `Free Trial`. |
| Client MAC, AP MAC, SSID Name, Radio ID | From the portal redirect. Omada needs them to authorize the device. |
| Package Name, Amount, Duration | Copied from the package at purchase. |
| Omada Authorized | Read-only. Set once the device has been authorized on the controller. |

| Kind | Phone Number | Reference ID | Counted as a sale |
| --- | --- | --- | --- |
| Mobile money | customer's number | Abliner transaction ID | Yes |
| Customer voucher | `Voucher` | `VOUCHER:<code>` | Yes |
| Staff voucher | `Staff` | `STAFF:<code>` | No |
| Free trial | `Free Trial` | `FREE_TRIAL:<client MAC>` | Amount 0 |

## Flow

1. The portal calls `bandofy.api.initiate_payment` (guest). It refuses if the AP isn't registered or the site is inactive, online payment is off, or it is Sabbath time. It then creates a Pending transaction and sends the STK push (`POST /deposits`, signed with `x-abliner-signature`, an HMAC-SHA256 of `<timestamp>.<body>`).
2. Abliner calls `bandofy.api.payment_callback` (guest) with `transaction.completed` or `transaction.failed`. The webhook is checked against `X-Webhook-Signature` and `X-Webhook-Timestamp`, and timestamps older than 5 minutes are rejected.
3. On Paid, the device is authorized on Omada (`authorize_mac_on_omada`), with the package's bandwidth when the site enforces it.
4. The portal polls `get_omada_connection_status` and redirects the browser to the site's Success Redirect URL once authorized.
5. Every 5 minutes the scheduler runs `bandofy.api.sync_pending_payments`, which asks Abliner (`GET /transactions`) about transactions still Pending, in case a webhook was missed.

Admins can also mark a stuck Pending transaction Paid or Failed from the mobile app (`mobile_api.set_transaction_status`). Marking it Paid takes the same path as a confirmed payment, so the device is authorized too.

The `on_update` doc event on Hotspot Transaction pushes a `foh_payment_received` realtime alert on the Pending → Paid change (see [dashboards-and-reports.md](dashboards-and-reports.md)).
