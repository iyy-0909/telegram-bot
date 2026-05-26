<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="isEdit ? '编辑监听任务' : '新增监听任务'"
    width="860px"
  >
    <el-form label-width="150px">
      <el-form-item v-if="!isEdit" label="复制已有任务">
        <el-select
          v-model="copyTaskId"
          clearable
          filterable
          placeholder="可选择一条已有监听任务作为模板"
          @change="applyCopyTask"
        >
          <el-option
            v-for="task in copyableTasks"
            :key="task.id"
            :label="copyTaskLabel(task)"
            :value="task.id"
          />
        </el-select>
        <div class="field-tip">
          仅复制规则配置，不复制任务 ID 和运行状态。复制后可以继续修改。
        </div>
      </el-form-item>

      <el-form-item label="任务名称">
        <el-input v-model="localForm.name" placeholder="例如 上海频道实时监听" />
      </el-form-item>

      <el-form-item>
        <template #label>
          <div class="field-label">
            <span>源频道</span>
            <el-tooltip content="添加源频道" placement="top">
              <el-button
                class="add-channel-button"
                type="primary"
                circle
                @click="addSourceChannel"
              >
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
              placeholder="例如 @source_channel"
              clearable
            />
            <el-button
              :disabled="sourceChannels.length <= 1"
              @click="removeSourceChannel(index)"
            >
              删除
            </el-button>
          </div>
        </div>
      </el-form-item>

      <el-form-item>
        <template #label>
          <div class="field-label">
            <span>目标频道</span>
          </div>
        </template>
        <ChannelSelect
          v-model="targetChannels"
          multiple
          include-disabled
          :bot-id="localForm.bot_id"
          placeholder="请选择目标频道"
        />
      </el-form-item>

      <el-form-item label="监听账号">
        <el-select v-model="localForm.account_id" filterable>
          <el-option
            v-for="account in accounts"
            :key="account.id"
            :label="`${account.id} - ${account.name}`"
            :value="account.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="分发 Bot">
        <el-select
          v-model="localForm.bot_id"
          placeholder="请选择分发 Bot"
          clearable
          filterable
        >
          <el-option
            v-for="bot in enabledBots()"
            :key="bot.id"
            :label="`${bot.name} (#${bot.id})`"
            :value="bot.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="过滤关键词">
        <el-input
          v-model="localForm.blocked_keywords"
          type="textarea"
          :rows="3"
          placeholder='例如 ["广告","推广"]'
        />
      </el-form-item>

      <el-form-item label="替换词">
        <ReplaceRulesEditor v-model="localForm.replace_words" />
      </el-form-item>

      <el-form-item label="删除旧联系方式">
        <el-switch v-model="localForm.remove_contact_lines" />
      </el-form-item>

      <el-divider content-position="left">内容模板规则</el-divider>

      <el-form-item label="启用 head">
        <div class="template-row">
          <el-switch v-model="localForm.use_random_head" />
          <el-select
            v-model="localForm.selected_head_template_group_id"
            :disabled="!localForm.use_random_head"
            placeholder="选择规则"
            clearable
            class="template-select"
            @change="localForm.selected_head_template_id = null"
          >
            <el-option
              v-for="group in enabledTemplateGroupsByType('head')"
              :key="group.id"
              :label="templateLabel(group)"
              :value="group.id"
            />
          </el-select>
          <el-select
            v-model="localForm.selected_head_template_id"
            :disabled="!localForm.use_random_head || !localForm.selected_head_template_group_id"
            placeholder="规则内随机"
            clearable
            class="template-select"
          >
            <el-option label="规则内随机" :value="null" />
            <el-option
              v-for="template in enabledTemplateItemsByGroup('head', localForm.selected_head_template_group_id)"
              :key="template.id"
              :label="templateLabel(template)"
              :value="template.id"
            />
          </el-select>
        </div>
      </el-form-item>

      <el-form-item label="启用 body">
        <div class="template-row">
          <el-switch v-model="localForm.use_random_body" />
          <el-select
            v-model="localForm.selected_body_template_group_id"
            :disabled="!localForm.use_random_body"
            placeholder="选择规则"
            clearable
            class="template-select"
            @change="localForm.selected_body_template_id = null"
          >
            <el-option
              v-for="group in enabledTemplateGroupsByType('body')"
              :key="group.id"
              :label="templateLabel(group)"
              :value="group.id"
            />
          </el-select>
          <el-select
            v-model="localForm.selected_body_template_id"
            :disabled="!localForm.use_random_body || !localForm.selected_body_template_group_id"
            placeholder="规则内随机"
            clearable
            class="template-select"
          >
            <el-option label="规则内随机" :value="null" />
            <el-option
              v-for="template in enabledTemplateItemsByGroup('body', localForm.selected_body_template_group_id)"
              :key="template.id"
              :label="templateLabel(template)"
              :value="template.id"
            />
          </el-select>
        </div>
      </el-form-item>

      <el-form-item label="启用 footer">
        <div class="template-row">
          <el-switch v-model="localForm.use_random_footer" />
          <el-select
            v-model="localForm.selected_footer_template_group_id"
            :disabled="!localForm.use_random_footer"
            placeholder="选择规则"
            clearable
            class="template-select"
            @change="localForm.selected_footer_template_id = null"
          >
            <el-option
              v-for="group in enabledTemplateGroupsByType('footer')"
              :key="group.id"
              :label="templateLabel(group)"
              :value="group.id"
            />
          </el-select>
          <el-select
            v-model="localForm.selected_footer_template_id"
            :disabled="!localForm.use_random_footer || !localForm.selected_footer_template_group_id"
            placeholder="规则内随机"
            clearable
            class="template-select"
          >
            <el-option label="规则内随机" :value="null" />
            <el-option
              v-for="template in enabledTemplateItemsByGroup('footer', localForm.selected_footer_template_group_id)"
              :key="template.id"
              :label="templateLabel(template)"
              :value="template.id"
            />
          </el-select>
        </div>
      </el-form-item>

      <el-form-item label="启用">
        <el-switch v-model="localForm.enabled" />
      </el-form-item>
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
import ChannelSelect from "./ChannelSelect.vue"
import ReplaceRulesEditor from "./ReplaceRulesEditor.vue"

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
  album_wait_seconds: 3,
})

const sourceChannels = ref([""])
const targetChannels = ref([""])
const copyTaskId = ref(null)
const copyableTasks = computed(() => props.existingTasks.filter((task) => task?.id))

watch(
  () => props.form,
  (val) => {
    if (!val) return
    Object.assign(localForm, {
      ...val,
      use_random_head: val.use_random_head ?? false,
      use_random_body: val.use_random_body ?? false,
      use_random_footer: val.use_random_footer ?? false,
      selected_head_template_group_id: normalizeTemplateId(val.selected_head_template_group_id),
      selected_body_template_group_id: normalizeTemplateId(val.selected_body_template_group_id),
      selected_footer_template_group_id: normalizeTemplateId(val.selected_footer_template_group_id),
      selected_head_template_id: normalizeTemplateId(val.selected_head_template_id),
      selected_body_template_id: normalizeTemplateId(val.selected_body_template_id),
      selected_footer_template_id: normalizeTemplateId(val.selected_footer_template_id),
    })
    sourceChannels.value = normalizeChannelItems(
      val.source_channels || val.source_channel || "",
    )
    targetChannels.value = normalizeChannelItems(val.target_channels || "[]")
    copyTaskId.value = null
  },
  { immediate: true, deep: true },
)

function applyCopyTask(taskId) {
  const task = props.existingTasks.find((item) => Number(item.id) === Number(taskId))

  if (!task) {
    return
  }

  Object.assign(localForm, {
    id: null,
    name: task.name ? `${task.name} 副本` : "",
    source_channel: task.source_channel || "",
    target_channels: task.target_channels || "[]",
    account_id: toPositiveNumber(task.account_id, props.accounts[0]?.id || 1),
    bot_id: normalizeBotId(task.bot_id),
    enabled: true,
    status: "running",
    blocked_keywords: task.blocked_keywords || "[]",
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
    album_wait_seconds: toPositiveNumber(task.album_wait_seconds, 3),
  })

  sourceChannels.value = normalizeChannelItems(task.source_channel || "")
  targetChannels.value = normalizeChannelItems(task.target_channels || "[]")
}

function copyTaskLabel(task) {
  const source = task.source_channel || "-"
  const targets = normalizeChannelItems(task.target_channels || "[]").join(", ") || "-"
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

function addTargetChannel() {
  targetChannels.value.push("")
}

function removeTargetChannel(index) {
  targetChannels.value.splice(index, 1)
  if (!targetChannels.value.length) {
    targetChannels.value.push("")
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
    footer: "",
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

function enabledBots() {
  return props.bots.filter((bot) => bot.enabled)
}

function enabledTemplateGroupsByType(type) {
  return props.templates.filter(
    (template) => template.type === type && template.enabled && !template.parent_id,
  )
}

function enabledTemplateItemsByGroup(type, groupId) {
  return props.templates.filter(
    (template) => (
      template.type === type
      && template.enabled
      && template.parent_id === groupId
      && (template.content || "").trim()
    ),
  )
}

function templateLabel(template) {
  return template.name || `模板 ${template.id}`
}

function normalizeChannelItems(value) {
  let items = []

  if (Array.isArray(value)) {
    items = value
  } else if (typeof value === "string") {
    const text = value.trim()

    if (text.startsWith("[") && text.endsWith("]")) {
      try {
        const parsed = JSON.parse(text)
        items = Array.isArray(parsed) ? parsed : [text]
      } catch {
        items = [text]
      }
    } else {
      items = text.split(/[\n,，]/)
    }
  }

  const normalized = uniqueChannels(items)
  return normalized.length ? normalized : [""]
}

function uniqueChannels(items) {
  const seen = new Set()
  const result = []

  for (const item of items || []) {
    const channel = String(item || "").trim()

    if (!channel || seen.has(channel)) {
      continue
    }

    seen.add(channel)
    result.push(channel)
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
  if (value === null || value === undefined || value === "") {
    return null
  }

  const numberValue = Number(value)
  return Number.isInteger(numberValue) && numberValue > 0 ? numberValue : null
}

function toPositiveNumber(value, fallback) {
  const numberValue = Number(value)

  if (!Number.isFinite(numberValue) || numberValue < 1) {
    return fallback
  }

  return Math.floor(numberValue)
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

.template-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  width: 100%;
}

.template-select {
  max-width: 260px;
  width: 100%;
}

.field-tip {
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
  line-height: 1.4;
}
</style>
