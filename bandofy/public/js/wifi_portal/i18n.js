// Every static UI string of the captive portal, in both languages. Data
// coming from the database (site/vendor/package names, ad copy) is shown
// as-is and is not part of this dictionary.
import { ref } from "vue";

const MESSAGES = {
	sw: {
		title_suffix: "Ungana Sasa",
		tagline_default: "Ungana na intaneti kwa sekunde chache",
		tagline_with_vendor: "Huduma inatolewa na {vendor}",
		premium_tag: "Ufikiaji wa Premium wa WiFi",
		step_choose: "Chagua",
		step_pay: "Lipa",
		step_connect: "Unganisha",
		voucher_placeholder: "weka vocha hapa",
		connect_now_btn: "Unganisha Sasa",
		find_voucher_btn: "Tafuta Voucher Yangu",
		pay_label: "Tunakubali malipo kupitia",
		choose_plan_heading: "Chagua Kifurushi",
		premium_plans_badge: "Vifurushi vya Premium",
		group_unlimited: "Bila Kikomo",
		group_bundle: "Vifurushi vya Data",
		buy_now_btn: "Nunua Sasa",
		empty_packages: "Hakuna vifurushi kwa sasa. Tafadhali wasiliana na msimamizi wa mtandao.",
		no_site:
			"Hatukuweza kutambua kifaa hiki cha mtandao. Tafadhali unganisha tena kwenye Wi-Fi na ujaribu tena.",
		footer_powered: "Inaendeshwa na Bandofy",
		modal_pkg_label: "Kifurushi Ulichochagua",
		modal_phone_label: "Nambari ya Simu ya Malipo",
		modal_phone_placeholder: "mfano 0745 123 456",
		modal_hint: "Utapokea ujumbe wa STK Push kwenye nambari hii ili uthibitishe malipo.",
		modal_submit_btn: "Lipa Sasa",
		modal_close_label: "Funga",
		find_voucher_modal_title: "Tafuta Voucher Yangu",
		find_voucher_modal_body:
			"Angalia ujumbe wa SMS ulioupokea baada ya kulipa, au kadi yako ya voucher, kwa nambari yako ya siri. Kama huwezi kuipata, piga simu kwa msaada.",
		find_voucher_call_btn: "Piga Simu kwa Msaada",
		call_label: "Piga Simu kwa Msaada",
		lipa_select_title: "Chagua Njia ya Lipa",
		lipa_select_hint: "Chagua mtandao unaotaka kulipia ili uone namba/QR yake.",
		lipa_default_hint:
			"Tumia namba hii au scan QR kulipa moja kwa moja kupitia mtandao wowote au benki.",
		lipa_fab_label: "Lipa Namba",
		maintenance_title: "Mfumo wa kulipa kwa pesa upo katika matengenezo.",
		maintenance_body: "Tumia Lipa Namba au nambari ya Voucher kuunganishwa kwa sasa.",
		maintenance_close_btn: "Nimeelewa",
		success_title: "Umefanikiwa!",
		success_redirect_note: "Unaelekezwa kwenye intaneti...",
		msg_please_enter_voucher: "Tafadhali ingiza nambari yako ya voucher.",
		msg_generic_error: "Hitilafu imetokea. Tafadhali jaribu tena.",
		msg_network_error:
			"Hitilafu ya mtandao. Tafadhali angalia muunganisho wako na ujaribu tena.",
		msg_waiting_payment:
			"Tunasubiri uthibitisho wa malipo yako... Tafadhali kamilisha kwenye simu yako.",
		msg_payment_confirmed_connected: "Malipo yamethibitishwa. Umeunganishwa kwenye Wi-Fi!",
		msg_connected_default: "Umeunganishwa kwenye Wi-Fi!",
		msg_payment_confirmed_no_redirect:
			"Malipo yamethibitishwa, lakini hatukuweza kukuunganisha moja kwa moja. Tafadhali unganisha tena kwenye mtandao wa Wi-Fi.",
		msg_payment_failed: "Malipo hayakukamilika. Tafadhali jaribu tena.",
		msg_please_enter_phone: "Tafadhali ingiza nambari yako ya simu.",
		msg_sending_request: "Inatuma ombi...",
		msg_processing: "Inachakata...",
		msg_stk_sent_default: "Ombi la STK limetumwa. Angalia simu yako.",
		unit_day: "Siku",
		unit_hour: "Saa",
		unit_minute: "Dakika",
		price_for_duration: "{price} kwa {duration}",
		chat_title: "Chat na Msimamizi",
		chat_subtitle: "Uliza chochote, tutakujibu hapa hapa",
		chat_empty: "Bado hakuna ujumbe. Anza mazungumzo!",
		chat_placeholder: "Andika ujumbe wako...",
		chat_send: "Tuma",
		msg_chat_send_failed: "Imeshindikana kutuma ujumbe. Tafadhali jaribu tena.",
		free_trial_title: "Jaribu Bure - Dakika {minutes}",
		free_trial_subtitle: "Unganisha bila malipo, mara moja kwa kila kifaa",
		free_trial_btn: "Anza Bure",
		free_trial_used_badge: "Imekwisha Tumika",
		sabbath_title: "Sabato Njema 🕊️",
		sabbath_verse: "Ikumbuke siku ya Sabato, uitakase.",
		sabbath_verse_ref: "Kutoka 20:8",
		sabbath_body:
			"Leo ni siku ya pumziko takatifu. Kuanzia Ijumaa saa 12 jioni hadi Jumamosi saa 12 jioni hatupokei malipo wala vocha. Huduma zitarejea Jumamosi saa 12 jioni.",
		sabbath_connected:
			"Kama tayari umeunganishwa, endelea kufurahia intaneti hadi muda wako uishe. Mungu akubariki!",
		sabbath_verse_2:
			"Sabato ilifanyika kwa ajili ya mwanadamu, si mwanadamu kwa ajili ya Sabato.",
		sabbath_verse_2_ref: "Marko 2:27",
	},
	en: {
		title_suffix: "Connect Now",
		tagline_default: "Get online in seconds",
		tagline_with_vendor: "Service provided by {vendor}",
		premium_tag: "Premium WiFi Access",
		step_choose: "Choose",
		step_pay: "Pay",
		step_connect: "Connect",
		voucher_placeholder: "enter voucher here",
		connect_now_btn: "Connect Now",
		find_voucher_btn: "Find My Voucher",
		pay_label: "We accept payment via",
		choose_plan_heading: "Choose a Plan",
		premium_plans_badge: "Premium Plans",
		group_unlimited: "Unlimited",
		group_bundle: "Data Bundles",
		buy_now_btn: "Buy Now",
		empty_packages: "No plans available right now. Please contact the network admin.",
		no_site:
			"We couldn't identify this network device. Please reconnect to the Wi-Fi and try again.",
		footer_powered: "Powered by Bandofy",
		modal_pkg_label: "Selected Plan",
		modal_phone_label: "Payment Phone Number",
		modal_phone_placeholder: "e.g. 0745 123 456",
		modal_hint: "You'll receive an STK Push prompt on this number to confirm payment.",
		modal_submit_btn: "Pay Now",
		modal_close_label: "Close",
		find_voucher_modal_title: "Find My Voucher",
		find_voucher_modal_body:
			"Check the SMS you received after paying, or your physical voucher card, for your code. If you can't find it, call for help.",
		find_voucher_call_btn: "Call for Help",
		call_label: "Call for Help",
		lipa_select_title: "Choose Payment Method",
		lipa_select_hint: "Choose the network you want to pay via to see its number/QR.",
		lipa_default_hint:
			"Use this number or scan the QR to pay directly via any network or bank.",
		lipa_fab_label: "Pay by Number",
		maintenance_title: "The mobile payment system is under maintenance.",
		maintenance_body: "Use Pay by Number or a Voucher code to connect for now.",
		maintenance_close_btn: "Got it",
		success_title: "Success!",
		success_redirect_note: "Redirecting you to the internet...",
		msg_please_enter_voucher: "Please enter your voucher code.",
		msg_generic_error: "Something went wrong. Please try again.",
		msg_network_error: "Network error. Please check your connection and try again.",
		msg_waiting_payment:
			"Waiting for your payment confirmation... Please complete it on your phone.",
		msg_payment_confirmed_connected: "Payment confirmed. You're connected to Wi-Fi!",
		msg_connected_default: "You're connected to Wi-Fi!",
		msg_payment_confirmed_no_redirect:
			"Payment confirmed, but we couldn't connect you automatically. Please reconnect to the Wi-Fi network.",
		msg_payment_failed: "Payment did not complete. Please try again.",
		msg_please_enter_phone: "Please enter your phone number.",
		msg_sending_request: "Sending request...",
		msg_processing: "Processing...",
		msg_stk_sent_default: "STK request sent. Check your phone.",
		unit_day: "Day",
		unit_hour: "Hour",
		unit_minute: "Minute",
		price_for_duration: "{price} for {duration}",
		chat_title: "Chat with Admin",
		chat_subtitle: "Ask us anything, we'll reply right here",
		chat_empty: "No messages yet. Start the conversation!",
		chat_placeholder: "Type your message...",
		chat_send: "Send",
		msg_chat_send_failed: "Failed to send message. Please try again.",
		free_trial_title: "Free Trial - {minutes} Minutes",
		free_trial_subtitle: "Connect for free, once per device",
		free_trial_btn: "Start Free",
		free_trial_used_badge: "Already Used",
		sabbath_title: "Happy Sabbath 🕊️",
		sabbath_verse: "Remember the Sabbath day, to keep it holy.",
		sabbath_verse_ref: "Exodus 20:8",
		sabbath_body:
			"Today is a holy day of rest. From Friday 18:00 until Saturday 18:00 we are not accepting payments or vouchers. Service resumes Saturday at 18:00.",
		sabbath_connected:
			"If you are already connected, keep enjoying the internet until your time ends. God bless you!",
		sabbath_verse_2: "The Sabbath was made for man, not man for the Sabbath.",
		sabbath_verse_2_ref: "Mark 2:27",
	},
};

function storedLang() {
	try {
		const stored = localStorage.getItem("foh_lang");
		if (stored === "en" || stored === "sw") return stored;
	} catch (e) {
		// localStorage blocked (private mode) -- use the default language
	}
	return "sw";
}

export const lang = ref(storedLang());

export function setLang(value) {
	if (value !== "en" && value !== "sw") return;
	lang.value = value;
	try {
		localStorage.setItem("foh_lang", value);
	} catch (e) {
		// localStorage blocked (private mode) -- the choice just isn't remembered
	}
}

// t("free_trial_title", { minutes: 15 }) fills "{minutes}" placeholders.
// Reads lang.value, so any template calling t() re-renders on a switch.
export function t(key, params) {
	let text = (MESSAGES[lang.value] && MESSAGES[lang.value][key]) || MESSAGES.sw[key] || key;
	for (const name in params || {}) {
		text = text.replace("{" + name + "}", params[name]);
	}
	return text;
}

export function formatDuration(minutes) {
	minutes = parseInt(minutes, 10) || 0;
	let n, unitKey;
	if (minutes && minutes % 1440 === 0) {
		n = minutes / 1440;
		unitKey = "unit_day";
	} else if (minutes && minutes % 60 === 0) {
		n = minutes / 60;
		unitKey = "unit_hour";
	} else {
		n = minutes;
		unitKey = "unit_minute";
	}

	const label = t(unitKey);
	// English: number first, unit after, pluralized ("6 Hours").
	if (lang.value === "en") return n + " " + label + (n === 1 ? "" : "s");
	// Swahili: unit first, number after, no plural form ("Saa 6").
	return label + " " + n;
}
