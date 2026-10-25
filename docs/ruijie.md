# Ruijie controllers

Module: **Bandofy**. Sidebar: **Settings → Hotspot Ruijie Settings**; on each **Hotspot Site**, Controller Type **Ruijie**.

Bandofy supports locally configured Ruijie RG-series wireless controllers (an AC with its APs) next to Omada sites. Payments, vouchers, staff vouchers, the free trial, ads, chat, dashboards and reports work the same on both.

## How it works

A Ruijie AC has no API that Bandofy can call to let a customer online. Its external portal works through RADIUS instead:

1. A phone joins the hotspot SSID. The AC redirects it to `/wifi_login` with the parameters set in its web-auth template: `wlanacname`, `wlanapmac`, `mac`, `wlanuserip`, `wlannasip`, `ssid` and `url`.
2. Bandofy finds the Hotspot Site whose **Ruijie AC Name** equals `wlanacname`. If there is none, the portal says the network isn't registered and shows the AC name it received.
3. When the customer has paid, redeemed a voucher or taken the free trial, Bandofy issues a **one-time login** for that transaction: the username is the transaction ID and the password is random. It is valid until the package's time runs out.
4. The portal page submits that login to the AC's own login server (`web-auth auth-server submit-url`, by default `http://1.1.1.1:8082/login`).
5. The AC sends an Access-Request to **Bandofy's RADIUS server**. It answers Access-Accept with a `Session-Timeout` of the remaining paid time.
6. If the AC sends the client's MAC (`Calling-Station-Id`), it must be the paying device's, so a login seen on someone else's screen can't be used elsewhere.
7. With **Allow MAC Re-login** on, a device that reconnects while its time is still running (the AC's `dot1x-mab` MAC re-login) is accepted without going through the portal again.

## 1. Run the RADIUS server

The RADIUS server is a separate long-running process on the Bandofy server. It needs `pyrad`, which `bench get-app` and `bench setup requirements` install from `pyproject.toml`.

Run it with supervisor, for example `/etc/supervisor/conf.d/bandofy-radius.conf`:

```ini
[program:bandofy-radius]
command=bench --site <site> execute bandofy.radius_server.start
directory=/home/frappe/frappe-bench
user=frappe
autostart=true
autorestart=true
stdout_logfile=/home/frappe/frappe-bench/logs/bandofy-radius.log
redirect_stderr=true
```

Then `sudo supervisorctl reread && sudo supervisorctl update`. On a development bench, add the same command to the `Procfile` instead.

Open **UDP 1812** (authentication) and **UDP 1813** (accounting) on the server's firewall. If the server is behind a cloud firewall or security group, open them there too.

## 2. Hotspot Ruijie Settings (single)

Only System Manager can read or edit it. Changes reach the running RADIUS server within a minute.

| Field | What it is for |
| --- | --- |
| Enabled | While off, the RADIUS server rejects every login. |
| RADIUS Shared Secret | The `key` in `radius-server host` on every AC. Use a long random value. Sites behind mobile-network NAT have changing, shared IPs, so the server admits ACs by this secret rather than by IP. |
| Allow MAC Re-login | Accept the AC's MAC-based re-login for a device whose paid time hasn't run out. On by default. |
| Listen IP, Authentication Port, Accounting Port | Default `0.0.0.0`, `1812`, `1813`. Restart the RADIUS process after changing these. |
| Login Submit URL | Where the portal page submits the one-time login. Must match `web-auth auth-server submit-url` on the AC. Default `http://1.1.1.1:8082/login`. |
| Login Method | `POST` (default) or `GET`. |
| Username Field, Password Field | The form field names the AC's login server reads. Default `username` and `password`. |
| Extra Fields | Optional JSON object of more fields to send, for example `{"userip": "{user_ip}", "usermac": "{user_mac}"}`. |

The Login Submit URL and the fields can use these placeholders: `{username}`, `{password}`, `{user_ip}`, `{user_mac}`, `{ac_name}`, `{nas_ip}`, `{ap_mac}`, `{ssid}`, `{url}` (where the customer was going) and `{success_url}` (the site's success redirect).

## 3. Hotspot Site

Create one Hotspot Site per AC, as for Omada, with:

- **Controller Type**: Ruijie.
- **Ruijie AC Name**: the name the AC sends as `wlanacname`, usually its hostname. Every vendor's AC needs a different name; Bandofy refuses a duplicate.

The Omada Site ID, the Omada menu and the live AP status don't apply to Ruijie sites and are hidden. **Check Connection** on the Access Points tab shows the AC name, whether the RADIUS server is enabled, and when the site's latest login was issued.

## 4. Configure the AC

Replace `<BANDOFY_IP>` with the Bandofy server's public IP, `<BANDOFY_DOMAIN>` with its domain, `<SECRET>` with the RADIUS Shared Secret, and `<WLAN_ID>` with the hotspot WLAN's ID. The commands follow a published RG-series external-portal configuration ([Octopus Wi-Fi: Ruijie](https://octopuswifi.atlassian.net/wiki/spaces/WIKIEN/pages/2583199745/Ruijie)) with only the names and addresses changed. Check them against your AC's RGOS release; the same settings are also in the AC's web interface under Authentication.

Give the AC a unique name, used as the Ruijie AC Name:

```
AC# configure terminal
AC(config)# hostname <AC_NAME>
```

RADIUS server and AAA:

```
AC(config)# radius-server host <BANDOFY_IP> key <SECRET>
AC(config)# aaa new-model
AC(config)# aaa groupserver radius bandofy_radius
AC(config-gs-radius)# server <BANDOFY_IP>
AC(config-gs-radius)# exit
AC(config)# aaa authentication cpweb bandofy group bandofy_radius
AC(config)# aaa accounting network bandofy start-stop group bandofy_radius
AC(config)# aaa authentication dot1x bandofy group bandofy_radius
AC(config)# wr
```

The AC's local login server, which the portal page submits the one-time login to (HTTP only, and exactly this address and port):

```
AC(config)# web-auth auth-server ip 1.1.1.1
AC(config)# web-auth auth-server http
AC(config)# web-auth auth-server submit-url http://1.1.1.1:8082/login
AC(config)# wr
```

The portal template. The `fmt custom` line sets the parameter names Bandofy reads, so keep it exactly as shown:

```
AC(config)# web-auth template cpweb
AC(config.tmplt.cpweb)# ip <BANDOFY_IP>
AC(config.tmplt.cpweb)# url http://<BANDOFY_DOMAIN>/wifi_login
AC(config.tmplt.cpweb)# fmt custom encry none ac-name wlanacname ap-mac wlanapmac mac-format none ap-name wlanapname nas-ip wlannasip ssid ssid url url user-ip wlanuserip user-mac mac mac-format none
AC(config.tmplt.cpweb)# end
AC(config)# wr
```

Turn it on for the hotspot WLAN. `dot1x-mab` enables the MAC re-login:

```
AC(config)# wlansec <WLAN_ID>
AC(config-wlansec)# dot1x-mab
AC(config-wlansec)# dot1x authentication bandofy
AC(config-wlansec)# dot1x accounting bandofy
AC(config-wlansec)# web-auth accounting cpweb bandofy
AC(config-wlansec)# web-auth authentication cpweb bandofy
AC(config-wlansec)# web-auth portal cpweb
AC(config-wlansec)# webauth
AC(config-wlansec)# exit
AC(config)# wr
```

Allow the portal before login: in the AC's web interface, under Authentication → Web Auth → Advanced Settings, enable **Whitelisted URL** and add your Bandofy domain. The customer's payment is an STK push to their phone, so no payment-provider domains are needed.

Session time comes from Bandofy's `Session-Timeout`. For bandwidth, set per-user rate limits on the AC; Bandofy's package bandwidth limits apply to Omada sites only.

## 5. First test

Do this once on a new AC model or firmware:

- [ ] Join the SSID with a phone. The portal opens and shows the site's packages. If it says the network isn't registered, copy the AC Name it shows into the Hotspot Site.
- [ ] Redeem a voucher. The phone should get online within a few seconds.
- [ ] If the AC shows a login error instead: check the RADIUS log (`logs/bandofy-radius.log`) and Error Log. No Access-Request at all means the AC rejected the form: check the field names your firmware's login server expects and set Username Field, Password Field and Extra Fields.
- [ ] Turn Wi-Fi off and on again. With Allow MAC Re-login, the phone reconnects without the portal until its time runs out.
- [ ] Wait for a short package (or a 15-minute free trial) to end. The AC should disconnect the phone.

If the portal page is HTTPS, some phones warn when it submits the login to the AC's HTTP address. If that happens, use an `http://` portal URL in the template.

## Code

| File | Role |
| --- | --- |
| `bandofy/ruijie.py` | One-time logins: `issue_login`, `login_form`, and `check_login`, the RADIUS server's decision. |
| `bandofy/radius_server.py` | The RADIUS server process (`pyrad`). |
| `bandofy/radius_dictionary.txt` | The RADIUS attributes it reads and sends. |
| `bandofy/api.py` | `_authorize_transaction` sends Ruijie sites to `issue_login` and Omada sites to the controller. |
| `bandofy/public/js/wifi_portal/login.js` | `submitLogin` fills in the AC's values and submits the login form. |
