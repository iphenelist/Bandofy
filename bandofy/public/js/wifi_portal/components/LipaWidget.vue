<template>
	<button type="button" class="fab-lipa" @click="openLipa">
		<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
			<rect x="3" y="3" width="7" height="7" rx="1" stroke="currentColor" stroke-width="1.8" />
			<rect x="14" y="3" width="7" height="7" rx="1" stroke="currentColor" stroke-width="1.8" />
			<rect x="3" y="14" width="7" height="7" rx="1" stroke="currentColor" stroke-width="1.8" />
			<rect x="14.5" y="14.5" width="2.5" height="2.5" fill="currentColor" />
			<rect x="18.5" y="14.5" width="2.5" height="2.5" fill="currentColor" />
			<rect x="14.5" y="18.5" width="2.5" height="2.5" fill="currentColor" />
			<rect x="18.5" y="18.5" width="2.5" height="2.5" fill="currentColor" />
		</svg>
		<span>{{ t("lipa_fab_label") }}</span>
	</button>

	<BaseModal v-if="images.length > 1" :open="picking" @close="picking = false">
		<h3>{{ t("lipa_select_title") }}</h3>
		<p>{{ t("lipa_select_hint") }}</p>
		<div class="lipa-options">
			<button v-for="row in images" :key="row.image" type="button" class="lipa-option" @click="choose(row)">
				{{ row.label }}
			</button>
		</div>
	</BaseModal>

	<BaseModal :open="showing" @close="showing = false">
		<h3>{{ selected.label || "Lipa Namba" }}</h3>
		<p>{{ t("lipa_default_hint") }}</p>
		<img :src="selected.image" alt="Lipa Namba" />
	</BaseModal>
</template>

<script setup>
// Lipa Namba: manual pay-by-QR/till-number card for customers who'd rather
// pay directly than wait on an STK push. With more than one image (one per
// network) a picker is shown first.
import { ref } from "vue";
import { t } from "../i18n";
import { portal } from "../portal";
import BaseModal from "./BaseModal.vue";

const images = portal.lipa_images || [];
const picking = ref(false);
const showing = ref(false);
const selected = ref(portal.lipa_default || {});

function openLipa() {
	if (images.length > 1) picking.value = true;
	else showing.value = true;
}

function choose(row) {
	picking.value = false;
	selected.value = row;
	showing.value = true;
}
</script>
