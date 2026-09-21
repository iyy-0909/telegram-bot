<template>
  <el-card class="provider-card" shadow="never">
    <template #header>
      <div class="card-header">
        <div>
          <div class="card-title">模型供应商</div>
          <div class="card-subtitle">集中查看密钥状态、默认模型，并指定新任务使用的默认 AI。</div>
        </div>
        <el-button type="primary" :loading="saving" :disabled="loading" @click="save">
          保存模型配置
        </el-button>
      </div>
    </template>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="默认 AI 用于文案试写和以后新建的任务；已有任务继续使用各自保存的供应商。任务单独填写的模型名称优先于表格中的默认模型。"
    />

    <el-form class="provider-form" :disabled="saving || loading" @submit.prevent="save">
      <div class="table-scroll-hint">可左右滑动查看密钥、模型和操作</div>
      <div class="provider-table-scroll">
        <el-table
          v-loading="loading"
          :data="providerList"
          class="provider-table"
          max-height="420"
          row-key="key"
          empty-text="暂无可配置的模型供应商"
        >
          <el-table-column label="供应商" min-width="150">
            <template #default="{ row }">
              <div class="provider-name">
                <strong>{{ row.title }}</strong>
                <span>{{ row.key }}</span>
              </div>
            </template>
          </el-table-column>

          <el-table-column label="密钥状态" width="120">
            <template #default="{ row }">
              <el-tag :type="providerConfigured(row.key) ? 'success' : 'info'">
                {{ providerConfigured(row.key) ? "已配置" : "未配置" }}
              </el-tag>
            </template>
          </el-table-column>

          <el-table-column label="默认 AI" width="140">
            <template #default="{ row }">
              <el-radio
                v-model="localForm.default_provider"
                :value="row.key"
                :aria-label="`将 ${row.title} 设为默认 AI`"
              >
                {{ localForm.default_provider === row.key ? "当前默认" : "设为默认" }}
              </el-radio>
            </template>
          </el-table-column>

          <el-table-column label="API Key" min-width="250">
            <template #default="{ row }">
              <el-input
                v-model="localForm[`${row.key}_api_key`]"
                type="password"
                show-password
                :aria-label="`${row.title} API Key`"
                :placeholder="providerConfigured(row.key) ? '留空则保持当前密钥' : `请输入 ${row.title} API Key`"
                autocomplete="new-password"
              />
            </template>
          </el-table-column>

          <el-table-column label="默认模型" min-width="210">
            <template #default="{ row }">
              <el-input
                v-model="localForm[`${row.key}_model`]"
                :aria-label="`${row.title} 默认模型`"
                :placeholder="row.defaultModel"
              />
            </template>
          </el-table-column>

          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-popconfirm
                title="确定清除这个供应商已保存的密钥吗？相关任务将无法调用该模型。"
                @confirm="clearKey(row.key)"
              >
                <template #reference>
                  <el-button
                    link
                    type="danger"
                    :loading="clearingKey === row.key"
                    :disabled="saving || !providerConfigured(row.key)"
                  >
                    清除密钥
                  </el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-form>
  </el-card>
</template>

<script setup>
import { reactive, ref, watch } from "vue"

const props = defineProps({
  settings: { type: Object, default: () => ({ providers: {}, default_provider: "grok" }) },
  saving: Boolean,
  loading: Boolean,
})

const emit = defineEmits(["submit"])

const providerList = [
  { key: "grok", title: "Grok（xAI）", defaultModel: "grok-4.6" },
  { key: "deepseek", title: "DeepSeek", defaultModel: "deepseek-v4-flash" },
]

const localForm = reactive({
  default_provider: "grok",
  grok_api_key: "",
  grok_model: "grok-4.6",
  deepseek_api_key: "",
  deepseek_model: "deepseek-v4-flash",
})
const clearingKey = ref("")

watch(
  () => props.settings,
  (settings) => {
    localForm.default_provider = settings?.default_provider === "deepseek" ? "deepseek" : "grok"
    for (const provider of providerList) {
      localForm[`${provider.key}_api_key`] = ""
      localForm[`${provider.key}_model`] = settings?.providers?.[provider.key]?.model || provider.defaultModel
    }
    clearingKey.value = ""
  },
  { immediate: true, deep: true },
)

watch(
  () => props.saving,
  (saving) => {
    if (!saving) clearingKey.value = ""
  },
)

function providerConfigured(key) {
  return Boolean(props.settings?.providers?.[key]?.configured)
}

function save() {
  emit("submit", {
    default_provider: localForm.default_provider,
    grok_api_key: localForm.grok_api_key || undefined,
    grok_model: localForm.grok_model.trim() || "grok-4.6",
    deepseek_api_key: localForm.deepseek_api_key || undefined,
    deepseek_model: localForm.deepseek_model.trim() || "deepseek-v4-flash",
  })
}

function clearKey(key) {
  clearingKey.value = key
  emit("submit", { [`clear_${key}_api_key`]: true })
}
</script>

<style scoped>
.provider-card {
  min-width: 0;
  border-radius: 8px;
}

.card-header {
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

.provider-form {
  margin-top: 16px;
}

.provider-table-scroll {
  max-width: 100%;
  overflow-x: auto;
}

.table-scroll-hint {
  display: none;
  margin-bottom: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.provider-table {
  min-width: 940px;
}

.provider-name {
  display: grid;
  gap: 3px;
}

.provider-name span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.provider-table :deep(.el-input),
.provider-table :deep(.el-radio) {
  width: 100%;
}

.provider-table :deep(.el-radio__label) {
  padding-left: 6px;
}

@media (max-width: 600px) {
  .card-header {
    align-items: stretch;
    flex-direction: column;
  }

  .card-header .el-button {
    width: 100%;
  }

}

@media (max-width: 1000px) {
  .table-scroll-hint {
    display: block;
  }
}
</style>
