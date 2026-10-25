# Sites and the Omada Controller

Module: **Bandofy**. Sidebar: top-level **Hotspot Site**; **Settings → Hotspot Omada Settings**.

Bandofy authorizes customers on one central TP-Link Omada SDN Controller. Each vendor's location is a **Hotspot Site**, linked to one site on the controller by its **Omada Site ID**. The controller's address and hotspot operator live once, in **Hotspot Omada Settings**.

## How a customer is matched to a site

When a phone joins a hotspot SSID, Omada's External Portal sends it to `/wifi_login` with `site` (the Omada site ID), `clientMac`, `apMac`, `ssidName` and `radioId`. Bandofy finds the Hotspot Site whose **Omada Site ID** equals `site`. If there is none (no `site` in the redirect, or the site has no ID yet), it falls back to the **Access Points** table and matches `apMac`.

So with the Omada Site ID filled in, a site needs no Access Points rows, and an AP adopted on the controller works at once without any change in Bandofy. If the portal says the network isn't registered, it shows the site ID it received so the admin can copy it into the right Hotspot Site.

## Setting up a site

There are two ways. Both end with the Omada Site ID on the Hotspot Site, and both kinds of site work side by side.

### Option 1: set up in the Omada Controller (no Open API needed)

Once for the controller: in **Hotspot Manager → Operators**, create the hotspot operator Bandofy uses, and enter its name and password in Hotspot Omada Settings with the Controller URL. Click **Test Connection**.

For each new location (menu names vary slightly between controller versions):

1. **Global View → Sites → Add New Site**, and adopt the location's APs into it.
2. In the site's **Settings → Wireless Networks**, create an open SSID (Security: None).
3. In **Settings → Authentication → Portal**, create a portal for that SSID: Authentication Type **External Portal Server**, Custom Portal Server URL `https://<your Bandofy site>/wifi_login`, Authentication Timeout at least your longest package. If the portal page doesn't load on a phone, add your Bandofy domain under **Pre-Authentication Access**.
4. Give the hotspot operator access to the site, unless it already has all sites.
5. In Bandofy, create the **Hotspot Site** and paste the site's **Omada Site ID**: 24 hex characters, shown in the portal address (`site=…`) when a phone joins the SSID, and in the controller's URL while the site is open.

### Option 2: automatic setup (Open API)

Fill in **Advanced: Open API** in Hotspot Omada Settings. Then on each Hotspot Site, **Omada → Create on Omada** creates (or links) the Omada site, the open SSID, the external portal and the operator access, and fills in the Omada Site ID. **Adopt Device** and **Wi-Fi Networks** become available too. This saves time when onboarding many vendors.

## Hotspot Omada Settings (single)

Only System Manager can read or edit it.

| Field | What it is for |
| --- | --- |
| Controller URL | e.g. `https://169.58.222.183:8043`. `https://` is added if you leave it out, and a trailing `/` is removed. |
| Controller ID (omadacId) | Read-only. Filled by **Test Connection** (and on first use) from the controller's `/api/info`. |
| Request Timeout | Seconds to wait for the controller (default 10). |
| Verify Controller SSL Certificate | Off by default, because local controllers and OC200s use self-signed certificates. |
| Operator Name / Password | The hotspot operator Bandofy uses to authorize customers. Required. |
| Default Success Redirect URL | Where customers go after connecting, for sites that leave their own blank. |

**Advanced: Open API (optional)**, collapsed until filled in. Only needed for Option 2, live AP status and reboot, and package bandwidth limits.

| Field | What it is for |
| --- | --- |
| Open API Client ID / Secret | From Omada: Settings → Platform Integration → Open API → Add New App (Client mode, Admin role, all sites). |
| Region, Time Zone, Application Scenario | Defaults for new Omada sites. The time zone must be an IANA ID such as `Africa/Nairobi`; a bare city name is converted when it matches exactly one zone, otherwise saving fails. |
| Device Account Username / Password | The device login Omada sets on every new site's APs. The password must be 10–64 characters with upper and lower case letters, a number and one of `! # $ % & * @ ^`. |
| Adopt Username / Password | Login used to adopt a factory-default AP. Blank means `admin`/`admin`. |
| Portal URL | Your public `/wifi_login` address, used when Bandofy creates the external portal. |
| Default Hotspot SSID Name | Default `Bandofy`. |

**Test Connection** (form button): without Open API keys, it reaches the controller, saves its Controller ID and checks that the hotspot operator can log in. With them, it also gets an Open API token, lists the sites and fills any empty new-site defaults from the first existing site.

## Hotspot Site

Named `HTS-#####`. Only System Manager has Desk permissions; vendors reach their site through `/vendor-dashboard` and the mobile app.

The form is the one place to manage a site. Its tabs hold the site's own fields and live tables of everything linked to it. The live tables use the same `bandofy.mobile_api` endpoints as the mobile app, so both show the same numbers and enforce the same rules. Each table loads the first time its tab is opened; on a new site they show "Save the site first".

| Tab | Fields | Live table and actions |
| --- | --- | --- |
| **Details** | Site Name (the one name: also used as the vendor name on the portal and as the hotspot Wi-Fi/SSID name, max 32 characters on Omada), Controller Type (Omada, or Ruijie: see [ruijie.md](ruijie.md)), Omada Site ID (Ruijie AC Name on Ruijie sites), Is Active (inactive sites refuse payments and vouchers); Vendor User (the vendor's Website User, one per site), Phone Number, Mobile Money Account | none |
| **Dashboard** | none | Revenue today and this month, paid connections, ad views, vouchers issued and redeemed, AP count, Omada controller status and live clients, and a 7-day revenue chart. |
| **Packages & Payments** | Pricing Packages (at least one; see [packages-and-vouchers.md](packages-and-vouchers.md)); Enable Online Payment (off: the portal shows a maintenance message instead of the STK push), Enforce Package Bandwidth (needs the Open API), Lipa Namba Image | none |
| **Access Points & Omada** | Access Points (AP MAC, label, active; optional); Success Redirect URL. **Create on Omada** uses the Site Name as the SSID; renaming the hotspot SSID under **Wi-Fi Networks** renames the site too | The listed APs, with **Check Connection** (a step-by-step controller check). With the Open API: each AP's live status, model and IP, and **Reboot** (asks first: it disconnects everyone on that AP). |
| **Portal & Ads** | Portal Logo, Portal Tagline; Enable Free Trial and its duration, Enable Sabbath Mode (see [captive-portal.md](captive-portal.md)) | The site's ads plus global ones: status, schedule, order and views. **New Ad** and **Edit** open a popup on the form; **Delete** asks first. |
| **Vouchers** | none | **Voucher Batches**: stock (quantity, generated, unused, redeemed), **New Batch** (creates and generates in one step), **PDF** cards. **Staff Vouchers**: devices used, **New Staff Voucher**, **Enable/Disable**, **Reset Devices**. **Vouchers**: filter by status, search by code, **Block/Unblock**. |
| **Transactions** | none | The site's transactions, newest first, filterable by status. Pending ones can be marked **Paid** (the device is authorized as for a real payment) or **Failed**. |
| **Chat** | none | Guest threads with unread counts. Opening one marks it read and shows a reply box. |

Validation on save:
- The Omada Site ID must be 24 hex characters, and belongs to one Hotspot Site only. Vendors can't change it (in the mobile app it is admin-only), because it decides which site's customers and sales a Hotspot Site gets.
- An AP MAC can't appear twice on a site, or on two sites. MACs are compared ignoring `:`/`-` and case.
- The Vendor User can't already belong to another site.
- At least one pricing package is required.

### Omada buttons on the form

Shown only when the Open API is set up in Hotspot Omada Settings.

| Button | What it does |
| --- | --- |
| Omada → Create on Omada / Re-run Omada Setup | `bandofy.mobile_api.provision_omada_site`. Creates or links the site on the central controller, an open hotspot SSID, the Bandofy external portal and operator access, and fills in the Omada Site ID. Shows a step-by-step report. |
| Omada → Adopt Device | Lists APs waiting for adoption and adopts one into the site. The AP is added to the Access Points table. |
| Omada → Wi-Fi Networks | Lists, renames, creates or deletes the site's SSIDs. |

The same actions are in the mobile app (see [dashboards-and-reports.md](dashboards-and-reports.md)).

## Upgrading

`bench --site <site> migrate` makes the Omada Site ID unique: blank IDs become NULL so many sites can be without one, and if two sites share an ID the newer one is cleared, with a comment and an Error Log entry. Every active site without a valid ID gets a comment asking for it; until it is filled in, the Access Points table keeps matching customers as before.

## Code

| File | Role |
| --- | --- |
| `bandofy/omada_service.py` | Hotspot authorization (operator API), live stats, the site → controller lookup. |
| `bandofy/omada_openapi.py` | Omada Open API client: token, sites, SSIDs, portals, devices. |
| `bandofy/omada_provisioning.py` | The provisioning, adoption and SSID steps. |
| `bandofy/utils.py` | `find_site` (Omada site ID, then AP MAC), `find_site_by_ap_mac`, `normalize_mac`, `site_ap_macs`. |
