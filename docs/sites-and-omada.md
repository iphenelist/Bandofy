# Sites and the Omada Controller

Module: **Bandofy**. Sidebar: top-level **Hotspot Site**; **Settings → Hotspot Omada Settings**.

Bandofy authorizes customers on one central TP-Link Omada SDN Controller. Each paying location is a **Hotspot Site**. The controller's address and login live once, in **Hotspot Omada Settings**.

## Hotspot Omada Settings (single)

Only System Manager can read or edit it.

| Field | What it is for |
| --- | --- |
| Controller URL | e.g. `https://169.58.222.183:8043`. `https://` is added if you leave it out, and a trailing `/` is removed. |
| Controller ID (omadacId) | Read-only. Filled by **Test Connection** from the controller's `/api/info`. |
| Open API Client ID / Secret | From Omada: Settings → Platform Integration → Open API → Add New App (Client mode, Admin role, all sites). |
| Operator Name / Password | The hotspot operator Bandofy uses to authorize customers. |
| Region, Time Zone, Application Scenario | Defaults for new Omada sites. The time zone must be an IANA ID such as `Africa/Nairobi`; a bare city name is converted when it matches exactly one zone, otherwise saving fails. |
| Device Account Username / Password | The device login Omada sets on every new site's APs. The password must be 10–64 characters with upper and lower case letters, a number and one of `! # $ % & * @ ^`. |
| Adopt Username / Password | Login used to adopt a factory-default AP. Blank means `admin`/`admin`. |
| Portal URL | Your public `/wifi_login` address. Omada's External Portal sends customers here. |
| Default Hotspot SSID Name | Default `Bandofy`. |
| Request Timeout | Seconds to wait for the controller (default 10). |
| Verify Controller SSL Certificate | Off by default, because local controllers and OC200s use self-signed certificates. |
| Default Success Redirect URL | Where customers go after connecting, for sites that leave their own blank. |

**Test Connection** (form button) checks the controller, gets the controller ID and an Open API token, lists the sites, and fills any empty new-site defaults from the first existing site.

## Hotspot Site

Named `HTS-#####`. Only System Manager has Desk permissions; vendors reach their site through `/vendor-dashboard` and the mobile app.

The form is the one place to manage a site. Its tabs hold the site's own fields and live tables of everything linked to it. The live tables use the same `bandofy.mobile_api` endpoints as the mobile app, so both show the same numbers and enforce the same rules. Each table loads the first time its tab is opened; on a new site they show "Save the site first".

| Tab | Fields | Live table and actions |
| --- | --- | --- |
| **Details** | Site Name, Is Active (inactive sites refuse payments and vouchers); Vendor Name, Vendor User (the vendor's Website User, one per site), Phone Number, Mobile Money Account | none |
| **Dashboard** | none | Revenue today and this month, paid connections, ad views, vouchers issued and redeemed, AP count, Omada controller status and live clients, and a 7-day revenue chart. |
| **Packages & Payments** | Pricing Packages (at least one; see [packages-and-vouchers.md](packages-and-vouchers.md)); Enable Online Payment (off: the portal shows a maintenance message instead of the STK push), Enforce Package Bandwidth, Lipa Namba Image | none |
| **Access Points & Omada** | Access Points (AP MAC, label, active); Hotspot SSID Name, Success Redirect URL; the read-only Omada Site / WLAN / SSID / Portal IDs set by **Create on Omada** | Each AP's live status, model and IP from the controller, with **Reboot** (asks first: it disconnects everyone on that AP) and **Check Connection** (a step-by-step controller check). |
| **Portal & Ads** | Portal Logo, Portal Tagline; Enable Free Trial and its duration, Enable Sabbath Mode (see [captive-portal.md](captive-portal.md)) | The site's ads plus global ones: status, schedule, order and views. **New Ad** opens a Hotspot Ad for this site. |
| **Vouchers** | none | **Voucher Batches**: stock (quantity, generated, unused, redeemed), **New Batch** (creates and generates in one step), **PDF** cards. **Staff Vouchers**: devices used, **New Staff Voucher**, **Enable/Disable**, **Reset Devices**. **Vouchers**: filter by status, search by code, **Block/Unblock**. |
| **Transactions** | none | The site's transactions, newest first, filterable by status. Pending ones can be marked **Paid** (the device is authorized as for a real payment) or **Failed**. |
| **Chat** | none | Guest threads with unread counts. Opening one marks it read and shows a reply box. |

Validation on save:
- An AP MAC can't appear twice on a site, or on two sites. MACs are compared ignoring `:`/`-` and case, because the portal finds the site from the AP the customer connected through.
- The Vendor User can't already belong to another site.
- At least one pricing package is required.

### Omada buttons on the form

| Button | What it does |
| --- | --- |
| Omada → Create on Omada / Re-run Omada Setup | `bandofy.mobile_api.provision_omada_site`. Creates or links the site on the central controller, an open hotspot SSID, the Bandofy external portal and operator access. Shows a step-by-step report. |
| Omada → Adopt Device | Lists APs waiting for adoption and adopts one into the site. The AP is added to the Access Points table. |
| Omada → Wi-Fi Networks | Lists, renames, creates or deletes the site's SSIDs. |

The same actions are in the mobile app (see [dashboards-and-reports.md](dashboards-and-reports.md)).

## Code

| File | Role |
| --- | --- |
| `bandofy/omada_service.py` | Hotspot authorization (operator API), live stats, the site → controller lookup. |
| `bandofy/omada_openapi.py` | Omada Open API client: token, sites, SSIDs, portals, devices. |
| `bandofy/omada_provisioning.py` | The provisioning, adoption and SSID steps. |
| `bandofy/utils.py` | `normalize_mac`, `find_site_by_ap_mac`, `site_ap_macs`. |
