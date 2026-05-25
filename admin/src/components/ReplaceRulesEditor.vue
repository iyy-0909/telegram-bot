<template>
  <div class="replace-rules-editor">
    <div
      v-for="(rule, index) in rules"
      :key="rule.id"
      class="rule-row"
    >
      <el-switch
        v-model="rule.enabled"
        @change="syncValue"
      />

      <el-select
        v-model="rule.type"
        class="rule-type"
        @change="syncValue"
      >
        <el-option label="替换文本" value="replace" />
        <el-option label="删除整行" value="delete_line" />
      </el-select>

      <el-input
        v-model="rule.match"
        class="rule-match"
        placeholder="命中文本"
        @input="syncValue"
      />

      <el-input
        v-if="rule.type === 'replace'"
        v-model="rule.value"
        class="rule-value"
        placeholder="替换为"
        @input="syncValue"
      />
      <div
        v-else
        class="rule-value"
      />

      <el-button
        type="danger"
        text
        @click="removeRule(index)"
      >
        删除
      </el-button>
    </div>

    <el-button
      type="primary"
      plain
      @click="addRule"
    >
      添加规则
    </el-button>
  </div>
</template>

<script setup>
import { ref, watch } from "vue"

const props = defineProps({
  modelValue: {
    type: String,
    default: "{}",
  },
})

const emit = defineEmits([
  "update:modelValue",
])

const rules = ref([])
const lastEmitted = ref("")

function createRule(data = {}) {
  return {
    id: `${Date.now()}-${Math.random()}`,
    type: data.type === "delete_line" ? "delete_line" : "replace",
    match: data.match || "",
    value: data.value || "",
    enabled: data.enabled !== false,
  }
}

function parseRules(value) {
  let parsed = {}

  try {
    parsed = JSON.parse(value || "{}")
  } catch {
    parsed = {}
  }

  if (Array.isArray(parsed.rules)) {
    return parsed.rules.map(createRule)
  }

  const items = []

  if (parsed.replace || parsed.delete_lines) {
    Object.entries(parsed.replace || {}).forEach(([match, replacement]) => {
      items.push(createRule({
        type: "replace",
        match,
        value: replacement,
      }))
    })

    ;(parsed.delete_lines || []).forEach((match) => {
      items.push(createRule({
        type: "delete_line",
        match,
      }))
    })

    return items
  }

  Object.entries(parsed || {}).forEach(([match, replacement]) => {
    items.push(createRule({
      type: "replace",
      match,
      value: replacement,
    }))
  })

  return items
}

function serializeRules() {
  return JSON.stringify(
    {
      version: 2,
      rules: rules.value
        .filter((rule) => rule.match && rule.match.trim())
        .map((rule) => ({
          type: rule.type,
          match: rule.match.trim(),
          value: rule.type === "replace" ? rule.value : "",
          enabled: rule.enabled !== false,
        })),
    },
    null,
    2,
  )
}

function syncValue() {
  const value = serializeRules()
  lastEmitted.value = value
  emit("update:modelValue", value)
}

function addRule() {
  rules.value.push(createRule())
  syncValue()
}

function removeRule(index) {
  rules.value.splice(index, 1)
  syncValue()
}

watch(
  () => props.modelValue,
  (value) => {
    if (value === lastEmitted.value) return

    rules.value = parseRules(value)
  },
  {
    immediate: true,
  },
)
</script>

<style scoped>
.replace-rules-editor {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.rule-row {
  align-items: center;
  display: grid;
  gap: 8px;
  grid-template-columns: 48px 112px minmax(150px, 1fr) minmax(140px, 1fr) 56px;
}

.rule-type,
.rule-match,
.rule-value {
  width: 100%;
}
</style>
