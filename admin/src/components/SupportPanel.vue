<template>
  <div class="support-page">
    <el-tabs v-model="activeTab" class="support-tabs" @tab-change="handleTabChange">
      <el-tab-pane label="客户列表" name="customers">
        <div class="section-card">
          <div class="section-toolbar">
            <el-input
              v-model="customerQuery"
              clearable
              placeholder="搜索 Telegram ID、用户名、昵称、来源"
              class="search-input"
              @keyup.enter="loadCustomers"
              @clear="loadCustomers"
            />
            <el-button @click="loadCustomers">刷新</el-button>
          </div>

          <el-table :data="customers" border>
            <el-table-column label="客户" min-width="180">
              <template #default="{ row }">
                <div class="customer-name">{{ displayCustomer(row) }}</div>
                <div class="muted">ID：{{ row.telegram_user_id }}</div>
              </template>
            </el-table-column>
            <el-table-column prop="source" label="来源" min-width="140" show-overflow-tooltip />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag :type="row.blocked ? 'danger' : 'success'">
                  {{ row.blocked ? "已拉黑" : row.status || "active" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="last_message_at" label="最后消息" width="170">
              <template #default="{ row }">{{ formatTime(row.last_message_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="260">
              <template #default="{ row }">
                <el-button size="small" @click="openCustomerMessages(row)">查看记录</el-button>
                <el-button
                  v-if="row.blocked"
                  size="small"
                  type="success"
                  @click="unblockCustomer(row)"
                >
                  取消拉黑
                </el-button>
                <el-button
                  v-else
                  size="small"
                  type="danger"
                  plain
                  @click="blockCustomer(row)"
                >
                  拉黑
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="会话记录" name="records">
        <div class="records-layout">
          <aside class="conversation-list">
            <div class="list-toolbar">
              <el-select v-model="conversationFilters.status" size="small" @change="loadConversations">
                <el-option label="全部" value="all" />
                <el-option label="未关闭" value="open" />
                <el-option label="已关闭" value="closed" />
                <el-option label="已拉黑" value="blocked" />
              </el-select>
              <el-input
                v-model="conversationFilters.q"
                size="small"
                clearable
                placeholder="搜索客户或消息"
                @keyup.enter="loadConversations"
                @clear="loadConversations"
              />
            </div>

            <button
              v-for="item in conversations"
              :key="item.id"
              type="button"
              class="conversation-item"
              :class="{ active: selectedConversationId === item.id }"
              @click="selectConversation(item.id)"
            >
              <strong>{{ displayCustomer(item.customer) }}</strong>
              <span>{{ formatTime(item.last_message_at) }}</span>
              <p>{{ item.last_message || "暂无消息" }}</p>
            </button>

            <el-empty v-if="!conversations.length" description="暂无会话" :image-size="80" />
          </aside>

          <section class="message-panel">
            <template v-if="conversationDetail">
              <header class="message-header">
                <div>
                  <h3>{{ displayCustomer(conversationDetail.conversation.customer) }}</h3>
                  <p>
                    会话ID：{{ conversationDetail.conversation.id }}
                    · 来源：{{ conversationDetail.conversation.customer.source || "-" }}
                    · 状态：{{ conversationDetail.conversation.status }}
                    <span v-if="conversationDetail.conversation.support_thread_id">
                      · 话题ID：{{ conversationDetail.conversation.support_thread_id }}
                    </span>
                  </p>
                </div>
                <el-button size="small" @click="closeConversation">关闭会话</el-button>
              </header>

              <div class="message-scroll">
                <div
                  v-for="message in conversationDetail.messages"
                  :key="message.id"
                  class="message-row"
                  :class="message.sender_type === 'customer' ? 'from-customer' : 'from-support'"
                >
                  <div class="message-bubble">
                    <div class="message-text">
                      <template v-if="message.text">{{ message.text }}</template>
                      <template v-else-if="message.file_id">
                        [{{ message.message_type }}] {{ message.file_id }}
                      </template>
                      <template v-else>[{{ message.message_type || "other" }}]</template>
                    </div>
                    <div class="message-meta">
                      {{ senderLabel(message.sender_type) }}
                      · {{ formatTime(message.created_at) }}
                      <span v-if="message.support_group_message_id">
                        · 群消息 {{ message.support_group_message_id }}
                      </span>
                      <span v-if="message.send_status === 'failed'" class="failed">发送失败</span>
                    </div>
                    <div v-if="message.error_message" class="message-error">
                      {{ message.error_message }}
                    </div>
                  </div>
                </div>
              </div>
            </template>

            <el-empty v-else description="请选择会话查看记录" />
          </section>
        </div>
      </el-tab-pane>

      <el-tab-pane label="快捷回复" name="quick">
        <div class="section-card">
          <div class="section-toolbar">
            <el-button type="primary" @click="openQuickDialog()">新增快捷回复</el-button>
          </div>

          <el-table :data="quickReplies" border>
            <el-table-column prop="title" label="标题" width="180" />
            <el-table-column prop="content" label="内容" min-width="320" show-overflow-tooltip />
            <el-table-column prop="sort" label="排序" width="90" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">
                <el-tag :type="row.enabled ? 'success' : 'info'">
                  {{ row.enabled ? "启用" : "禁用" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <el-button size="small" @click="openQuickDialog(row)">编辑</el-button>
                <el-button size="small" type="danger" plain @click="removeQuickReply(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane label="客服设置" name="settings">
        <div class="section-card settings-card">
          <el-alert
            title="当前接收模式：polling。启动 polling 前系统会自动 deleteWebhook。建议关闭 BotFather 的 Group Privacy，否则 Bot 可能收不到客服群普通消息。"
            type="info"
            show-icon
            :closable="false"
            class="setting-alert"
          />

          <el-form label-width="150px">
            <el-form-item label="复用已有 Bot">
              <el-select v-model="settings.support_bot_id" clearable placeholder="选择 Bot">
                <el-option
                  v-for="bot in bots"
                  :key="bot.id"
                  :label="`${bot.name} #${bot.id}`"
                  :value="String(bot.id)"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="或填写 Bot Token">
              <el-input
                v-model="settings.support_bot_token"
                type="password"
                show-password
                placeholder="未选择已有 Bot 时使用"
              />
            </el-form-item>

            <el-form-item label="接收模式">
              <el-tag type="success">polling</el-tag>
            </el-form-item>

            <el-form-item label="本地 polling">
              <el-switch
                v-model="settings.support_polling_enabled"
                active-value="1"
                inactive-value="0"
              />
            </el-form-item>

            <el-form-item label="客服群 chat_id">
              <el-input v-model="settings.support_group_chat_id" placeholder="-100..." />
            </el-form-item>

            <el-form-item label="检测工具">
              <div class="tool-row">
                <el-button :loading="testingBot" @click="detectBot">检测 Bot</el-button>
                <el-button :loading="loadingUpdates" @click="loadRecentUpdates">
                  获取最近 updates
                </el-button>
              </div>
              <div v-if="botTestResult" class="result-line">{{ botTestResult }}</div>
            </el-form-item>

            <el-form-item v-if="groupCandidates.length" label="群候选">
              <el-table :data="groupCandidates" border size="small" class="group-table">
                <el-table-column prop="title" label="群名称" min-width="160" />
                <el-table-column prop="chat_id" label="chat_id" min-width="180" />
                <el-table-column prop="type" label="类型" width="110" />
                <el-table-column label="话题权限" width="170">
                  <template #default="{ row }">
                    <el-tag :type="row.permission?.ok ? 'success' : 'danger'">
                      {{ row.permission?.ok ? "可管理话题" : "缺少权限" }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="last_seen_at" label="发现时间" width="170" />
                <el-table-column label="操作" width="150">
                  <template #default="{ row }">
                    <el-button size="small" type="primary" plain @click="useSupportGroup(row)">
                      使用此群
                    </el-button>
                  </template>
                </el-table-column>
              </el-table>
            </el-form-item>

            <el-form-item label="后台链接">
              <el-input v-model="settings.support_backend_base_url" placeholder="http://127.0.0.1:5173" />
            </el-form-item>

            <el-form-item label="欢迎语">
              <el-input v-model="settings.welcome_message" type="textarea" :rows="3" />
            </el-form-item>

            <el-form-item label="非营业时间回复">
              <el-input v-model="settings.off_hours_message" type="textarea" :rows="3" />
            </el-form-item>

            <el-form-item label="营业时间">
              <div class="business-row">
                <el-switch
                  v-model="settings.business_hours_enabled"
                  active-value="1"
                  inactive-value="0"
                />
                <el-input-number v-model="businessStartHour" :min="0" :max="23" />
                <span>至</span>
                <el-input-number v-model="businessEndHour" :min="0" :max="23" />
              </div>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="saveSettings">保存设置</el-button>
            </el-form-item>
          </el-form>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog
      v-model="quickDialogVisible"
      :title="quickForm.id ? '编辑快捷回复' : '新增快捷回复'"
      width="520px"
    >
      <el-form label-width="80px">
        <el-form-item label="标题">
          <el-input v-model="quickForm.title" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="quickForm.content" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="quickForm.sort" :min="0" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="quickForm.enabled" />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="quickDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveQuickReply">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"

import {
  blockSupportCustomer,
  closeSupportConversation,
  createSupportQuickReply,
  deleteSupportQuickReply,
  getRecentSupportUpdates,
  getSupportConversation,
  getSupportConversations,
  getSupportCustomers,
  getSupportQuickReplies,
  getSupportSettings,
  testSupportBot,
  updateSupportQuickReply,
  updateSupportSettings,
  unblockSupportCustomer,
} from "../api/support"

defineProps({
  bots: {
    type: Array,
    default: () => [],
  },
})

const activeTab = ref("customers")
const customers = ref([])
const customerQuery = ref("")
const conversations = ref([])
const conversationDetail = ref(null)
const selectedConversationId = ref(null)
const quickReplies = ref([])
const groupCandidates = ref([])
const botTestResult = ref("")
const testingBot = ref(false)
const loadingUpdates = ref(false)

const conversationFilters = reactive({
  status: "all",
  q: "",
})

const settings = reactive({
  support_bot_id: "",
  support_bot_token: "",
  support_polling_enabled: "0",
  support_group_chat_id: "",
  support_backend_base_url: "http://127.0.0.1:5173",
  welcome_message: "",
  off_hours_message: "",
  business_hours_enabled: "0",
  business_start_hour: "9",
  business_end_hour: "22",
})

const businessStartHour = computed({
  get: () => Number(settings.business_start_hour || 9),
  set: (value) => {
    settings.business_start_hour = String(value)
  },
})

const businessEndHour = computed({
  get: () => Number(settings.business_end_hour || 22),
  set: (value) => {
    settings.business_end_hour = String(value)
  },
})

const quickDialogVisible = ref(false)
const quickForm = reactive({
  id: null,
  title: "",
  content: "",
  sort: 0,
  enabled: true,
})

function displayCustomer(customer) {
  if (!customer) return "未知客户"
  if (customer.username) return `@${customer.username}`
  const name = [customer.first_name, customer.last_name].filter(Boolean).join(" ")
  return name || customer.telegram_user_id || "未知客户"
}

function formatTime(value) {
  if (!value) return "-"
  return String(value).replace("T", " ").slice(0, 19)
}

function senderLabel(senderType) {
  if (senderType === "customer") return "客户"
  if (senderType === "bot") return "机器人"
  return "客服群"
}

async function loadCustomers() {
  const res = await getSupportCustomers({ q: customerQuery.value, limit: 200 })
  customers.value = res.data.customers || []
}

async function loadConversations() {
  const res = await getSupportConversations({
    status: conversationFilters.status,
    q: conversationFilters.q,
    limit: 100,
  })
  conversations.value = res.data.conversations || []
}

async function selectConversation(id) {
  selectedConversationId.value = id
  const res = await getSupportConversation(id)
  if (!res.data.ok) {
    ElMessage.error(res.data.message || "会话不存在")
    return
  }
  conversationDetail.value = res.data
  await nextTick()
}

async function openCustomerMessages(row) {
  activeTab.value = "records"
  await loadConversations()
  const matched = conversations.value.find((item) => item.customer_id === row.id)
  if (matched) await selectConversation(matched.id)
}

async function closeConversation() {
  if (!selectedConversationId.value) return
  const res = await closeSupportConversation(selectedConversationId.value)
  if (res.data.ok) {
    ElMessage.success("会话已关闭")
    await selectConversation(selectedConversationId.value)
    await loadConversations()
  }
}

async function blockCustomer(row) {
  await ElMessageBox.confirm("拉黑后客户消息不再转发到客服群，确定继续？", "拉黑客户", {
    type: "warning",
  })
  const res = await blockSupportCustomer(row.id)
  if (res.data.ok) {
    ElMessage.success("已拉黑")
    await loadCustomers()
    await loadConversations()
  }
}

async function unblockCustomer(row) {
  const res = await unblockSupportCustomer(row.id)
  if (res.data.ok) {
    ElMessage.success("已取消拉黑")
    await loadCustomers()
    await loadConversations()
  }
}

async function loadQuickReplies() {
  const res = await getSupportQuickReplies()
  quickReplies.value = res.data.items || []
}

async function loadSettings() {
  const res = await getSupportSettings()
  Object.assign(settings, res.data.settings || {})
}

async function detectBot() {
  testingBot.value = true
  botTestResult.value = ""
  try {
    const res = await testSupportBot()
    if (res.data.ok) {
      const bot = res.data.bot || {}
      const permission = res.data.group_permission
      const permissionText = permission
        ? (permission.ok ? "客服群话题权限正常" : permission.message || "客服群话题权限异常")
        : "尚未配置客服群"
      botTestResult.value = `检测成功：@${bot.username || bot.first_name || bot.id}，模式 polling；${permissionText}`
      ElMessage.success("Bot 检测成功")
    } else {
      botTestResult.value = res.data.message || "检测失败"
      ElMessage.error(botTestResult.value)
    }
  } finally {
    testingBot.value = false
  }
}

async function loadRecentUpdates() {
  loadingUpdates.value = true
  try {
    const res = await getRecentSupportUpdates({ limit: 50 })
    groupCandidates.value = res.data.groups || []
    if (!res.data.ok) {
      ElMessage.warning(res.data.message || "获取 updates 失败")
      return
    }
    if (!groupCandidates.value.length) {
      ElMessage.info("未发现群消息，请把 Bot 拉进客服群后发送一条测试消息")
    } else {
      ElMessage.success(`发现 ${groupCandidates.value.length} 个群候选`)
    }
  } finally {
    loadingUpdates.value = false
  }
}

function useSupportGroup(row) {
  settings.support_group_chat_id = row.chat_id
  ElMessage.success(`已填入客服群：${row.title || row.chat_id}`)
}

function openQuickDialog(row = null) {
  Object.assign(quickForm, {
    id: row?.id || null,
    title: row?.title || "",
    content: row?.content || "",
    sort: row?.sort || 0,
    enabled: row?.enabled ?? true,
  })
  quickDialogVisible.value = true
}

async function saveQuickReply() {
  const payload = {
    title: quickForm.title.trim(),
    content: quickForm.content,
    sort: quickForm.sort,
    enabled: quickForm.enabled,
  }
  if (!payload.title || !payload.content.trim()) {
    ElMessage.warning("请填写标题和内容")
    return
  }
  if (quickForm.id) await updateSupportQuickReply(quickForm.id, payload)
  else await createSupportQuickReply(payload)
  quickDialogVisible.value = false
  ElMessage.success("已保存")
  await loadQuickReplies()
}

async function removeQuickReply(row) {
  await ElMessageBox.confirm(`确定删除快捷回复「${row.title}」？`, "删除确认", {
    type: "warning",
  })
  const res = await deleteSupportQuickReply(row.id)
  if (res.data.ok) {
    ElMessage.success("已删除")
    await loadQuickReplies()
  }
}

async function saveSettings() {
  const res = await updateSupportSettings({ ...settings })
  Object.assign(settings, res.data.settings || {})
  ElMessage.success("设置已保存")
}

async function handleTabChange(name) {
  if (name === "customers") await loadCustomers()
  if (name === "records") await loadConversations()
  if (name === "quick") await loadQuickReplies()
  if (name === "settings") await loadSettings()
}

onMounted(async () => {
  await Promise.all([
    loadCustomers(),
    loadConversations(),
    loadQuickReplies(),
    loadSettings(),
  ])
  const queryConversationId = Number(
    new URLSearchParams(window.location.search).get("conversation_id") || 0,
  )
  if (queryConversationId) {
    activeTab.value = "records"
    await selectConversation(queryConversationId)
  }
})
</script>

<style scoped>
.support-page {
  min-height: calc(100vh - 100px);
}

.support-tabs {
  background: #ffffff;
  border-radius: 8px;
  padding: 14px;
}

.section-card {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 16px;
}

.section-toolbar {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-bottom: 12px;
}

.search-input {
  max-width: 360px;
}

.customer-name {
  font-weight: 600;
  color: #111827;
}

.muted {
  margin-top: 3px;
  font-size: 12px;
  color: #6b7280;
}

.records-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  min-height: calc(100vh - 210px);
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}

.conversation-list {
  background: #f8fafc;
  border-right: 1px solid #e5e7eb;
  overflow-y: auto;
}

.list-toolbar {
  padding: 12px;
  display: grid;
  gap: 8px;
  border-bottom: 1px solid #e5e7eb;
}

.conversation-item {
  width: calc(100% - 16px);
  margin: 8px;
  padding: 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  text-align: left;
  cursor: pointer;
  color: #1f2937;
}

.conversation-item span,
.conversation-item p {
  display: block;
  margin: 4px 0 0;
  font-size: 12px;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.conversation-item:hover,
.conversation-item.active {
  background: #ffffff;
  border-color: #dbeafe;
}

.message-panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: #ffffff;
}

.message-header {
  padding: 14px 18px;
  border-bottom: 1px solid #e5e7eb;
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.message-header h3 {
  margin: 0 0 4px;
  font-size: 18px;
}

.message-header p {
  margin: 0;
  color: #6b7280;
  font-size: 12px;
}

.message-scroll {
  flex: 1;
  overflow-y: auto;
  padding: 18px;
  background: #f9fafb;
}

.message-row {
  display: flex;
  margin-bottom: 12px;
}

.message-row.from-support {
  justify-content: flex-end;
}

.message-bubble {
  max-width: min(640px, 76%);
  padding: 10px 12px;
  border-radius: 8px;
  background: #ffffff;
  border: 1px solid #e5e7eb;
}

.from-support .message-bubble {
  background: #ecfdf5;
  border-color: #bbf7d0;
}

.message-text {
  white-space: pre-wrap;
  word-break: break-word;
  color: #111827;
}

.message-meta {
  margin-top: 6px;
  font-size: 12px;
  color: #6b7280;
}

.failed,
.message-error {
  margin-top: 4px;
  color: #dc2626;
}

.settings-card {
  max-width: 920px;
}

.setting-alert {
  margin-bottom: 16px;
}

.business-row,
.tool-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.result-line {
  margin-top: 8px;
  color: #4b5563;
  font-size: 13px;
}

.group-table {
  width: 100%;
}

@media (max-width: 980px) {
  .records-layout {
    grid-template-columns: 1fr;
  }

  .conversation-list {
    min-height: 260px;
    border-right: none;
    border-bottom: 1px solid #e5e7eb;
  }
}
</style>
