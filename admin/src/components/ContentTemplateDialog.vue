<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="isEdit ? '编辑内容模板规则' : '添加内容模板规则'"
    width="780px"
  >
    <el-form label-width="110px">
      <el-form-item label="规则类型">
        <el-select v-model="localForm.type">
          <el-option label="头部 head" value="head" />
          <el-option label="正文 body" value="body" />
          <el-option label="底部 footer" value="footer" />
          <el-option label="过滤关键词 filter" value="filter" />
          <el-option label="链接配置 link" value="link" />
        </el-select>
      </el-form-item>

      <el-form-item label="规则名称">
        <el-input
          v-model="localForm.name"
          placeholder="例如 A规则 / 上海footer / 通用过滤词"
        />
      </el-form-item>

      <el-form-item label="启用">
        <el-switch v-model="localForm.enabled" />
      </el-form-item>

      <el-divider content-position="left">{{ contentTitle }}</el-divider>

      <el-descriptions
        v-if="localForm.type === 'link'"
        :column="1"
        border
        class="link-rules-descriptions"
      >
        <el-descriptions-item
          v-for="field in linkRuleFields"
          :key="field.key"
          :label="field.label"
        >
          <div class="link-rule-control">
            <el-select v-model="linkConfig[field.key]" class="link-action-select">
              <el-option
                v-for="option in linkActionOptionsFor(field.key)"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
            <el-input
              v-if="linkConfig[field.key] === 'replace'"
              v-model="linkConfig[replacementKey(field.key)]"
              class="link-replacement-input"
              placeholder="替换为，例如 https://t.me/username"
              clearable
            />
          </div>
        </el-descriptions-item>
      </el-descriptions>

      <div v-else class="content-list">
        <div
          v-for="(item, index) in localForm.items"
          :key="item.local_key"
          class="content-item"
        >
          <div class="content-item-head">
            <span>{{ localForm.type === "filter" ? "关键词组" : "内容" }} {{ index + 1 }}</span>
            <div class="content-actions">
              <el-switch v-model="item.enabled" active-text="启用" />
              <el-input-number
                v-model="item.weight"
                :min="1"
                :step="1"
                controls-position="right"
                class="weight-input"
              />
              <el-button type="danger" text @click="removeItem(index)">
                删除
              </el-button>
            </div>
          </div>

          <div v-if="showRichToolbar" class="rich-toolbar">
            <el-button-group>
              <el-tooltip
                v-for="action in primaryFormatActions"
                :key="action.key"
                :content="action.label"
                placement="top"
              >
                <el-button
                  size="small"
                  @click="applyFormat(index, action)"
                >
                  {{ action.shortLabel }}
                </el-button>
              </el-tooltip>
            </el-button-group>

            <el-dropdown trigger="click" @command="(key) => applyFormatByKey(index, key)">
              <el-button size="small">
                更多格式
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item
                    v-for="action in moreFormatActions"
                    :key="action.key"
                    :command="action.key"
                  >
                    {{ action.label }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>

            <el-button size="small" @click="clearHtmlTags(index)">
              清除格式
            </el-button>
          </div>

          <el-input
            :ref="(el) => setTextareaRef(el, index)"
            v-model="item.content"
            type="textarea"
            :rows="localForm.type === 'filter' ? 5 : 4"
            :placeholder="contentPlaceholder"
          />
        </div>
      </div>

      <el-button v-if="localForm.type !== 'link'" class="add-content-button" @click="addItem">
        添加一条{{ localForm.type === "filter" ? "关键词组" : "内容" }}
      </el-button>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:visible', false)">取消</el-button>
      <el-button type="primary" @click="submit">保存规则</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, nextTick, reactive, watch } from "vue"

const props = defineProps({
  visible: Boolean,
  form: Object,
  isEdit: Boolean,
})

const emit = defineEmits(["update:visible", "submit"])

let localKeySeed = 1

const textareaRefs = reactive({})

const localForm = reactive({
  id: null,
  name: "",
  type: "footer",
  enabled: true,
  items: [],
})

const DEFAULT_LINK_CONFIG = {
  source_message_link: "target_link",
  missing_mapping: "downgrade",
  missing_mapping_replacement: "",
  target_channel_link: "keep",
  target_channel_link_replacement: "",
  external_channel_link: "downgrade",
  external_channel_link_replacement: "",
  username_link: "downgrade",
  username_link_replacement: "",
  bot_link: "downgrade",
  bot_link_replacement: "",
  external_url: "downgrade",
  external_url_replacement: "",
  invite_link: "downgrade",
  invite_link_replacement: "",
  source_message_link_replacement: "",
}

const linkActionOptions = [
  { label: "目标链接", value: "target_link" },
  { label: "降级文本", value: "downgrade" },
  { label: "保留", value: "keep" },
  { label: "直接删除", value: "delete" },
  { label: "替换链接", value: "replace" },
]

const linkConfig = reactive({ ...DEFAULT_LINK_CONFIG })

const linkRuleFields = [
  { key: "source_message_link", label: "源频道内部消息链接" },
  { key: "missing_mapping", label: "找不到映射时" },
  { key: "target_channel_link", label: "目标频道链接" },
  { key: "external_channel_link", label: "外部频道链接" },
  { key: "username_link", label: "用户名链接" },
  { key: "bot_link", label: "Bot 链接" },
  { key: "external_url", label: "普通外部网址" },
  { key: "invite_link", label: "邀请链接" },
]

const primaryFormatActions = [
  {
    key: "bold",
    label: "加粗",
    shortLabel: "B",
    prefix: "<b>",
    suffix: "</b>",
    sample: "加粗文字",
  },
  {
    key: "italic",
    label: "斜体",
    shortLabel: "I",
    prefix: "<i>",
    suffix: "</i>",
    sample: "斜体文字",
  },
  {
    key: "underline",
    label: "下划线",
    shortLabel: "U",
    prefix: "<u>",
    suffix: "</u>",
    sample: "下划线文字",
  },
  {
    key: "strike",
    label: "删除线",
    shortLabel: "S",
    prefix: "<s>",
    suffix: "</s>",
    sample: "删除线文字",
  },
  {
    key: "code",
    label: "行内代码",
    shortLabel: "code",
    prefix: "<code>",
    suffix: "</code>",
    sample: "代码",
  },
]

const moreFormatActions = [
  {
    key: "spoiler",
    label: "隐藏剧透",
    prefix: "<tg-spoiler>",
    suffix: "</tg-spoiler>",
    sample: "隐藏文字",
  },
  {
    key: "link",
    label: "链接模板",
    prefix: '<a href="https://t.me/username">',
    suffix: "</a>",
    sample: "点击联系",
  },
  {
    key: "pre",
    label: "预格式文本",
    prefix: "<pre>",
    suffix: "</pre>",
    sample: "预格式文本",
  },
  {
    key: "quote",
    label: "引用",
    prefix: "<blockquote>",
    suffix: "</blockquote>",
    sample: "引用内容",
  },
]

const allFormatActions = [
  ...primaryFormatActions,
  ...moreFormatActions,
]

const contentTitle = computed(() => (
  localForm.type === "filter"
    ? "过滤关键词"
    : localForm.type === "link"
      ? "链接处理配置"
      : "规则内容"
))

const contentPlaceholder = computed(() => (
  localForm.type === "filter"
    ? "每行填写一个过滤关键词。任务选择该规则后，任意关键词命中都会跳过整条内容。"
    : "填写这条模板内容，可使用上方富文本格式按钮插入 Telegram HTML 标签。"
))

const showRichToolbar = computed(() => !["filter", "link"].includes(localForm.type))

function linkActionOptionsFor(fieldKey) {
  return linkActionOptions
}

function replacementKey(fieldKey) {
  return `${fieldKey}_replacement`
}

watch(
  () => props.form,
  (val) => {
    if (!val) return

    Object.assign(localForm, {
      id: val.id || null,
      name: val.name || "",
      type: val.type || "footer",
      enabled: val.enabled ?? true,
      items: normalizeItems(val.items || []),
    })

    if (!localForm.items.length) {
      addItem()
    }

    Object.assign(linkConfig, parseLinkConfig(localForm.items[0]?.content))
  },
  { immediate: true, deep: true },
)

function addItem() {
  localForm.items.push({
    id: null,
    local_key: localKeySeed++,
    content: "",
    enabled: true,
    weight: 1,
  })
}

function removeItem(index) {
  localForm.items.splice(index, 1)
  delete textareaRefs[index]

  if (!localForm.items.length) {
    addItem()
  }
}

function setTextareaRef(el, index) {
  if (el) {
    textareaRefs[index] = el
  }
}

function getTextarea(index) {
  const input = textareaRefs[index]
  return input?.textarea || input?.$refs?.textarea || null
}

function applyFormatByKey(index, key) {
  const action = allFormatActions.find((item) => item.key === key)

  if (action) {
    applyFormat(index, action)
  }
}

async function applyFormat(index, action) {
  const item = localForm.items[index]

  if (!item) return

  const textarea = getTextarea(index)
  const value = item.content || ""
  const start = textarea?.selectionStart ?? value.length
  const end = textarea?.selectionEnd ?? value.length
  const selected = value.slice(start, end)
  const innerText = selected || action.sample
  const wrapped = `${action.prefix}${innerText}${action.suffix}`

  item.content = `${value.slice(0, start)}${wrapped}${value.slice(end)}`

  await nextTick()

  const nextTextarea = getTextarea(index)

  if (nextTextarea) {
    const selectStart = start + action.prefix.length
    const selectEnd = selectStart + innerText.length
    nextTextarea.focus()
    nextTextarea.setSelectionRange(selectStart, selectEnd)
  }
}

async function clearHtmlTags(index) {
  const item = localForm.items[index]

  if (!item) return

  item.content = (item.content || "").replace(/<\/?[^>]+>/g, "")

  await nextTick()
  getTextarea(index)?.focus()
}

function submit() {
  const items = localForm.type === "link"
    ? [{
        id: normalizeTemplateId(localForm.items[0]?.id),
        name: "链接配置",
        content: JSON.stringify(normalizeLinkConfig(linkConfig), null, 2),
        enabled: true,
        weight: 1,
      }]
    : localForm.items.map((item, index) => ({
        id: normalizeTemplateId(item.id),
        name: `${localForm.type === "filter" ? "关键词组" : "内容"} ${index + 1}`,
        content: item.content || "",
        enabled: item.enabled ?? true,
        weight: toPositiveNumber(item.weight, 1),
      }))

  emit("submit", {
    id: localForm.id,
    name: (localForm.name || "").trim(),
    type: localForm.type,
    enabled: localForm.enabled,
    items,
  })
}

function parseLinkConfig(value) {
  try {
    return normalizeLinkConfig(JSON.parse(value || "{}"))
  } catch {
    return { ...DEFAULT_LINK_CONFIG }
  }
}

function normalizeLinkConfig(value) {
  const allowed = new Set(linkActionOptions.map((option) => option.value))
  const result = { ...DEFAULT_LINK_CONFIG }

  for (const field of linkRuleFields) {
    const nextValue = value?.[field.key]
    if (allowed.has(nextValue)) {
      result[field.key] = nextValue
    }
  }

  for (const field of linkRuleFields) {
    const key = replacementKey(field.key)
    result[key] = result[field.key] === "replace"
      ? String(value?.[key] || "").trim()
      : ""
  }

  return result
}

function normalizeItems(items) {
  return (items || []).map((item) => ({
    id: normalizeTemplateId(item.id),
    local_key: localKeySeed++,
    content: item.content || "",
    enabled: item.enabled ?? true,
    weight: toPositiveNumber(item.weight, 1),
  }))
}

function normalizeTemplateId(value) {
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
.content-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.content-item {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 12px;
  background: #fafafa;
}

.content-item-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
}

.content-actions,
.rich-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.content-actions {
  flex-wrap: wrap;
  justify-content: flex-end;
}

.rich-toolbar {
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.weight-input {
  width: 96px;
}

.add-content-button {
  margin-top: 12px;
}

.link-rules-descriptions :deep(.el-descriptions__label) {
  width: 180px;
  white-space: nowrap;
}

.link-rule-control {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-width: 0;
}

.link-action-select {
  width: 150px;
  flex: 0 0 150px;
}

.link-replacement-input {
  min-width: 260px;
  flex: 1 1 320px;
}

@media (max-width: 820px) {
  .link-rule-control {
    align-items: stretch;
    flex-direction: column;
    gap: 8px;
  }

  .link-action-select,
  .link-replacement-input {
    width: 100%;
    min-width: 0;
    flex: none;
  }
}
</style>
