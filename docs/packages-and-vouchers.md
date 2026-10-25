# Packages and vouchers

Module: **Bandofy**. Sidebar: top-level **Hotspot Voucher Batch**; **Packages & Vouchers → Hotspot Package, Hotspot Voucher, Hotspot Staff Voucher**.

All of these doctypes are System Manager only in Desk. None is submittable.

## Hotspot Package

Named by **Package Name** (unique, so it can't be renamed in the mobile app).

| Field | Notes |
| --- | --- |
| Package Type | `Unlimited` or `Bundle`. The portal groups them as *Bila Kikomo* and *Vifurushi vya Data*. |
| Price, Duration (Minutes) | Required. |
| Download / Upload Bandwidth (Kbps) | Defaults 3072 / 1024. 0 means no cap. Applied only on sites with **Enforce Package Bandwidth** on. |

`after_install` creates six default packages (`bandofy/install.py`), sized so a 40 Mbps line serves about 25–35 customers:

| Package | Price (TZS) | Duration | Down / Up Kbps |
| --- | --- | --- | --- |
| Masaa 6 | 300 | 6 h | 2048 / 1024 |
| Masaa 12 | 500 | 12 h | 3072 / 1024 |
| Siku | 1,000 | 1 day | 4096 / 1024 |
| Siku 3 | 1,500 | 3 days | 5120 / 2048 |
| Wiki | 5,000 | 7 days | 6144 / 2048 |
| Mwezi | 15,000 | 30 days | 8192 / 3072 |

## Hotspot Package Item (child of Hotspot Site, "Pricing Packages")

A link to a Hotspot Package. Type, price, duration and bandwidth are fetched from the package. The portal sells exactly the rows in a site's table, in table order.

## Hotspot Voucher Batch

Named `HVB-YY.MM.-#####`. Fields: Site, Package, Quantity, optional code Prefix, Vouchers Expire On, Notes. Status (`Draft` → `Generated` → `Closed`) and Generated Count are read-only.

- **Generate Vouchers** (form button) creates the remaining `Quantity − Generated Count` vouchers and sets the status to Generated.
- **View Vouchers** opens the batch's vouchers.
- Print format **Hotspot Voucher Batch Cards** prints the whole batch as cards. The mobile app downloads it as a PDF.

## Hotspot Voucher

Named by its code: 6 random digits, easy to key in on a phone. Fields: Status (`Unused`, `Used`, `Expired`, `Blocked`), Site, Batch, Package, Price, Duration, Generated On, Expires On, and, once used, Used On, Used By (Client MAC), Redeemed At AP MAC and Transaction.

**Mark Sold** (Vouchers tab, or `set_voucher_status` with `Used`) records a voucher sold outside the captive portal, for example internet sold through the ISP router. It creates the same Paid Hotspot Transaction (`VOUCHER:<code>`, Client MAC `Manual Sale`) a portal redemption does, at the voucher's price, so the sale appears in the Hotspot Sales Report and dashboards. Like any Used voucher, it can't be changed back.

- Before redemption, **Expires On** is the last date the code can be redeemed. When a voucher is redeemed, it is recalculated to *Used On + Duration*.
- Redemption (`bandofy.api.redeem_voucher`) creates a Paid Hotspot Transaction with phone number `Voucher` and reference `VOUCHER:<code>`, then authorizes the device.
- A Used voucher is a record of access already given, so the mobile app can't make it redeemable again.
- Print format **Hotspot Voucher Card** prints a single voucher.

## Hotspot Staff Voucher

Free, reusable access codes for staff. Named by an 8-digit code (a different length from customer vouchers, so they can't collide), or a code you type.

| Field | Notes |
| --- | --- |
| Staff Name, Phone Number, Site | |
| Status | `Active` or `Disabled`. |
| Valid Until | Optional last day. |
| Minutes Per Login | How long each login lasts (default 1440). Must be above zero. |
| Max Devices | Different devices allowed (default 1, 0 = unlimited). |
| Registered Devices (Hotspot Staff Voucher Device) | Devices that have used the code. Delete a row to free a slot. |
| Times Used, Last Used On | Read-only counters. |

Staff enter the code in the portal's voucher box. Each login creates a Paid Hotspot Transaction with phone number `Staff`, reference `STAFF:<code>` and amount 0. Sales figures exclude these (see [dashboards-and-reports.md](dashboards-and-reports.md)). A staff code can't reuse a customer voucher's code.
