<template>
  <div class="mobile-alerts">
    <div class="page-actions">
      <el-button plain @click="$emit('back')">返回</el-button>
      <el-button :icon="Refresh" :loading="loading" @click="loadAlerts">刷新</el-button>
    </div>

    <el-alert
      type="info"
      show-icon
      :closable="false"
      title="告警仅在系统内显示，Telegram 不再重复提醒。"
    />

    <div class="stats">
      <div><span>待确认</span><strong>{{ stats.pending || 0 }}</strong></div>
      <div><span>错误</span><strong class="danger">{{ stats.error || 0 }}</strong></div>
      <div><span>警告</span><strong class="warning">{{ stats.warning || 0 }}</strong></div>
    </div>

    <div class="filters">
      <el-input
        v-model="keyword"
        :prefix-icon="Search"
        clearable
        placeholder="搜索标题 / 频道 / Bot"
        @keyup.enter="loadAlerts"
        @clear="loadAlerts"
      />
      <el-segmented
        v-model="status"
        :options="statusOptions"
        block
        @change="loadAlerts"
      />
    </div>

    <el-alert v-if="error" type="error" show-icon :closable="false" :title="error">
      <el-button link type="primary" @click="loadAlerts">重新加载</el-button>
    </el-alert>

    <div v-else v-loading="loading" class="alert-list">
      <el-empty v-if="!loading && !items.length" description="当前没有符合条件的告警" />
      <article v-for="item in items" :key="item.id" class="alert-item">
        <button type="button" class="alert-summary" @click="toggle(item.id)">
          <span class="summary-main">
            <span class="summary-title">{{ item.title || "未命名告警" }}</span>
            <span class="summary-meta">{{ item.module || "系统" }} · {{ formatTime(item.updated_at) }}</span>
          </span>
          <span class="summary-side">
            <el-tag :type="levelType(item.level)" size="small">{{ levelLabel(item.level) }}</el-tag>
            <el-icon><ArrowDownBold v-if="expandedId !== item.id" /><ArrowUpBold v-else /></el-icon>
          </span>
        </button>
        <div v-if="expandedId === item.id" class="alert-detail">
          <dl>
            <div><dt>状态</dt><dd>{{ item.status === "pending" ? "待确认" : "已确认" }}</dd></div>
            <div><dt>任务</dt><dd>{{ item.task_id ? `#${item.task_id}` : "-" }}</dd></div>
            <div><dt>频道</dt><dd>{{ item.channel || item.target || "-" }}</dd></div>
            <div><dt>Bot</dt><dd>{{ item.bot_name || item.support_bot_id || "-" }}</dd></div>
            <div><dt>次数</dt><dd>{{ Math.max(Number(item.repeat_count || 0), 1) }}</dd></div>
          </dl>
          <pre>{{ item.detail || "无详细信息" }}</pre>
          <div class="detail-actions">
            <el-button
              v-if="taskType(item)"
              plain
              :icon="Document"
              @click="openTask(item)"
            >查看任务</el-button>
            <el-button
              v-if="item.status === 'pending'"
              type="primary"
              :icon="CircleCheck"
              :loading="acknowledgingId === item.id"
              @click="acknowledge(item)"
            >已读</el-button>
          </div>
        </div>
      </article>
    </div>

    <el-button
      v-if="stats.pending"
      class="ack-all"
      :loading="acknowledgingAll"
      @click="acknowledgeAll"
    >全部标记为已读</el-button>
  </div>
</template>

<script setup>
import { onMounted, ref } from "vue"
import { ArrowDownBold, ArrowUpBold, CircleCheck, Document, Refresh, Search } from "@element-plus/icons-vue"
import { ElMessage, ElMessageBox } from "element-plus"
import {
  acknowledgeAllControlAlerts,
  acknowledgeControlAlert,
  getControlAlerts,
} from "../api"
import { getErrorMessage } from "../api/client"

const emit = defineEmits(["back", "open-task"])

const items = ref([])
const stats = ref({})
const loading = ref(false)
const error = ref("")
const keyword = ref("")
const status = ref("pending")
const expandedId = ref(null)
const acknowledgingId = ref(null)
const acknowledgingAll = ref(false)
const statusOptions = [
  { label: "待确认", value: "pending" },
  { label: "已确认", value: "acknowledged" },
  { label: "全部", value: "all" },
]

async function loadAlerts() {
  loading.value = true
  error.value = ""
  try {
    const response = await getControlAlerts({ status: status.value, q: keyword.value, limit: 100 })
    items.value = response.data?.items || []
    stats.value = response.data?.stats || {}
  } catch (requestError) {
    error.value = getErrorMessage(requestError, "加载系统告警失败")
  } finally {
    loading.value = false
  }
}

function toggle(id) {
  expandedId.value = expandedId.value === id ? null : id
}

function taskType(item) {
  if (!Number(item?.task_id)) return ""
  const explicitType = String(item.context?.task_type || "").trim().toLowerCase()
  if (["listener", "clone"].includes(explicitType)) return explicitType

  const module = String(item.module || "").toLowerCase()
  const title = String(item.title || "")
  if (module.includes("listener") || module.includes("监听") || title.includes("监听")) return "listener"
  if (module.includes("clone") || module.includes("克隆") || title.includes("克隆")) return "clone"
  return ""
}

function openTask(item) {
  const type = taskType(item)
  if (type) emit("open-task", { alert: item, taskType: type })
}

async function acknowledge(item) {
  acknowledgingId.value = item.id
  try {
    await acknowledgeControlAlert(item.id)
    ElMessage.success("告警已确认")
    await loadAlerts()
  } catch (requestError) {
    ElMessage.error(getErrorMessage(requestError, "确认告警失败"))
  } finally {
    acknowledgingId.value = null
  }
}

async function acknowledgeAll() {
  try {
    await ElMessageBox.confirm("确定将全部待确认告警标记为已读吗？", "全部已读", {
      type: "warning",
      confirmButtonText: "全部已读",
      cancelButtonText: "取消",
    })
  } catch (dialogError) {
    if (dialogError === "cancel" || dialogError === "close") return
    throw dialogError
  }
  acknowledgingAll.value = true
  try {
    await acknowledgeAllControlAlerts()
    ElMessage.success("全部告警已确认")
    await loadAlerts()
  } catch (requestError) {
    ElMessage.error(getErrorMessage(requestError, "批量确认失败"))
  } finally {
    acknowledgingAll.value = false
  }
}

function levelType(level) {
  return level === "error" ? "danger" : level === "warning" ? "warning" : "info"
}

function levelLabel(level) {
  return level === "error" ? "错误" : level === "warning" ? "警告" : "信息"
}

function formatTime(value) {
  return value ? String(value).replace("T", " ").slice(0, 16) : "-"
}

onMounted(loadAlerts)
</script>

<style scoped>
.mobile-alerts { padding: 12px 12px 88px; }
.page-actions { display: flex; justify-content: space-between; margin-bottom: 12px; }
.stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin: 12px 0; }
.stats > div { padding: 10px; border: 1px solid var(--border-color); border-radius: 6px; background: #fff; }
.stats span { display: block; color: var(--text-muted); font-size: 12px; }
.stats strong { display: block; margin-top: 2px; font-size: 20px; }
.stats .danger { color: var(--danger); }
.stats .warning { color: var(--warning); }
.filters { display: grid; gap: 10px; margin-bottom: 12px; }
.alert-list { min-height: 180px; }
.alert-item { margin-bottom: 10px; border: 1px solid var(--border-color); border-radius: 6px; background: #fff; overflow: hidden; }
.alert-summary { display: flex; width: 100%; min-height: 68px; align-items: center; justify-content: space-between; gap: 10px; border: 0; background: #fff; padding: 12px; color: inherit; text-align: left; }
.summary-main { min-width: 0; }
.summary-title, .summary-meta { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.summary-title { font-weight: 600; }
.summary-meta { margin-top: 4px; color: var(--text-muted); font-size: 12px; }
.summary-side { display: flex; flex: 0 0 auto; align-items: center; gap: 8px; }
.alert-detail { padding: 0 12px 12px; border-top: 1px solid var(--border-color); }
.alert-detail dl { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.alert-detail dl div { min-width: 0; }
.alert-detail dt { color: var(--text-muted); font-size: 12px; }
.alert-detail dd { margin: 2px 0 0; overflow-wrap: anywhere; }
.alert-detail pre { max-height: 220px; overflow: auto; padding: 10px; background: var(--el-fill-color-light); font: inherit; line-height: 1.5; white-space: pre-wrap; overflow-wrap: anywhere; }
.detail-actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.detail-actions > :only-child { grid-column: 1 / -1; }
.alert-detail .el-button, .ack-all { width: 100%; margin-left: 0; }
.ack-all { margin-top: 4px; }
</style>
