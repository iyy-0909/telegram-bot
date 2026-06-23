<template>
  <div class="listener-page">
    <div class="overview-grid">
      <div class="overview-card">
        <span>运行中任务</span>
        <strong>{{ overview.running }}</strong>
      </div>
      <div class="overview-card success">
        <span>成功发送</span>
        <strong>{{ overview.success }}</strong>
      </div>
      <div class="overview-card warning">
        <span>过滤 / 去重</span>
        <strong>{{ overview.skipped }}</strong>
      </div>
      <div class="overview-card danger">
        <span>失败 / 异常</span>
        <strong>{{ overview.failed }}</strong>
      </div>
    </div>

    <el-card class="listener-card">
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">监听任务</div>
            <div class="card-subtitle">展示任务运行状态、最近动作、最后监听时间和最后错误。</div>
          </div>

          <div class="header-actions">
            <el-input
              v-model="keyword"
              clearable
              class="task-search"
              placeholder="搜索任务名 / 源频道 / 目标频道"
            />
            <el-button type="primary" @click="emit('add')">
              新增任务
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        :data="filteredTasks"
        v-loading="loading"
        border
        stripe
        height="492"
        class="listener-table"
        empty-text="暂无监听任务，请点击“新增任务”创建实时监听任务。"
      >
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="name" label="任务名" min-width="150" show-overflow-tooltip />

        <el-table-column label="源频道" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <CopyText
              v-if="row.source_channel"
              :value="row.source_channel"
              :text="row.source_channel"
              tone="primary"
            />
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column label="目标频道" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <CopyText
              :value="formatTargets(row.target_channels)"
              :text="formatTargets(row.target_channels)"
              tone="success"
            />
          </template>
        </el-table-column>

        <el-table-column label="运行状态" width="110" align="center">
          <template #default="{ row }">
            <StatusTag :status="row.enabled ? 'running' : 'stopped'" />
          </template>
        </el-table-column>

        <el-table-column label="最近动作" min-width="210" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="recent-action">
              <StatusTag
                v-if="latestEvent(row.id)"
                :status="latestEvent(row.id).event_type || latestEvent(row.id).status"
              />
              <span v-if="latestEvent(row.id)" class="recent-message">
                {{ latestEvent(row.id).message || latestEvent(row.id).error || "-" }}
              </span>
              <span v-else>-</span>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="最后监听" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            {{ formatLastReceived(row.last_received_at) }}
          </template>
        </el-table-column>

        <el-table-column label="账号 / Bot" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="muted-line">账号 {{ row.account_id || "-" }} / Bot {{ row.bot_id || "默认" }}</div>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="360" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-button
                size="small"
                type="success"
                :disabled="row.enabled"
                @click="emit('start', row.id)"
              >
                启动
              </el-button>
              <el-button
                size="small"
                type="warning"
                :disabled="!row.enabled"
                @click="emit('stop', row.id)"
              >
                停止
              </el-button>
              <el-button size="small" @click="emit('edit', row)">
                编辑
              </el-button>
              <el-button
                size="small"
                type="primary"
                plain
                @click="emit('catchup', row.id)"
              >
                一键补齐
              </el-button>
              <el-button
                size="small"
                type="danger"
                @click="emit('delete', row.id)"
              >
                删除
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="listener-log-card">
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">监听执行记录</div>
            <div class="card-subtitle">展示最近 50 条监听执行结果；建议需要时手动刷新。</div>
          </div>

          <div class="log-actions">
            <el-input
              v-model="eventKeyword"
              clearable
              class="event-search"
              placeholder="搜索任务 / 频道 / 消息 / 错误"
            />
            <el-select v-model="eventFilter" clearable placeholder="事件筛选" class="event-filter">
              <el-option label="收到" value="received" />
              <el-option label="准备完成" value="prepared" />
              <el-option label="发送中" value="sending" />
              <el-option label="成功" value="success" />
              <el-option label="过滤" value="filtered" />
              <el-option label="空内容" value="empty" />
              <el-option label="去重" value="deduped" />
              <el-option label="失败" value="failed" />
              <el-option label="账号异常" value="account_error" />
            </el-select>
            <el-button :loading="logsLoading" @click="emit('refresh-logs')">
              刷新
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        :data="runtimeEvents"
        v-loading="logsLoading"
        border
        stripe
        height="492"
        class="listener-log-table"
        empty-text="暂无监听执行记录，监听收到消息后会在这里显示处理过程。"
      >
        <el-table-column prop="time" label="时间" width="160" />
        <el-table-column label="事件" width="100" align="center">
          <template #default="{ row }">
            <StatusTag :status="row.event_type || row.status" />
          </template>
        </el-table-column>
        <el-table-column prop="task_id" label="任务ID" width="90" align="center" />
        <el-table-column prop="task_name" label="任务名" min-width="140" show-overflow-tooltip />
        <el-table-column prop="source_channel" label="源频道" min-width="130" show-overflow-tooltip />

        <el-table-column label="目标" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <CopyText :value="row.target" :text="row.target" />
          </template>
        </el-table-column>

        <el-table-column label="源链接" min-width="190" show-overflow-tooltip>
          <template #default="{ row }">
            <CopyText
              v-if="row.source_message_url"
              :value="row.source_message_url"
              :text="row.source_message_url"
              tone="primary"
            />
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column label="目标链接" min-width="190" show-overflow-tooltip>
          <template #default="{ row }">
            <CopyText
              v-if="row.target_message_url"
              :value="row.target_message_url"
              :text="row.target_message_url"
              tone="success"
            />
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column prop="bot_name" label="Bot" min-width="120" show-overflow-tooltip />
        <el-table-column prop="message" label="详情" min-width="220" show-overflow-tooltip />
        <el-table-column prop="error" label="错误" min-width="220" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, ref } from "vue"
import CopyText from "./CopyText.vue"
import StatusTag from "./StatusTag.vue"
import { matchesSearch } from "../utils/search"

const props = defineProps({
  tasks: {
    type: Array,
    required: true,
  },
  events: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  logsLoading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(["add", "edit", "delete", "start", "stop", "catchup", "refresh-logs"])
const eventFilter = ref("")
const eventKeyword = ref("")
const keyword = ref("")

const filteredTasks = computed(() => {
  if (!keyword.value.trim()) return props.tasks

  return props.tasks.filter((task) => {
    const latest = latestEvent(task.id)
    const values = [
      task.id,
      task.name,
      task.source_channel,
      formatTargets(task.target_channels),
      task.status,
      task.enabled ? "running" : "stopped",
      task.account_id,
      task.bot_id,
      latest?.message,
      latest?.error,
    ]

    return matchesSearch(values, keyword.value)
  })
})

const runtimeEvents = computed(() => {
  let list = props.events || []

  if (eventFilter.value) {
    list = list.filter((event) => (event.event_type || event.status) === eventFilter.value)
  }

  if (!eventKeyword.value.trim()) return list

  return list.filter((event) => {
    const values = [
      event.time,
      event.event_type,
      event.status,
      event.task_id,
      event.task_name,
      event.source_channel,
      event.target,
      event.source_message_id,
      event.target_message_id,
      event.grouped_id,
      event.source_message_url,
      event.target_message_url,
      event.message_type,
      event.message,
      event.error,
      event.bot_name,
    ]

    return matchesSearch(values, eventKeyword.value)
  })
})

const overview = computed(() => {
  const events = props.events || []
  const failedTypes = new Set(["failed", "error", "account_error", "bot_error", "permission_error"])
  const skippedTypes = new Set(["filtered", "empty", "deduped"])

  return {
    running: filteredTasks.value.filter((task) => task.enabled).length,
    success: events.filter((event) => (event.event_type || event.status) === "success").length,
    skipped: events.filter((event) => skippedTypes.has(event.event_type || event.status)).length,
    failed: events.filter((event) => failedTypes.has(event.event_type || event.status)).length,
  }
})

const latestEventMap = computed(() => {
  const map = new Map()

  for (const event of props.events || []) {
    if (!map.has(event.task_id)) {
      map.set(event.task_id, event)
    }
  }

  return map
})

function latestEvent(taskId) {
  return latestEventMap.value.get(taskId)
}

function formatLastReceived(value) {
  if (!value) return "-"

  const raw = String(value)
  const normalized = /[zZ]|[+-]\d{2}:?\d{2}$/.test(raw)
    ? raw
    : `${raw.replace(" ", "T")}Z`
  const time = new Date(normalized)

  if (Number.isNaN(time.getTime())) {
    return value
  }

  const seconds = Math.max(Math.floor((Date.now() - time.getTime()) / 1000), 0)

  if (seconds < 60) return "刚刚"

  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes} 分钟前`

  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时前`

  const days = Math.floor(hours / 24)
  if (days < 30) return `${days} 天前`

  return value
}

function formatTargets(value) {
  if (!value) return "-"

  try {
    const parsed = typeof value === "string" ? JSON.parse(value) : value
    return Array.isArray(parsed) ? parsed.join(", ") : String(parsed)
  } catch {
    return String(value)
  }
}
</script>

<style scoped>
.listener-page {
  width: 100%;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.overview-card {
  padding: 12px 14px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #ebeef5;
}

.overview-card span {
  display: block;
  color: #606266;
  font-size: 13px;
}

.overview-card strong {
  display: block;
  margin-top: 6px;
  font-size: 24px;
  color: #303133;
}

.overview-card.success strong {
  color: #67c23a;
}

.overview-card.warning strong {
  color: #e6a23c;
}

.overview-card.danger strong {
  color: #f56c6c;
}

.listener-card,
.listener-log-card {
  border-radius: 8px;
}

.listener-log-card {
  margin-top: 14px;
}

.card-header,
.header-actions,
.log-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.card-header {
  justify-content: space-between;
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

.event-filter {
  width: 160px;
}

.event-search {
  width: 240px;
}

.task-search {
  width: 260px;
}

.listener-table,
.listener-log-table {
  width: 100%;
}

.recent-action {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.recent-message,
.muted-line {
  color: #606266;
  font-size: 12px;
}

.recent-message {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: nowrap;
}

.action-buttons .el-button {
  margin-left: 0;
}

@media (max-width: 900px) {
  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
