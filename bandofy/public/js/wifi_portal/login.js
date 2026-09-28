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
	call(method, { transaction_id: transactionId })
		.then(({ data }) => {
			if (!handle(data && data.message)) retry();
		})
		.catch(retry);
}

// Local-RADIUS sites only: once a transaction is Paid, fetch its one-time
// RADIUS credential and send the browser through the EAP's own login
// endpoint so it completes RADIUS auth.
function handleRadius(result) {
	if (!(result && result.login_url)) return false;
	redirectAfterSuccess(result.login_url, t("msg_payment_confirmed_connected"));
	return true;
}

// Omada-Controller-API sites only: once the payment is confirmed Paid and
// authorized on the controller, send the browser to the breakout URL.
function handleOmada(result) {
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
	const method = portal.authorization_method;
	if (payload.redirect_url) {
		// Voucher fast path: already authorized synchronously.
		redirectAfterSuccess(payload.redirect_url, payload.message);
	} else if (method === "Local RADIUS Server" && payload.transaction_id) {
		// Mobile Money is Pending until the webhook/poller confirms it.
		showMessage(t("msg_waiting_payment"), "success");
		poll("get_radius_credentials", payload.transaction_id, handleRadius);
	} else if (method === "Omada Controller API" && payload.transaction_id) {
		showMessage(t("msg_waiting_payment"), "success");
		poll("get_omada_connection_status", payload.transaction_id, handleOmada);
	}
}
