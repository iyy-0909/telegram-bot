<template>
  <div class="ai-config-workspace">
    <header class="page-header">
      <div>
        <h1>AI 配置</h1>
        <p>统一管理模型供应商和任务可复用的改写提示词。</p>
      </div>
      <el-button :loading="loading" @click="emit('refresh')">刷新</el-button>
    </header>

    <AiSettingsPanel :settings="settings" :saving="settingsSaving" @submit="emit('save-settings', $event)" />
    <AiPromptLibrary
      :prompts="prompts"
      :loading="loading"
      :deleting-id="deletingId"
      :defaulting-id="defaultingId"
      @add="emit('add-prompt')"
      @edit="emit('edit-prompt', $event)"
      @delete="emit('delete-prompt', $event)"
      @set-default="emit('set-default-prompt', $event)"
    />
  </div>
</template>

<script setup>
import AiPromptLibrary from "./AiPromptLibrary.vue"
import AiSettingsPanel from "./AiSettingsPanel.vue"

defineProps({
  settings: { type: Object, default: () => ({ providers: {} }) },
  settingsSaving: Boolean,
  prompts: { type: Array, default: () => [] },
  loading: Boolean,
  deletingId: { type: Number, default: null },
  defaultingId: { type: Number, default: null },
})

const emit = defineEmits([
  "refresh",
  "save-settings",
  "add-prompt",
  "edit-prompt",
  "delete-prompt",
  "set-default-prompt",
])
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
