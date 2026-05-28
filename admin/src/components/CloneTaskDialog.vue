<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="isEdit ? '编辑克隆任务' : '新增克隆任务'"
    width="860px"
  >
    <el-form label-width="160px">
      <el-form-item label="任务名称">
        <el-input v-model="localForm.name" placeholder="例如 杭州频道克隆" />
      </el-form-item>

      <el-form-item label="源频道">
        <el-input
          v-model="localForm.source_channel"
          placeholder="支持 @channel、chat_id、https://t.me/channel"
        />
      </el-form-item>

      <el-form-item label="开始内容链接">
        <el-input
          v-model="localForm.start_message_url"
          placeholder="为空则从第一条可读取内容开始，例如 https://t.me/channel/123"
        />
      </el-form-item>

      <el-form-item label="结束内容链接">
        <el-input
          v-model="localForm.end_message_url"
          placeholder="为空则克隆到当前最后一条，例如 https://t.me/channel/456"
        />
      </el-form-item>

      <el-form-item label="分发 Bot">
        <el-select
          v-model="localForm.bot_id"
          placeholder="请先选择分发 Bot"
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

      <el-form-item label="目标频道">
        <ChannelSelect
          v-model="targetChannelValues"
          multiple
          include-disabled
          allow-create
          :bot-id="localForm.bot_id"
          placeholder="选择目标频道，也可手动输入 @username / chat_id / https://t.me/channel"
        />
        <div class="field-tip">
          先选择分发 Bot，再选择目标频道；下拉没有时可以直接输入并回车。
        </div>
      </el-form-item>

      <el-form-item label="采集账号">
        <el-input :model-value="collectorAccountLabel" disabled />
      </el-form-item>

      <el-form-item label="内容间隔分钟">
        <el-input-number v-model="localForm.single_delay" :min="1" :step="1" />
      </el-form-item>

      <el-form-item label="目标间隔秒">
        <el-input-number v-model="localForm.target_delay" :min="1" :step="1" />
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

      <el-form-item label="克隆完成后监听">
        <el-switch v-model="localForm.enable_listener" />
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
import { computed, defineComponent, h, reactive, resolveComponent, watch } from "vue"
import ChannelSelect from "./ChannelSelect.vue"
import ReplaceRulesEditor from "./ReplaceRulesEditor.vue"

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
    return "暂无可用采集账号"
  }

  const username = collectorAccount.value.username ? ` @${collectorAccount.value.username}` : ""
  return `${collectorAccount.value.id} - ${collectorAccount.value.name || "采集账号"}${username}`
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
      selected_head_template_id: normalizeTemplateId(val.selected_head_template_id),
      selected_body_template_id: normalizeTemplateId(val.selected_body_template_id),
      selected_footer_template_id: normalizeTemplateId(val.selected_footer_template_id),
      selected_filter_template_group_id: normalizeTemplateId(val.selected_filter_template_group_id),
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

function enabledBots() {
  return props.bots.filter((bot) => bot.enabled)
}

function templateLabel(template) {
  return template.name || `模板 ${template.id}`
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

  return uniqueChannels(text.split(/[\n,，]+/))
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
