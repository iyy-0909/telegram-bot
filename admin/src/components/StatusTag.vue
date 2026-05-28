<template>
  <el-tag :type="tag.type" :size="size" :effect="effect">
    {{ tag.label }}
  </el-tag>
</template>

<script setup>
import { computed } from "vue"

const props = defineProps({
  status: {
    type: [String, Boolean, Number],
    default: "unknown",
  },
  size: {
    type: String,
    default: "small",
  },
  effect: {
    type: String,
    default: "light",
  },
  labels: {
    type: Object,
    default: () => ({}),
  },
})

const STATUS_MAP = {
  enabled: { label: "正常", type: "success" },
  disabled: { label: "已禁用", type: "info" },
  error: { label: "异常", type: "danger" },
  pending: { label: "待处理", type: "warning" },
  running: { label: "运行中", type: "success" },
  stopped: { label: "已停止", type: "info" },
  blocked: { label: "已拉黑", type: "danger" },
  unknown: { label: "未知", type: "info" },
  idle: { label: "空闲", type: "info" },
  paused: { label: "已暂停", type: "warning" },
  done: { label: "已完成", type: "success" },
  success: { label: "成功", type: "success" },
  failed: { label: "失败", type: "danger" },
  empty: { label: "空内容", type: "warning" },
  filtered: { label: "过滤", type: "warning" },
  deduped: { label: "去重", type: "warning" },
  sending: { label: "发送中", type: "primary" },
  prepared: { label: "准备", type: "primary" },
  received: { label: "收到", type: "primary" },
  account_error: { label: "账号异常", type: "danger" },
  bot_error: { label: "Bot 异常", type: "danger" },
  permission_error: { label: "权限异常", type: "danger" },
}

const tag = computed(() => {
  const key = normalizeStatus(props.status)
  const customLabel = props.labels[key]
  const item = STATUS_MAP[key] || { label: key || STATUS_MAP.unknown.label, type: "info" }

  return {
    ...item,
    label: customLabel || item.label,
  }
})

function normalizeStatus(value) {
  if (value === true) return "enabled"
  if (value === false) return "disabled"
  const text = String(value || "unknown").trim()
  return text || "unknown"
}
</script>
