<template>
  <el-tooltip
    v-if="message"
    :content="message"
    placement="top"
    effect="dark"
  >
    <span class="error-text">{{ message }}</span>
  </el-tooltip>
  <span v-else class="error-empty">-</span>
</template>

<script setup>
defineProps({
  message: {
    type: String,
    default: "",
  },
})
</script>

<style scoped>
.error-text {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #f56c6c;
  vertical-align: middle;
}

.error-empty {
  color: #909399;
}
</style>
