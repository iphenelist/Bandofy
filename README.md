### Bandofy

Paid Wi-Fi hotspots on TP-Link Omada access points and Ruijie wireless controllers, without a MikroTik router. Bandofy is a Frappe v16 app that runs the customer captive portal, mobile money payments (Abliner), vouchers, ads and guest chat, and gives vendors and admins dashboards, a sales report and a mobile app API.

Requires Frappe `>=16.0.0,<17.0.0` and Python 3.14. It has no other app dependencies; Ruijie sites also use `pyrad`, installed with the app.

### Documentation

| Page | Covers |
| --- | --- |
| [Sites and the Omada Controller](docs/sites-and-omada.md) | Setting up a site (by hand or automatically), Hotspot Site, Omada Site ID, Hotspot Omada Settings, adoption and SSIDs |
| [Packages and vouchers](docs/packages-and-vouchers.md) | Hotspot Package, Pricing Packages, Voucher Batches, Vouchers, Staff Vouchers, print formats |
| [Payments](docs/payments.md) | Hotspot Transaction, Hotspot Payment Settings, the Abliner STK push, webhook and fallback poll |
| [Ruijie controllers](docs/ruijie.md) | Ruijie sites: one-time RADIUS logins, Bandofy's RADIUS server, Hotspot Ruijie Settings, AC configuration and first test |
| [Captive portal, ads and chat](docs/captive-portal.md) | `/wifi_login`, free trial, Sabbath mode, Hotspot Ad, Ad View Log, Chat Message |
| [Dashboards, reports and the mobile app](docs/dashboards-and-reports.md) | Vendor and admin access, `/vendor-dashboard`, Network Dashboard, Hotspot Sales Report, mobile API, realtime alerts |

In the v16 desk, Bandofy has its own tile on the apps screen and a **Bandofy** sidebar: Hotspot Site, Hotspot Transaction, Hotspot Voucher Batch and Network Dashboard first, then Packages & Vouchers, Ads & Chat, Reports and Settings. Each **Hotspot Site** form brings everything about that site together in tabs: details, dashboard, packages and payments, access points and Omada, portal and ads, vouchers, transactions and chat.

### Installation

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench --site <site> install-app bandofy
bench build --app bandofy
```

Installing creates six default packages (Masaa 6 to Mwezi).

### Setting up

1. **Hotspot Omada Settings**: set the Controller URL and the hotspot operator's name and password (create the operator in the controller's Hotspot Manager first). Then click **Test Connection**.
2. **Hotspot Payment Settings**: add the Abliner API key (`tsl_live_…`) and webhook secret (`whsec_…`). Register the webhook URL shown on the form with Abliner, then tick **Enabled**.
3. **Omada Controller**, for each location: create the site, an open SSID, and an External Portal Server portal pointing at `https://<your site>/wifi_login`, and give the operator access to the site.
4. **Hotspot Site**: one per location. Add the vendor's Website User, the pricing packages and the site's 24-character **Omada Site ID**.
5. Optional: the site's Lipa Namba image, portal logo and tagline, and ads.

To have Bandofy do step 3 for you (useful when onboarding many vendors), fill in **Advanced: Open API** in Hotspot Omada Settings and use **Omada → Create on Omada** on each Hotspot Site. The Open API also enables AP adoption, live AP status and reboot, and package bandwidth limits. See [Sites and the Omada Controller](docs/sites-and-omada.md).

For a Ruijie controller instead of Omada, set the site's Controller Type to Ruijie and follow [Ruijie controllers](docs/ruijie.md): it replaces step 3 and the Omada fields in step 4.

Payment network badges are read from `bandofy/public/images/payment_logos/` (`mixx_by_yas.png`, `airtel_money.png`, `halopesa.png`). A text badge replaces any file that is missing.

### Upgrading from v1

The v2 patches (`bandofy/patches.txt`) run on `bench --site <site> migrate`. They:

- save a private backup file of v1 data (`bandofy_v1_backup_*.json`);
- move the controller details from each site into Hotspot Omada Settings;
- merge `ap_mac` and additional devices into one Access Points table;
- create Hotspot Packages for free-text package names;
- switch the gateway to Abliner.

A site that used a different controller gets a comment and an Error Log entry. Its customers aren't authorized until it is moved to the central controller.

### Development

This app uses `pre-commit` for formatting and linting (ruff, prettier, eslint):

```bash
cd apps/bandofy
pre-commit install
```

All database access uses `frappe.qb` (query builder); please don't add raw `frappe.db.sql`.

GitHub Actions run these workflows:

| Workflow | Runs |
| --- | --- |
| CI (`ci.yml`) | Installs the app on a fresh site and runs the tests. |
| Linters (`linter.yml`) | [Frappe Semgrep Rules](https://github.com/frappe/semgrep-rules) and `pip-audit`. |
| Pre-commit (`pre-commit.yml`) | The pre-commit hooks above, on every pull request. |
| Semantic Commits (`semantic-commits.yml`) | Checks that every commit message in a pull request follows [Conventional Commits](https://www.conventionalcommits.org/), e.g. `fix: …`, `feat: …`, `refactor: …`. |

### License

MIT
