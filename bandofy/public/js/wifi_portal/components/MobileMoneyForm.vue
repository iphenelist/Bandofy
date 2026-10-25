<template>
	<div class="mm-form">
		<div class="field-step">{{ t("step_select_package") }}</div>

		<div v-if="packages.length" class="pkg-list">
			<button
				v-for="pkg in packages"
				:key="pkg.idx"
				type="button"
				class="pkg-row"
				:class="{ selected: selected && selected.idx === pkg.idx }"
				@click="selected = pkg"
			>
				<span class="pkg-main">
					<span class="pkg-title">
						<span class="pkg-name">{{ pkg.package_name }}</span>
						<span class="pkg-badge">{{ formatDuration(pkg.duration_minutes) }}</span>
					</span>
					<span class="pkg-sub">{{ subtitle(pkg) }}</span>
				</span>
				<span class="pkg-price">
					{{ amount(pkg) }} <small>{{ portal.currency }}</small>
				</span>
			</button>
		</div>
		<div v-else class="empty-state">{{ t("empty_packages") }}</div>

		<template v-if="packages.length">
			<label class="field-step" for="mm-phone">{{ t("step_phone_number") }}</label>
			<div class="phone-pill">
				<input
					id="mm-phone"
					ref="phoneInput"
					v-model.trim="phone"
					type="tel"
					inputmode="tel"
					:placeholder="t('modal_phone_placeholder')"
					@keydown.enter="pay"
				/>
			</div>

			<button type="button" class="btn-primary btn-pay" :disabled="busy" @click="pay">
				{{
					busy
						? t("msg_sending_request")
						: selected
						? t("pay_and_connect_btn", {
								price: `${amount(selected)} ${portal.currency}`,
						  })
						: t("choose_package_first")
				}}
			</button>
		</template>
	</div>
</template>

<script setup>
// "Mobile Money" tab: pick a package, enter the paying number, and send an
// STK push via initiate_payment -- all on the card, no popup.
import { ref } from "vue";
import { call, errorText, resultMessage } from "../api";
import { formatDuration, t } from "../i18n";
import { clearMessage, handleSuccessPayload, showMessage } from "../login";
import { connectArgs, portal } from "../portal";

const props = defineProps({ packages: { type: Array, required: true } });
const emit = defineEmits(["unavailable"]);

const selected = ref(props.packages.length ? props.packages[0] : null);
const phone = ref("");
const busy = ref(false);
const phoneInput = ref(null);

function amount(pkg) {
	return Number(pkg.price || 0).toLocaleString("en-US");
}

function subtitle(pkg) {
	const kind = t(pkg.package_type === "Bundle" ? "group_bundle" : "group_unlimited");
	const kbps = parseInt(pkg.bandwidth_down_kbps, 10) || 0;
	if (!kbps) return kind;
	const speed = kbps >= 1024 ? `${Math.round(kbps / 102.4) / 10} Mbps` : `${kbps} Kbps`;
	return `${kind} · ${speed}`;
}

function pay() {
	if (busy.value) return;
	if (!selected.value) {
		showMessage(t("choose_package_first"), "error");
		return;
	}
	if (!portal.online_payment_enabled) {
		emit("unavailable");
		return;
	}
	if (!phone.value) {
		showMessage(t("msg_please_enter_phone"), "error");
		phoneInput.value && phoneInput.value.focus();
		return;
	}

	busy.value = true;
	clearMessage();
	call("initiate_payment", {
		phone: phone.value,
		package_idx: selected.value.idx,
		...connectArgs(),
	})
		.then((result) => {
			const payload = resultMessage(result);
			if (payload) {
				showMessage(payload.message || t("msg_stk_sent_default"), "success");
				handleSuccessPayload(payload);
			} else {
				showMessage(errorText(result), "error");
			}
		})
		.catch(() => showMessage(t("msg_network_error"), "error"))
		.finally(() => (busy.value = false));
}
</script>
