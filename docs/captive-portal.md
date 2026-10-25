# Captive portal, ads and chat

Module: **Bandofy**. Sidebar: **Ads & Chat → Hotspot Ad, Hotspot Ad View Log, Hotspot Chat Message**.

## The portal page: `/wifi_login`

`bandofy/www/wifi_login.py` renders the page, and a Vue app (`bandofy/public/js/wifi_portal/`, bundle `wifi_portal.bundle.js`) runs it. Omada's External Portal redirects customers here with these query parameters, read in either spelling:

| Parameter | Also accepted as |
| --- | --- |
| `apMac` | `ap`, `ap_mac` |
| `clientMac` | `client_mac` |
| `ssidName` | `ssid` |
| `radioId` | `radio_id` |
| `origUrl` | `orig_url` |
| `site` (Omada site ID) | none |

The site is found from the `site` parameter Omada adds to the redirect (the Hotspot Site's Omada Site ID), or else from the AP MAC, using any active row of a site's Access Points table, ignoring `:`/`-` and case. Every guest API call sends both, as `omada_site` and `ap_mac`. The page shows:

- the site's packages, grouped into Unlimited and Bundle; **Nunua Sasa** asks for the paying number and starts the STK push (see [payments.md](payments.md));
- a voucher box for customer and staff codes;
- **Lipa Namba**: the site's QR or till-number image for manual payment;
- the free-trial card, when enabled;
- an ad carousel, and a chat widget.

The page is in Swahili and English (`i18n.js`). On sites with Sabbath Mode, sales stop from Friday 18:00 to Saturday 18:00 and the page says so.

A site's vendor, or an admin, can preview unsaved branding with `?preview=1&preview_tagline=…&preview_logo=…`. The mobile app's Customize Portal screen uses this. Nothing is written to the database.

The older template is kept at `/wifi_login_legacy`.

## Free trial

`bandofy.api.claim_free_trial` (guest) connects a new device for the site's Free Trial Duration. Each device gets it once per site; the Free Trial transaction is the record of that. When the site has ads marked **Show Before Free Internet**, the device must have logged a view of one of them at least 5 seconds earlier, within the last 15 minutes.

## Hotspot Ad

Named by hash. System Manager only in Desk; vendors manage their own site's ads in the mobile app.

| Field | Notes |
| --- | --- |
| Ad Title, Is Active, Display Order | |
| Site | Blank shows the ad on every site. Only an admin can create a global ad. |
| Banner Image | 1200 × 240 px (5:1), under 150 KB. Required. |
| Target URL, Short Description, Contact Phone | Description and phone scroll beneath the banner; without them the title scrolls. |
| Show Before Free Internet, Full-Screen Image (1080 × 1920), Video (MP4, 720 × 1280) | The full-screen ad shown before a free trial. |
| Start Date, End Date | Schedule. |
| Views Count | Read-only. |

## Hotspot Ad View Log

One row per impression: Ad, Site, AP MAC, Client MAC, Viewed On. `bandofy.api.log_ad_view` (guest) writes it and increases the ad's Views Count.

## Hotspot Chat Message

Named by hash. Guests are anonymous, so a thread is identified by **Site + Client MAC**.

| Field | Notes |
| --- | --- |
| Direction | `Guest` or `Admin`. |
| Read | Set once an admin or vendor has seen a Guest message. |
| Message | |

- Guests send messages with `bandofy.api.send_chat_message` and poll with `get_chat_messages` (both guest).
- In Desk, opening a message marks it read, and **Actions → Reply** sends an Admin reply.
- In the mobile app, `get_chat_threads`, `get_chat_thread` (which marks the thread read) and `send_chat_reply` do the same, scoped to the vendor's site.
- A new Guest message pushes a `foh_new_chat_message` realtime alert.
