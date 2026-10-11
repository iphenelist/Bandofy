<template>
	<div class="ad-full" role="dialog" :aria-label="ad.title">
		<div v-if="poster" class="ad-full-backdrop" :style="{ backgroundImage: `url(${poster})` }"></div>

		<video
			v-if="ad.video && !mediaFailed"
			ref="videoEl"
			class="ad-full-media"
			:src="ad.video"
			:poster="poster"
			autoplay
			muted
			playsinline
			loop
			@playing="start"
			@error="fail"
			@click="toggleSound"
		></video>
		<img
			v-else
			class="ad-full-media"
			:src="poster"
			:alt="ad.title"
			@load="start"
			@error="fail"
		/>

		<div class="ad-full-top">
			<span class="ad-full-badge">{{ t("ad_badge") }}</span>
			<div class="ad-full-timer" :class="{ done: remaining === 0 }">
				<svg viewBox="0 0 36 36">
					<circle class="track" cx="18" cy="18" r="16" />
					<circle
						class="bar"
						cx="18"
						cy="18"
						r="16"
						:style="{ strokeDashoffset: 100.5 * (remaining / SECONDS) }"
					/>
				</svg>
				<span>{{ remaining }}</span>
			</div>
		</div>

		<button
			v-if="ad.video && !mediaFailed"
			type="button"
			class="ad-full-sound"
			@click="toggleSound"
		>
			{{ muted ? t("ad_tap_sound") : t("ad_sound_on") }}
		</button>

		<div class="ad-full-bottom">
			<div class="ad-full-title">{{ ad.title }}</div>
			<div v-if="ad.marquee_text && ad.marquee_text !== ad.title" class="ad-full-desc">
				{{ ad.marquee_text }}
			</div>
			<div class="ad-full-note">
				{{ remaining > 0 ? t("ad_connect_in", { seconds: remaining }) : t("msg_processing") }}
			</div>
		</div>
	</div>
</template>

<script setup>
// Full-screen ad a customer watches before the free trial connects. The
// view is logged as soon as the ad appears and `done` fires SECONDS later;
// api.claim_free_trial refuses a claim without a view at least that old.
// The countdown starts once the media is showing, or after a short grace
// period if it is slow, and a broken ad never blocks the customer.
import { onMounted, onUnmounted, ref } from "vue";
import { call } from "../api";
import { t } from "../i18n";
import { deviceArgs } from "../portal";

const SECONDS = 5;
const GRACE_MS = 2500;

const props = defineProps({ ad: { type: Object, required: true } });
const emit = defineEmits(["done"]);

const poster = props.ad.fullscreen_image || props.ad.image;
const remaining = ref(SECONDS);
const muted = ref(true);
const mediaFailed = ref(false);
const videoEl = ref(null);
let ticker = null;
let grace = null;

function start() {
	if (ticker) return;
	clearTimeout(grace);
	ticker = setInterval(() => {
		remaining.value -= 1;
		if (remaining.value <= 0) {
			clearInterval(ticker);
			emit("done");
		}
	}, 1000);
}

function fail() {
	// a missing video falls back to the image; a missing image just counts down
	if (props.ad.video && !mediaFailed.value) mediaFailed.value = true;
	else start();
}

function toggleSound() {
	if (!videoEl.value) return;
	muted.value = !muted.value;
	videoEl.value.muted = muted.value;
	videoEl.value.play().catch(() => {});
}

onMounted(() => {
	call("log_ad_view", { ad: props.ad.name, ...deviceArgs() }).catch(() => {});
	grace = setTimeout(start, GRACE_MS);
});
onUnmounted(() => {
	clearInterval(ticker);
	clearTimeout(grace);
});
</script>
