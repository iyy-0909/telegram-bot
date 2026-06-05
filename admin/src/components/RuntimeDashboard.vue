<template>
  <div class="runtime-dashboard">
    <el-card class="page-card">
      <template #header>
        <div class="page-header">
          <div>
            <div class="page-title">运行看板</div>
            <div class="page-subtitle">查看当前发送队列、运行中的克隆任务和监听任务概况。</div>
          </div>

          <el-button :loading="loading" @click="$emit('refresh')">
            刷新
          </el-button>
        </div>
      </template>

      <div class="stat-grid">
        <div class="stat-item stat-primary">
          <div class="stat-label">等待发送</div>
          <div class="stat-value">{{ stats.waiting_count || 0 }}</div>
          <div class="stat-help">全局队列中等待锁的内容</div>
        </div>
        <div class="stat-item stat-active">
          <div class="stat-label">正在发送</div>
          <div class="stat-value">{{ stats.sending_count || 0 }}</div>
          <div class="stat-help">当前占用发送锁</div>
        </div>
        <div class="stat-item">
          <div class="stat-label">运行中克隆</div>
          <div class="stat-value">{{ stats.clone_running_count || 0 }}</div>
          <div class="stat-help">后台 clone worker</div>
        </div>
        <div class="stat-item">
          <div class="stat-label">启用监听</div>
          <div class="stat-value">{{ stats.listener_enabled_count || 0 }}</div>
          <div class="stat-help">实时监听任务数量</div>
        </div>
        <div class="stat-item">
          <div class="stat-label">已加载账号</div>
          <div class="stat-value">{{ stats.loaded_account_count || 0 }}</div>
          <div class="stat-help">可用采集账号</div>
        </div>
      </div>
      
    </el-card>

    <el-card class="page-card">
      <template #header>
        <div class="section-title">当前发送</div>
      </template>

      <el-empty
        v-if="!current"
        description="当前没有正在发送或等待发送间隔的内容。"
      />

      <div v-else class="current-panel">
        <div class="current-topline">
          <div class="current-main">
            <StatusTag :status="current.status" size="default" />
            <div>
              <div class="current-title">{{ current.task_name || formatTask(current) }}</div>
              <div class="current-subtitle">
                {{ sourceTypeLabel(current.source_type) }}任务 #{{ current.task_id || "-" }}
              </div>
            </div>
          </div>
          <div class="countdown-box">
            <div class="countdown-label">预计发送</div>
            <div class="countdown-value">{{ formatCountdown(current) }}</div>
          </div>
        </div>

        <div class="info-grid">
          <div class="info-item">
            <span>源频道</span>
            <strong>{{ current.source_channel || "-" }}</strong>
          </div>
          <div class="info-item">
            <span>目标频道</span>
            <strong>{{ current.target_channel || "-" }}</strong>
          </div>
          <div class="info-item">
            <span>源消息ID</span>
            <strong>{{ current.source_message_id || "-" }}</strong>
          </div>
          <div class="info-item">
            <span>相册ID</span>
            <strong>{{ current.grouped_id || "-" }}</strong>
          </div>
          <div class="info-item">
            <span>内容类型</span>
            <strong>{{ current.message_type || "-" }}</strong>
          </div>
          <div class="info-item">
            <span>排队时间</span>
            <strong>{{ current.queued_at || "-" }}</strong>
          </div>
        </div>

        <div class="reason-line">
          <span>当前原因</span>
          <strong>{{ current.reason || "-" }}</strong>
        </div>
      </div>
    </el-card>

    <el-card class="page-card">
      <template #header>
        <div class="section-title">排队任务列表</div>
      </template>

      <el-table
        class="queue-table"
        :data="waiting"
        v-loading="loading"
        border
        height="492"
        empty-text="暂无排队任务。"
      >
        <el-table-column prop="queued_at" label="排队时间" min-width="150" show-overflow-tooltip />
        <el-table-column label="预计发送时间" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.estimated_send_at || "-" }}
          </template>
        </el-table-column>
        <el-table-column label="来源" min-width="80">
          <template #default="{ row }">
            <el-tag size="small">{{ sourceTypeLabel(row.source_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="任务" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="single-line-cell">
              {{ formatTaskLine(row) }}
            </div>
          </template>
        </el-table-column>
        <el-table-column label="频道" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="single-line-cell">
              {{ formatChannelLine(row) }}
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="source_message_id" label="源消息ID" min-width="100" />
        <el-table-column prop="message_type" label="内容类型" min-width="100" />
        <el-table-column label="状态" min-width="100">
          <template #default="{ row }">
            <StatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="等待原因" min-width="160" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-card class="page-card">
      <template #header>
        <div class="section-title">最近完成</div>
      </template>

      <el-table
        :data="recent"
        v-loading="loading"
        border
        height="360"
        empty-text="暂无最近发送记录。"
      >
        <el-table-column prop="finished_at" label="完成时间" min-width="150" show-overflow-tooltip />
        <el-table-column label="来源" width="90">
          <template #default="{ row }">
            <el-tag size="small">{{ sourceTypeLabel(row.source_type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="任务" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="task-cell">
              <strong>{{ row.task_name || formatTask(row) }}</strong>
              <span>#{{ row.task_id || "-" }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="target_channel" label="目标频道" min-width="140" show-overflow-tooltip />
        <el-table-column prop="source_message_id" label="源消息ID" width="110" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <StatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column prop="error" label="错误" min-width="200" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from "vue"
import StatusTag from "./StatusTag.vue"

const props = defineProps({
  dashboard: {
    type: Object,
    default: () => ({}),
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(["refresh"])

const queue = computed(() => props.dashboard.queue || {})
const stats = computed(() => props.dashboard.stats || {})
const current = computed(() => queue.value.current || null)
const waiting = computed(() => queue.value.waiting || [])
const recent = computed(() => queue.value.recent || [])
const nowTick = ref(Date.now())
let tickTimer = null
let currentPollingTimer = null
let pollingItemId = ""

function sourceTypeLabel(value) {
  const map = {
    clone: "克隆",
    listener: "监听",
    support: "客服",
    bulk_replace: "批量替换",
    control: "云台",
  }
  return map[value] || value || "-"
}

function formatTask(row) {
  if (!row?.task_id) {
    return "-"
  }
  return `#${row.task_id}`
}

function formatTaskLine(row) {
  const name = row?.task_name || formatTask(row)
  const id = row?.task_id ? `#${row.task_id}` : ""
  return [name, id].filter(Boolean).join(" ")
}

function formatChannelLine(row) {
  const source = row?.source_channel ? `源：${row.source_channel}` : ""
  const target = row?.target_channel ? `目标：${row.target_channel}` : ""
  return [source, target].filter(Boolean).join(" / ") || "-"
}

function formatCountdown(row) {
  nowTick.value

  if (row?.status === "sending") {
    return "发送中"
  }

  if (row?.status === "retrying") {
    return "重试中"
  }

  const seconds = Number(row?.estimated_send_remaining_seconds)
  if (!Number.isFinite(seconds)) {
    return row?.estimated_send_at || "-"
  }

  return `${Math.max(seconds, 0)} 秒后`
}

function stopCurrentPolling() {
  if (currentPollingTimer) {
    window.clearInterval(currentPollingTimer)
    currentPollingTimer = null
  }
  pollingItemId = ""
}

function startCurrentPolling() {
  if (currentPollingTimer) {
    return
  }

  pollingItemId = current.value?.id || ""
  currentPollingTimer = window.setInterval(() => {
    emit("refresh")
  }, 10000)
}

onMounted(() => {
  tickTimer = window.setInterval(() => {
    nowTick.value = Date.now()

    if (pollingItemId && current.value?.id !== pollingItemId) {
      stopCurrentPolling()
    }

    if (!current.value) {
      stopCurrentPolling()
      return
    }

    if (current.value.estimated_send_remaining_seconds == null) {
      return
    }

    const previous = Number(current.value.estimated_send_remaining_seconds || 0)
    current.value.estimated_send_remaining_seconds = Math.max(
      previous - 1,
      0,
    )

    if (previous > 0 && current.value.estimated_send_remaining_seconds === 0) {
      emit("refresh")
      startCurrentPolling()
    }
  }, 1000)
})

onUnmounted(() => {
  if (tickTimer) {
    window.clearInterval(tickTimer)
    tickTimer = null
  }
  stopCurrentPolling()
})
</script>

<style scoped>
.runtime-dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.page-card {
  border-radius: 8px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.page-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.page-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}

.section-title {
  font-weight: 600;
  color: #303133;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
  gap: 12px;
}

.stat-item {
  position: relative;
  overflow: hidden;
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
}

.stat-item::before {
  position: absolute;
  top: 0;
  left: 0;
  width: 4px;
  height: 100%;
  content: "";
  background: #d1d5db;
}

.stat-primary::before {
  background: #409eff;
}

.stat-active::before {
  background: #67c23a;
}

.stat-label {
  font-size: 12px;
  color: #909399;
}

.stat-value {
  margin-top: 8px;
  font-size: 24px;
  font-weight: 700;
  color: #303133;
}

.stat-help {
  margin-top: 4px;
  font-size: 12px;
  color: #9ca3af;
}

.current-panel {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 16px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #f8fbff;
}

.current-topline {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.current-main {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.current-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
}

.current-subtitle {
  margin-top: 3px;
  font-size: 12px;
  color: #6b7280;
}

.countdown-box {
  min-width: 132px;
  padding: 10px 12px;
  border: 1px solid #bfdbfe;
  border-radius: 8px;
  background: #eff6ff;
  text-align: right;
}

.countdown-label {
  font-size: 12px;
  color: #6b7280;
}

.countdown-value {
  margin-top: 4px;
  font-size: 20px;
  font-weight: 700;
  color: #1d4ed8;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.info-item {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #ffffff;
}

.info-item span {
  display: block;
  margin-bottom: 4px;
  font-size: 12px;
  color: #909399;
}

.info-item strong {
  display: block;
  overflow: hidden;
  color: #374151;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.reason-line {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border-radius: 6px;
  background: #ffffff;
  color: #606266;
}

.reason-line span {
  flex: 0 0 auto;
  color: #909399;
}

.reason-line strong {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-cell,
.channel-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.task-cell strong,
.channel-cell span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-cell span {
  font-size: 12px;
  color: #909399;
}

.queue-table :deep(.el-table__row) {
  height: 44px;
}

.queue-table :deep(.el-table__cell) {
  padding: 6px 0;
}

.single-line-cell {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 1024px) {
  .stat-grid {
    grid-template-columns: repeat(2, minmax(120px, 1fr));
  }

  .info-grid {
    grid-template-columns: 1fr;
  }

  .current-topline {
    flex-direction: column;
  }

  .countdown-box {
    width: 100%;
    text-align: left;
  }
}
</style>
