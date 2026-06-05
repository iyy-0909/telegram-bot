<template>
  <el-card class="binding-card">
    <template #header>
      <div class="card-header">
        <div>
          <div class="card-title">目标频道绑定</div>
          <div class="card-subtitle">配置每个目标频道使用哪个 Bot 分发</div>
        </div>

        <el-button type="primary" @click="emit('add')">
          新增绑定
        </el-button>
      </div>
    </template>

    <el-table
      :data="bindings"
      border
      stripe
      height="492"
      style="width: 100%"
      empty-text="暂无绑定"
    >
      <el-table-column prop="id" label="ID" width="70" align="center" />

      <el-table-column prop="target_channel" label="目标频道" min-width="180" />

      <el-table-column label="Bot" min-width="180">
        <template #default="{ row }">
          {{ getBotName(row.bot_id) }}
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

      <el-table-column prop="remark" label="备注" min-width="180" />

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
          </div>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
const props = defineProps({
  bindings: {
    type: Array,
    required: true,
  },
  bots: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits([
  "add",
  "edit",
  "delete",
  "toggle",
])

const getBotName = (botId) => {
  const bot = props.bots.find(item => item.id === botId)

  if (!bot) {
    return `Bot #${botId}`
  }

  return `${bot.name} (#${bot.id})`
}
</script>

<style scoped>
.binding-card {
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

.action-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
}

.action-buttons .el-button {
  margin-left: 0;
}
</style>
