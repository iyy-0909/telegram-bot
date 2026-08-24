<template>
  <el-card class="provider-card" shadow="never">
    <template #header>
      <div class="card-header">
        <div>
          <div class="card-title">模型供应商</div>
          <div class="card-subtitle">配置任务可调用的模型密钥与默认模型名称。</div>
        </div>
        <el-button type="primary" :loading="saving" @click="save">
          保存模型配置
        </el-button>
      </div>
    </template>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="任务中单独填写的模型名称优先；未填写时使用这里的默认模型。保存后不会回显 API Key 明文。"
    />

    <div class="provider-grid">
      <section v-for="provider in providerList" :key="provider.key" class="provider-section">
        <div class="provider-heading">
          <strong>{{ provider.title }}</strong>
          <el-tag :type="providerConfigured(provider.key) ? 'success' : 'info'">
            {{ providerConfigured(provider.key) ? "已配置密钥" : "未配置密钥" }}
          </el-tag>
        </div>

        <el-form label-position="top">
          <el-form-item label="API Key">
            <el-input
              v-model="localForm[`${provider.key}_api_key`]"
              type="password"
              show-password
              :placeholder="providerConfigured(provider.key) ? '留空则保持当前密钥' : `请输入 ${provider.title} API Key`"
              autocomplete="new-password"
            />
          </el-form-item>
          <el-form-item label="默认模型">
            <el-input
              v-model="localForm[`${provider.key}_model`]"
              :placeholder="provider.defaultModel"
            />
          </el-form-item>
          <el-popconfirm
            title="确定清除这个供应商已保存的密钥吗？相关任务将无法调用该模型。"
            @confirm="clearKey(provider.key)"
          >
            <template #reference>
              <el-button
                plain
                type="danger"
                :loading="saving"
                :disabled="!providerConfigured(provider.key)"
              >
                清除密钥
              </el-button>
            </template>
          </el-popconfirm>
        </el-form>
      </section>
    </div>
  </el-card>
</template>

<script setup>
import { reactive, watch } from "vue"

const props = defineProps({
  settings: { type: Object, default: () => ({ providers: {} }) },
  saving: Boolean,
})

const emit = defineEmits(["submit"])

const providerList = [
  { key: "grok", title: "Grok（xAI）", defaultModel: "grok-4.6" },
  { key: "deepseek", title: "DeepSeek", defaultModel: "deepseek-v4-flash" },
]

const localForm = reactive({
  grok_api_key: "",
  grok_model: "grok-4.6",
  deepseek_api_key: "",
  deepseek_model: "deepseek-v4-flash",
})

watch(
  () => props.settings,
  (settings) => {
    for (const provider of providerList) {
      localForm[`${provider.key}_api_key`] = ""
      localForm[`${provider.key}_model`] = settings?.providers?.[provider.key]?.model || provider.defaultModel
    }
  },
  { immediate: true, deep: true },
)

function providerConfigured(key) {
  return Boolean(props.settings?.providers?.[key]?.configured)
}

function save() {
  emit("submit", {
    grok_api_key: localForm.grok_api_key || undefined,
    grok_model: localForm.grok_model.trim() || "grok-4.6",
    deepseek_api_key: localForm.deepseek_api_key || undefined,
    deepseek_model: localForm.deepseek_model.trim() || "deepseek-v4-flash",
  })
}

function clearKey(key) {
  emit("submit", { [`clear_${key}_api_key`]: true })
}
</script>

<style scoped>
.provider-card {
  border-radius: 8px;
}

.card-header,
.provider-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-title {
  color: var(--el-text-color-primary);
  font-size: 16px;
  font-weight: 600;
}

.card-subtitle {
  margin-top: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.provider-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.provider-section {
  padding: 16px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-fill-color-blank);
}

.provider-heading {
  margin-bottom: 12px;
}

.provider-section :deep(.el-form-item) {
  margin-bottom: 12px;
}

@media (max-width: 900px) {
  .card-header {
    align-items: stretch;
    flex-direction: column;
  }

  .provider-grid {
    grid-template-columns: 1fr;
  }
}
</style>
