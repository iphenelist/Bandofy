<template>
	<div class="page">
		<div class="lang-toggle">
			<div class="lang-toggle-inner">
				<button
					v-for="code in ['sw', 'en']"
					:key="code"
					type="button"
					class="lang-btn"
					:class="{ active: lang === code }"
					@click="setLang(code)"
				>
					{{ code.toUpperCase() }}
				</button>
			</div>
		</div>

		<div class="card">
			<div class="hero-icon">
				<img v-if="portal.portal_logo" :src="portal.portal_logo" :alt="portal.site_label || 'Logo'" />
				<svg v-else viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
					<path d="M12 18.5C12.8284 18.5 13.5 17.8284 13.5 17C13.5 16.1716 12.8284 15.5 12 15.5C11.1716 15.5 10.5 16.1716 10.5 17C10.5 17.8284 11.1716 18.5 12 18.5Z" fill="#fff" />
					<path d="M8.5 14C10.5 12 13.5 12 15.5 14" stroke="#fff" stroke-width="1.8" stroke-linecap="round" />
					<path d="M5.5 10.8C9.5 7 14.5 7 18.5 10.8" stroke="#fff" stroke-width="1.8" stroke-linecap="round" />
					<path d="M2.5 7.6C8 2.5 16 2.5 21.5 7.6" stroke="#fff" stroke-width="1.8" stroke-linecap="round" />
				</svg>
			</div>
			<h1>{{ portal.site_label || "Wi-Fi Hotspot" }}</h1>
			<p class="tagline">
				{{ portal.vendor_name ? t("tagline_with_vendor", { vendor: portal.vendor_name }) : t("tagline_default") }}
			</p>
			<p class="premium-tag">{{ portal.portal_tagline || t("premium_tag") }}</p>

			<template v-if="portal.site_found">
				<div class="steps">
					<span>{{ t("step_choose") }}</span><span class="chevron">&#8250;</span>
					<span>{{ t("step_pay") }}</span><span class="chevron">&#8250;</span>
					<span>{{ t("step_connect") }}</span>
				</div>

				<FreeTrialCard v-if="portal.free_trial_enabled" />
				<VoucherForm @find="modal = 'find'" />

				<div class="pay-label">{{ t("pay_label") }}</div>
				<div class="pay-logos">
					<div v-for="p in portal.payment_providers" :key="p.file" class="pay-logo" :title="p.name">
						<img
							v-if="!brokenLogos[p.file]"
							:src="`/assets/bandofy/images/payment_logos/${p.file}.png`"
							:alt="p.name"
							@error="brokenLogos[p.file] = true"
						/>
						<span v-else class="pay-fallback" style="display: flex">{{ p.name }}</span>
					</div>
				</div>
			</template>
		</div>

		<AdCarousel v-if="portal.ads && portal.ads.length" :ads="portal.ads" />

		<div v-if="!portal.site_found" class="no-site">{{ t("no_site") }}</div>
		<template v-else>
			<PackageList :packages="portal.packages || []" @select="selectPackage" />
			<div v-if="status.text" class="msg show" :class="status.type">{{ status.text }}</div>
		</template>

		<div class="footer-note">{{ t("footer_powered") }}</div>
	</div>

	<template v-if="portal.site_found">
		<BuyModal :pkg="buyingPackage" @close="buyingPackage = null" />

		<BaseModal :open="modal === 'find'" @close="modal = null">
			<div class="info-icon">
				<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
					<circle cx="11" cy="11" r="7" stroke="currentColor" stroke-width="1.8" />
					<path d="M21 21l-4.3-4.3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
				</svg>
			</div>
			<h3>{{ t("find_voucher_modal_title") }}</h3>
			<p class="modal-info-text">{{ t("find_voucher_modal_body") }}</p>
			<a
				v-if="portal.support_phone"
				:href="`tel:${portal.support_phone}`"
				class="modal-submit"
				style="display: block; text-decoration: none; margin-top: 16px"
			>
				{{ t("find_voucher_call_btn") }}
			</a>
		</BaseModal>

		<BaseModal :open="modal === 'maintenance'" :close-button="false" @close="modal = null">
			<div class="maintenance-icon">
				<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
					<path d="M12 9v4m0 4h.01M10.29 3.86 1.82 18a1.5 1.5 0 0 0 1.3 2.25h17.76a1.5 1.5 0 0 0 1.3-2.25L13.71 3.86a1.5 1.5 0 0 0-2.42 0Z" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
				</svg>
			</div>
			<h3>{{ t("maintenance_title") }}</h3>
			<p class="msg-body">{{ t("maintenance_body") }}</p>
			<button type="button" class="modal-submit" style="margin-top: 18px" @click="modal = null">
				{{ t("maintenance_close_btn") }}
			</button>
		</BaseModal>

		<BaseModal :open="success.open" :close-button="false" :dismissable="false">
			<div class="success-icon">
				<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
					<path d="M5 13l4 4L19 7" stroke="#fff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
				</svg>
			</div>
			<h3>{{ t("success_title") }}</h3>
			<p class="msg-body">{{ success.text }}</p>
			<p class="redirect-note">{{ t("success_redirect_note") }}</p>
		</BaseModal>

		<ChatWidget />
		<a v-if="portal.support_phone" :href="`tel:${portal.support_phone}`" class="fab-call" :aria-label="t('call_label')">
			<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
				<path d="M6.6 10.8c1.4 2.8 3.8 5.2 6.6 6.6l2.2-2.2c.3-.3.7-.4 1.1-.2 1.2.4 2.5.6 3.8.6.6 0 1 .4 1 1V20c0 .6-.4 1-1 1C11.4 21 3 12.6 3 2.7c0-.6.4-1 1-1H7.7c.6 0 1 .4 1 1 0 1.3.2 2.6.6 3.8.1.4 0 .8-.2 1.1L6.6 10.8Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
			</svg>
		</a>
		<LipaWidget />
	</template>
</template>

<script setup>
import { reactive, ref, watchEffect } from "vue";
import AdCarousel from "./components/AdCarousel.vue";
import BaseModal from "./components/BaseModal.vue";
import BuyModal from "./components/BuyModal.vue";
import ChatWidget from "./components/ChatWidget.vue";
import FreeTrialCard from "./components/FreeTrialCard.vue";
import LipaWidget from "./components/LipaWidget.vue";
import PackageList from "./components/PackageList.vue";
import VoucherForm from "./components/VoucherForm.vue";
import { lang, setLang, t } from "./i18n";
import { status, success } from "./login";
import { portal } from "./portal";

// Which of the simple modals is open: "find" | "maintenance" | null.
const modal = ref(null);
const buyingPackage = ref(null);
const brokenLogos = reactive({});

function selectPackage(pkg) {
	if (portal.online_payment_enabled) buyingPackage.value = pkg;
	else modal.value = "maintenance";
}

watchEffect(() => {
	document.documentElement.setAttribute("lang", lang.value);
	document.title = (portal.site_label || "Wi-Fi") + " - " + t("title_suffix");
});
</script>
