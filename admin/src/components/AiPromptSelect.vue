<template>
  <div class="ai-prompt-select">
    <el-select
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

    <div class="field-help">
      选择“系统默认提示词”时，会自动跟随 AI 配置中的默认项；以后修改默认提示词，无需逐个修改任务。
    </div>
  </div>
</template>

<script setup>
import { computed } from "vue"

const props = defineProps({
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

const emit = defineEmits(["update:modelValue"])

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

.field-help {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.6;
}
</style>
