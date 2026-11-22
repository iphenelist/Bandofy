<template>
	<div class="mm-form">
		<div class="field-step">{{ t("step_select_package") }}</div>

		<div v-if="packages.length" class="pkg-list">
			<button
				v-for="pkg in packages"
				:key="pkg.idx"
				type="button"
				class="pkg-card"
				@click="selectPackage(pkg)"
			>
				<div class="pkg-card-header">
					<span class="pkg-card-name">{{ pkg.package_name }}</span>
					<span class="pkg-card-type">{{ pkg.package_type || 'Unlimited' }}</span>
				</div>
				<div class="pkg-card-price">{{ amount(pkg) }} <span class="pkg-card-currency">{{ portal.currency }}</span></div>
				<div class="pkg-pills">
					<span class="pkg-pill">⏱ {{ formatDuration(pkg.duration_minutes) }}</span>
					<span v-if="getSpeed(pkg)" class="pkg-pill">⚡ {{ getSpeed(pkg) }}</span>
					<span v-if="pkg.device_limit > 0" class="pkg-pill">👥 {{ pkg.device_limit === 1 ? '1 device' : pkg.device_limit + ' devices' }}</span>
					<span v-if="pkg.data_limit_mb > 0" class="pkg-pill">📦 {{ pkg.data_limit_mb }} MB</span>
				</div>
			</button>
		</div>
		<div v-else class="empty-state">{{ t("empty_packages") }}</div>
	</div>

	<BaseModal :open="voucherModal" @close="closeModal">
		<template v-if="selected">
			<div class="mm-modal-pkg">
				<span class="mm-modal-pkg-name">{{ selected.package_name }}</span>
				<span class="mm-modal-pkg-price">{{ amount(selected) }} <span class="mm-modal-pkg-currency">{{ portal.currency }}</span></span>
			</div>
		</template>
		<label class="field-step" for="voucher-code">{{ t("step_voucher_code") }}</label>
		<p class="mm-modal-hint">{{ t("voucher_modal_hint") }}</p>
		<div class="voucher-input-wrap">
			<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
				<path d="M4 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7Z" stroke="currentColor" stroke-width="1.8" />
				<path d="M2 10h20" stroke="currentColor" stroke-width="1.8" />
			</svg>
			<input
				id="voucher-code"
				ref="codeInput"
				v-model.trim="code"
				type="text"
				:placeholder="t('voucher_placeholder')"
				@keydown.enter="redeem"
			/>
		</div>
		<div v-if="localError" class="mm-modal-error">{{ localError }}</div>
		<button type="button" class="modal-submit" :disabled="busy" @click="redeem">
			{{ busy ? t("msg_processing") : t("connect_now_btn") }}
		</button>
		<button type="button" class="btn-secondary" style="margin-top:8px" @click="$emit('find')">
			<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
				<circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="1.8" />
				<path d="M21 21l-4.3-4.3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
			</svg>
			<span>{{ t("find_voucher_btn") }}</span>
		</button>
	</BaseModal>
</template>

<script setup>
// Voucher redemption: select a package then enter the code in a popup.
import { nextTick, ref } from "vue";
import { call, errorText, resultMessage } from "../api";
import { formatDuration, t } from "../i18n";
import { clearMessage, handleSuccessPayload, showMessage } from "../login";
import { connectArgs, portal } from "../portal";
import BaseModal from "./BaseModal.vue";

const props = defineProps({ packages: { type: Array, default: () => [] } });
defineEmits(["find"]);

const selected = ref(null);
const code = ref("");
const busy = ref(false);
const voucherModal = ref(false);
const localError = ref("");
const codeInput = ref(null);

function amount(pkg) {
	return Number(pkg.price || 0).toLocaleString("en-US");
}

function getSpeed(pkg) {
	const kbps = parseInt(pkg.bandwidth_down_kbps, 10) || 0;
	if (!kbps) return null;
	return kbps >= 1024 ? `${Math.round(kbps / 102.4) / 10} Mbps` : `${kbps} Kbps`;
}

function selectPackage(pkg) {
	selected.value = pkg;
	code.value = "";
	localError.value = "";
	voucherModal.value = true;
	nextTick(() => codeInput.value && codeInput.value.focus());
}

function closeModal() {
	if (busy.value) return;
	voucherModal.value = false;
}

function redeem() {
	if (busy.value) return;
	if (!code.value) {
		localError.value = t("msg_please_enter_voucher");
		codeInput.value && codeInput.value.focus();
		return;
	}
	localError.value = "";
	busy.value = true;
	clearMessage();
	call("redeem_voucher", { voucher_code: code.value, ...connectArgs() })
		.then((result) => {
			const payload = resultMessage(result);
			if (payload) {
				voucherModal.value = false;
				handleSuccessPayload(payload);
			} else {
				localError.value = errorText(result);
			}
		})
		.catch(() => { localError.value = t("msg_network_error"); })
		.finally(() => (busy.value = false));
}
</script>

<style scoped>
.mm-modal-hint {
	font-size: 0.82em;
	color: var(--text-dim, rgba(224,230,237,0.55));
	margin: 2px 0 10px;
}
.pkg-card-currency {
	font-size: 0.7em;
	font-weight: 600;
	color: var(--text-dim, rgba(224,230,237,0.55));
}
</style>
