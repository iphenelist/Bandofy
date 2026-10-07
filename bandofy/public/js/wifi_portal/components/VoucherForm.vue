<template>
	<div class="voucher-hero">
		<div class="voucher-input-wrap">
			<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
				<path
					d="M4 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7Z"
					stroke="currentColor"
					stroke-width="1.8"
				/>
				<path d="M2 10h20" stroke="currentColor" stroke-width="1.8" />
			</svg>
			<input
				v-model.trim="code"
				type="text"
				:placeholder="t('voucher_placeholder')"
				@keydown.enter="redeem"
			/>
		</div>
		<button type="button" class="btn-primary" :disabled="busy" @click="redeem">
			{{ busy ? t("msg_processing") : t("connect_now_btn") }}
		</button>
		<button type="button" class="btn-secondary" @click="$emit('find')">
			<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
				<circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="1.8" />
				<path
					d="M21 21l-4.3-4.3"
					stroke="currentColor"
					stroke-width="1.8"
					stroke-linecap="round"
				/>
			</svg>
			<span>{{ t("find_voucher_btn") }}</span>
		</button>
	</div>
</template>

<script setup>
// Voucher redemption -- the hero's primary "Connect Now" action.
import { ref } from "vue";
import { call, errorText, resultMessage } from "../api";
import { t } from "../i18n";
import { clearMessage, handleSuccessPayload, showMessage } from "../login";
import { connectArgs } from "../portal";

defineEmits(["find"]);

const code = ref("");
const busy = ref(false);

function redeem() {
	if (busy.value) return;
	if (!code.value) {
		showMessage(t("msg_please_enter_voucher"), "error");
		return;
	}

	busy.value = true;
	clearMessage();
	call("redeem_voucher", { voucher_code: code.value, ...connectArgs() })
		.then((result) => {
			const payload = resultMessage(result);
			if (payload) handleSuccessPayload(payload);
			else showMessage(errorText(result), "error");
		})
		.catch(() => showMessage(t("msg_network_error"), "error"))
		.finally(() => (busy.value = false));
}
</script>
