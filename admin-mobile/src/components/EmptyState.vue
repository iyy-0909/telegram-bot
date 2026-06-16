<template>
  <div class="empty-state">
    <div class="empty-title">{{ title }}</div>
    <div class="empty-text">{{ text }}</div>
  </div>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: "暂无数据",
  },
  text: {
    type: String,
    default: "下拉刷新或调整搜索条件后再试。",
  },
})
</script>
