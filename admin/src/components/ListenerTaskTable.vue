<template>
  <div class="listener-page">
    <el-card class="listener-card">
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">监听任务</div>
            <div class="card-subtitle">实时监听源频道新消息，并通过 Bot API 分发</div>
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
        <el-table-column prop="source_channel" label="源频道" min-width="150" show-overflow-tooltip />
        <el-table-column label="目标频道" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            {{ formatTargets(row.target_channels) }}
          </template>
        </el-table-column>
        <el-table-column prop="account_id" label="账号" width="80" align="center" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
              {{ row.enabled ? "运行中" : "已停止" }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="last_error" label="最近错误" min-width="180" show-overflow-tooltip />

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
            <div class="card-title">监听发送缓存</div>
            <div class="card-subtitle">只缓存最近 20 条监听发送记录，最新在最上方</div>
          </div>
        </div>
      </template>

      <el-table
        :data="events"
        border
        stripe
        height="320"
        class="listener-log-table"
        empty-text="暂无监听发送记录"
      >
        <el-table-column prop="time" label="时间" width="160" />
        <el-table-column prop="task_id" label="任务ID" width="90" align="center" />
        <el-table-column prop="task_name" label="任务名" min-width="140" show-overflow-tooltip />

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
        <el-table-column prop="message" label="内容" min-width="180" show-overflow-tooltip />
        <el-table-column prop="error" label="错误" min-width="180" show-overflow-tooltip />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ElMessage } from "element-plus"
import { CopyDocument } from "@element-plus/icons-vue"

defineProps({
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

function formatTargets(value) {
  if (!value) return "-"

  try {
    const parsed = typeof value === "string" ? JSON.parse(value) : value
    return Array.isArray(parsed) ? parsed.join(", ") : String(parsed)
  } catch {
    return String(value)
  }
}

async function copyValue(value) {
  const text = String(value || "").trim()

  if (!text || text === "-") {
    return
  }

  try {
    await navigator.clipboard.writeText(text)
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

.listener-card,
.listener-log-card {
  border-radius: 12px;
}

.listener-log-card {
  margin-top: 16px;
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

.listener-table,
.listener-log-table {
  width: 100%;
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
</style>
