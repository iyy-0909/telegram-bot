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

    <el-table :data="accounts" border>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="账号名称" min-width="140" show-overflow-tooltip />

      <el-table-column label="Telegram 用户名" min-width="160">
        <template #default="{ row }">
          <button
            v-if="row.username"
            class="copy-username"
            type="button"
            @click="copyUsername(row.username)"
          >
            {{ formatUsername(row.username) }}
          </button>
          <span v-else>-</span>
        </template>
      </el-table-column>

      <el-table-column prop="phone" label="手机号" min-width="140" show-overflow-tooltip />
      <el-table-column prop="session_path" label="Session" min-width="220" show-overflow-tooltip />

      <el-table-column label="启用" width="100">
        <template #default="{ row }">
          <el-switch
            v-model="row.enabled"
            @change="$emit('toggle', row)"
          />
        </template>
      </el-table-column>

      <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip />

      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button
            size="small"
            @click="$emit('edit', row)"
          >
            编辑
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
import { ElMessage } from "element-plus"
import { copyText } from "../utils/clipboard"

defineProps({
  accounts: {
    type: Array,
    default: () => [],
  },
})

defineEmits([
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

async function copyUsername(username) {
  const value = formatUsername(username)

  try {
    const ok = await copyText(value)
    if (!ok) throw new Error("copy failed")
    ElMessage.success("已复制")
  } catch {
    ElMessage.error("复制失败")
  }
}
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.copy-username {
  border: 0;
  padding: 0;
  color: #1677ff;
  background: transparent;
  cursor: pointer;
  font: inherit;
}

.copy-username:hover {
  text-decoration: underline;
}
</style>
