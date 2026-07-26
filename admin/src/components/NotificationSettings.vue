<template>
  <div class="notification-page">
    <div class="page-hero">
      <div>
        <div class="title">Telegram 消息通知</div>
        <div class="subtitle">为每个登录账号配置独立的 ntfy 推送主题。</div>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadSettings">刷新</el-button>
    </div>

    <el-alert
      type="info"
      show-icon
      :closable="false"
      class="page-notice"
      title="每个账号配置一个独立主题，例如 telegram_4_xxxxx；服务器地址由系统自动添加。"
    />
    <div class="fallback-hint">
      全局推送已关闭。未保存独立主题的账号不会发送通知。
    </div>

    <el-alert
      v-if="loadError"
      type="error"
      show-icon
      :closable="false"
      class="page-notice"
      :title="loadError"
    >
      <template #default>
        <el-button link type="primary" @click="loadSettings">重新加载</el-button>
      </template>
    </el-alert>

    <el-card class="settings-card">
      <template #header>
        <div class="card-header">
          <div>
            <div class="card-title">账号推送主题</div>
            <div class="card-subtitle">
              已配置 {{ configuredCount }} 个，已启用 {{ enabledCount }} 个
            </div>
          </div>
        </div>
      </template>

      <el-table
        class="desktop-table"
        :data="rows"
        v-loading="loading"
        border
        height="492"
        empty-text="暂无 Telegram 账号，请先到账号管理登录账号。"
      >
        <el-table-column label="Telegram 账号" min-width="180">
          <template #default="{ row }">
            <div class="account-name">{{ row.account_name }}</div>
            <div class="account-meta">
              {{ formatUsername(row.account_username) }} · #{{ row.account_id }}
            </div>
          </template>
        </el-table-column>

        <el-table-column label="账号状态" width="100" align="center">
          <template #default="{ row }">
            <StatusTag :status="row.account_enabled ? 'enabled' : 'disabled'" />
          </template>
        </el-table-column>

        <el-table-column label="ntfy 主题" min-width="390">
          <template #default="{ row }">
            <el-input
              v-model="row.ntfy_url"
              clearable
              :disabled="isBusy(row)"
              placeholder="例如 telegram_4_xxxxx"
              @input="clearRowError(row)"
            />
            <div v-if="row.validationError" class="field-error">{{ row.validationError }}</div>
          </template>
        </el-table-column>

        <el-table-column label="启用" width="90" align="center">
          <template #default="{ row }">
            <el-switch
              v-model="row.enabled"
              :disabled="!row.account_enabled || isBusy(row)"
            />
          </template>
        </el-table-column>

        <el-table-column label="最近测试" min-width="180">
          <template #default="{ row }">
            <div v-if="row.last_test_at" class="test-result">
              <el-tag
                :type="row.last_test_status === 'success' ? 'success' : 'danger'"
                size="small"
              >
                {{ row.last_test_status === "success" ? "成功" : "失败" }}
              </el-tag>
              <span>{{ formatTime(row.last_test_at) }}</span>
              <el-tooltip
                v-if="row.last_test_message"
                :content="row.last_test_message"
                placement="top"
              >
                <el-icon class="result-info"><InfoFilled /></el-icon>
              </el-tooltip>
            </div>
            <span v-else class="muted">尚未测试</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="250" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button
                type="primary"
                link
                :icon="Check"
                :loading="savingId === row.account_id"
                :disabled="testingId === row.account_id"
                @click="saveRow(row)"
              >
                保存
              </el-button>
              <el-button
                type="primary"
                link
                :icon="MagicStick"
                :loading="generatingId === row.account_id"
                :disabled="savingId === row.account_id || testingId === row.account_id"
                @click="generateRow(row)"
              >
                自动生成
              </el-button>
              <el-button
                type="primary"
                link
                :icon="Promotion"
                :loading="testingId === row.account_id"
                :disabled="!row.account_enabled || savingId === row.account_id"
                @click="testRow(row)"
              >
                测试
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <div v-loading="loading" class="mobile-list">
        <el-empty
          v-if="!loading && !rows.length"
          description="暂无 Telegram 账号，请先到账号管理登录账号。"
        />
        <section v-for="row in rows" :key="row.account_id" class="mobile-item">
          <div class="mobile-item__header">
            <div>
              <div class="account-name">{{ row.account_name }}</div>
              <div class="account-meta">
                {{ formatUsername(row.account_username) }} · #{{ row.account_id }}
              </div>
            </div>
            <StatusTag :status="row.account_enabled ? 'enabled' : 'disabled'" />
          </div>

          <label class="mobile-label">ntfy 主题</label>
          <el-input
            v-model="row.ntfy_url"
            clearable
            :disabled="isBusy(row)"
            placeholder="例如 telegram_4_xxxxx"
            @input="clearRowError(row)"
          />
          <div v-if="row.validationError" class="field-error">{{ row.validationError }}</div>

          <div class="mobile-item__line">
            <span>启用通知</span>
            <el-switch
              v-model="row.enabled"
              :disabled="!row.account_enabled || isBusy(row)"
            />
          </div>
          <div class="mobile-item__line">
            <span>最近测试</span>
            <span class="test-summary">
              {{ row.last_test_at ? `${testStatusText(row)} · ${formatTime(row.last_test_at)}` : "尚未测试" }}
            </span>
          </div>

          <div class="mobile-actions">
            <el-button
              :icon="Check"
              :loading="savingId === row.account_id"
              :disabled="testingId === row.account_id"
              @click="saveRow(row)"
            >
              保存
            </el-button>
            <el-button
              :icon="MagicStick"
              :loading="generatingId === row.account_id"
              :disabled="savingId === row.account_id || testingId === row.account_id"
              @click="generateRow(row)"
            >
              自动生成
            </el-button>
            <el-button
              type="primary"
              :icon="Promotion"
              :loading="testingId === row.account_id"
              :disabled="!row.account_enabled || savingId === row.account_id"
              @click="testRow(row)"
            >
              测试推送
            </el-button>
          </div>
        </section>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { Check, InfoFilled, MagicStick, Promotion, Refresh } from "@element-plus/icons-vue"
import { ElMessage, ElMessageBox } from "element-plus"
import StatusTag from "./StatusTag.vue"
import {
  getNotificationSettings,
  generateNotificationSetting,
  testNotificationSetting,
  updateNotificationSetting,
} from "../api/notifications"

const rows = ref([])
const loading = ref(false)
const loadError = ref("")
const savingId = ref(null)
const generatingId = ref(null)
const testingId = ref(null)

const configuredCount = computed(() => rows.value.filter((row) => row.ntfy_url.trim()).length)
const enabledCount = computed(() => rows.value.filter((row) => row.enabled && row.account_enabled).length)

function readError(error, fallback) {
  return error?.response?.data?.detail
    || error?.response?.data?.message
    || error?.message
    || fallback
}

function normalizeRows(items) {
  return (items || []).map((item) => ({
    ...item,
    ntfy_url: item.ntfy_url || "",
    enabled: Boolean(item.enabled),
    validationError: "",
  }))
}

async function loadSettings() {
  loading.value = true
  loadError.value = ""
  try {
    const response = await getNotificationSettings()
    rows.value = normalizeRows(response.data)
  } catch (error) {
    loadError.value = readError(error, "加载消息通知设置失败")
  } finally {
    loading.value = false
  }
}

function validateRow(row) {
  const topic = normalizeTopic(row.ntfy_url)
  if (row.enabled && !topic) {
    row.validationError = "启用通知前请填写 ntfy 主题"
    return false
  }
  if (topic && !/^[A-Za-z0-9_-]{1,64}$/.test(topic)) {
    row.validationError = "主题只能包含字母、数字、下划线和短横线，最长 64 个字符"
    return false
  }
  row.ntfy_url = topic
  row.validationError = ""
  return true
}

function normalizeTopic(value) {
  const input = String(value || "").trim()
  if (!/^https?:\/\//i.test(input)) return input.replace(/^\/+|\/+$/g, "")
  try {
    const url = new URL(input)
    return url.pathname.split("/").filter(Boolean).at(-1) || ""
  } catch {
    return input
  }
}

async function persistRow(row, showSuccess = true) {
  if (!validateRow(row)) return false
  savingId.value = row.account_id
  try {
    const response = await updateNotificationSetting(row.account_id, {
      ntfy_url: row.ntfy_url.trim(),
      enabled: row.enabled,
    })
    Object.assign(row, response.data, { validationError: "" })
    if (showSuccess) ElMessage.success(`${row.account_name} 的通知设置已保存`)
    return true
  } catch (error) {
    ElMessage.error(readError(error, "保存消息通知设置失败"))
    return false
  } finally {
    savingId.value = null
  }
}

async function saveRow(row) {
  await persistRow(row)
}

async function generateRow(row) {
  if (row.ntfy_url.trim()) {
    try {
      await ElMessageBox.confirm(
        `重新生成后，“${row.account_name}”的旧 ntfy 主题将失效。确定继续吗？`,
        "重新生成 ntfy 主题",
        {
          type: "warning",
          confirmButtonText: "确认生成",
          cancelButtonText: "取消",
        },
      )
    } catch (error) {
      if (error === "cancel" || error === "close") return
      throw error
    }
  }

  generatingId.value = row.account_id
  try {
    const response = await generateNotificationSetting(row.account_id)
    Object.assign(row, response.data?.setting || {}, { validationError: "" })
    ElMessage.success("主题已生成并保存，请在 ntfy 客户端订阅后启用通知")
  } catch (error) {
    ElMessage.error(readError(error, "自动生成 ntfy 主题失败"))
  } finally {
    generatingId.value = null
  }
}

async function testRow(row) {
  if (!validateRow(row)) return
  testingId.value = row.account_id
  try {
    const saved = await updateNotificationSetting(row.account_id, {
      ntfy_url: row.ntfy_url.trim(),
      enabled: row.enabled,
    })
    Object.assign(row, saved.data, { validationError: "" })
    const response = await testNotificationSetting(row.account_id)
    if (response.data?.setting) {
      Object.assign(row, response.data.setting, { validationError: "" })
    }
    ElMessage.success(response.data?.message || "测试通知已发送")
  } catch (error) {
    ElMessage.error(readError(error, "测试通知发送失败"))
    await loadSettings()
  } finally {
    testingId.value = null
  }
}

function clearRowError(row) {
  row.validationError = ""
}

function isBusy(row) {
  return savingId.value === row.account_id
    || generatingId.value === row.account_id
    || testingId.value === row.account_id
}

function formatUsername(value) {
  const username = String(value || "").trim().replace(/^@/, "")
  return username ? `@${username}` : "无用户名"
}

function formatTime(value) {
  if (!value) return "-"
  return String(value).replace("T", " ").slice(0, 19)
}

function testStatusText(row) {
  return row.last_test_status === "success" ? "成功" : "失败"
}

onMounted(loadSettings)
</script>

<style scoped>
.notification-page {
  min-width: 0;
}

.page-hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.title {
  font-size: 20px;
  font-weight: 700;
}

.subtitle {
  margin-top: 4px;
  color: var(--text-muted);
  font-size: 13px;
}

.page-notice {
  margin-bottom: 6px;
}

.fallback-hint {
  margin-bottom: 14px;
  color: var(--text-muted);
  font-size: 12px;
}

.settings-card {
  border-radius: 8px;
}

.account-name {
  overflow: hidden;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-meta,
.muted {
  overflow: hidden;
  color: var(--text-muted);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.field-error {
  margin-top: 4px;
  color: var(--danger);
  font-size: 12px;
  line-height: 18px;
}

.test-result {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 6px;
}

.test-result span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-info {
  flex: 0 0 auto;
  color: var(--text-muted);
  cursor: help;
}

.mobile-list {
  display: none;
  min-height: 160px;
}

.mobile-item {
  padding: 16px 0;
  border-bottom: 1px solid var(--border-color);
}

.mobile-item:first-child {
  padding-top: 0;
}

.mobile-item:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.mobile-item__header,
.mobile-item__line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.mobile-item__header {
  margin-bottom: 14px;
}

.mobile-label {
  display: block;
  margin-bottom: 6px;
  font-weight: 600;
}

.mobile-item__line {
  min-height: 40px;
  margin-top: 8px;
}

.test-summary {
  overflow: hidden;
  color: var(--text-muted);
  text-align: right;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mobile-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.mobile-actions .el-button {
  width: 100%;
  margin-left: 0;
}

@media (max-width: 900px) {
  .page-hero {
    align-items: stretch;
  }

  .desktop-table {
    display: none;
  }

  .mobile-list {
    display: block;
  }
}
</style>
