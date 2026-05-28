<template>
  <div class="bot-page">
    <el-card class="bot-card">
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">Bot 管理</div>
            <div class="card-subtitle">管理用于频道分发、权限检测和发送测试的官方 Bot</div>
          </div>

          <div class="header-actions">
            <el-tag type="success" effect="plain">启用 {{ enabledCount }}</el-tag>
            <el-tag type="info" effect="plain">全部 {{ bots.length }}</el-tag>
            <el-button type="primary" @click="emit('add')">
              <el-icon><Plus /></el-icon>
              新增 Bot
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        :data="bots"
        v-loading="loading"
        border
        stripe
        size="large"
        style="width: 100%"
        empty-text="暂无 Bot，请点击“新增 Bot”添加分发机器人。"
      >
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="name" label="Bot 名称" min-width="160" />

        <el-table-column label="Bot 链接" min-width="160">
          <template #default="{ row }">
            <CopyText
              v-if="botUsername(row)"
              :value="botUsername(row)"
              :text="botUsername(row)"
              tone="primary"
            />
            <span v-else class="muted">测试或保存 Token 后生成</span>
          </template>
        </el-table-column>

        <el-table-column label="Token" min-width="260">
          <template #default="{ row }">
            <span class="token-text code-pill">
              {{ maskToken(row.token) }}
            </span>
          </template>
        </el-table-column>

        <el-table-column label="启用" width="100" align="center">
          <template #default="{ row }">
            <StatusTag :status="row.enabled ? 'enabled' : 'disabled'" />
          </template>
        </el-table-column>

        <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip />

        <el-table-column label="最后错误" min-width="220">
          <template #default="{ row }">
            <ErrorText :message="row.last_error" />
          </template>
        </el-table-column>

        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <div class="action-buttons">
              <el-tooltip content="编辑" placement="top">
                <el-button size="small" circle @click="emit('edit', row)">
                  <el-icon><Edit /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="测试 Bot" placement="top">
                <el-button
                  size="small"
                  type="primary"
                  plain
                  circle
                  @click="emit('test', row)"
                >
                  <el-icon><CircleCheck /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip :content="row.enabled ? '停用' : '启用'" placement="top">
                <el-button
                  size="small"
                  :type="row.enabled ? 'warning' : 'success'"
                  plain
                  circle
                  @click="emit('toggle', row, !row.enabled)"
                >
                  <el-icon><SwitchButton /></el-icon>
                </el-button>
              </el-tooltip>
              <el-tooltip content="删除" placement="top">
                <el-button
                  size="small"
                  type="danger"
                  circle
                  @click="emit('delete', row.id)"
                >
                  <el-icon><Delete /></el-icon>
                </el-button>
              </el-tooltip>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed } from "vue"
import { CircleCheck, Delete, Edit, Plus, SwitchButton } from "@element-plus/icons-vue"
import CopyText from "./CopyText.vue"
import ErrorText from "./ErrorText.vue"
import StatusTag from "./StatusTag.vue"

const props = defineProps({
  bots: {
    type: Array,
    required: true,
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  "add",
  "edit",
  "delete",
  "toggle",
  "test",
])

const enabledCount = computed(() => props.bots.filter((bot) => bot.enabled).length)

const botUsername = (bot) => {
  const username = String(bot?.username || "").trim()

  if (username) {
    return username.startsWith("@") ? username : `@${username}`
  }

  const link = String(bot?.bot_link || "").trim()
  const match = link.match(/t\.me\/([^/?#]+)/i)

  return match ? `@${match[1]}` : ""
}

const maskToken = (token) => {
  if (!token) {
    return "-"
  }

  if (token.length <= 12) {
    return "******"
  }

  return `${token.slice(0, 8)}...${token.slice(-6)}`
}
</script>

<style scoped>
.bot-page {
  width: 100%;
}

.bot-card {
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.card-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
}

.token-text {
  font-family: monospace;
  color: #606266;
}

.code-pill {
  display: inline-flex;
  max-width: 100%;
  padding: 3px 8px;
  border-radius: 6px;
  background: #f5f7fa;
  border: 1px solid #e5e7eb;
}

.muted {
  color: #909399;
  font-size: 12px;
}

.action-buttons {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.action-buttons .el-button {
  margin-left: 0;
}
</style>
