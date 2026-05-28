<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>账号管理</span>

        <el-button type="primary" @click="$emit('add')">
          新增账号
        </el-button>
      </div>
    </template>

    <el-table
      :data="accounts"
      v-loading="loading"
      border
      empty-text="暂无采集账号，请运行 login_account.py 登录或点击新增账号。"
    >
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="账号名称" min-width="140" show-overflow-tooltip />

      <el-table-column label="Telegram 用户名" min-width="160">
        <template #default="{ row }">
          <CopyText
            v-if="row.username"
            :value="formatUsername(row.username)"
            :text="formatUsername(row.username)"
            tone="primary"
          />
          <span v-else>-</span>
        </template>
      </el-table-column>

      <el-table-column prop="phone" label="手机号" min-width="140" show-overflow-tooltip />
      <el-table-column prop="session_path" label="Session" min-width="220" show-overflow-tooltip />

      <el-table-column label="启用" width="100">
        <template #default="{ row }">
          <StatusTag :status="row.enabled ? 'enabled' : 'disabled'" />
        </template>
      </el-table-column>

      <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip />

      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button
            size="small"
            @click="$emit('edit', row)"
          >
            编辑
          </el-button>

          <el-button
            size="small"
            @click="toggleAccount(row)"
          >
            {{ row.enabled ? "禁用" : "启用" }}
          </el-button>

          <el-button
            size="small"
            type="danger"
            @click="$emit('delete', row.id)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import CopyText from "./CopyText.vue"
import StatusTag from "./StatusTag.vue"

const props = defineProps({
  accounts: {
    type: Array,
    default: () => [],
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
])

function formatUsername(username) {
  const value = String(username || "").trim()

  if (!value) {
    return "-"
  }

  return value.startsWith("@") ? value : `@${value}`
}

function toggleAccount(row) {
  row.enabled = !row.enabled
  emit("toggle", row)
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

</style>
