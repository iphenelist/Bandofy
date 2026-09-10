### FOH-MS

Frappe Omada Hotspot Management System — a Frappe custom app for running paid
Wi-Fi hotspots on TP-Link Omada-managed access points, or standalone TP-Link
EAPs, without needing a MikroTik router. It covers the customer-facing
captive portal, mobile-money payment collection, voucher sales, ad
monetization, and vendor/admin reporting, all in one app.

### Features

**Customer captive portal** (`/wifi_login`)

- Per-site branding: site name, vendor, and (optionally) a support phone
  number the customer can tap to copy if they run into trouble.
- Fully localized in Swahili, white background with green accents.
- Pricing packages pulled live from the site's own package list (no code
  changes needed to add/edit/remove a plan) and grouped into **Bila Kikomo**
  (Unlimited) and **Vifurushi vya Data** (Bundle) sections.
- "Nunua Sasa" opens a popup to confirm the package and collect the
  customer's number before triggering an STK push — payment is never
  charged to whatever number happened to be typed elsewhere on the page.
- A floating **Lipa Namba** button opens the site's manual pay-by-QR/
  till-number card, for customers who'd rather pay directly than wait on
  an STK push.
- A success popup confirms once a payment or voucher redemption is actually
  verified and the device is being connected — not just when a payment
  request was sent.
- A rotating ad carousel (auto-advancing, with tap-to-jump dots) displays
  every active `Hotspot Ad` for the site, each with a logo sized to fit
  consistently and a scrolling marquee caption (short description + phone
  number).
- Recognized mobile money networks (Mixx by Yas, Airtel Money, HaloPesa,
  M-Pesa — see `public/images/payment_logos/`) are shown as trust badges.
- A voucher redemption section for prepaid voucher codes, alongside the
  paid packages.

**Two authorization backends**, auto-selected per `Hotspot Site`:

- **Omada Controller API** — authorizes the client directly against a TP-Link
  Omada SDN Controller's hotspot REST API (`omada_service.py`).
- **Local RADIUS Server** — a built-in RADIUS server (`radius_server.py`)
  for standalone EAPs with no Omada Controller, driven by
  `Hotspot Radius Settings`.

**Payments**

- Mobile Money STK push via a configurable gateway (`Hotspot Payment
  Settings`), with webhook callback + signature verification
  (`api.payment_callback`) and a 5-minute cron
  (`api.sync_pending_payments`) that reconciles any transaction the
  webhook missed.
- While the gateway is disabled/unconfigured, payments fall back to a
  logging-only stub so the portal stays usable in development.

**Vouchers**

- `Hotspot Voucher Batch` bulk-generates single-use `Hotspot Voucher` codes
  for a site and package, redeemable from the captive portal without any
  payment step.
- A printable voucher card format (`Hotspot Voucher Card`) for handing out
  physical vouchers.

**Ads**

- `Hotspot Ad` supports per-site or global ads, scheduled by date range,
  with impression tracking in `Hotspot Ad View Log`.

**Dashboards & reporting**

- `/vendor-dashboard` — a portal for vendors (non-System-Manager users) to
  see their own site's activity without any access to the Desk backend.
- **Network Dashboard** (Desk page, System Manager only) — an overview
  across all sites.
- **Hotspot Sales Report** — paid transactions by date range and site.

**Access control**

- Vendors are blocked from the Desk backend entirely
  (`api.restrict_desk_access`) and redirected to their own portal.

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch main
bench install-app foh_ms
```

### Configuration

- **Hotspot Site** — one record per access point: vendor info, support
  phone number, `ap_mac`, authorization method, controller/RADIUS
  credentials, and its `Pricing Packages` table (`Hotspot Package Item`).
- **Hotspot Payment Settings** (single) — mobile money gateway credentials
  and webhook secret.
- **Hotspot Radius Settings** (single) — enables/configures the built-in
  local RADIUS server for standalone-EAP sites.
- **Payment network logos** — drop the real brand images into
  `foh_ms/public/images/payment_logos/` as `mixx_by_yas.png`,
  `airtel_money.png`, `halopesa.png`, and `mpesa.png`; a text badge is
  shown as a fallback for any file that's missing.
- **Lipa Namba card** — drop the site's manual pay QR/till-number image at
  `foh_ms/public/images/lipanamba/lipa_namba.jpeg`.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/foh_ms
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade
### CI

This app can use GitHub Actions for CI. The following workflows are configured:

- CI: Installs this app and runs unit tests on every push to `develop` branch.
- Linters: Runs [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and [pip-audit](https://pypi.org/project/pip-audit/) on every pull request.


### License

mit
