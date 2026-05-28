<template>
  <button
    v-if="displayText"
    class="copy-text"
    :class="toneClass"
    type="button"
    :title="displayText"
    @click="handleCopy"
  >
    <span>{{ displayText }}</span>
    <el-icon class="copy-icon"><CopyDocument /></el-icon>
  </button>
  <span v-else class="copy-empty">-</span>
</template>

<script setup>
import { computed } from "vue"
import { ElMessage } from "element-plus"
import { CopyDocument } from "@element-plus/icons-vue"
import { copyText } from "../utils/clipboard"

const props = defineProps({
  value: {
    type: [String, Number],
    default: "",
  },
  text: {
    type: [String, Number],
    default: "",
  },
  tone: {
    type: String,
    default: "default",
  },
  successMessage: {
    type: String,
    default: "已复制",
  },
})

const displayText = computed(() => String(props.text || props.value || "").trim())
const copyValue = computed(() => String(props.value || props.text || "").trim())
const toneClass = computed(() => (props.tone ? `copy-text--${props.tone}` : ""))

async function handleCopy() {
  if (!copyValue.value || copyValue.value === "-") return

  try {
    const ok = await copyText(copyValue.value)
    if (!ok) throw new Error("copy failed")
    ElMessage.success(props.successMessage)
  } catch {
    ElMessage.error("复制失败")
  }
}
</script>

<style scoped>
.copy-text {
  appearance: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 100%;
  margin: 0;
  padding: 3px 9px;
  border: 1px solid #dcdfe6;
  border-radius: 999px;
  color: inherit;
  background: #ffffff;
  font: inherit;
  text-align: left;
  cursor: pointer;
  vertical-align: middle;
  transition: border-color 0.15s ease, background-color 0.15s ease, color 0.15s ease;
}

.copy-text:hover {
  border-color: #409eff;
  background: #ecf5ff;
  color: #409eff;
}

.copy-text span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.copy-icon {
  flex: 0 0 auto;
  font-size: 13px;
  opacity: 0.75;
}

.copy-text--primary {
  color: #409eff;
}

.copy-text--success {
  color: #67c23a;
}

.copy-text--danger {
  color: #f56c6c;
}

.copy-empty {
  color: #909399;
}
</style>
