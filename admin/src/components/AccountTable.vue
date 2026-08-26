<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>账号管理</span>

        <div class="header-actions">
          <el-button @click="$emit('add')">
            手动新增
          </el-button>
          <el-button type="primary" @click="$emit('login')">
            登录账号
          </el-button>
        </div>
      </div>
    </template>

    <el-table
      :data="accounts"
      v-loading="loading"
      border
      height="492"
      empty-text="暂无采集账号，请运行 login_account.py 登录或点击新增账号。"
    >
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="账号名称" width="110" show-overflow-tooltip />

      <el-table-column label="Telegram 用户名" width="130">
        <template #default="{ row }">
          <CopyText
            v-if="row.username"
            :value="formatUsername(row.username)"
            :text="formatAccountUsername(row)"
            tone="primary"
          />
          <span v-else>-</span>
        </template>
      </el-table-column>

      <el-table-column prop="phone" label="手机号" width="110" show-overflow-tooltip />
      <el-table-column prop="session_path" label="Session" width="160" show-overflow-tooltip />

      <el-table-column label="默认账号" width="100" align="center">
        <template #default="{ row }">
          <el-tag v-if="row.is_default" type="success" size="small">全局默认</el-tag>
          <el-button
            v-else
            text
            type="primary"
            :disabled="!row.enabled"
            :loading="defaultSettingId === row.id"
            @click="$emit('set-default', row)"
          >
            设为默认
          </el-button>
        </template>
      </el-table-column>

      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <StatusTag :status="row.enabled ? 'enabled' : 'disabled'" />
        </template>
      </el-table-column>

      <el-table-column label="自动回复" width="145">
        <template #default="{ row }">
          <div class="reply-tags">
            <el-tag v-if="row.greeting_enabled" type="success" size="small">问候</el-tag>
            <el-tag v-if="row.away_enabled" type="warning" size="small">离线</el-tag>
            <span v-if="!row.greeting_enabled && !row.away_enabled">未开启</span>
          </div>
        </template>
      </el-table-column>

      <el-table-column prop="remark" label="备注" min-width="100" show-overflow-tooltip />

      <el-table-column label="操作" width="285">
        <template #default="{ row }">
          <div class="row-actions">
            <el-button
              size="small"
              type="primary"
              plain
              @click="$emit('relogin', row)"
            >
              重新登录
            </el-button>

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
          </div>
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
  defaultSettingId: {
    type: Number,
    default: null,
  },
})

const emit = defineEmits([
  "add",
  "login",
  "relogin",
  "edit",
  "delete",
  "toggle",
  "set-default",
])

function formatUsername(username) {
  const value = String(username || "").trim()

  if (!value) {
    return "-"
  }

  return value.startsWith("@") ? value : `@${value}`
}

function formatAccountUsername(row) {
  return `${formatUsername(row.username)} (#${row.id})`
}

function toggleAccount(row) {
  row.enabled = !row.enabled
  emit("toggle", row)
}
</script>

<style scoped>
.reply-tags {
  display: flex;
  gap: 6px;
  align-items: center;
  white-space: nowrap;
  color: var(--el-text-color-secondary);
}
</style>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.row-actions {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .card-header,
  .header-actions {
    align-items: stretch;
    flex-direction: column;
    width: 100%;
  }
}

</style>
