# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

# Pre-Vue captive portal, kept at /wifi_login_legacy as a fallback while the
# Vue version of /wifi_login is verified on real Omada hardware. Delete this
# file and wifi_login_legacy.html once that's done.

from bandofy.www.wifi_login import get_context  # noqa: F401

no_cache = 1
