// Page-wide status message, success modal, and the "get this device online"
// flow shared by voucher redemption, the free trial and mobile payments.
import { reactive } from "vue";
import { call } from "./api";
import { t } from "./i18n";
import { portal } from "./portal";

export const status = reactive({ text: "", type: "" });

// Shown only once a connection is actually confirmed -- a voucher redeemed,
// or a payment poll came back with a redirect. An STK push merely being
// sent is not this moment; that stays a pending status message.
export const success = reactive({ open: false, text: "" });

export function showMessage(text, type) {
	status.text = text;
	status.type = type;
}

export function clearMessage() {
	status.text = "";
}

function redirectAfterSuccess(url, message) {
	clearMessage();
	success.text = message || t("msg_connected_default");
	success.open = true;
	setTimeout(() => {
		window.location.href = url;
	}, 1600);
}

// Polls `method` every 3s until `handle(result)` returns true, giving up
// after ~90s.
function poll(method, transactionId, handle, attempt = 0) {
	if (attempt > 30) {
		showMessage(t("msg_payment_confirmed_no_redirect"), "error");
		return;
	}
	const retry = () => setTimeout(() => poll(method, transactionId, handle, attempt + 1), 3000);
	call(method, { transaction_id: transactionId, client_mac: portal.client_mac })
		.then(({ data }) => {
			if (!handle(data && data.message)) retry();
		})
		.catch(retry);
}

// Ruijie sites: the AC logs the device in. Fill the AC's own redirect
// values into the one-time login Bandofy issued (see bandofy.ruijie) and
// submit it to the AC's login server, which checks it with Bandofy's
// RADIUS server and then lets the device online.
const LOGIN_PLACEHOLDERS = {
	"{user_ip}": () => portal.user_ip,
	"{user_mac}": () => portal.client_mac,
	"{ac_name}": () => portal.ac_name,
	"{nas_ip}": () => portal.nas_ip,
	"{ap_mac}": () => portal.ap_mac,
	"{ssid}": () => portal.ssid_name,
	"{url}": () => portal.orig_url,
};

function fillLogin(value) {
	return Object.entries(LOGIN_PLACEHOLDERS).reduce(
		(text, [placeholder, get]) => text.split(placeholder).join(get() || ""),
		String(value)
	);
}

function submitLogin(login, message) {
	clearMessage();
	success.text = message || t("msg_connected_default");
	success.open = true;
	setTimeout(() => {
		const action = fillLogin(login.action);
		const fields = Object.entries(login.fields || {}).map(([name, value]) => [
			name,
			fillLogin(value),
		]);
		if (login.method === "GET") {
			const url = new URL(action);
			fields.forEach(([name, value]) => url.searchParams.set(name, value));
			window.location.href = url.toString();
			return;
		}
		const form = document.createElement("form");
		form.method = "POST";
		form.action = action;
		fields.forEach(([name, value]) => {
			const input = document.createElement("input");
			input.type = "hidden";
			input.name = name;
			input.value = value;
			form.appendChild(input);
		});
		document.body.appendChild(form);
		form.submit();
	}, 1600);
}

// Once the payment is confirmed Paid and the device authorized, send the
// browser to the breakout URL (Omada) or log it in on the AC (Ruijie).
function handleOmada(result) {
	if (result && result.ready && result.login) {
		submitLogin(result.login, t("msg_payment_confirmed_connected"));
		return true;
	}
	if (result && result.ready && result.redirect_url) {
		redirectAfterSuccess(result.redirect_url, t("msg_payment_confirmed_connected"));
		return true;
	}
	if (result && result.failed) {
		showMessage(t("msg_payment_failed"), "error");
		return true;
	}
	return false;
}

export function handleSuccessPayload(payload) {
	if (payload.login) {
		// Ruijie voucher / free trial: login issued synchronously.
		submitLogin(payload.login, payload.message);
	} else if (payload.redirect_url) {
		// Voucher fast path: already authorized synchronously.
		redirectAfterSuccess(payload.redirect_url, payload.message);
	} else if (payload.transaction_id) {
		// Mobile Money is Pending until the webhook/poller confirms it.
		showMessage(t("msg_waiting_payment"), "success");
		poll("get_omada_connection_status", payload.transaction_id, handleOmada);
	}
}
