<template>
  <el-card class="settings-card">
    <template #header>
      <div class="card-header">
        <div>
          <div class="card-title">发送设置</div>
          <div class="card-subtitle">控制所有任务共享的 Bot API 发送节奏</div>
        </div>

        <el-button type="primary" @click="submit">
          保存设置
        </el-button>
      </div>
    </template>

    <el-form label-width="180px" class="settings-form">
      <el-form-item label="全局发送间隔秒">
        <el-input-number v-model="localForm.global_send_delay" :min="0" :step="1" />
      </el-form-item>

      <el-form-item label="发送异常重试次数">
        <el-input-number v-model="localForm.send_retry_count" :min="0" :step="1" />
      </el-form-item>

      <el-form-item label="重试等待秒">
        <el-input-number v-model="localForm.send_retry_delay" :min="0" :step="1" />
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup>
import { reactive, watch } from "vue"

const props = defineProps({
  settings: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(["submit"])

const localForm = reactive({
  global_send_delay: 3,
  send_retry_count: 2,
  send_retry_delay: 5,
})

function toNonNegativeNumber(value, fallback) {
  const numberValue = Number(value)

  if (!Number.isFinite(numberValue) || numberValue < 0) {
    return fallback
  }

  return Math.floor(numberValue)
}

watch(
  () => props.settings,
  (value) => {
    localForm.global_send_delay = toNonNegativeNumber(value.global_send_delay, 3)
    localForm.send_retry_count = toNonNegativeNumber(value.send_retry_count, 2)
    localForm.send_retry_delay = toNonNegativeNumber(value.send_retry_delay, 5)
  },
  {
    immediate: true,
    deep: true,
  },
)

function submit() {
  emit("submit", {
    global_send_delay: toNonNegativeNumber(localForm.global_send_delay, 3),
    send_retry_count: toNonNegativeNumber(localForm.send_retry_count, 2),
    send_retry_delay: toNonNegativeNumber(localForm.send_retry_delay, 5),
  })
}
</script>

<style scoped>
.settings-card {
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.card-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}

.settings-form {
  max-width: 520px;
}
</style>
