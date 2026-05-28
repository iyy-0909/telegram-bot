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
            <div class="card-subtitle">展示任务运行状态、最近处理动作和最后错误。</div>
          </div>

          <el-button type="primary" @click="emit('add')">
            新增任务
          </el-button>
        </div>
      </template>

      <el-table
        :data="tasks"
        border
        stripe
        class="listener-table"
        empty-text="暂无监听任务"
      >
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="name" label="任务名" min-width="150" show-overflow-tooltip />

        <el-table-column label="源频道" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <button
              v-if="row.source_channel"
              class="copy-text link-primary"
              type="button"
              @click="copyValue(row.source_channel)"
            >
              <span>{{ row.source_channel }}</span>
              <el-icon class="copy-icon"><CopyDocument /></el-icon>
            </button>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column label="目标频道" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <button
              class="copy-text link-success"
              type="button"
              @click="copyValue(formatTargets(row.target_channels))"
            >
              <span>{{ formatTargets(row.target_channels) }}</span>
              <el-icon class="copy-icon"><CopyDocument /></el-icon>
            </button>
          </template>
        </el-table-column>

        <el-table-column label="运行状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? "运行中" : "已停止" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column label="最近动作" min-width="210" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="recent-action">
              <el-tag
                v-if="latestEvent(row.id)"
                :type="eventTagType(latestEvent(row.id).event_type || latestEvent(row.id).status)"
                size="small"
              >
                {{ eventLabel(latestEvent(row.id).event_type || latestEvent(row.id).status) }}
              </el-tag>
              <span v-if="latestEvent(row.id)" class="recent-message">
                {{ latestEvent(row.id).message || latestEvent(row.id).error || "-" }}
              </span>
              <span v-else>-</span>
            </div>
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
                补齐
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
            <div class="card-subtitle">保留最近 200 条执行流水，展示收到、过滤、去重、发送中、成功和失败。</div>
          </div>

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
        </div>
      </template>

      <el-table
        :data="runtimeEvents"
        border
        stripe
        height="460"
        class="listener-log-table"
        empty-text="暂无监听执行记录"
      >
        <el-table-column prop="time" label="时间" width="160" />
        <el-table-column label="事件" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="eventTagType(row.event_type || row.status)" size="small">
              {{ eventLabel(row.event_type || row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="task_id" label="任务ID" width="90" align="center" />
        <el-table-column prop="task_name" label="任务名" min-width="140" show-overflow-tooltip />
        <el-table-column prop="source_channel" label="源频道" min-width="130" show-overflow-tooltip />

        <el-table-column label="目标" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <button class="copy-text" type="button" @click="copyValue(row.target)">
              <span>{{ row.target || "-" }}</span>
              <el-icon v-if="row.target" class="copy-icon"><CopyDocument /></el-icon>
            </button>
          </template>
        </el-table-column>

        <el-table-column label="源链接" min-width="190" show-overflow-tooltip>
          <template #default="{ row }">
            <button
              v-if="row.source_message_url"
              class="copy-text link-primary"
              type="button"
              @click="copyValue(row.source_message_url)"
            >
              <span>{{ row.source_message_url }}</span>
              <el-icon class="copy-icon"><CopyDocument /></el-icon>
            </button>
            <span v-else>-</span>
          </template>
        </el-table-column>

        <el-table-column label="目标链接" min-width="190" show-overflow-tooltip>
          <template #default="{ row }">
            <button
              v-if="row.target_message_url"
              class="copy-text link-success"
              type="button"
              @click="copyValue(row.target_message_url)"
            >
              <span>{{ row.target_message_url }}</span>
              <el-icon class="copy-icon"><CopyDocument /></el-icon>
            </button>
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
import { ElMessage } from "element-plus"
import { CopyDocument } from "@element-plus/icons-vue"
import { copyText } from "../utils/clipboard"

const props = defineProps({
  tasks: {
    type: Array,
    required: true,
  },
  events: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(["add", "edit", "delete", "start", "stop", "catchup"])
const eventFilter = ref("")

const runtimeEvents = computed(() => {
  const list = props.events || []
  if (!eventFilter.value) return list
  return list.filter((event) => (event.event_type || event.status) === eventFilter.value)
})

const overview = computed(() => {
  const events = props.events || []
  const failedTypes = new Set(["failed", "error", "account_error", "bot_error", "permission_error"])
  const skippedTypes = new Set(["filtered", "empty", "deduped"])

  return {
    running: props.tasks.filter((task) => task.enabled).length,
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

function formatTargets(value) {
  if (!value) return "-"

  try {
    const parsed = typeof value === "string" ? JSON.parse(value) : value
    return Array.isArray(parsed) ? parsed.join(", ") : String(parsed)
  } catch {
    return String(value)
  }
}

function eventLabel(type) {
  const labels = {
    received: "收到",
    prepared: "准备",
    sending: "发送中",
    success: "成功",
    filtered: "过滤",
    empty: "空内容",
    deduped: "去重",
    failed: "失败",
    error: "失败",
    account_error: "账号异常",
    bot_error: "Bot异常",
    permission_error: "权限异常",
  }
  return labels[type] || type || "-"
}

function eventTagType(type) {
  if (type === "success") return "success"
  if (type === "sending" || type === "prepared" || type === "received") return "primary"
  if (type === "filtered" || type === "empty" || type === "deduped") return "warning"
  if (["failed", "error", "account_error", "bot_error", "permission_error"].includes(type)) return "danger"
  return "info"
}

async function copyValue(value) {
  const text = String(value || "").trim()

  if (!text || text === "-") {
    return
  }

  try {
    const ok = await copyText(text)
    if (!ok) throw new Error("copy failed")
    ElMessage.success("已复制")
  } catch {
    ElMessage.error("复制失败")
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
  border-radius: 12px;
}

.listener-log-card {
  margin-top: 14px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
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
  flex-wrap: wrap;
}

.action-buttons .el-button {
  margin-left: 0;
}

.copy-text {
  appearance: none;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 1px solid #dcdfe6;
  border-radius: 999px;
  padding: 3px 9px;
  margin: 0;
  max-width: 100%;
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

.link-primary {
  color: #409eff;
}

.link-success {
  color: #67c23a;
}

@media (max-width: 900px) {
  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
