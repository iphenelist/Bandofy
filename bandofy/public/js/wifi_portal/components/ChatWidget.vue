<template>
	<button type="button" class="fab-chat" @click="openChat">
		<span class="chat-unread-dot" :class="{ show: unread }"></span>
		<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
			<path
				d="M4 5h16a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H9l-5 4v-4H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1Z"
				stroke="currentColor"
				stroke-width="1.8"
				stroke-linejoin="round"
			/>
		</svg>
	</button>

	<BaseModal :open="open" box-class="chat-box" @close="open = false">
		<div class="chat-header">
			<div>
				<h3>{{ t("chat_title") }}</h3>
				<p>{{ t("chat_subtitle") }}</p>
			</div>
		</div>
		<div ref="messagesEl" class="chat-messages">
			<div v-if="!messages.length" class="chat-empty">{{ t("chat_empty") }}</div>
			<div
				v-for="(m, i) in messages"
				:key="m.name || i"
				class="chat-bubble"
				:class="m.direction === 'Admin' ? 'admin' : 'guest'"
			>
				{{ m.message }}
			</div>
		</div>
		<div class="chat-input-row">
			<input
				ref="inputEl"
				v-model="draft"
				type="text"
				maxlength="500"
				:placeholder="t('chat_placeholder')"
				@keydown.enter="send"
			/>
			<button
				type="button"
				class="chat-send-btn"
				:disabled="sending"
				:aria-label="t('chat_send')"
				@click="send"
			>
				<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
					<path d="M4 20l16-8L4 4v6l10 2-10 2v6Z" fill="currentColor" />
				</svg>
			</button>
		</div>
	</BaseModal>
</template>

<script setup>
// Chat with the admin: an anonymous thread keyed on this device's MAC
// (guests never log in, so the MAC is the only stable identity a captive
// portal has). Polls from page load, not just while open, so the unread
// dot can light up after the guest closes the panel.
import { nextTick, onMounted, onUnmounted, ref } from "vue";
import { call, resultMessage } from "../api";
import { t } from "../i18n";
import { showMessage } from "../login";
import { deviceArgs } from "../portal";
import BaseModal from "./BaseModal.vue";

const open = ref(false);
const unread = ref(false);
const messages = ref([]);
const draft = ref("");
const sending = ref(false);
const messagesEl = ref(null);
const inputEl = ref(null);
let lastSeen = null;
let timer = null;

function scrollToBottom() {
	nextTick(() => {
		if (messagesEl.value) messagesEl.value.scrollTop = messagesEl.value.scrollHeight;
	});
}

function poll() {
	const args = deviceArgs();
	if (lastSeen) args.after = lastSeen;
	call("get_chat_messages", args)
		.then((result) => {
			const incoming =
				(result.data && result.data.message && result.data.message.messages) || [];
			if (!incoming.length) return;
			for (const m of incoming) {
				messages.value.push(m);
				lastSeen = m.name;
				if (m.direction === "Admin" && !open.value) unread.value = true;
			}
			if (open.value) scrollToBottom();
		})
		.catch(() => {});
}

function openChat() {
	open.value = true;
	unread.value = false;
	scrollToBottom();
	setTimeout(() => inputEl.value && inputEl.value.focus(), 50);
}

function send() {
	const text = draft.value.trim();
	if (!text || sending.value) return;

	draft.value = "";
	sending.value = true;
	call("send_chat_message", { ...deviceArgs(), message: text })
		.then((result) => {
			const payload = resultMessage(result);
			if (payload) {
				messages.value.push({ direction: "Guest", message: text });
				lastSeen = payload.name;
				scrollToBottom();
			} else {
				showMessage(t("msg_chat_send_failed"), "error");
			}
		})
		.catch(() => showMessage(t("msg_chat_send_failed"), "error"))
		.finally(() => {
			sending.value = false;
			inputEl.value && inputEl.value.focus();
		});
}

onMounted(() => {
	poll();
	timer = setInterval(poll, 6000);
});
onUnmounted(() => clearInterval(timer));
</script>
