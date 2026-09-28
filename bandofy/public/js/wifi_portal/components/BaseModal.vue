<template>
	<div class="modal-overlay" :class="{ show: open }" @click.self="dismiss">
		<div :class="boxClass">
			<button
				v-if="closeButton"
				type="button"
				class="modal-close"
				:aria-label="t('modal_close_label')"
				@click="dismiss"
			>
				&times;
			</button>
			<slot />
		</div>
	</div>
</template>

<script setup>
// Every portal modal: fades in via .show, closes on overlay click, the x
// button and Escape -- unless `dismissable` is off (the success modal,
// which is followed by a redirect).
import { onMounted, onUnmounted } from "vue";
import { t } from "../i18n";

const props = defineProps({
	open: Boolean,
	boxClass: { type: String, default: "lipa-box" },
	closeButton: { type: Boolean, default: true },
	dismissable: { type: Boolean, default: true },
});
const emit = defineEmits(["close"]);

function dismiss() {
	if (props.dismissable) emit("close");
}

function onKeydown(e) {
	if (e.key === "Escape" && props.open) dismiss();
}

onMounted(() => document.addEventListener("keydown", onKeydown));
onUnmounted(() => document.removeEventListener("keydown", onKeydown));
</script>
