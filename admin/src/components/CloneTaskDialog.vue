<template>
  <el-dialog
    :model-value="visible"
    @update:model-value="$emit('update:visible', $event)"
    :title="isEdit ? '编辑克隆任务' : '新增克隆任务'"
    width="820px"
  >
    <el-form label-width="160px">
      <el-form-item label="任务名称">
        <el-input v-model="localForm.name" placeholder="例如 杭州频道克隆" />
      </el-form-item>

      <el-form-item label="源频道">
        <el-input v-model="localForm.source_channel" placeholder="例如 @HZKTV_XZ" />
      </el-form-item>

      <el-form-item label="源频道开始内容链接">
        <el-input
          v-model="localForm.start_message_url"
          placeholder="为空则从第一条可读取内容开始，例如 https://t.me/channel/123"
        />
      </el-form-item>

      <el-form-item label="源频道结束内容链接">
        <el-input
          v-model="localForm.end_message_url"
          placeholder="为空则克隆到当前最后一条，例如 https://t.me/channel/456"
        />
      </el-form-item>

      <el-form-item label="目标频道">
        <ChannelSelect
          v-model="targetChannelValues"
          multiple
          include-disabled
          :bot-id="localForm.bot_id"
          placeholder="请选择目标频道"
        />
      </el-form-item>

      <el-form-item label="账号ID">
        <el-input-number v-model="localForm.account_id" :min="1" />
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

      <el-form-item label="内容间隔分钟">
        <el-input-number v-model="localForm.single_delay" :min="1" :step="1" />
      </el-form-item>

      <el-form-item label="目标间隔秒">
        <el-input-number v-model="localForm.target_delay" :min="1" :step="1" />
      </el-form-item>

      <el-form-item label="过滤关键词">
        <el-input
          v-model="localForm.blocked_keywords"
          type="textarea"
          :rows="3"
          placeholder='例如 ["广告","加微信"]'
        />
      </el-form-item>

      <el-form-item label="替换词">
        <ReplaceRulesEditor v-model="localForm.replace_words" />
      </el-form-item>

      <el-form-item label="删除旧联系方式">
        <el-switch v-model="localForm.remove_contact_lines" />
      </el-form-item>

      <!-- 旧 Footer 功能已停用。保留字段兼容旧数据，请使用内容模板规则里的 footer。 -->
      <!--
      <el-form-item label="旧 Footer">
        <el-input v-model="localForm.footer" type="textarea" :rows="3" />
      </el-form-item>
      -->

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

      <el-form-item label="启用监听">
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
import { computed, reactive, watch } from "vue"
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
  templates: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(["update:visible", "submit"])

const targetChannelValues = computed({
  get() {
    return parseChannels(localForm.target_channels)
  },
  set(value) {
    localForm.target_channels = JSON.stringify(uniqueChannels(value))
  },
})

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
  status: "idle",
  last_message_id: 0,
  remove_contact_lines: true,
})

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
  },
  { immediate: true, deep: true },
)

function submit() {
  emit("submit", {
    ...localForm,
    start_message_url: (localForm.start_message_url || "").trim(),
    end_message_url: (localForm.end_message_url || "").trim(),
    account_id: toPositiveNumber(localForm.account_id, 1),
    bot_id: normalizeBotId(localForm.bot_id),
    single_delay: toPositiveNumber(localForm.single_delay, 3),
    target_delay: toPositiveNumber(localForm.target_delay, 2),
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

function enabledBots() {
  return props.bots.filter((bot) => bot.enabled)
}

function templateLabel(template) {
  return template.name || `模板 ${template.id}`
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

function parseChannels(value) {
  if (Array.isArray(value)) {
    return uniqueChannels(value)
  }

  const text = String(value || "").trim()

  if (!text) {
    return []
  }

  try {
    const parsed = JSON.parse(text)
    return Array.isArray(parsed) ? uniqueChannels(parsed) : []
  } catch {
    return uniqueChannels(text.split(/[\n,，]/))
  }
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
</style>
