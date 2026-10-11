<template>
	<div class="free-trial-card" :class="{ used: !portal.free_trial_available }">
		<div class="free-trial-icon">
			<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
				<path
					d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10Z"
					stroke="currentColor"
					stroke-width="1.8"
				/>
				<path
					d="M12 7v5l3.5 2"
					stroke="currentColor"
					stroke-width="1.8"
					stroke-linecap="round"
					stroke-linejoin="round"
				/>
			</svg>
		</div>
		<div class="free-trial-text">
			<div class="free-trial-title">
				{{ t("free_trial_title", { minutes: portal.free_trial_minutes }) }}
			</div>
			<div class="free-trial-sub">{{ t("free_trial_subtitle") }}</div>
		</div>
		<button
			v-if="portal.free_trial_available"
			type="button"
			class="free-trial-btn"
			:disabled="busy || claimed"
			@click="claim"
		>
			{{
				claimed
					? t("free_trial_used_badge")
					: busy
					? t("msg_processing")
					: t("free_trial_btn")
			}}
		</button>
		<span v-else class="free-trial-used-badge">{{ t("free_trial_used_badge") }}</span>
	</div>
</template>

<script setup>
// One-time free trial. The server is the source of truth for "already
// used" (wifi_login.py); disabling the button after a claim is only
// immediate feedback -- a reload renders it as used anyway.
import { ref } from "vue";
import { call, errorText, resultMessage } from "../api";
import { t } from "../i18n";
import { clearMessage, handleSuccessPayload, showMessage } from "../login";
import { connectArgs, portal } from "../portal";

const busy = ref(false);
const claimed = ref(false);

function claim() {
	busy.value = true;
	clearMessage();
	call("claim_free_trial", connectArgs())
		.then((result) => {
			const payload = resultMessage(result);
			if (payload) {
				claimed.value = true;
				handleSuccessPayload(payload);
			} else {
				showMessage(errorText(result), "error");
			}
		})
		.catch(() => showMessage(t("msg_network_error"), "error"))
		.finally(() => (busy.value = false));
}
</script>
