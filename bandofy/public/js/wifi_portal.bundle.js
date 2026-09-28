// Captive portal app for /wifi_login (www/wifi_login.html). Built by
// `bench build --app bandofy`; served from this Frappe host, so it loads
// before the guest is authorized (no CDN in the walled garden).
import { createApp } from "vue";
import App from "./wifi_portal/App.vue";

createApp(App).mount("#portal");
