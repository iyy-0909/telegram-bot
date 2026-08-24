<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="isEdit ? '编辑监听任务' : '新增监听任务'"
    width="980px"
    class="task-dialog"
  >
    <el-form class="task-form" label-position="top">
      <div class="section-row">
        <section class="form-section">
          <div class="section-title">基础信息</div>
          <div class="form-grid two">
            <el-form-item v-if="!isEdit" label="复制规则">
              <el-select
                v-model="copyTaskId"
                clearable
                filterable
                placeholder="选择已有任务作为模板"
                @change="applyCopyTask"
              >
                <el-option
                  v-for="task in copyableTasks"
                  :key="task.id"
                  :label="copyTaskLabel(task)"
                  :value="task.id"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="任务名称">
              <el-input v-model="localForm.name" placeholder="例如：上海频道实时监听" />
            </el-form-item>

            <el-form-item label="监听账号">
              <AccountSelect v-model="localForm.account_id" :accounts="props.accounts" />
            </el-form-item>

            <el-form-item label="分发 Bot">
              <BotSelect
                v-model="localForm.bot_id"
                :bots="props.bots"
                placeholder="请选择分发 Bot"
              />
            </el-form-item>
          </div>
        </section>

        <section class="form-section">
          <div class="section-title">频道与分发</div>

          <el-form-item>
            <template #label>
              <div class="field-label">
                <span>源频道</span>
                <el-tooltip content="添加源频道" placement="top">
                  <el-button class="add-channel-button" type="primary" circle @click="addSourceChannel">
                    <el-icon><Plus /></el-icon>
                  </el-button>
                </el-tooltip>
              </div>
            </template>
            <div class="channel-list">
              <div
                v-for="(_, index) in sourceChannels"
                :key="`source-${index}`"
                class="channel-row"
              >
                <el-input
                  v-model="sourceChannels[index]"
                  placeholder="@channel / chat_id / t.me"
                  clearable
                />
                <el-button :disabled="sourceChannels.length <= 1" @click="removeSourceChannel(index)">
                  删除
                </el-button>
              </div>
            </div>
          </el-form-item>

          <el-form-item label="目标频道">
            <ChannelSelect
              v-model="targetChannels"
              multiple
              include-disabled
              allow-create
              :bot-id="localForm.bot_id"
              placeholder="选择或输入目标频道"
            />
          </el-form-item>
        </section>
      </div>

      <section class="form-section">
        <div class="section-title">内容处理</div>

        <div class="form-grid two">
          <el-form-item label="通用过滤词">
            <el-select
              v-model="localForm.selected_filter_template_group_id"
              clearable
              filterable
              placeholder="选择过滤规则"
            >
              <el-option
                v-for="group in enabledTemplateGroupsByType('filter')"
                :key="group.id"
                :label="templateLabel(group)"
                :value="group.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="链接配置">
            <el-select
              v-model="localForm.selected_link_template_group_id"
              clearable
              filterable
              placeholder="不选则保持当前链接处理逻辑"
            >
              <el-option
                v-for="group in enabledTemplateGroupsByType('link')"
                :key="group.id"
                :label="templateLabel(group)"
                :value="group.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="联系方式配置">
            <el-select
              v-model="localForm.selected_contact_template_group_id"
              clearable
              filterable
              placeholder="不选则使用默认联系方式删除配置"
            >
              <el-option
                v-for="group in enabledTemplateGroupsByType('contact')"
                :key="group.id"
                :label="templateLabel(group)"
                :value="group.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="任务补充过滤词">
            <el-select
              v-model="blockedKeywordList"
              multiple
              filterable
              allow-create
              default-first-option
              placeholder="输入关键词后回车"
            >
              <el-option
                v-for="keyword in blockedKeywordList"
                :key="keyword"
                :label="keyword"
                :value="keyword"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="只监听内容">
            <el-select
              v-model="requiredKeywordList"
              multiple
              filterable
              allow-create
              default-first-option
              placeholder="输入源消息必须包含的内容后回车"
            >
              <el-option
                v-for="keyword in requiredKeywordList"
                :key="keyword"
                :label="keyword"
                :value="keyword"
              />
            </el-select>
            <div class="field-tip">留空表示全部监听；填写后，源消息包含任意一条才会发送。</div>
          </el-form-item>
        </div>

        <el-form-item label="替换词">
          <ReplaceRulesEditor v-model="localForm.replace_words" />
        </el-form-item>

        <div class="switch-grid">
          <div class="switch-row">
            <span>删除旧联系方式</span>
            <el-switch v-model="localForm.remove_contact_lines" />
          </div>
          <div class="switch-row">
            <span>过滤二维码图片</span>
            <el-switch v-model="localForm.filter_qr_code" />
          </div>
        </div>
      </section>

      <section class="form-section">
        <div class="section-title">AI 改写</div>
        <div class="switch-row"><span>启用 AI 改写</span><el-switch v-model="localForm.ai_rewrite_enabled" /></div>
        <template v-if="localForm.ai_rewrite_enabled">
          <div class="field-help">先完成本地清洗再调用所选模型；密钥未配置或请求失败时可回退原文。</div>
          <div class="form-grid two ai-grid">
            <el-form-item label="模型供应商"><el-select v-model="localForm.ai_rewrite_provider"><el-option label="Grok（xAI）" value="grok" /><el-option label="DeepSeek" value="deepseek" /></el-select></el-form-item>
            <el-form-item label="模型名称（可选）"><el-input v-model="localForm.ai_rewrite_model" :placeholder="localForm.ai_rewrite_provider === 'deepseek' ? '默认 deepseek-v4-flash' : '默认 grok-4.6'" /></el-form-item>
            <el-form-item label="最大输出字数"><el-input-number v-model="localForm.ai_rewrite_max_chars" :min="100" :max="4000" /></el-form-item>
            <el-form-item label="调用失败时"><el-select v-model="localForm.ai_rewrite_failure_mode"><el-option label="发送清洗后的原文" value="fallback" /><el-option label="跳过本条内容" value="skip" /></el-select></el-form-item>
          </div>
          <el-form-item label="改写比例">
            <AiRewriteRatioField v-model="localForm.ai_rewrite_ratio" />
          </el-form-item>
          <el-form-item label="改写提示词">
            <AiPromptSelect v-model="localForm.ai_prompt_template_id" :prompts="aiPrompts" />
          </el-form-item>
        </template>
      </section>

      <section class="form-section">
        <TemplateRulePanel
          :values="localForm"
          :templates="templates"
          @update="updateTemplateField"
        />
      </section>

      <section class="form-section">
        <div class="section-title">任务开关</div>
        <div class="switch-row">
          <span>启用任务</span>
          <el-switch v-model="localForm.enabled" />
        </div>
      </section>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" @click="submit">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from "vue"
import { Plus } from "@element-plus/icons-vue"
import AccountSelect from "./AccountSelect.vue"
import AiPromptSelect from "./AiPromptSelect.vue"
import AiRewriteRatioField from "./AiRewriteRatioField.vue"
import BotSelect from "./BotSelect.vue"
import ChannelSelect from "./ChannelSelect.vue"
import ReplaceRulesEditor from "./ReplaceRulesEditor.vue"
import TemplateRulePanel from "./TemplateRulePanel.vue"

const props = defineProps({
  visible: Boolean,
  form: Object,
  isEdit: Boolean,
  existingTasks: {
    type: Array,
    default: () => [],
  },
  accounts: {
    type: Array,
    default: () => [],
  },
  bots: {
    type: Array,
    default: () => [],
  },
  templates: {
    type: Array,
    default: () => [],
  },
  aiPrompts: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(["update:visible", "submit"])

const localForm = reactive({
  id: null,
  name: "",
  source_channel: "",
  target_channels: "[]",
  account_id: 1,
  bot_id: null,
  enabled: true,
  status: "running",
  blocked_keywords: "[]",
  listen_required_keywords: "[]",
  replace_words: "{}",
  footer: "",
  remove_contact_lines: true,
  ai_rewrite_enabled: false,
  ai_rewrite_provider: "grok",
  ai_rewrite_model: "",
  ai_rewrite_prompt: "",
  ai_prompt_template_id: null,
  ai_rewrite_max_chars: 800,
  ai_rewrite_ratio: 70,
  ai_rewrite_failure_mode: "fallback",
  filter_qr_code: true,
  use_random_head: false,
  use_random_body: false,
  use_random_footer: false,
  footer_leading_blank_line: true,
  selected_head_template_group_id: null,
  selected_body_template_group_id: null,
  selected_footer_template_group_id: null,
  selected_link_template_group_id: null,
  selected_contact_template_group_id: null,
  selected_head_template_id: null,
  selected_body_template_id: null,
  selected_footer_template_id: null,
  selected_filter_template_group_id: null,
  album_wait_seconds: 3,
})

const sourceChannels = ref([""])
const targetChannels = ref([])
const copyTaskId = ref(null)
const copyableTasks = computed(() => props.existingTasks.filter((task) => task?.id))

const blockedKeywordList = computed({
  get() {
    return parseJsonArray(localForm.blocked_keywords)
  },
  set(value) {
    localForm.blocked_keywords = JSON.stringify(uniqueStrings(value), null, 0)
  },
})

const requiredKeywordList = computed({
  get() {
    return parseJsonArray(localForm.listen_required_keywords)
  },
  set(value) {
    localForm.listen_required_keywords = JSON.stringify(uniqueStrings(value), null, 0)
  },
})

watch(
  () => props.form,
  (val) => {
    if (!val) return
    Object.assign(localForm, {
      ...val,
      target_channels: JSON.stringify(uniqueChannels(parseChannelItems(val.target_channels || "[]"))),
      blocked_keywords: normalizeJsonArrayString(val.blocked_keywords || "[]"),
      listen_required_keywords: normalizeJsonArrayString(val.listen_required_keywords || "[]"),
      use_random_head: val.use_random_head ?? false,
      use_random_body: val.use_random_body ?? false,
      use_random_footer: val.use_random_footer ?? false,
      footer_leading_blank_line: val.footer_leading_blank_line ?? true,
      selected_head_template_group_id: normalizeTemplateId(val.selected_head_template_group_id),
      selected_body_template_group_id: normalizeTemplateId(val.selected_body_template_group_id),
      selected_footer_template_group_id: normalizeTemplateId(val.selected_footer_template_group_id),
      selected_link_template_group_id: normalizeTemplateId(val.selected_link_template_group_id),
      selected_contact_template_group_id: normalizeTemplateId(val.selected_contact_template_group_id),
      selected_head_template_id: normalizeTemplateId(val.selected_head_template_id),
      selected_body_template_id: normalizeTemplateId(val.selected_body_template_id),
      selected_footer_template_id: normalizeTemplateId(val.selected_footer_template_id),
      selected_filter_template_group_id: normalizeTemplateId(val.selected_filter_template_group_id),
      filter_qr_code: val.filter_qr_code ?? true,
      ai_rewrite_enabled: val.ai_rewrite_enabled ?? false,
      ai_rewrite_provider: val.ai_rewrite_provider === "deepseek" ? "deepseek" : "grok",
      ai_rewrite_model: val.ai_rewrite_model || "",
      ai_rewrite_prompt: val.ai_rewrite_prompt || "",
      ai_prompt_template_id: normalizeTemplateId(val.ai_prompt_template_id),
      ai_rewrite_max_chars: toBoundedNumber(val.ai_rewrite_max_chars, 800, 100, 4000),
      ai_rewrite_ratio: toBoundedNumber(val.ai_rewrite_ratio, 70, 0, 100),
      ai_rewrite_failure_mode: val.ai_rewrite_failure_mode === "skip" ? "skip" : "fallback",
    })
    sourceChannels.value = parseChannelItems(val.source_channels || val.source_channel || "")
    targetChannels.value = parseChannelItems(val.target_channels || "[]")
    copyTaskId.value = null
  },
  { immediate: true, deep: true },
)

function applyCopyTask(taskId) {
  const task = props.existingTasks.find((item) => Number(item.id) === Number(taskId))
  if (!task) return

  Object.assign(localForm, {
    id: null,
    name: task.name ? `${task.name} 副本` : "",
    source_channel: task.source_channel || "",
    target_channels: task.target_channels || "[]",
    account_id: toPositiveNumber(task.account_id, props.accounts[0]?.id || 1),
    bot_id: normalizeBotId(task.bot_id),
    enabled: true,
    status: "running",
    blocked_keywords: normalizeJsonArrayString(task.blocked_keywords || "[]"),
    listen_required_keywords: normalizeJsonArrayString(task.listen_required_keywords || "[]"),
    replace_words: task.replace_words || "{}",
    footer: "",
    remove_contact_lines: task.remove_contact_lines ?? true,
    filter_qr_code: task.filter_qr_code ?? true,
    use_random_head: task.use_random_head ?? false,
    use_random_body: task.use_random_body ?? false,
    use_random_footer: task.use_random_footer ?? false,
    footer_leading_blank_line: task.footer_leading_blank_line ?? true,
    selected_head_template_group_id: normalizeTemplateId(task.selected_head_template_group_id),
    selected_body_template_group_id: normalizeTemplateId(task.selected_body_template_group_id),
    selected_footer_template_group_id: normalizeTemplateId(task.selected_footer_template_group_id),
    selected_link_template_group_id: normalizeTemplateId(task.selected_link_template_group_id),
    selected_contact_template_group_id: normalizeTemplateId(task.selected_contact_template_group_id),
    selected_head_template_id: normalizeTemplateId(task.selected_head_template_id),
    selected_body_template_id: normalizeTemplateId(task.selected_body_template_id),
    selected_footer_template_id: normalizeTemplateId(task.selected_footer_template_id),
    selected_filter_template_group_id: normalizeTemplateId(task.selected_filter_template_group_id),
    album_wait_seconds: toPositiveNumber(task.album_wait_seconds, 3),
    ai_rewrite_enabled: task.ai_rewrite_enabled ?? false,
    ai_rewrite_provider: task.ai_rewrite_provider === "deepseek" ? "deepseek" : "grok",
    ai_rewrite_model: task.ai_rewrite_model || "",
    ai_rewrite_prompt: task.ai_rewrite_prompt || "",
    ai_prompt_template_id: normalizeTemplateId(task.ai_prompt_template_id),
    ai_rewrite_max_chars: toBoundedNumber(task.ai_rewrite_max_chars, 800, 100, 4000),
    ai_rewrite_ratio: toBoundedNumber(task.ai_rewrite_ratio, 70, 0, 100),
    ai_rewrite_failure_mode: task.ai_rewrite_failure_mode === "skip" ? "skip" : "fallback",
  })

  sourceChannels.value = parseChannelItems(task.source_channel || "")
  targetChannels.value = parseChannelItems(task.target_channels || "[]")
}

function copyTaskLabel(task) {
  const source = task.source_channel || "-"
  const targets = parseChannelItems(task.target_channels || "[]").join(", ") || "-"
  return `#${task.id} ${task.name || "未命名"} | ${source} -> ${targets}`
}

function addSourceChannel() {
  sourceChannels.value.push("")
}

function removeSourceChannel(index) {
  sourceChannels.value.splice(index, 1)
  if (!sourceChannels.value.length) {
    sourceChannels.value.push("")
  }
}

function submit() {
  const sources = uniqueChannels(sourceChannels.value)
  const targets = uniqueChannels(targetChannels.value)

  emit("submit", {
    ...localForm,
    name: (localForm.name || "").trim(),
    source_channel: sources[0] || "",
    source_channels: sources,
    target_channels: JSON.stringify(targets),
    account_id: toPositiveNumber(localForm.account_id, 1),
    bot_id: normalizeBotId(localForm.bot_id),
    album_wait_seconds: toPositiveNumber(localForm.album_wait_seconds, 3),
    blocked_keywords: normalizeJsonArrayString(localForm.blocked_keywords),
    listen_required_keywords: normalizeJsonArrayString(localForm.listen_required_keywords),
    footer: "",
    selected_filter_template_group_id: normalizeTemplateId(localForm.selected_filter_template_group_id),
    selected_link_template_group_id: normalizeTemplateId(localForm.selected_link_template_group_id),
    selected_contact_template_group_id: normalizeTemplateId(localForm.selected_contact_template_group_id),
    filter_qr_code: localForm.filter_qr_code,
    ai_rewrite_enabled: Boolean(localForm.ai_rewrite_enabled),
    ai_rewrite_provider: localForm.ai_rewrite_provider === "deepseek" ? "deepseek" : "grok",
    ai_rewrite_model: (localForm.ai_rewrite_model || "").trim(),
    ai_rewrite_prompt: "",
    ai_prompt_template_id: normalizeTemplateId(localForm.ai_prompt_template_id),
    ai_rewrite_max_chars: toBoundedNumber(localForm.ai_rewrite_max_chars, 800, 100, 4000),
    ai_rewrite_ratio: toBoundedNumber(localForm.ai_rewrite_ratio, 70, 0, 100),
    ai_rewrite_failure_mode: localForm.ai_rewrite_failure_mode === "skip" ? "skip" : "fallback",
    selected_head_template_group_id: localForm.use_random_head
      ? normalizeTemplateId(localForm.selected_head_template_group_id)
      : null,
    selected_body_template_group_id: localForm.use_random_body
      ? normalizeTemplateId(localForm.selected_body_template_group_id)
      : null,
    selected_footer_template_group_id: localForm.use_random_footer
      ? normalizeTemplateId(localForm.selected_footer_template_group_id)
      : null,
    selected_head_template_id: localForm.use_random_head
      ? normalizeTemplateId(localForm.selected_head_template_id)
      : null,
    selected_body_template_id: localForm.use_random_body
      ? normalizeTemplateId(localForm.selected_body_template_id)
      : null,
    selected_footer_template_id: localForm.use_random_footer
      ? normalizeTemplateId(localForm.selected_footer_template_id)
      : null,
  })
}

function enabledTemplateGroupsByType(type) {
  return props.templates.filter(
    (template) => template.type === type && template.enabled && !template.parent_id,
  )
}

function templateLabel(template) {
  return template.name || `模板 ${template.id}`
}

function parseChannelItems(value) {
  let items = []

  if (Array.isArray(value)) {
    items = value
  } else {
    const text = String(value || "").trim()
    if (text.startsWith("[") && text.endsWith("]")) {
      try {
        const parsed = JSON.parse(text)
        items = Array.isArray(parsed) ? parsed : [text]
      } catch {
        items = [text]
      }
    } else if (text) {
      items = text.split(/[\n,，\s]+/)
    }
  }

  const normalized = uniqueChannels(items)
  return normalized.length ? normalized : [""]
}

function uniqueChannels(items) {
  const seen = new Set()
  const result = []

  for (const item of items || []) {
    const channel = normalizeChannelInput(item)
    const key = channel.toLowerCase()

    if (!channel || seen.has(key)) {
      continue
    }

    seen.add(key)
    result.push(channel)
  }

  return result
}

function normalizeChannelInput(value) {
  let text = String(value || "").trim()
  if (!text) return ""
  if (/^-?\d+$/.test(text)) return text

  text = text.replace(/^https?:\/\//i, "")
  text = text.replace(/^telegram\.me\//i, "t.me/")

  if (/^t\.me\//i.test(text)) {
    const parts = text.replace(/^t\.me\//i, "").split(/[/?#]/).filter(Boolean)
    if (parts[0] === "c" && parts[1] && /^\d+$/.test(parts[1])) {
      return `-100${parts[1]}`
    }
    text = parts[0] || ""
  }

  if (text.startsWith("@")) text = text.slice(1)
  if (text.includes("/")) text = text.split("/")[0]
  text = text.trim()

  if (!text) return ""
  if (/^-?\d+$/.test(text)) return text
  return `@${text}`
}

function parseJsonArray(value) {
  try {
    const parsed = JSON.parse(value || "[]")
    return Array.isArray(parsed) ? uniqueStrings(parsed) : []
  } catch {
    return uniqueStrings(String(value || "").split(/[\n,，\s]+/))
  }
}

function normalizeJsonArrayString(value) {
  return JSON.stringify(parseJsonArray(value), null, 0)
}

function uniqueStrings(items) {
  const seen = new Set()
  const result = []

  for (const item of items || []) {
    const text = String(item || "").trim()
    if (!text || seen.has(text)) continue
    seen.add(text)
    result.push(text)
  }

  return result
}

function normalizeTemplateId(value) {
  if (value === null || value === undefined || value === "") {
    return null
  }

  const numberValue = Number(value)
  return Number.isInteger(numberValue) && numberValue > 0 ? numberValue : null
}

function normalizeBotId(value) {
  return normalizeTemplateId(value)
}

function toPositiveNumber(value, fallback) {
  const numberValue = Number(value)

  if (!Number.isFinite(numberValue) || numberValue < 1) {
    return fallback
  }

  return Math.floor(numberValue)
}

function toBoundedNumber(value, fallback, min, max) {
  const numberValue = Number(value)
  if (!Number.isFinite(numberValue)) return fallback
  return Math.max(min, Math.min(max, Math.floor(numberValue)))
}

function updateTemplateField({ key, value }) {
  if (Object.prototype.hasOwnProperty.call(localForm, key)) {
    localForm[key] = value
  }
}
</script>

<style scoped>
.field-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.add-channel-button {
  width: 22px;
  height: 22px;
  min-height: 22px;
  padding: 0;
}

.channel-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
}

.channel-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
  width: 100%;
}

.task-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.section-row {
  display: grid;
  grid-template-columns: minmax(0, 0.92fr) minmax(0, 1.08fr);
  gap: 10px;
}

.form-section {
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
}

.section-title {
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.field-tip {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.4;
  color: #909399;
}

.form-grid {
  display: grid;
  gap: 10px 12px;
}

.form-grid.two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.task-form :deep(.el-form-item) {
  margin-bottom: 12px;
}

.task-form :deep(.form-section > .el-form-item:last-child),
.task-form :deep(.form-grid .el-form-item) {
  margin-bottom: 0;
}

.switch-grid {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.switch-row {
  width: fit-content;
  max-width: 100%;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  min-height: 38px;
  padding: 8px 10px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #f9fafb;
  color: #303133;
}

.ai-grid { margin-top: 10px; }

:global(.task-dialog) {
  max-width: calc(100vw - 32px);
}

:global(.task-dialog .el-dialog__body) {
  max-height: min(70vh, 720px);
  overflow: auto;
}

@media (max-width: 900px) {
  :global(.task-dialog) {
    width: calc(100vw - 24px) !important;
    margin: 12px auto !important;
  }

  :global(.task-dialog .el-dialog__header),
  :global(.task-dialog .el-dialog__body),
  :global(.task-dialog .el-dialog__footer) {
    padding-left: 14px;
    padding-right: 14px;
  }

  .section-row,
  .form-grid.two {
    grid-template-columns: 1fr;
  }
}
</style>
