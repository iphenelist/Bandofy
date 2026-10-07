<template>
	<div class="section">
		<div class="section-card">
			<div class="section-header">
				<div class="title-group">
					<div class="badge">
						<svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
							<path
								d="M4 6h16M4 12h16M4 18h10"
								stroke="currentColor"
								stroke-width="2"
								stroke-linecap="round"
							/>
						</svg>
					</div>
					<h2>{{ t("choose_plan_heading") }}</h2>
				</div>
				<span class="plans-chip">{{ t("premium_plans_badge") }}</span>
			</div>

			<template v-for="group in groups" :key="group.type">
				<template v-if="group.packages.length">
					<div class="group-title">{{ t(group.titleKey) }}</div>
					<div class="plan-grid">
						<div
							v-for="pkg in group.packages"
							:key="pkg.idx"
							class="package-card"
							@click="$emit('select', pkg)"
						>
							<div class="package-info">
								<div class="package-name">{{ pkg.package_name }}</div>
								<div class="package-meta">
									{{ formatDuration(pkg.duration_minutes) }}
								</div>
								<div class="price-tag">{{ pkg.price_label }}</div>
							</div>
							<button type="button" class="buy-btn">{{ t("buy_now_btn") }}</button>
						</div>
					</div>
				</template>
			</template>

			<div v-if="!packages.length" class="empty-state">{{ t("empty_packages") }}</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { formatDuration, t } from "../i18n";

const props = defineProps({ packages: { type: Array, required: true } });
defineEmits(["select"]);

const groups = computed(() =>
	[
		{ type: "Unlimited", titleKey: "group_unlimited" },
		{ type: "Bundle", titleKey: "group_bundle" },
	].map((g) => ({ ...g, packages: props.packages.filter((p) => p.package_type === g.type) }))
);
</script>
