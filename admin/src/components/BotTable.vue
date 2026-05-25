<template>
  <el-card class="bot-card">
    <template #header>
      <div class="card-header">
        <div>
          <div class="card-title">Bot 管理</div>
          <div class="card-subtitle">官方 Bot 分发账号管理</div>
        </div>

        <el-button type="primary" @click="emit('add')">
          新增 Bot
        </el-button>
      </div>
    </template>

    <el-table
      :data="bots"
      border
      stripe
      style="width: 100%"
      empty-text="暂无 Bot"
    >
      <el-table-column prop="id" label="ID" width="70" align="center" />

      <el-table-column prop="name" label="Bot 名称" min-width="160" />

      <el-table-column label="Token" min-width="260">
        <template #default="{ row }">
          <span class="token-text">
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

      <el-table-column prop="remark" label="备注" min-width="160" />

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
            <el-button
              size="small"
              @click="emit('edit', row)"
            >
              编辑
            </el-button>

            <el-button
              size="small"
              type="danger"
              @click="emit('delete', row.id)"
            >
              删除
            </el-button>
            <el-button
                size="small"
                type="primary"
                plain
                @click="emit('test', row)"
                >
                测试
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
defineProps({
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
.bot-card {
  border-radius: 12px;
}

.card-header {
  display: flex;
  align-items: center;
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

.token-text {
  font-family: monospace;
  color: #606266;
}

.error-text {
  color: #f56c6c;
  font-size: 12px;
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
}

.action-buttons .el-button {
  margin-left: 0;
}
</style>