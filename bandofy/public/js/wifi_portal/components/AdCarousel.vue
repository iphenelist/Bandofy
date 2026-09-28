<template>
	<div class="ad-card">
		<div class="ad-slides">
			<div v-for="(ad, i) in ads" :key="ad.name" class="ad-slide" :class="{ active: i === current }">
				<a :href="ad.target_url || '#'" target="_blank" rel="noopener" class="ad-image-wrap ad-link">
					<img class="ad-banner" :src="ad.image" :alt="ad.title" />
				</a>
				<div v-if="ad.marquee_text" class="ad-marquee">
					<div class="ad-marquee-track" :style="{ animationDuration: ad.marquee_duration + 's' }">
						<span class="ad-marquee-item">{{ ad.marquee_text }}</span>
						<span class="ad-marquee-item" aria-hidden="true">{{ ad.marquee_text }}</span>
					</div>
				</div>
			</div>
		</div>
		<div v-if="ads.length > 1" class="ad-dots">
			<span
				v-for="(ad, i) in ads"
				:key="ad.name"
				class="ad-dot"
				:class="{ active: i === current }"
				@click="pick(i)"
			></span>
		</div>
	</div>
</template>

<script setup>
// Rotates through every active ad every 5s. Each ad's impression is logged
// (fire-and-forget) the first time it's shown, not on every loop.
import { onMounted, onUnmounted, ref } from "vue";
import { call } from "../api";
import { deviceArgs } from "../portal";

const props = defineProps({ ads: { type: Array, required: true } });

const current = ref(0);
const logged = new Set();
let timer = null;

function show(idx) {
	current.value = idx;
	const ad = props.ads[idx];
	if (!ad || logged.has(ad.name)) return;
	logged.add(ad.name);
	call("log_ad_view", { ad: ad.name, ...deviceArgs() }).catch(() => {});
}

function startRotation() {
	clearInterval(timer);
	if (props.ads.length < 2) return;
	timer = setInterval(() => show((current.value + 1) % props.ads.length), 5000);
}

function pick(idx) {
	show(idx);
	startRotation();
}

onMounted(() => pick(0));
onUnmounted(() => clearInterval(timer));
</script>
