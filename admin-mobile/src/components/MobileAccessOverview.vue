<template>
  <div class="access-page">
    <section class="access-card">
      <div class="access-heading">
        <div>
          <p class="eyebrow">当前后台账号</p>
          <h2>{{ user?.username || "-" }}</h2>
        </div>
        <el-tag :type="accessStateType(user?.access_state)">
          {{ user?.role === "admin" ? "管理员" : accessStateLabel(user?.access_state) }}
        </el-tag>
      </div>

      <dl class="access-facts">
        <div>
          <dt>账号角色</dt>
          <dd>{{ user?.role === "admin" ? "管理员（全部功能）" : "普通用户" }}</dd>
        </div>
        <div>
          <dt>账号版本</dt>
          <dd>{{ user?.role === "admin" ? "管理员" : user?.plan_tier === "paid" ? "付费版" : "免费版" }}</dd>
        </div>
        <div>
          <dt>使用期限</dt>
          <dd>
            {{ user?.role === "admin"
              ? "长期有效"
              : ["pending", "waiting"].includes(user?.access_state) && !user?.access_expires_at
                ? "待管理员设置"
                : formatAccessTime(user?.access_expires_at) }}
          </dd>
        </div>
      </dl>

      <el-alert
        v-if="user?.role !== 'admin' && user?.plan_tier !== 'paid'"
        type="info"
        show-icon
        :closable="false"
        title="免费版按原文直接克隆，不能配置内容处理和 AI 改写；系统每日发送一次广告。"
        class="plan-alert"
      />

      <el-alert
        v-if="user?.role !== 'admin' && ['pending', 'waiting'].includes(user?.access_state)"
        type="warning"
        show-icon
        :closable="false"
        title="账号已注册，当前使用免费版；如需付费版或调整使用时间，请联系管理员。"
      />
      <el-alert
        v-else-if="user?.role !== 'admin' && user?.access_state === 'expired'"
        type="error"
        show-icon
        :closable="false"
        title="账号使用时间已到期，请联系管理员续期。"
      />
      <el-alert
        v-else-if="user?.role !== 'admin' && user?.access_state === 'disabled'"
        type="error"
        show-icon
        :closable="false"
        title="账号已被禁用，请联系管理员处理。"
      />
      <el-alert
        v-else
        type="success"
        show-icon
        :closable="false"
        title="当前账号可正常使用已开通功能。"
      />
    </section>

    <section class="access-card">
      <div class="section-title">已开通功能</div>
      <div v-if="visibleFeatures.length" class="feature-list">
        <div v-for="item in visibleFeatures" :key="item.key" class="feature-item">
          <el-tag :type="item.desktopOnly ? 'info' : 'success'" effect="plain">
            {{ item.label }}{{ item.desktopOnly ? "（仅桌面端）" : "" }}
          </el-tag>
          <small v-if="featureRequirementLabels(item.key).length">
            依赖：{{ featureRequirementLabels(item.key).join("、") }}
          </small>
        </div>
      </div>
      <el-empty v-else :image-size="64" description="暂未开通业务功能，管理员授权后刷新即可使用。" />
      <p v-if="desktopOnlyFeatures.length" class="desktop-only-note">
        标注“仅桌面端”的功能请在电脑浏览器中使用。
      </p>
    </section>

    <section class="access-card guide-card">
      <div class="section-title">使用说明</div>
      <ol>
        <li>免费版不限任务、账号和 Bot 数量，但只能原文克隆并每日发送广告。</li>
        <li>付费版开放内容处理、AI 改写、频道管理和系统配置，不发送广告。</li>
        <li>版本、期限或状态变更会立即生效，无需重新注册账号。</li>
      </ol>
      <div class="access-actions">
        <request-button type="primary" :loading="refreshing" @click="emit('refresh')">刷新授权</request-button>
        <request-button @click="emit('logout')">退出登录</request-button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { useRequestEmit } from '../../../frontend-shared/requestActions.mjs'

import { computed } from "vue"
import {
  FEATURE_DEFINITIONS,
  accessStateLabel,
  accessStateType,
  featureRequirementLabels,
  formatAccessTime,
  userFeatureKeys,
} from "../utils/access"

const props = defineProps({
  requestActions: { type: Object, default: () => ({}) },
  user: { type: Object, default: null },
  refreshing: { type: Boolean, default: false },
})

const rawEmit = defineEmits(["refresh", "logout"])
const emit = useRequestEmit(rawEmit, props)

const visibleFeatures = computed(() => {
  const enabled = new Set(userFeatureKeys(props.user))
  return FEATURE_DEFINITIONS.filter((item) => enabled.has(item.key))
})
const desktopOnlyFeatures = computed(() => visibleFeatures.value.filter((item) => item.desktopOnly))
</script>

<style scoped>
.access-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px 12px calc(84px + env(safe-area-inset-bottom));
}

.access-card {
  padding: 16px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-bg-color);
}

.access-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.eyebrow {
  margin: 0 0 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.access-heading h2,
.section-title {
  margin: 0;
  color: var(--el-text-color-primary);
  font-size: 18px;
}

.section-title {
  margin-bottom: 12px;
  font-size: 16px;
  font-weight: 700;
}

.access-facts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin: 0 0 14px;
}

.plan-alert { margin-bottom: 12px; }

.access-facts div {
  min-width: 0;
  padding: 10px;
  border-radius: 6px;
  background: var(--el-fill-color-lighter);
}

.access-facts dt {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.access-facts dd {
  margin: 5px 0 0;
  overflow-wrap: anywhere;
  font-weight: 600;
}

.feature-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 5px;
}

.feature-item small {
  color: var(--el-text-color-secondary);
  font-size: 11px;
}

.desktop-only-note {
  margin: 10px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.guide-card ol {
  margin: 0;
  padding-left: 20px;
  color: var(--el-text-color-regular);
  line-height: 1.75;
}

.access-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  margin-top: 16px;
}

.access-actions :deep(.el-button) {
  width: 100%;
  min-height: 44px;
  margin-left: 0;
}

@media (max-width: 360px) {
  .access-facts,
  .access-actions {
    grid-template-columns: 1fr;
  }
}
</style>
