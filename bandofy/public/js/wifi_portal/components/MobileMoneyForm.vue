<template>
	<div>
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

		<BaseModal :open="phoneModal" @close="closeModal">
			<template v-if="selected">
				<div class="mm-modal-pkg">
					<div class="mm-modal-pkg-name">{{ selected.package_name }}</div>
					<div class="mm-modal-pkg-price">{{ amount(selected) }} <span class="mm-modal-pkg-currency">{{ portal.currency }}</span></div>
				</div>
			</template>
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
			<div v-if="localError" class="mm-modal-error">{{ localError }}</div>
			<button type="button" class="modal-submit" :disabled="busy" @click="pay">
				{{ busy ? t("msg_sending_request") : t("pay_and_connect_btn", { price: `${amount(selected || {})} ${portal.currency}` }) }}
			</button>
		</BaseModal>
	</div>
</template>

<script setup>
// "Mobile Money" tab: pick a package then enter the paying number in a popup.
import { nextTick, ref } from "vue";
import { call, errorText, resultMessage } from "../api";
import { formatDuration, t } from "../i18n";
import { clearMessage, handleSuccessPayload, showMessage } from "../login";
import { connectArgs, portal } from "../portal";
import BaseModal from "./BaseModal.vue";

const props = defineProps({ packages: { type: Array, required: true } });
const emit = defineEmits(["unavailable"]);

const selected = ref(null);
const phone = ref("");
const busy = ref(false);
const phoneModal = ref(false);
const localError = ref("");
const phoneInput = ref(null);

function amount(pkg) {
	return Number(pkg.price || 0).toLocaleString("en-US");
}

function getSpeed(pkg) {
	const kbps = parseInt(pkg.bandwidth_down_kbps, 10) || 0;
	if (!kbps) return null;
	return kbps >= 1024 ? `${Math.round(kbps / 102.4) / 10} Mbps` : `${kbps} Kbps`;
}

function selectPackage(pkg) {
	if (!portal.online_payment_enabled) {
		emit("unavailable");
		return;
	}
	selected.value = pkg;
	localError.value = "";
	phone.value = "";
	phoneModal.value = true;
	nextTick(() => phoneInput.value && phoneInput.value.focus());
}

function closeModal() {
	if (busy.value) return;
	phoneModal.value = false;
}

function pay() {
	if (busy.value) return;
	if (!phone.value) {
		localError.value = t("msg_please_enter_phone");
		phoneInput.value && phoneInput.value.focus();
		return;
	}
	localError.value = "";
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
				phoneModal.value = false;
				showMessage(payload.message || t("msg_stk_sent_default"), "success");
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
.mm-modal-pkg {
	text-align: center;
	margin-bottom: 16px;
	padding-bottom: 14px;
	padding-right: 24px;
	border-bottom: 1px solid var(--line, rgba(255,255,255,0.07));
}
.mm-modal-pkg-name {
	font-size: 0.88em;
	font-weight: 700;
	color: var(--text-dim, rgba(224,230,237,0.65));
	margin-bottom: 4px;
	text-transform: uppercase;
	letter-spacing: 0.5px;
}
.mm-modal-pkg-price {
	font-size: 1.6em;
	font-weight: 800;
	color: var(--teal, #00c896);
	line-height: 1;
}
.mm-modal-pkg-currency {
	font-size: 0.6em;
	font-weight: 600;
	color: var(--text-dim, rgba(224,230,237,0.55));
}
.mm-modal-error {
	margin-top: 8px;
	font-size: 0.85em;
	color: #f87171;
}
.pkg-card-currency {
	font-size: 0.65em;
	font-weight: 600;
	color: var(--text-dim, rgba(224,230,237,0.55));
}
.pkg-list {
	display: grid;
	grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
	gap: 10px;
	margin-bottom: 16px;
}
.pkg-card {
	display: flex;
	flex-direction: column;
	gap: 8px;
	text-align: left;
	background: var(--surface-2, #1f2a3c);
	border: 1.5px solid var(--line, rgba(255,255,255,0.07));
	border-radius: 10px;
	padding: 14px;
	cursor: pointer;
	transition: border-color 0.15s, background 0.15s;
	color: var(--text, #e0e6ed);
	font-family: inherit;
}
.pkg-card:hover,
.pkg-card.selected {
	border-color: var(--teal, #00c896);
	background: var(--teal-d, rgba(0,200,150,0.12));
}
.pkg-card-header {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 6px;
}
.pkg-card-name {
	font-size: 0.9em;
	font-weight: 700;
	line-height: 1.2;
	flex: 1;
	min-width: 0;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
.pkg-card-type {
	font-size: 0.7em;
	font-weight: 700;
	padding: 2px 6px;
	border-radius: 999px;
	background: var(--teal-d, rgba(0,200,150,0.12));
	color: var(--teal, #00c896);
	flex-shrink: 0;
}
.pkg-card-price {
	font-size: 1.4em;
	font-weight: 800;
	color: var(--text, #e0e6ed);
	line-height: 1;
}
.pkg-card-price small {
	font-size: 0.55em;
	font-weight: 600;
	color: var(--text-dim, rgba(224,230,237,0.55));
}
.pkg-pills {
	display: flex;
	flex-wrap: wrap;
	gap: 4px;
}
.pkg-pill {
	font-size: 0.72em;
	padding: 2px 7px;
	border-radius: 999px;
	background: var(--surface, #1a2332);
	color: var(--text-dim, rgba(224,230,237,0.55));
	border: 1px solid var(--line, rgba(255,255,255,0.07));
}
</style>
