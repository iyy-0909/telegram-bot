<!-- eslint-disable vue/no-multiple-template-root -->
<template>
  <el-card class="clone-card">
    <template #header>
      <div class="card-header">
        <div>
          <div class="card-title">克隆任务</div>
          <div class="card-subtitle">频道历史克隆任务管理</div>
        </div>

        <el-button type="primary" @click="emit('add')">
          新增任务
        </el-button>
      </div>
    </template>

<el-table
      :data="tasks"
      v-loading="loading"
      border
      stripe
      class="clone-table"
      empty-text="暂无克隆任务，请点击“新增任务”创建历史克隆任务。"
    >
      <el-table-column prop="id" label="ID" width="70" align="center" />

      <el-table-column prop="name" label="任务名" min-width="150" />

      <el-table-column prop="source_channel" label="源频道" min-width="170">
        <template #default="{ row }">
          <CopyText
            :value="row.source_channel"
            :text="row.source_channel"
            tone="primary"
          />
        </template>
      </el-table-column>

      <el-table-column label="目标频道" min-width="240">
        <template #default="{ row }">
          <el-tooltip
            effect="dark"
            :content="formatTargets(row.target_channels)"
            placement="top"
          >
            <span class="target-text">
              {{ formatTargets(row.target_channels) }}
            </span>
          </el-tooltip>
        </template>
      </el-table-column>

      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <StatusTag :status="row.status || 'idle'" />
        </template>
      </el-table-column>

      <el-table-column label="Worker" width="110" align="center">
        <template #default="{ row }">
          <StatusTag :status="row.worker_running ? 'running' : 'stopped'" />
        </template>
      </el-table-column>

      <el-table-column
        prop="last_message_id"
        label="进度"
        width="100"
        align="center"
      />

      <el-table-column label="监听" width="100" align="center">
        <template #default="{ row }">
          <el-switch
            :model-value="row.enable_listener"
            size="small"
            active-text="开"
            inactive-text="关"
            @change="value => emit('toggle-listener', row, value)"
          />
        </template>
      </el-table-column>

      <el-table-column label="操作" width="420" fixed="right">
        <template #default="{ row }">
          <div class="action-buttons">
            <el-button
              size="small"
              type="success"
              :disabled="row.worker_running"
              @click="emit('start', row.id)"
            >
              开始
            </el-button>

            <el-button
              size="small"
              type="warning"
              :disabled="!row.worker_running"
              @click="emit('pause', row.id)"
            >
              暂停
            </el-button>

            <el-button
              size="small"
              type="primary"
              :disabled="row.worker_running"
              @click="emit('resume', row.id)"
            >
              继续
            </el-button>

            <el-button
              size="small"
              type="danger"
              plain
              :disabled="!row.worker_running"
              @click="emit('stop', row.id)"
            >
              停止
            </el-button>

            <el-button
              size="small"
              @click="emit('edit', row)"
            >
              编辑
            </el-button>

            <el-button
              size="small"
              type="danger"
              :disabled="row.worker_running"
              @click="emit('delete', row.id)"
            >
              删除
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
  </el-card>

  <el-card class="clone-log-card">
    <template #header>
      <div class="card-header">
        <div>
          <div class="card-title">最近克隆发送结果</div>
          <div class="card-subtitle">
            展示最近发送结果，成功、失败都会显示；建议需要时手动刷新
          </div>
        </div>
        <el-button :loading="logsLoading" @click="emit('refresh-logs')">
          刷新
        </el-button>
      </div>
    </template>
    <el-table
        :data="taskLogs"
        v-loading="logsLoading"
        border
        stripe
        height="320"
        class="clone-log-table"
        empty-text="暂无发送结果，任务发送后会显示最近记录。"
      >
      <el-table-column prop="time" label="时间" width="160" />

      <el-table-column label="结果" width="90" align="center">
        <template #default="{ row }">
          <StatusTag :status="row.result || 'unknown'" />
        </template>
      </el-table-column>

      <el-table-column prop="task_id" label="任务ID" width="90" align="center" />
      <el-table-column label="目标" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">
          <CopyText :value="row.target" :text="row.target" />
        </template>
      </el-table-column>
      <el-table-column prop="source_message_id" label="源消息" width="90" align="center" />
      <el-table-column prop="grouped_id" label="相册ID" width="110" show-overflow-tooltip />

      <el-table-column label="源链接" min-width="190" show-overflow-tooltip>
        <template #default="{ row }">
          <CopyText
            v-if="row.source_message_url"
            :value="row.source_message_url"
            :text="row.source_message_url"
            tone="primary"
          />
          <span v-else>{{ row.source_message_url || "-" }}</span>
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
          <span v-else>{{ row.target_message_url || "-" }}</span>
        </template>
      </el-table-column>

      <el-table-column prop="message" label="内容" min-width="260" show-overflow-tooltip />
      <el-table-column prop="error" label="错误" min-width="220" show-overflow-tooltip />
      </el-table>
  </el-card>
</template>

<script setup>
import CopyText from "./CopyText.vue"
import StatusTag from "./StatusTag.vue"

defineProps({
  tasks: {
    type: Array,
    required: true,
  },
  taskLogs: {
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

const emit = defineEmits([
  "add",
  "edit",
  "delete",
  "start",
  "pause",
  "resume",
  "stop",
  "toggle-listener",
  "refresh-logs",
])

const formatTargets = (value) => {
  if (!value) {
    return "-"
  }

  try {
    const parsed = typeof value === "string" ? JSON.parse(value) : value

    if (Array.isArray(parsed)) {
      return parsed.join(", ")
    }

    return String(parsed)
  } catch (e) {
    return String(value)
  }
}

const targetSummary = (value) => {
  const text = formatTargets(value)
  if (!text || text === "-") return "-"
  const parts = text.split(",").map((item) => item.trim()).filter(Boolean)
  return parts.length > 1 ? `已选 ${parts.length} 个频道` : text
}

</script>

<style scoped>
.clone-card {
  border-radius: 12px;
}

.clone-log-card {
  margin-top: 16px;
  border-radius: 12px;
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

.clone-table {
  width: 100%;
}

.clone-log-table {
  width: 100%;
}

.target-text {
  display: inline-block;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: middle;
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
