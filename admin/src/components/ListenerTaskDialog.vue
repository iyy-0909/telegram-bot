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

        <div class="switch-row">
          <span>删除旧联系方式</span>
          <el-switch v-model="localForm.remove_contact_lines" />
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
  replace_words: "{}",
  footer: "",
  remove_contact_lines: true,
  use_random_head: false,
  use_random_body: false,
  use_random_footer: false,
  selected_head_template_group_id: null,
  selected_body_template_group_id: null,
  selected_footer_template_group_id: null,
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

watch(
  () => props.form,
  (val) => {
    if (!val) return
    Object.assign(localForm, {
      ...val,
      target_channels: JSON.stringify(uniqueChannels(parseChannelItems(val.target_channels || "[]"))),
      blocked_keywords: normalizeJsonArrayString(val.blocked_keywords || "[]"),
      use_random_head: val.use_random_head ?? false,
      use_random_body: val.use_random_body ?? false,
      use_random_footer: val.use_random_footer ?? false,
      selected_head_template_group_id: normalizeTemplateId(val.selected_head_template_group_id),
      selected_body_template_group_id: normalizeTemplateId(val.selected_body_template_group_id),
      selected_footer_template_group_id: normalizeTemplateId(val.selected_footer_template_group_id),
      selected_head_template_id: normalizeTemplateId(val.selected_head_template_id),
      selected_body_template_id: normalizeTemplateId(val.selected_body_template_id),
      selected_footer_template_id: normalizeTemplateId(val.selected_footer_template_id),
      selected_filter_template_group_id: normalizeTemplateId(val.selected_filter_template_group_id),
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
    replace_words: task.replace_words || "{}",
    footer: "",
    remove_contact_lines: task.remove_contact_lines ?? true,
    use_random_head: task.use_random_head ?? false,
    use_random_body: task.use_random_body ?? false,
    use_random_footer: task.use_random_footer ?? false,
    selected_head_template_group_id: normalizeTemplateId(task.selected_head_template_group_id),
    selected_body_template_group_id: normalizeTemplateId(task.selected_body_template_group_id),
    selected_footer_template_group_id: normalizeTemplateId(task.selected_footer_template_group_id),
    selected_head_template_id: normalizeTemplateId(task.selected_head_template_id),
    selected_body_template_id: normalizeTemplateId(task.selected_body_template_id),
    selected_footer_template_id: normalizeTemplateId(task.selected_footer_template_id),
    selected_filter_template_group_id: normalizeTemplateId(task.selected_filter_template_group_id),
    album_wait_seconds: toPositiveNumber(task.album_wait_seconds, 3),
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
    footer: "",
    selected_filter_template_group_id: normalizeTemplateId(localForm.selected_filter_template_group_id),
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
  .form-grid.two {
    grid-template-columns: 1fr;
  }
}
</style>
