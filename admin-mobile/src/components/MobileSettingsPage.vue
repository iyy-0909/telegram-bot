<template>
  <div class="mobile-settings">
    <section class="settings-section">
      <div class="section-head">
        <div>
          <h2>发送设置</h2>
          <p>控制所有任务共享的 Bot API 发送节奏</p>
        </div>
      </div>
      <el-form label-position="top">
        <el-form-item label="全局发送间隔秒">
          <el-input-number v-model="sendForm.global_send_delay" :min="0" controls-position="right" />
        </el-form-item>
        <el-form-item label="发送异常重试次数">
          <el-input-number v-model="sendForm.send_retry_count" :min="0" controls-position="right" />
        </el-form-item>
        <el-form-item label="重试等待秒">
          <el-input-number v-model="sendForm.send_retry_delay" :min="0" controls-position="right" />
        </el-form-item>
        <el-button type="primary" class="full-button" :loading="saving" @click="emit('save-settings', { ...sendForm })">保存发送设置</el-button>
      </el-form>
    </section>

    <section class="settings-section">
      <div class="section-head">
        <div><h2>AI 内容改写</h2><p>密钥不会重新显示；留空保存不会覆盖已配置密钥。</p></div>
      </div>
      <el-form label-position="top">
        <el-form-item label="默认改写提示词"><el-input v-model="aiForm.default_rewrite_prompt" type="textarea" :rows="8" placeholder="任务没有自定义提示词时使用；支持 {{content}} 和 {{max_chars}}。" /></el-form-item>
        <div class="prompt-help">任务中的自定义提示词会覆盖此默认值。</div>
        <template v-for="provider in providerList" :key="provider.key">
          <div class="provider-title"><strong>{{ provider.title }}</strong><el-tag :type="configured(provider.key) ? 'success' : 'info'">{{ configured(provider.key) ? '已配置' : '未配置' }}</el-tag></div>
          <el-form-item label="API Key"><el-input v-model="aiForm[`${provider.key}_api_key`]" type="password" show-password :placeholder="configured(provider.key) ? '留空保持当前密钥' : `输入 ${provider.title} API Key`" autocomplete="new-password" /></el-form-item>
          <el-form-item label="默认模型"><el-input v-model="aiForm[`${provider.key}_model`]" :placeholder="provider.defaultModel" /></el-form-item>
          <el-popconfirm title="确定清除已保存的密钥吗？" @confirm="clearKey(provider.key)"><template #reference><el-button plain type="danger" :disabled="!configured(provider.key)">清除密钥</el-button></template></el-popconfirm>
        </template>
        <el-button type="primary" class="full-button ai-save" :loading="saving" @click="saveAi">保存 AI 配置</el-button>
      </el-form>
    </section>

    <el-collapse v-model="openSections" class="settings-collapse">
      <el-collapse-item
        v-for="section in visibleSections"
        :key="section.key"
        :name="section.key"
      >
        <template #title>
          <div class="collapse-title">
            <strong>{{ section.title }}</strong>
            <span>{{ section.subtitle }}</span>
          </div>
        </template>

        <el-tabs v-if="section.types.length > 1" v-model="activeTypes[section.key]" stretch>
          <el-tab-pane
            v-for="type in section.types"
            :key="type"
            :label="typeLabel(type)"
            :name="type"
          />
        </el-tabs>

        <div class="section-actions">
          <span>共 {{ rulesFor(section).length }} 条</span>
          <el-button
            circle
            type="primary"
            :icon="Plus"
            aria-label="新增配置"
            title="新增配置"
            @click="emit('create-template', activeType(section))"
          />
        </div>

        <div v-if="rulesFor(section).length" class="rule-list">
          <article v-for="rule in rulesFor(section)" :key="rule.id" class="rule-item">
            <div class="rule-head">
              <div>
                <strong>{{ rule.name || `${typeLabel(rule.type)}配置` }}</strong>
                <span>{{ ruleSummary(rule) }}</span>
              </div>
              <el-switch :model-value="rule.enabled" @change="emit('toggle-template', rule)" />
            </div>
            <div class="icon-actions">
              <el-button circle plain :icon="Edit" aria-label="编辑配置" title="编辑配置" @click="emit('edit-template', rule)" />
              <el-button circle plain type="danger" :icon="Delete" aria-label="删除配置" title="删除配置" @click="emit('delete-template', rule)" />
            </div>
          </article>
        </div>
        <el-empty v-else :image-size="56" :description="`暂无${typeLabel(activeType(section))}配置`" />
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue"
import { Delete, Edit, Plus } from "@element-plus/icons-vue"

const props = defineProps({
  settings: { type: Object, required: true },
  aiSettings: { type: Object, default: () => ({ providers: {} }) },
  templates: { type: Array, default: () => [] },
  saving: { type: Boolean, default: false },
})

const emit = defineEmits(["save-settings", "save-ai-settings", "create-template", "edit-template", "delete-template", "toggle-template"])

const sectionRegistry = [
  { key: "contact", title: "联系方式配置", subtitle: "手机号、链接、用户名和关键词删除", types: ["contact"] },
  { key: "filter", title: "关键词过滤配置", subtitle: "任务可选择的通用过滤关键词", types: ["filter"] },
  { key: "content", title: "内容模板", subtitle: "头部、正文和底部内容", types: ["head", "body", "footer"] },
  { key: "link", title: "链接配置", subtitle: "链接保留、替换和删除动作", types: ["link"] },
]

const sendForm = reactive({
  global_send_delay: 3,
  send_retry_count: 2,
  send_retry_delay: 5,
})
const providerList = [{ key: "grok", title: "Grok（xAI）", defaultModel: "grok-4.6" }, { key: "deepseek", title: "DeepSeek", defaultModel: "deepseek-v4-flash" }]
const aiForm = reactive({ grok_api_key: "", grok_model: "grok-4.6", deepseek_api_key: "", deepseek_model: "deepseek-v4-flash", default_rewrite_prompt: "" })
const openSections = ref(["contact"])
const activeTypes = reactive(Object.fromEntries(sectionRegistry.map((section) => [section.key, section.types[0]])))

watch(
  () => props.settings,
  (settings) => {
    sendForm.global_send_delay = nonNegative(settings?.global_send_delay, 3)
    sendForm.send_retry_count = nonNegative(settings?.send_retry_count, 2)
    sendForm.send_retry_delay = nonNegative(settings?.send_retry_delay, 5)
  },
  { immediate: true, deep: true },
)

watch(() => props.aiSettings, (settings) => {
  for (const provider of providerList) {
    aiForm[`${provider.key}_api_key`] = ""
    aiForm[`${provider.key}_model`] = settings?.providers?.[provider.key]?.model || provider.defaultModel
  }
  aiForm.default_rewrite_prompt = settings?.default_rewrite_prompt || ""
}, { immediate: true, deep: true })

function configured(key) { return Boolean(props.aiSettings?.providers?.[key]?.configured) }
function saveAi() {
  emit("save-ai-settings", {
    grok_api_key: aiForm.grok_api_key || undefined,
    grok_model: aiForm.grok_model.trim() || "grok-4.6",
    deepseek_api_key: aiForm.deepseek_api_key || undefined,
    deepseek_model: aiForm.deepseek_model.trim() || "deepseek-v4-flash",
    default_rewrite_prompt: aiForm.default_rewrite_prompt.trim(),
  })
}
function clearKey(key) { emit("save-ai-settings", { [`clear_${key}_api_key`]: true }) }

const visibleSections = computed(() => {
  const known = new Set(sectionRegistry.flatMap((section) => section.types))
  const otherTypes = Array.from(new Set(props.templates.map((rule) => rule.type).filter((type) => type && !known.has(type))))
  return otherTypes.length
    ? [...sectionRegistry, { key: "other", title: "其他配置", subtitle: "尚未归类的新配置", types: otherTypes }]
    : sectionRegistry
})

function activeType(section) {
  if (!activeTypes[section.key]) activeTypes[section.key] = section.types[0] || ""
  return activeTypes[section.key]
}

function rulesFor(section) {
  const type = activeType(section)
  return props.templates.filter((rule) => rule.type === type)
}

function typeLabel(type) {
  return ({ head: "头部", body: "正文", footer: "底部", filter: "过滤", link: "链接", contact: "联系方式" })[type] || type || "其他"
}

function ruleSummary(rule) {
  const contents = (rule.items || []).map((item) => String(item.content || "").trim()).filter(Boolean)
  if (!contents.length) return "暂无内容"
  if (rule.type === "contact") {
    const config = parseJson(contents[0])
    const count = Array.isArray(config.keywords) ? config.keywords.length : 0
    return `已配置 ${count} 个关键词`
  }
  if (rule.type === "link") {
    const config = parseJson(contents[0])
    return `已配置 ${Object.keys(config).filter((key) => !key.endsWith("_replacement")).length} 类链接`
  }
  if (rule.type === "filter") {
    const count = contents.flatMap((content) => content.split(/\r?\n/).filter((item) => item.trim())).length
    return `${count} 个过滤关键词`
  }
  return `${contents.length} 条内容`
}

function parseJson(value) {
  try {
    const parsed = JSON.parse(value || "{}")
    return parsed && typeof parsed === "object" ? parsed : {}
  } catch {
    return {}
  }
}

function nonNegative(value, fallback) {
  const number = Number(value)
  return Number.isFinite(number) && number >= 0 ? Math.floor(number) : fallback
}
</script>

<style scoped>
.mobile-settings { display: flex; flex-direction: column; gap: 12px; padding-bottom: 12px; }
.settings-section { padding: 14px; border: 1px solid var(--el-border-color-light); border-radius: 8px; background: var(--el-bg-color); }
.section-head h2 { margin: 0; font-size: 16px; }
.section-head p { margin: 4px 0 14px; color: var(--el-text-color-secondary); font-size: 12px; }
.full-button, :deep(.el-input-number) { width: 100%; }
.provider-title { display: flex; align-items: center; justify-content: space-between; margin: 12px 0 8px; }
.ai-save { margin-top: 14px; }
.prompt-help { margin: -6px 0 12px; color: var(--el-text-color-secondary); font-size: 12px; }
.settings-collapse { border: 1px solid var(--el-border-color-light); border-radius: 8px; background: var(--el-bg-color); overflow: hidden; }
:deep(.el-collapse-item__header) { min-height: 58px; height: auto; padding: 8px 14px; line-height: 1.35; }
:deep(.el-collapse-item__content) { padding: 0 12px 14px; }
.collapse-title { display: flex; flex-direction: column; min-width: 0; }
.collapse-title span { margin-top: 3px; color: var(--el-text-color-secondary); font-size: 11px; }
.section-actions { display: flex; align-items: center; justify-content: space-between; margin: 8px 0; color: var(--el-text-color-secondary); font-size: 12px; }
.rule-list { display: flex; flex-direction: column; gap: 8px; }
.rule-item { padding: 10px; border: 1px solid var(--el-border-color-lighter); border-radius: 6px; }
.rule-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.rule-head > div { min-width: 0; }
.rule-head strong, .rule-head span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rule-head span { margin-top: 4px; color: var(--el-text-color-secondary); font-size: 12px; }
.icon-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--el-border-color-extra-light); }
.icon-actions .el-button { margin-left: 0; }
</style>
