<template>
	<div class="sabbath-card">
		<div class="sabbath-icon">
			<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
				<path d="M3 18h18" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
				<path d="M6.5 18a5.5 5.5 0 0 1 11 0" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
				<path d="M12 4v3M5.2 7.2l2 2M18.8 7.2l-2 2M2.5 13.5h2.3M19.2 13.5h2.3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
				<path d="M8 21h8" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
			</svg>
		</div>
		<div class="sabbath-title">{{ t("sabbath_title") }}</div>
		<blockquote class="sabbath-verse">
			&ldquo;{{ t("sabbath_verse") }}&rdquo;
			<cite>&mdash; {{ t("sabbath_verse_ref") }}</cite>
		</blockquote>
		<p class="sabbath-body">{{ t("sabbath_body") }}</p>
		<p class="sabbath-connected">{{ t("sabbath_connected") }}</p>
		<p class="sabbath-verse-small">
			&ldquo;{{ t("sabbath_verse_2") }}&rdquo; &mdash; {{ t("sabbath_verse_2_ref") }}
		</p>
	</div>
</template>

<script setup>
// Shown in place of every way to buy access while the site's weekly
// Sabbath window (Fri 18:00 - Sat 18:00) is active -- see
// bandofy.utils.is_sabbath_now. The server enforces it too; this card is
// only the friendly explanation.
import { t } from "../i18n";
</script>
