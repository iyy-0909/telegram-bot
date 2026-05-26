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
      border
      stripe
      size="large"
      style="width: 100%"
      empty-text="暂无 Bot"
    >
      <el-table-column prop="id" label="ID" width="70" align="center" />

      <el-table-column prop="name" label="Bot 名称" min-width="160" />

      <el-table-column label="Bot 链接" min-width="190">
        <template #default="{ row }">
          <a
            v-if="row.bot_link"
            class="bot-link chip-link"
            :href="row.bot_link"
            target="_blank"
            rel="noopener noreferrer"
          >
            <el-icon><Link /></el-icon>
            {{ row.bot_link }}
          </a>
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
          <el-switch
            :model-value="row.enabled"
            size="small"
            @change="value => emit('toggle', row, value)"
          />
        </template>
      </el-table-column>

      <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip />

      <el-table-column label="最后错误" min-width="220">
        <template #default="{ row }">
          <span class="error-text">
            {{ row.last_error || "-" }}
          </span>
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
import { CircleCheck, Delete, Edit, Link, Plus } from "@element-plus/icons-vue"

const props = defineProps({
  bots: {
    type: Array,
    required: true,
  },
})

const emit = defineEmits([
  "add",
  "edit",
  "delete",
  "toggle",
  "test"
])

const enabledCount = computed(() => props.bots.filter((bot) => bot.enabled).length)

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

.bot-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #409eff;
  text-decoration: none;
}

.chip-link {
  max-width: 100%;
  padding: 3px 9px;
  border-radius: 999px;
  background: #ecf5ff;
  border: 1px solid #b3d8ff;
}

.bot-link:hover {
  text-decoration: underline;
}

.muted {
  color: #909399;
  font-size: 12px;
}

.error-text {
  color: #f56c6c;
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
