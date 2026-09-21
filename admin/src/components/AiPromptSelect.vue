<template>
  <div class="ai-prompt-select">
    <el-select :model-value="mode" :disabled="disabled" aria-label="提示词模式" class="full-width" @update:model-value="emit('update:mode', $event)">
      <el-option label="固定提示词" value="fixed" />
      <el-option label="自动分析并匹配提示词" value="auto" />
    </el-select>
    <div v-if="mode === 'auto'" class="field-help">
      先分析源正文，再按类型改写，最后追加内容模板。通常需要两次 AI 调用。
      同类型采用最近保存且启用的提示词；未配置时采用内置规则，分类不明确时使用通用规则。
      <div v-for="category in aiContentTypes" :key="category.value" class="routing-line">
        <span>{{ category.label }}</span><span>{{ matchedName(category.value) }}</span>
      </div>
    </div>
    <el-select
      v-else
      v-model="selectValue"
      class="full-width"
      placeholder="系统默认提示词"
      :disabled="disabled"
    >
      <el-option :label="systemDefaultLabel" :value="0" />
      <el-option
        v-for="prompt in prompts"
        :key="prompt.id"
        :label="promptOptionLabel(prompt)"
        :value="prompt.id"
        :disabled="!prompt.enabled && Number(prompt.id) !== Number(selectValue)"
      />
    </el-select>

    <div v-if="mode !== 'auto'" class="field-help">
      选择“系统默认提示词”时，会自动跟随 AI 配置中的默认项；以后修改默认提示词，无需逐个修改任务。
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue"
import { aiContentTypes } from "../config/aiContentTypes"

const props = defineProps({
  mode: { type: String, default: "fixed" },
  modelValue: {
    type: [Number, String],
    default: null,
  },
  prompts: {
    type: Array,
    default: () => [],
  },
  disabled: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(["update:modelValue", "update:mode"])

function matchedName(category) {
  const candidates = props.prompts.filter((prompt) => prompt.enabled && prompt.content_type === category)
  candidates.sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)) || b.id - a.id)
  return candidates[0]?.name || "内置规则"
}

const defaultPrompt = computed(() => props.prompts.find((prompt) => prompt.is_default))

const systemDefaultLabel = computed(() => {
  const name = defaultPrompt.value?.name
  return name && name !== "系统默认提示词"
    ? `系统默认提示词（${name}）`
    : "系统默认提示词"
})

const selectValue = computed({
  get() {
    const id = Number(props.modelValue)
    return Number.isInteger(id) && id > 0 ? id : 0
  },
  set(value) {
    const id = Number(value)
    emit("update:modelValue", Number.isInteger(id) && id > 0 ? id : null)
  },
})

function promptOptionLabel(prompt) {
  const suffixes = []
  if (prompt.is_default) suffixes.push("默认")
  if (!prompt.enabled) suffixes.push("已停用")
  return suffixes.length ? `${prompt.name}（${suffixes.join("、")}）` : prompt.name
}
</script>

<style scoped>
.ai-prompt-select,
.full-width {
  width: 100%;
}

.full-width + .full-width { margin-top: 8px; }
.routing-line { display: flex; justify-content: space-between; gap: 12px; padding-top: 4px; }
.routing-line span:last-child { overflow-wrap: anywhere; text-align: right; }

.field-help {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.6;
}
</style>
