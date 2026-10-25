// Server-rendered context from www/wifi_login.py (build_portal_data),
// injected by wifi_login.html as window.PORTAL.
export const portal = window.PORTAL || {};

// The device identity every guest-facing API call is keyed on, plus the
// Omada site ID or Ruijie AC name the server uses to find the Hotspot Site.
export function deviceArgs() {
	return {
		ap_mac: portal.ap_mac,
		client_mac: portal.client_mac,
		omada_site: portal.omada_site,
		ac_name: portal.ac_name,
	};
}

// deviceArgs plus what the Omada Controller API needs to authorize the
// client (see api.authorize_mac_on_omada).
export function connectArgs() {
	return { ...deviceArgs(), ssid_name: portal.ssid_name, radio_id: portal.radio_id };
}
