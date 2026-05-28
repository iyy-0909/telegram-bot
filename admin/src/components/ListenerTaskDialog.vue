<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="isEdit ? '编辑监听任务' : '新增监听任务'"
    width="880px"
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
          只复制规则配置，不复制任务 ID 和运行状态，复制后可以继续修改。
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
              placeholder="支持 @channel、chat_id、https://t.me/channel"
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
          placeholder="选择目标频道，也可手动输入 @username / chat_id / https://t.me/channel"
        />
      </el-form-item>

      <el-form-item label="监听账号">
        <el-select v-model="localForm.account_id" filterable>
          <el-option
            v-for="account in accounts"
            :key="account.id"
            :label="accountLabel(account)"
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

      <el-form-item label="通用过滤词">
        <el-select
          v-model="localForm.selected_filter_template_group_id"
          clearable
          filterable
          placeholder="选择内容模板规则里的过滤关键词"
        >
          <el-option
            v-for="group in enabledTemplateGroupsByType('filter')"
            :key="group.id"
            :label="templateLabel(group)"
            :value="group.id"
          />
        </el-select>
        <div class="field-tip">
          命中过滤词后整条内容会跳过，不再拼接模板。
        </div>
      </el-form-item>

      <el-form-item label="任务补充过滤词">
        <el-select
          v-model="blockedKeywordList"
          multiple
          filterable
          allow-create
          default-first-option
          placeholder="输入关键词后回车，可添加多个"
        >
          <el-option
            v-for="keyword in blockedKeywordList"
            :key="keyword"
            :label="keyword"
            :value="keyword"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="替换词">
        <ReplaceRulesEditor v-model="localForm.replace_words" />
      </el-form-item>

      <el-form-item label="删除旧联系方式">
        <el-switch v-model="localForm.remove_contact_lines" />
      </el-form-item>

      <el-divider content-position="left">内容模板规则</el-divider>

      <el-form-item label="启用 head">
        <TemplatePicker
          v-model:enabled="localForm.use_random_head"
          v-model:group-id="localForm.selected_head_template_group_id"
          v-model:item-id="localForm.selected_head_template_id"
          type="head"
          :templates="templates"
        />
      </el-form-item>

      <el-form-item label="启用 body">
        <TemplatePicker
          v-model:enabled="localForm.use_random_body"
          v-model:group-id="localForm.selected_body_template_group_id"
          v-model:item-id="localForm.selected_body_template_id"
          type="body"
          :templates="templates"
        />
      </el-form-item>

      <el-form-item label="启用 footer">
        <TemplatePicker
          v-model:enabled="localForm.use_random_footer"
          v-model:group-id="localForm.selected_footer_template_group_id"
          v-model:item-id="localForm.selected_footer_template_id"
          type="footer"
          :templates="templates"
        />
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
import { computed, defineComponent, h, reactive, ref, resolveComponent, watch } from "vue"
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

function accountLabel(account) {
  const username = account.username ? ` @${account.username}` : ""
  return `${account.id} - ${account.name}${username}`
}

function enabledBots() {
  return props.bots.filter((bot) => bot.enabled)
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
      items = text.split(/[\n,，]+/)
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
    return uniqueStrings(String(value || "").split(/[\n,，]+/))
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

const TemplatePicker = defineComponent({
  props: {
    enabled: Boolean,
    groupId: {
      type: [Number, String],
      default: null,
    },
    itemId: {
      type: [Number, String],
      default: null,
    },
    type: String,
    templates: {
      type: Array,
      default: () => [],
    },
  },
  emits: ["update:enabled", "update:groupId", "update:itemId"],
  setup(componentProps, { emit: componentEmit }) {
    const groups = computed(() => componentProps.templates.filter(
      (template) => (
        template.type === componentProps.type
        && template.enabled
        && !template.parent_id
      ),
    ))
    const items = computed(() => componentProps.templates.filter(
      (template) => (
        template.type === componentProps.type
        && template.enabled
        && Number(template.parent_id) === Number(componentProps.groupId)
        && (template.content || "").trim()
      ),
    ))

    return () => h("div", { class: "template-row" }, [
      h(resolveComponent("el-switch"), {
        modelValue: componentProps.enabled,
        "onUpdate:modelValue": (value) => componentEmit("update:enabled", value),
      }),
      h(resolveComponent("el-select"), {
        modelValue: componentProps.groupId,
        disabled: !componentProps.enabled,
        placeholder: "选择规则",
        clearable: true,
        class: "template-select",
        "onUpdate:modelValue": (value) => {
          componentEmit("update:groupId", value)
          componentEmit("update:itemId", null)
        },
      }, () => groups.value.map((group) => h(resolveComponent("el-option"), {
        key: group.id,
        label: group.name || `模板 ${group.id}`,
        value: group.id,
      }))),
      h(resolveComponent("el-select"), {
        modelValue: componentProps.itemId,
        disabled: !componentProps.enabled || !componentProps.groupId,
        placeholder: "规则内随机",
        clearable: true,
        class: "template-select",
        "onUpdate:modelValue": (value) => componentEmit("update:itemId", value),
      }, () => [
        h(resolveComponent("el-option"), {
          label: "规则内随机",
          value: null,
        }),
        ...items.value.map((item) => h(resolveComponent("el-option"), {
          key: item.id,
          label: item.name || `内容 ${item.id}`,
          value: item.id,
        })),
      ]),
    ])
  },
})
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
