<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>运行日志</span>
        <el-button type="primary" @click="$emit('refresh')">
          刷新
        </el-button>
      </div>
    </template>

    <div class="log-box">
      <div
        v-for="(line, index) in logs"
        :key="index"
        class="log-line"
      >
        {{ line }}
      </div>
    </div>
  </el-card>
</template>

<script setup>
defineProps({
  logs: {
    type: Array,
    required: true
  }
})

defineEmits(["refresh"])
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.log-box {
  background: #111827;
  color: #d1d5db;
  padding: 16px;
  border-radius: 8px;
  height: 500px;
  overflow-y: auto;
  font-family: Consolas, monospace;
  font-size: 13px;
}

.log-line {
  line-height: 1.6;
  white-space: pre-wrap;
}
</style>