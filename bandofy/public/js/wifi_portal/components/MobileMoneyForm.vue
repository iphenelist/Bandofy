<template>
	<div class="mm-form">
		<div class="field-step">{{ t("step_select_package") }}</div>

		<div v-if="packages.length" class="pkg-list">
			<button
				v-for="pkg in packages"
				:key="pkg.idx"
				type="button"
				class="pkg-card"
				:class="{ selected: selected && selected.idx === pkg.idx }"
				@click="selected = pkg"
			>
				<div class="pkg-card-header">
					<span class="pkg-card-name">{{ pkg.package_name }}</span>
					<span class="pkg-card-type">{{ pkg.package_type || 'Unlimited' }}</span>
				</div>
				<div class="pkg-card-price">{{ amount(pkg) }} <small>{{ portal.currency }}</small></div>
				<div class="pkg-pills">
					<span class="pkg-pill">⏱ {{ formatDuration(pkg.duration_minutes) }}</span>
					<span v-if="getSpeed(pkg)" class="pkg-pill">⚡ {{ getSpeed(pkg) }}</span>
					<span v-if="pkg.device_limit > 0" class="pkg-pill">👥 {{ pkg.device_limit === 1 ? '1 device' : pkg.device_limit + ' devices' }}</span>
					<span v-if="pkg.data_limit_mb > 0" class="pkg-pill">📦 {{ pkg.data_limit_mb }} MB</span>
				</div>
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
	const parts = [kind];
	if (kbps) parts.push(kbps >= 1024 ? `${Math.round(kbps / 102.4) / 10} Mbps` : `${kbps} Kbps`);
	if (pkg.device_limit > 0) parts.push(pkg.device_limit === 1 ? "1 device" : `${pkg.device_limit} devices`);
	if (pkg.data_limit_mb > 0) parts.push(`${pkg.data_limit_mb} MB data`);
	return parts.join(" · ");
}

function getSpeed(pkg) {
	const kbps = parseInt(pkg.bandwidth_down_kbps, 10) || 0;
	if (!kbps) return null;
	return kbps >= 1024 ? `${Math.round(kbps / 102.4) / 10} Mbps` : `${kbps} Kbps`;
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

<style scoped>
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
