<template>
	<BaseModal :open="!!pkg" box-class="modal-box" @close="$emit('close')">
		<template v-if="shown">
			<div class="modal-pkg">
				<div class="label">{{ t("modal_pkg_label") }}</div>
				<div class="name">{{ shown.package_name }}</div>
				<div class="meta">
					{{
						t("price_for_duration", {
							price: shown.price_label,
							duration: formatDuration(shown.duration_minutes),
						})
					}}
				</div>
			</div>

			<label class="field-label" for="modal-phone">{{ t("modal_phone_label") }}</label>
			<div class="phone-pill">
				<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
					<path
						d="M6.6 10.8c1.4 2.8 3.8 5.2 6.6 6.6l2.2-2.2c.3-.3.7-.4 1.1-.2 1.2.4 2.5.6 3.8.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C11.4 21 3 12.6 3 2.7c0-.6.4-1 1-1H7.7c.6 0 1 .4 1 1 0 1.3.2 2.6.6 3.8.1.4 0 .8-.2 1.1L6.6 10.8Z"
						stroke="currentColor"
						stroke-width="1.6"
						stroke-linejoin="round"
					/>
				</svg>
				<input
					id="modal-phone"
					ref="phoneInput"
					v-model.trim="phone"
					type="tel"
					inputmode="tel"
					:placeholder="t('modal_phone_placeholder')"
					@keydown.enter="pay"
				/>
			</div>
			<div class="modal-hint">{{ t("modal_hint") }}</div>

			<button type="button" class="modal-submit" :disabled="busy" @click="pay">
				{{ busy ? t("msg_sending_request") : t("modal_submit_btn") }}
			</button>
			<div v-if="msg.text" class="modal-msg show" :class="msg.type">{{ msg.text }}</div>
		</template>
	</BaseModal>
</template>

<script setup>
// STK-push phone-number popup for the chosen package; posts to
// initiate_payment once the customer confirms their number.
import { nextTick, reactive, ref, watch } from "vue";
import { call, errorText, resultMessage } from "../api";
import { formatDuration, t } from "../i18n";
import { handleSuccessPayload } from "../login";
import { connectArgs } from "../portal";
import BaseModal from "./BaseModal.vue";

const props = defineProps({ pkg: { type: Object, default: null } });
const emit = defineEmits(["close"]);

// Keeps the last package on screen while the modal fades out.
const shown = ref(null);
const phone = ref("");
const busy = ref(false);
const msg = reactive({ text: "", type: "" });
const phoneInput = ref(null);

watch(
	() => props.pkg,
	(pkg) => {
		if (!pkg) return;
		shown.value = pkg;
		phone.value = "";
		msg.text = "";
		busy.value = false;
		nextTick(() => setTimeout(() => phoneInput.value && phoneInput.value.focus(), 50));
	}
);

function setMsg(text, type) {
	msg.text = text;
	msg.type = type;
}

function pay() {
	if (busy.value) return;
	if (!phone.value) {
		setMsg(t("msg_please_enter_phone"), "error");
		phoneInput.value && phoneInput.value.focus();
		return;
	}

	busy.value = true;
	msg.text = "";
	call("initiate_payment", {
		phone: phone.value,
		package_idx: shown.value.idx,
		...connectArgs(),
	})
		.then((result) => {
			const payload = resultMessage(result);
			if (payload) {
				setMsg(payload.message || t("msg_stk_sent_default"), "success");
				setTimeout(() => emit("close"), 1800);
				handleSuccessPayload(payload);
			} else {
				setMsg(errorText(result), "error");
			}
		})
		.catch(() => setMsg(t("msg_network_error"), "error"))
		.finally(() => (busy.value = false));
}
</script>
