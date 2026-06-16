<template>
  <el-tag :type="statusType(status)" size="small" round>
    {{ label || status || "未知" }}
  </el-tag>
</template>

<script setup>
import { statusType } from "../utils/format"

defineProps({
  status: {
    type: [String, Boolean],
    default: "",
  },
  label: {
    type: String,
    default: "",
  },
})
</script>
