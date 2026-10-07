import { t } from "./i18n";

function getCookie(name) {
	const match = document.cookie.match(new RegExp("(^| )" + name + "=([^;]+)"));
	return match ? decodeURIComponent(match[2]) : "";
}

// POST to a whitelisted bandofy.api method. Resolves to { ok, data } for any
// HTTP status (Frappe errors still carry a JSON body); rejects only on a
// network failure.
export function call(method, args) {
	return fetch("/api/method/bandofy.api." + method, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			"X-Frappe-CSRF-Token": getCookie("csrf_token"),
		},
		body: JSON.stringify(args),
	}).then((res) => res.json().then((data) => ({ ok: res.ok, data })));
}

// The server's `message` when the call succeeded, otherwise null.
export function resultMessage(result) {
	return (result.ok && result.data && result.data.message) || null;
}

// Human-readable reason from a failed call: "frappe.exceptions.ValidationError:
// Invalid voucher code." -> "Invalid voucher code.", falling back to the
// message(s) Frappe packs as JSON in _server_messages.
export function errorText(result) {
	const data = result.data || {};
	if (typeof data.exception === "string" && data.exception) {
		return (
			data.exception.replace(/^[\w.]+(Error|Exception):\s*/, "") || t("msg_generic_error")
		);
	}
	try {
		const messages = JSON.parse(data._server_messages || "[]")
			.map((m) => JSON.parse(m).message)
			.filter(Boolean);
		if (messages.length) return messages.join(" ");
	} catch (e) {
		// not a Frappe error payload -- fall through to the generic message
	}
	return t("msg_generic_error");
}
