<template>
  <section class="alert-center">
    <header class="page-header">
      <div>
        <h2>系统告警</h2>
        <p>集中查看克隆、监听、客服机器人和系统运行告警。</p>
      </div>
      <div class="header-actions">
        <el-button :icon="Refresh" :loading="loading" @click="loadAlerts">刷新</el-button>
        <el-button
          type="primary"
          :icon="CircleCheck"
          :disabled="!stats.pending"
          :loading="acknowledgingAll"
          @click="acknowledgeAll"
        >
          全部已读
        </el-button>
      </div>
    </header>

    <el-alert
      type="info"
      show-icon
      :closable="false"
      title="告警已改为后台系统接收，Telegram 不再发送告警和重复提醒；云台命令功能不受影响。"
    />

    <div class="summary-grid">
      <div class="summary-item summary-item--pending">
        <span>待确认</span><strong>{{ stats.pending || 0 }}</strong>
      </div>
      <div class="summary-item summary-item--error">
        <span>错误</span><strong>{{ stats.error || 0 }}</strong>
      </div>
      <div class="summary-item summary-item--warning">
        <span>警告</span><strong>{{ stats.warning || 0 }}</strong>
      </div>
      <div class="summary-item">
        <span>已确认</span><strong>{{ stats.acknowledged || 0 }}</strong>
      </div>
    </div>

    <div class="table-panel">
      <div class="filters">
        <el-input
          v-model="filters.q"
          :prefix-icon="Search"
          clearable
          placeholder="搜索标题 / 详情 / 任务 / 频道 / Bot"
          @keyup.enter="applyFilters"
          @clear="applyFilters"
        />
        <el-select v-model="filters.status" aria-label="告警状态" @change="applyFilters">
          <el-option label="全部状态" value="all" />
          <el-option label="待确认" value="pending" />
          <el-option label="已确认" value="acknowledged" />
        </el-select>
        <el-select v-model="filters.level" aria-label="告警级别" @change="applyFilters">
          <el-option label="全部级别" value="all" />
          <el-option label="错误" value="error" />
          <el-option label="警告" value="warning" />
          <el-option label="信息" value="info" />
        </el-select>
        <el-input
          v-model="filters.module"
          clearable
          placeholder="模块，例如 listener_health"
          @keyup.enter="applyFilters"
          @clear="applyFilters"
        />
        <el-button type="primary" :icon="Search" @click="applyFilters">查询</el-button>
      </div>

      <el-alert v-if="loadError" type="error" show-icon :closable="false" class="load-error">
        <template #title>{{ loadError }}</template>
        <el-button link type="primary" @click="loadAlerts">重新加载</el-button>
      </el-alert>

      <el-table
        v-else
        v-loading="loading"
        :data="alerts"
        border
        height="492"
        empty-text="当前筛选条件下没有告警。"
        row-key="id"
        :row-class-name="alertRowClass"
        @row-click="handleRowClick"
      >
        <el-table-column label="时间" width="168">
          <template #default="{ row }">{{ formatTime(row.updated_at || row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="级别" width="88" align="center">
          <template #default="{ row }">
            <span class="alert-badge" :class="`alert-badge--${row.level || 'info'}`">
              {{ levelLabel(row.level) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="告警" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="alert-title">{{ row.title || "未命名告警" }}</div>
            <div class="alert-meta">{{ row.module || "系统" }} · #{{ row.id }}</div>
          </template>
        </el-table-column>
        <el-table-column label="关联对象" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ contextSummary(row) }}</template>
        </el-table-column>
        <el-table-column label="发生次数" width="96" align="center">
          <template #default="{ row }">{{ Math.max(Number(row.repeat_count || 0), 1) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <span class="alert-badge" :class="row.status === 'pending' ? 'alert-badge--pending' : 'alert-badge--acknowledged'">
              {{ row.status === "pending" ? "待确认" : "已确认" }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="taskType(row)"
              type="primary"
              link
              :icon="Document"
              @click.stop="openTask(row)"
            >任务</el-button>
            <el-button link :icon="View" @click.stop="openDetail(row)">详情</el-button>
            <el-button
              v-if="row.status === 'pending'"
              type="primary"
              link
              :icon="CircleCheck"
              :loading="acknowledgingId === row.id"
              @click.stop="acknowledge(row)"
            >
              已读
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > pageSize"
        v-model:current-page="page"
        background
        layout="prev, pager, next, total"
        :page-size="pageSize"
        :total="total"
        @current-change="loadAlerts"
      />
    </div>

    <el-dialog v-model="detailVisible" title="告警详情" width="680px" class="alert-detail-dialog">
      <el-descriptions v-if="selectedAlert" :column="2" border>
        <el-descriptions-item label="告警 ID">{{ selectedAlert.id }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ selectedAlert.status === "pending" ? "待确认" : "已确认" }}</el-descriptions-item>
        <el-descriptions-item label="级别">{{ levelLabel(selectedAlert.level) }}</el-descriptions-item>
        <el-descriptions-item label="模块">{{ selectedAlert.module || "系统" }}</el-descriptions-item>
        <el-descriptions-item label="任务 ID">{{ selectedAlert.task_id || "-" }}</el-descriptions-item>
        <el-descriptions-item label="Bot">{{ selectedAlert.bot_name || selectedAlert.support_bot_id || "-" }}</el-descriptions-item>
        <el-descriptions-item label="频道">{{ selectedAlert.channel || "-" }}</el-descriptions-item>
        <el-descriptions-item label="目标">{{ selectedAlert.target || "-" }}</el-descriptions-item>
        <el-descriptions-item label="首次发生">{{ formatTime(selectedAlert.first_sent_at || selectedAlert.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="最近发生">{{ formatTime(selectedAlert.last_sent_at || selectedAlert.updated_at) }}</el-descriptions-item>
        <el-descriptions-item label="确认人">{{ selectedAlert.acknowledged_by || "-" }}</el-descriptions-item>
        <el-descriptions-item label="确认时间">{{ formatTime(selectedAlert.acknowledged_at) }}</el-descriptions-item>
      </el-descriptions>
      <div v-if="selectedAlert" class="detail-block">
        <div class="detail-label">{{ selectedAlert.title }}</div>
        <pre>{{ selectedAlert.detail || "无详细信息" }}</pre>
      </div>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
        <el-button
          v-if="selectedAlert?.status === 'pending'"
          type="primary"
          :loading="acknowledgingId === selectedAlert.id"
          @click="acknowledge(selectedAlert, true)"
        >已读并关闭</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, onUnmounted, reactive, ref } from "vue"
import { CircleCheck, Document, Refresh, Search, View } from "@element-plus/icons-vue"
import { ElMessage, ElMessageBox } from "element-plus"
import {
  acknowledgeAllControlAlerts,
  acknowledgeControlAlert,
  getControlAlerts,
} from "../api/controlAlerts"

const alerts = ref([])
const stats = ref({})
const total = ref(0)
const page = ref(1)
const pageSize = 10
const loading = ref(false)
const loadError = ref("")
const acknowledgingId = ref(null)
const acknowledgingAll = ref(false)
const detailVisible = ref(false)
const selectedAlert = ref(null)
let refreshTimer = null

const filters = reactive({ q: "", status: "pending", level: "all", module: "" })
const emit = defineEmits(["open-task"])

function errorText(error, fallback) {
  return error?.response?.data?.detail || error?.response?.data?.message || error?.message || fallback
}

async function loadAlerts() {
  loading.value = true
  loadError.value = ""
  try {
    const response = await getControlAlerts({
      ...filters,
      limit: pageSize,
      offset: (page.value - 1) * pageSize,
    })
    alerts.value = response.data?.items || []
    stats.value = response.data?.stats || {}
    total.value = Number(response.data?.total || 0)
  } catch (error) {
    loadError.value = errorText(error, "加载系统告警失败")
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  page.value = 1
  loadAlerts()
}

async function acknowledge(row, closeAfter = false) {
  acknowledgingId.value = row.id
  try {
    await acknowledgeControlAlert(row.id)
    ElMessage.success("告警已确认")
    if (closeAfter) detailVisible.value = false
    await loadAlerts()
  } catch (error) {
    ElMessage.error(errorText(error, "确认告警失败"))
  } finally {
    acknowledgingId.value = null
  }
}

async function acknowledgeAll() {
  try {
    await ElMessageBox.confirm(
      `确定将当前全部 ${stats.value.pending || 0} 条待确认告警标记为已读吗？`,
      "全部告警已读",
      { type: "warning", confirmButtonText: "全部已读", cancelButtonText: "取消" },
    )
  } catch (error) {
    if (error === "cancel" || error === "close") return
    throw error
  }

  acknowledgingAll.value = true
  try {
    const response = await acknowledgeAllControlAlerts()
    ElMessage.success(response.data?.message || "全部告警已确认")
    page.value = 1
    await loadAlerts()
  } catch (error) {
    ElMessage.error(errorText(error, "批量确认告警失败"))
  } finally {
    acknowledgingAll.value = false
  }
}

function openDetail(row) {
  selectedAlert.value = row
  detailVisible.value = true
}

function taskType(row) {
  if (!Number(row?.task_id)) return ""
  const explicitType = String(row.context?.task_type || "").trim().toLowerCase()
  if (["listener", "clone"].includes(explicitType)) return explicitType

  const module = String(row.module || "").toLowerCase()
  const title = String(row.title || "")
  if (module.includes("listener") || module.includes("监听") || title.includes("监听")) return "listener"
  if (module.includes("clone") || module.includes("克隆") || title.includes("克隆")) return "clone"
  return ""
}

function openTask(row) {
  const type = taskType(row)
  if (!type) return
  emit("open-task", { alert: row, taskType: type })
}

function handleRowClick(row) {
  if (taskType(row)) openTask(row)
  else openDetail(row)
}

function alertRowClass({ row }) {
  return taskType(row) ? "alert-row--task" : ""
}

function levelLabel(level) {
  return level === "error" ? "错误" : level === "warning" ? "警告" : "信息"
}

function contextSummary(row) {
  return [
    row.task_id ? `任务 #${row.task_id}` : "",
    row.bot_name || (row.support_bot_id ? `SupportBot #${row.support_bot_id}` : ""),
    row.channel,
    row.target,
  ].filter(Boolean).join(" · ") || "-"
}

function formatTime(value) {
  if (!value) return "-"
  return String(value).replace("T", " ").slice(0, 19)
}

onMounted(() => {
  loadAlerts()
  refreshTimer = window.setInterval(loadAlerts, 30000)
})

onUnmounted(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
})
</script>

<style scoped>
.alert-center { min-width: 0; }
.page-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.page-header h2 { margin: 0; font-size: 20px; }
.page-header p { margin: 4px 0 0; color: var(--el-text-color-secondary, #6b7280); font-size: 13px; }
.header-actions { display: flex; gap: 10px; }
.summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 14px 0; }
.summary-item { display: flex; min-height: 64px; align-items: center; justify-content: space-between; padding: 0 16px; border: 1px solid var(--el-border-color, #e5e7eb); border-radius: 6px; background: var(--el-bg-color, #fff); }
.summary-item span { color: var(--el-text-color-secondary, #6b7280); }
.summary-item strong { font-size: 24px; }
.summary-item--pending strong, .summary-item--warning strong { color: var(--el-color-warning, #e6a23c); }
.summary-item--error strong { color: var(--el-color-danger, #f56c6c); }
.table-panel { padding: 16px; border: 1px solid var(--el-border-color, #e5e7eb); border-radius: 6px; background: var(--el-bg-color, #fff); }
.filters { display: grid; grid-template-columns: minmax(260px, 2fr) 140px 140px minmax(180px, 1fr) auto; gap: 10px; margin-bottom: 14px; }
.load-error { margin-bottom: 14px; }
.alert-title { overflow: hidden; font-weight: 600; text-overflow: ellipsis; white-space: nowrap; }
.alert-meta { margin-top: 3px; color: var(--el-text-color-secondary, #6b7280); font-size: 12px; }
.alert-badge { display: inline-flex; min-width: 40px; height: 22px; align-items: center; justify-content: center; padding: 0 7px; border-radius: 4px; color: #fff; font-size: 12px; line-height: 1; }
.alert-badge--error { background: var(--el-color-danger, #f56c6c); }
.alert-badge--warning, .alert-badge--pending { background: var(--el-color-warning, #e6a23c); }
.alert-badge--info { background: var(--el-text-color-secondary, #6b7280); }
.alert-badge--acknowledged { background: var(--el-color-success, #67c23a); }
:deep(.alert-row--task) { cursor: pointer; }
:deep(.alert-row--task:hover > td.el-table__cell) { background: var(--el-color-primary-light-9, #ecf5ff) !important; }
.el-pagination { justify-content: flex-end; margin-top: 14px; }
.detail-block { margin-top: 16px; }
.detail-label { margin-bottom: 8px; font-weight: 600; }
.detail-block pre { max-height: 260px; margin: 0; overflow: auto; padding: 12px; border: 1px solid var(--el-border-color, #e5e7eb); border-radius: 4px; background: var(--el-fill-color-light); font: inherit; line-height: 1.6; white-space: pre-wrap; overflow-wrap: anywhere; }
@media (max-width: 900px) {
  .page-header { align-items: stretch; flex-direction: column; }
  .header-actions { display: grid; grid-template-columns: 1fr 1fr; }
  .summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .filters { grid-template-columns: 1fr 1fr; }
  .filters > :first-child, .filters > :nth-child(4) { grid-column: 1 / -1; }
  .table-panel { padding: 12px; overflow: hidden; }
  :deep(.alert-detail-dialog) { width: calc(100% - 24px) !important; margin: 12px auto; }
}
</style>
