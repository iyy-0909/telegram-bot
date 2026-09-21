<template>
  <div class="ai-config-workspace">
    <header class="page-header">
      <div>
        <h1>AI 配置</h1>
        <p>统一管理模型供应商和任务可复用的改写提示词。</p>
      </div>
      <request-button :loading="loading" @click="emit('refresh')">刷新</request-button>
    </header>

    <AiSettingsPanel
      :settings="settings"
      :saving="settingsSaving"
      :loading="settingsLoading"
      :request-actions="{ 'submit': ($event) => (emit('save-settings', $event)) }"
    />
    <AiPromptLibrary
      :prompts="prompts"
      :loading="loading"
      :deleting-id="deletingId"
      :defaulting-id="defaultingId"
      :request-actions="{ 'add': ($event) => (emit('add-prompt')), 'edit': ($event) => (emit('edit-prompt', $event)), 'delete': ($event) => (emit('delete-prompt', $event)), 'set-default': ($event) => (emit('set-default-prompt', $event)) }"

    />
    <AiRewritePreview :default-provider="settings.default_provider" />
  </div>
</template>

<script setup>
import { useRequestEmit } from '../../../frontend-shared/requestActions.mjs'

import AiPromptLibrary from "./AiPromptLibrary.vue"
import AiSettingsPanel from "./AiSettingsPanel.vue"
import AiRewritePreview from "./AiRewritePreview.vue"

const requestProps = defineProps({
  requestActions: { type: Object, default: () => ({}) },
  settings: { type: Object, default: () => ({ providers: {} }) },
  settingsSaving: Boolean,
  settingsLoading: Boolean,
  prompts: { type: Array, default: () => [] },
  loading: Boolean,
  deletingId: { type: Number, default: null },
  defaultingId: { type: Number, default: null },
})

const rawEmit = defineEmits([
  "refresh",
  "save-settings",
  "add-prompt",
  "edit-prompt",
  "delete-prompt",
  "set-default-prompt",
])
const emit = useRequestEmit(rawEmit, requestProps)
</script>

<style scoped>
.ai-config-workspace {
  display: grid;
  min-width: 0;
  gap: 16px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-header h1 {
  margin: 0;
  color: var(--el-text-color-primary);
  font-size: 22px;
  line-height: 1.4;
}

.page-header p {
  margin: 4px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

@media (max-width: 600px) {
  .ai-config-workspace {
    gap: 12px;
  }

  .page-header {
    align-items: stretch;
    flex-direction: column;
  }

  .page-header h1 {
    font-size: 20px;
  }
}
</style>
