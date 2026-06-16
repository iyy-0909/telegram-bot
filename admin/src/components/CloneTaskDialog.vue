<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="isEdit ? '缂栬緫鍏嬮殕浠诲姟' : '鏂板鍏嬮殕浠诲姟'"
    width="980px"
    class="task-dialog"
  >
    <el-form class="task-form" label-position="top">
      <div class="section-row">
        <section class="form-section">
          <div class="section-title">鍩虹淇℃伅</div>
          <div class="form-grid two">
            <el-form-item label="任务名称">
              <el-input v-model="localForm.name" placeholder="例如：杭州频道克隆" />
            </el-form-item>

            <el-form-item label="采集账号">
              <el-input :model-value="collectorAccountLabel" disabled />
            </el-form-item>

            <el-form-item label="开始内容链接">
              <el-input
                v-model="localForm.start_message_url"
                placeholder="为空则从第一条开始"
              />
            </el-form-item>

            <el-form-item label="缁撴潫鍐呭閾炬帴">
              <el-input
                v-model="localForm.end_message_url"
                placeholder="为空则克隆到当前最新"
              />
            </el-form-item>
          </div>
        </section>

        <section class="form-section">
          <div class="section-title">频道与分发</div>
          <div class="form-grid two">
            <el-form-item label="源频道">
              <el-input
                v-model="localForm.source_channel"
                placeholder="@channel / chat_id / t.me"
              />
            </el-form-item>

            <el-form-item label="分发 Bot">
              <BotSelect
                v-model="localForm.bot_id"
                :bots="props.bots"
                placeholder="璇烽€夋嫨 Bot"
              />
            </el-form-item>
          </div>

          <el-form-item label="鐩爣棰戦亾">
            <ChannelSelect
              v-model="targetChannelValues"
              multiple
              include-disabled
              allow-create
              :bot-id="localForm.bot_id"
              placeholder="选择或输入目标频道"
            />
          </el-form-item>
        </section>
      </div>

      <section class="form-section dense">
        <div class="section-title">发送节奏</div>

        <div class="form-grid four">
          <el-form-item label="内容间隔分钟">
            <el-input-number v-model="localForm.single_delay" :min="1" :step="1" />
          </el-form-item>

          <el-form-item label="目标间隔秒">
            <el-input-number v-model="localForm.target_delay" :min="1" :step="1" />
          </el-form-item>
        </div>
      </section>

      <section class="form-section">
        <div class="section-title">内容处理</div>

        <div class="form-grid two">
          <el-form-item label="通用过滤规则">
            <el-select
              v-model="localForm.selected_filter_template_group_id"
              clearable
              filterable
              placeholder="閫夋嫨杩囨护瑙勫垯"
            >
              <el-option
                v-for="group in enabledTemplateGroupsByType('filter')"
                :key="group.id"
                :label="templateLabel(group)"
                :value="group.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="閾炬帴閰嶇疆">
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
        <TemplateRulePanel
          :values="localForm"
          :templates="templates"
          @update="updateTemplateField"
        />
      </section>

      <section class="form-section">
        <div class="section-title">任务开关</div>
        <div class="switch-grid">
          <div class="switch-row">
            <span>克隆完成后自动进入监听</span>
            <el-switch v-model="localForm.enable_listener" />
          </div>
          <div class="switch-row">
            <span>启用任务</span>
            <el-switch v-model="localForm.enabled" />
          </div>
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
import { computed, reactive, watch } from "vue"
import BotSelect from "./BotSelect.vue"
import ChannelSelect from "./ChannelSelect.vue"
import ReplaceRulesEditor from "./ReplaceRulesEditor.vue"
import TemplateRulePanel from "./TemplateRulePanel.vue"

const props = defineProps({
  visible: Boolean,
  form: Object,
  isEdit: Boolean,
  bots: {
    type: Array,
    default: () => [],
  },
  accounts: {
    type: Array,
    default: () => [],
  },
  templates: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(["update:visible", "submit"])

const localForm = reactive({
  id: null,
  name: "",
  source_channel: "",
  start_message_url: "",
  end_message_url: "",
  target_channels: "[]",
  account_id: 1,
  bot_id: null,
  single_delay: 3,
  target_delay: 2,
  blocked_keywords: "[]",
  replace_words: "{}",
  footer: "",
  enabled: true,
  enable_listener: false,
  filter_qr_code: true,
  use_random_head: false,
  use_random_body: false,
  use_random_footer: false,
  selected_head_template_group_id: null,
  selected_body_template_group_id: null,
  selected_footer_template_group_id: null,
  selected_link_template_group_id: null,
  selected_contact_template_group_id: null,
  selected_head_template_id: null,
  selected_body_template_id: null,
  selected_footer_template_id: null,
  selected_filter_template_group_id: null,
  status: "idle",
  last_message_id: 0,
  remove_contact_lines: true,
})

const targetChannelValues = computed({
  get() {
    return parseChannels(localForm.target_channels)
  },
  set(value) {
    localForm.target_channels = JSON.stringify(uniqueChannels(value))
  },
})

const blockedKeywordList = computed({
  get() {
    return parseJsonArray(localForm.blocked_keywords)
  },
  set(value) {
    localForm.blocked_keywords = JSON.stringify(uniqueStrings(value), null, 0)
  },
})

const collectorAccount = computed(() => (
  props.accounts.find((account) => account.enabled)
  || props.accounts[0]
  || null
))

const collectorAccountLabel = computed(() => {
  if (!collectorAccount.value) {
    return "鏆傛棤鍙敤閲囬泦璐﹀彿"
  }

  const username = collectorAccount.value.username ? ` @${collectorAccount.value.username}` : ""
  return `${collectorAccount.value.id} - ${collectorAccount.value.name || "閲囬泦璐﹀彿"}${username}`
})

watch(
  () => props.form,
  (val) => {
    if (!val) return
    Object.assign(localForm, {
      ...val,
      source_channel: val.source_channel || "",
      target_channels: JSON.stringify(uniqueChannels(parseChannels(val.target_channels || "[]"))),
      blocked_keywords: normalizeJsonArrayString(val.blocked_keywords || "[]"),
      use_random_head: val.use_random_head ?? false,
      use_random_body: val.use_random_body ?? false,
      use_random_footer: val.use_random_footer ?? false,
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
    })
  },
  { immediate: true, deep: true },
)

function submit() {
  emit("submit", {
    ...localForm,
    source_channel: normalizeChannelInput(localForm.source_channel),
    target_channels: JSON.stringify(uniqueChannels(parseChannels(localForm.target_channels))),
    start_message_url: (localForm.start_message_url || "").trim(),
    end_message_url: (localForm.end_message_url || "").trim(),
    account_id: collectorAccount.value?.id || toPositiveNumber(localForm.account_id, 1),
    bot_id: normalizeBotId(localForm.bot_id),
    single_delay: toPositiveNumber(localForm.single_delay, 3),
    target_delay: toPositiveNumber(localForm.target_delay, 2),
    blocked_keywords: normalizeJsonArrayString(localForm.blocked_keywords),
    footer: "",
    filter_qr_code: localForm.filter_qr_code,
    selected_filter_template_group_id: normalizeTemplateId(localForm.selected_filter_template_group_id),
    selected_link_template_group_id: normalizeTemplateId(localForm.selected_link_template_group_id),
    selected_contact_template_group_id: normalizeTemplateId(localForm.selected_contact_template_group_id),
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
  return template.name || `妯℃澘 ${template.id}`
}

function parseChannels(value) {
  if (Array.isArray(value)) {
    return uniqueChannels(value)
  }

  const text = String(value || "").trim()
  if (!text) return []

  try {
    const parsed = JSON.parse(text)
    if (Array.isArray(parsed)) return uniqueChannels(parsed)
  } catch {
    // fall through
  }

  return uniqueChannels(text.split(/[\n,锛孿s]+/))
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
    return uniqueStrings(String(value || "").split(/[\n,锛孿s]+/))
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

function updateTemplateField({ key, value }) {
  if (Object.prototype.hasOwnProperty.call(localForm, key)) {
    localForm[key] = value
  }
}
</script>

<style scoped>
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

.form-section.dense {
  padding-bottom: 4px;
}

.section-title {
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.form-grid {
  display: grid;
  gap: 10px 12px;
}

.form-grid.two {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.form-grid.four {
  grid-template-columns: repeat(4, minmax(0, 1fr));
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

@media (max-width: 900px) {
  .section-row,
  .form-grid.two,
  .form-grid.four {
    grid-template-columns: 1fr;
  }
}
</style>

