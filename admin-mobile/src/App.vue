<template>
  <div v-if="!authReady" class="auth-bootstrap" role="status" aria-live="polite">
    <el-icon class="is-loading"><Loading /></el-icon>
    <span>正在确认账号权限…</span>
  </div>

  <section
    v-else-if="authenticated && !currentUser"
    class="auth-bootstrap auth-bootstrap--error"
    aria-live="polite"
  >
    <el-alert
      type="error"
      show-icon
      :closable="false"
      title="暂时无法读取账号权限"
      :description="authLoadError || '请检查网络后重试。你的登录状态仍已保留。'"
    />
    <div class="auth-bootstrap__actions">
      <request-button type="primary" :loading="permissionRefreshing" @click="retryAuthBootstrap">重新加载</request-button>
      <request-button @click="logoutCurrentUser">退出登录</request-button>
    </div>
  </section>

  <AuthPanel v-else-if="!authenticated" :request-actions="{ 'authenticated': handleAuthSuccess }" />

  <MobileLayout
    v-else
    :active="activeTab"
    :nav-keys="mobileNavKeys"
    :user="currentUser"
    :refresh-disabled="!canRefreshActive"
    :detail-title="activeTab === 'channels' && selectedChannelId ? (selectedChannel?.title || selectedChannel?.username || `频道 #${selectedChannelId}`) : ''"
    :detail-subtitle="activeTab === 'channels' && selectedChannelId ? (selectedChannel?.username || selectedChannel?.chat_id || '频道详情') : ''"
    :request-actions="{ 'change': changeTab, 'refresh': loadActive, 'logout': logoutCurrentUser, 'back': closeChannel }"


  >
    <HomePage
      v-if="activeTab === 'home'"
      :status="status"
      :dashboard="dashboard"
      :loading="loading.home"
    />

    <div v-else-if="activeTab === 'listeners'" class="task-section">
      <el-tabs
        v-model="listenerView"
        stretch
        class="task-view-tabs"
        @tab-change="changeTaskView('listener', $event)"
      >
        <el-tab-pane label="监听任务" name="tasks" />
        <el-tab-pane label="执行任务" name="logs" />
      </el-tabs>
      <ListPage
        v-if="listenerView === 'tasks'"
        title="监听任务"
        placeholder="搜索任务名 / 源频道 / 目标频道 / https://t.me/..."
        empty-title="暂无监听任务"
        :keyword="keyword.listeners"
        :items="filteredListeners"
        :loading="loading.listeners"
        @update:keyword="keyword.listeners = $event"
      >
        <template #actions>
          <request-button size="small" type="primary" @click="openCreate('listener')">新增</request-button>
        </template>
        <template #default="{ item }">
          <TaskCard
            :title="item.name || `监听任务 #${item.id}`"
            :subtitle="item.source_channel"
            :status="item.status"
            :enabled="item.enabled"
            :meta="[
              ['任务 ID', item.id],
              ['目标频道', channelLine(item.target_channels)],
              ['运行状态', compactText(item.status)],
              ['启用状态', enabledLabel(item.enabled)],
              ['最后监听', formatDate(item.last_received_at)],
              ['最近动作', compactText(item.last_action || item.recent_action)],
              ['账号 / Bot', `${compactText(item.account_name || item.account_id)} / ${compactText(item.bot_name || item.bot_id)}`],
              ['只监听内容', channelLine(item.listen_required_keywords)],
              ['过滤词', channelLine(item.blocked_keywords)],
              ['删除联系方式', item.remove_contact_lines ? '是' : '否'],
              ['过滤二维码', item.filter_qr_code ? '是' : '否'],
              ['最后错误', compactText(item.last_error)],
            ]"
          >
            <request-button size="small" type="primary" plain @click="openEdit('listener', item)">编辑</request-button>
            <request-button size="small" :type="item.enabled ? 'warning' : 'success'" plain @click="toggleListener(item)">
              {{ item.enabled ? "停止" : "启动" }}
            </request-button>
            <request-button size="small" plain :loading="catchupCheckingId === item.id" :disabled="catchupVisible || catchupCheckingId !== null" @click="catchupListener(item)">补齐</request-button>
            <request-button size="small" type="danger" plain @click="removeItem('listener', item)">删除</request-button>
          </TaskCard>
        </template>
      </ListPage>
      <div v-else class="page task-log-page">
        <LogDrawer
          type="listener"
          :items="filteredLogItems"
          :keyword="logKeyword"
          :loading="logLoading"
          @update:keyword="logKeyword = $event"
          :request-actions="{ 'refresh': ($event) => (showLogs('listener')) }"
        />
      </div>
    </div>

    <div v-else-if="activeTab === 'clones'" class="task-section">
      <el-tabs
        v-model="cloneView"
        stretch
        class="task-view-tabs"
        @tab-change="changeTaskView('clone', $event)"
      >
        <el-tab-pane label="克隆任务" name="tasks" />
        <el-tab-pane label="执行任务" name="logs" />
      </el-tabs>
      <ListPage
        v-if="cloneView === 'tasks'"
        title="克隆任务"
        placeholder="搜索任务名 / 源频道 / 目标频道 / https://t.me/..."
        empty-title="暂无克隆任务"
        :keyword="keyword.clones"
        :items="filteredClones"
        :loading="loading.clones"
        @update:keyword="keyword.clones = $event"
      >
        <template #actions>
          <request-button size="small" type="primary" @click="openCreate('clone')">新增</request-button>
        </template>
        <template #default="{ item }">
          <TaskCard
            :title="item.name || `克隆任务 #${item.id}`"
            :subtitle="item.source_channel"
            :status="item.status"
            :enabled="item.enabled"
            :meta="[
              ['任务 ID', item.id],
              ['目标频道', channelLine(item.target_channels)],
              ['运行状态', compactText(item.status)],
              ['启用状态', enabledLabel(item.enabled)],
              ['最后监听', formatDate(item.last_received_at)],
              ['最近动作', compactText(item.last_action || item.recent_action)],
              ['账号 / Bot', `${compactText(item.account_name || item.account_id)} / ${compactText(item.bot_name || item.bot_id)}`],
              ['过滤词', channelLine(item.blocked_keywords)],
              ['删除联系方式', item.remove_contact_lines ? '是' : '否'],
              ['过滤二维码', item.filter_qr_code ? '是' : '否'],
              ['最后错误', compactText(item.last_error)],
            ]"
          >
            <request-button size="small" type="primary" plain @click="openEdit('clone', item)">编辑</request-button>
            <request-button size="small" type="success" plain @click="runAction(() => startCloneTask(item.id), '已启动克隆任务', loadClones)">启动</request-button>
            <request-button size="small" type="warning" plain @click="runAction(() => pauseCloneTask(item.id), '已暂停克隆任务', loadClones)">暂停</request-button>
            <request-button size="small" plain @click="runAction(() => resumeCloneTask(item.id), '已继续克隆任务', loadClones)">继续</request-button>
            <request-button size="small" type="danger" plain @click="runAction(() => stopCloneTask(item.id), '已停止克隆任务', loadClones)">停止</request-button>
            <request-button size="small" type="danger" plain @click="removeItem('clone', item)">删除</request-button>
          </TaskCard>
        </template>
      </ListPage>
      <div v-else class="page task-log-page">
        <LogDrawer
          type="clone"
          :items="filteredLogItems"
          :keyword="logKeyword"
          :loading="logLoading"
          @update:keyword="logKeyword = $event"
          :request-actions="{ 'refresh': ($event) => (showLogs('clone')) }"
        />
      </div>
    </div>

    <div v-else-if="activeTab === 'channels'" class="channel-section">
      <el-tabs v-if="!selectedChannelId" v-model="channelView" stretch class="channel-view-tabs">
        <el-tab-pane label="我的频道" name="channels" />
        <el-tab-pane label="机器人收录" name="collections" />
        <el-tab-pane label="搜索机器人" name="search-bots" />
      </el-tabs>
      <MobileChannelExplorer
      v-if="selectedChannelId || channelView === 'channels'"
      :channels="channels"
      :items="filteredChannels"
      :keyword="keyword.channels"
      :loading="loading.channels"
      :selected-id="selectedChannelId"
      :overview="channelOverview"
      :overview-loading="channelOverviewLoading"
      :overview-error="channelOverviewError"
      @update:keyword="keyword.channels = $event"
      @open="openChannel"
      @retry="loadChannelOverview"
      @create="openCreate('channel')"
      @batch-check="batchCheckChannels"
      @edit="openEdit('channel', $event)"
      @check="checkChannel"
      @submit="openChannelSubmit"
      @submissions="openChannelSubmissionStatus"
      @delete="removeItem('channel', $event)"
      @open-task="openChannelTask"
    />
      <MobileSearchBots
        ref="searchBotPanelRef"
        :page-visible="channelView === 'search-bots'"
        :request-actions="{ 'submission-changed': refreshChannelData }"
      />
      <MobileSearchBotCollections v-if="channelView === 'collections'" />
    </div>

    <MobileAccessOverview
      v-else-if="morePage === 'access'"
      :user="currentUser"
      :refreshing="permissionRefreshing"
      :request-actions="{ 'refresh': refreshAccessAndData, 'logout': logoutCurrentUser }"

    />

    <MobileControlAlerts
      v-else-if="morePage === 'alerts'"
      :request-actions="{ 'back': ($event) => (morePage = 'menu'), 'open-task': openTaskFromAlert }"

    />

    <MorePage
      v-else
      :page="morePage"
      :bots="filteredBots"
      :support-bots="filteredSupportBots"
      :templates="filteredTemplates"
      :accounts="filteredAccounts"
      :default-account-setting-id="defaultAccountSettingId"
      :settings="sendSettings"
      :ai-settings="aiSettings"
      :loading="loading"
      :keyword="keyword"
      :allowed-features="featureKeys"
      :is-admin="currentUser?.role === 'admin'"
      :request-actions="{ 'select': selectMorePage, 'update-keyword': updateKeyword, 'edit': openEdit, 'delete': removeItem, 'test-bot': testBotAction, 'manage-profile': openBotProfile, 'test-support': testSupportAction, 'toggle-account': toggleAccount, 'set-default-account': setDefaultAccount, 'toggle-bot': toggleBot, 'toggle-support': toggleSupportBot, 'toggle-template': toggleTemplate, 'save-settings': saveMobileSendSettings, 'save-ai-settings': saveMobileAiSettings, 'create': openCreate, 'login-account': openAccountLogin }"















    />

    <el-drawer
      v-model="editVisible"
      class="form-sheet"
      direction="btt"
      size="88%"
      :title="editTitle"
      destroy-on-close
    >
      <EditForm
        :type="editType"
        :form="editForm"
        :saving="saving"
        :bots="bots"
        :accounts="accounts"
        :templates="templates"
        :uploading="uploadingMedia"
        :request-actions="{ 'cancel': ($event) => (editVisible = false), 'save': saveEdit, 'upload-media': uploadWelcomeMedia, 'clear-media': clearWelcomeMedia }"



      />
    </el-drawer>

    <el-drawer
      v-model="accountLoginVisible"
      class="form-sheet"
      direction="btt"
      size="88%"
      title="账号登录"
      destroy-on-close
    >
      <AccountLoginForm
        :account="accountLoginTarget"
        :loading="accountLoginLoading"
        :request-actions="{ 'cancel': ($event) => (accountLoginVisible = false), 'start': startAccountLoginFlow, 'verify': verifyAccountLoginFlow }"


      />
    </el-drawer>

    <el-drawer
      v-model="botProfileVisible"
      class="form-sheet"
      direction="btt"
      size="90%"
      :title="`Telegram 公开资料${botProfileTarget?.name ? ` · ${botProfileTarget.name}` : ''}`"
      destroy-on-close
    >
      <MobileBotProfileEditor :bot="botProfileTarget" :visible="botProfileVisible" />
    </el-drawer>

    <el-drawer
      v-model="detailVisible"
      class="form-sheet"
      direction="btt"
      size="72%"
      title="详情"
    >
      <pre class="detail-text">{{ detailText }}</pre>
    </el-drawer>

    <el-dialog
      v-model="catchupVisible" title="一键补齐" width="min(520px, calc(100vw - 24px))"
      :close-on-click-modal="false" :close-on-press-escape="!catchupSubmitting"
      :show-close="!catchupSubmitting" destroy-on-close
    >
      <p>任务：{{ catchupPlan.task_name || '当前监听任务' }}</p>
      <p>检测到可补齐 {{ catchupPlan.catchup_count }} 条内容，仅发送各目标缺少的内容。</p>
      <el-form ref="catchupFormRef" :model="catchupForm" label-position="top" :disabled="catchupSubmitting">
        <el-form-item label="补齐条数" prop="limit" :rules="[{ required: true, type: 'integer', min: 1, max: catchupPlan.catchup_count, message: '请输入可补齐范围内的整数', trigger: 'change' }]">
          <el-input-number v-model="catchupForm.limit" :min="1" :max="catchupPlan.catchup_count" :precision="0" controls-position="right" aria-label="补齐条数" style="width: 100%" />
        </el-form-item>
        <el-form-item label="内容间隔（秒）" prop="interval_seconds" :rules="[{ required: true, type: 'integer', min: 1, max: 86400, message: '请输入 1 至 86400 秒的整数', trigger: 'change' }]">
          <el-input-number v-model="catchupForm.interval_seconds" :min="1" :max="86400" :precision="0" controls-position="right" aria-label="内容间隔（秒）" style="width: 100%" />
        </el-form-item>
      </el-form>
      <el-alert type="info" :closable="false" show-icon title="首条直接进入队列；每条发送完成后，等待设定间隔再处理下一条。相册按一条内容计算，全局发送限流仍生效。" />
      <el-alert v-if="catchupError" type="error" :closable="false" show-icon :title="catchupError" style="margin-top: 12px" />
      <template #footer>
        <request-button :disabled="catchupSubmitting" @click="catchupVisible = false">取消</request-button>
        <request-button type="primary" :loading="catchupSubmitting" @click="submitListenerCatchup">加入队列</request-button>
      </template>
    </el-dialog>

  </MobileLayout>
</template>

<script setup>
import { useRequestEmit } from '../../frontend-shared/requestActions.mjs'

import { computed, defineComponent, h, nextTick, onMounted, onUnmounted, reactive, ref, resolveComponent } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import { ArrowDownBold, ArrowUpBold, Loading } from "@element-plus/icons-vue"
import MobileLayout from "./components/MobileLayout.vue"
import MobileChannelExplorer from "./components/MobileChannelExplorer.vue"
import StatusPill from "./components/StatusPill.vue"
import EmptyState from "./components/EmptyState.vue"
import MobileSearchBots from "./components/MobileSearchBots.vue"
import MobileSearchBotCollections from "./components/MobileSearchBotCollections.vue"
import MobileSettingsPage from "./components/MobileSettingsPage.vue"
import MobileControlAlerts from "./components/MobileControlAlerts.vue"
import MobileBotProfileEditor from "./components/MobileBotProfileEditor.vue"
import MobileAccessOverview from "./components/MobileAccessOverview.vue"
import AuthPanel from "./components/AuthPanel.vue"
import {
  getErrorMessage,
  getSessionGeneration,
  getToken,
  isCanceledRequest,
  isCurrentSession,
  SESSION_INVALIDATED_EVENT,
  SESSION_STORAGE_CHANGED_EVENT,
  setToken,
} from "./api/client"
import {
  catchupListenerTask,
  checkListenerCatchup,
  checkListenerSourceSubscription,
  checkMyChannel,
  batchCheckMyChannels,
  createAccount,
  createBot,
  createCloneTask,
  createContentTemplate,
  createContentTemplateRule,
  createListenerTask,
  createMyChannel,
  createSupportBot,
  deleteAccount,
  deleteBot,
  deleteCloneTask,
  deleteContentTemplate,
  deleteContentTemplateRule,
  deleteListenerTask,
  deleteMyChannel,
  deleteSupportBot,
  getAccountOptions,
  getAccounts,
  getBots,
  getBotOptions,
  getCloneTasks,
  getCloneSendEvents,
  getContentTemplates,
  getContentTemplateRules,
  getCurrentUser,
  getListenerTasks,
  getListenerSendEvents,
  getMyChannels,
  getMyChannelOverview,
  getRuntimeDashboard,
  getAiSettings,
  getSendSettings,
  getStatus,
  getSupportBots,
  logoutUser,
  pauseCloneTask,
  resumeCloneTask,
  startCloneTask,
  startAccountLogin,
  startListenerTask,
  stopCloneTask,
  stopListenerTask,
  testBot,
  testSupportBotItem,
  uploadSupportMedia,
  updateAccount,
  updateBot,
  updateCloneTask,
  updateContentTemplate,
  updateContentTemplateRule,
  updateSendSettings,
  updateAiSettings,
  updateListenerTask,
  updateMyChannel,
  updateSupportBot,
  verifyAccountLogin,
} from "./api"
import {
  asArray,
  compactText,
  enabledLabel,
  formatDate,
  sourceTypeLabel,
} from "./utils/format"
import { matchesRow, searchRows } from "./utils/search"
import { hasAnyFeature, hasFeature, userFeatureKeys } from "./utils/access"

const authenticated = ref(Boolean(getToken()))
const authReady = ref(false)
const authLoadError = ref("")
const currentUser = ref(null)
const permissionRefreshing = ref(false)
const featureKeys = computed(() => userFeatureKeys(currentUser.value))
const mobileNavKeys = computed(() => {
  const items = []
  if (hasFeature(currentUser.value, "dashboard")) items.push("home")
  if (hasFeature(currentUser.value, "listener_tasks")) items.push("listeners")
  if (hasFeature(currentUser.value, "clone_tasks")) items.push("clones")
  if (hasFeature(currentUser.value, "channels")) items.push("channels")
  items.push("more")
  return items
})

const MORE_PAGE_FEATURES = {
  alerts: ["alerts"],
  bots: ["bots"],
  support: ["support"],
  settings: ["system_settings", "ai_settings"],
  accounts: ["accounts"],
}
const initialChannelId = Number(new URL(window.location.href).searchParams.get("channel")) || null
const activeTab = ref(initialChannelId ? "channels" : (window.localStorage.getItem("mobile_active_tab") || "home"))
const channelView = ref("channels")
const selectedChannelId = ref(initialChannelId)
const channelOverview = ref(null)
const channelOverviewLoading = ref(false)
const channelOverviewError = ref("")
let channelOverviewRequest = 0
let channelOpenedInApp = false
let channelListScrollY = 0
const selectedChannel = computed(() => channelOverview.value?.channel || channels.value.find(item => Number(item.id) === selectedChannelId.value))
const listenerView = ref("tasks")
const cloneView = ref("tasks")
const morePage = ref("menu")
const canRefreshActive = computed(() => {
  if (activeTab.value !== "more") return true
  return ["access", "bots", "support", "settings", "accounts"].includes(morePage.value)
})
const editVisible = ref(false)
const detailVisible = ref(false)
const detailText = ref("")
const editType = ref("")
const editForm = reactive({})
const saving = ref(false)
const uploadingMedia = ref(false)
const accountLoginVisible = ref(false)
const accountLoginLoading = ref(false)
const accountLoginTarget = ref(null)
const defaultAccountSettingId = ref(null)
const logLoading = ref(false)
const logType = ref("listener")
const logKeyword = ref("")
const logItems = ref([])
const searchBotPanelRef = ref(null)

const status = ref({})
const dashboard = ref({})
const sendSettings = ref({
  global_send_delay: 3,
  send_retry_count: 2,
  send_retry_delay: 5,
})
const listeners = ref([])
const clones = ref([])
const bots = ref([])
const channels = ref([])
const supportBots = ref([])
const templates = ref([])
const accounts = ref([])
const botProfileVisible = ref(false)
const botProfileTarget = ref(null)

const loading = reactive({
  home: false,
  listeners: false,
  clones: false,
  channels: false,
  bots: false,
  support: false,
  templates: false,
  settings: false,
  accounts: false,
})
const loadingOwners = new Map()
let permissionRefreshOwner = null

const keyword = reactive({
  listeners: "",
  clones: "",
  channels: "",
  bots: "",
  support: "",
  templates: "",
  settings: "",
  accounts: "",
})

const editTitle = computed(() => {
  const map = {
    listener: "监听任务",
    clone: "克隆任务",
    channel: "频道",
    bot: "Bot",
    support: "客服机器人",
    template: "内容模板",
    account: "账号",
  }
  const action = editForm.id ? "编辑" : "新增"
  return map[editType.value] ? `${action}${map[editType.value]}` : action
})
const aiSettings = ref({ providers: {} })

const filteredListeners = computed(() => searchRows(listeners.value, keyword.listeners, "tasks"))
const filteredClones = computed(() => searchRows(clones.value, keyword.clones, "tasks"))
const filteredChannels = computed(() => searchRows(channels.value, keyword.channels, "channels"))
const filteredBots = computed(() => searchRows(bots.value, keyword.bots, "bots"))
const filteredSupportBots = computed(() => searchRows(supportBots.value, keyword.support, "support"))
const templateGroups = computed(() => templates.value
  .filter((template) => !template.parent_id)
  .map((group) => ({
    ...group,
    items: templates.value.filter((template) => template.parent_id === group.id),
  }))
  .sort((a, b) => (b.id || 0) - (a.id || 0)))
const filteredTemplates = computed(() => searchRows(templateGroups.value, keyword.templates, "templates"))
const filteredAccounts = computed(() => searchRows(accounts.value, keyword.accounts, "accounts"))
const filteredLogItems = computed(() => filterLogItems(logItems.value, logKeyword.value))

function pickList(data) {
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.items)) return data.items
  if (Array.isArray(data?.data)) return data.data
  return []
}

function filterLogItems(items, value) {
  const text = String(value || "").trim()
  if (!text) return items
  return (items || []).filter((item) =>
    matchesRow(item, text, "events", [
      item.time,
      item.event_type,
      item.status,
      item.result,
      item.task_id,
      item.task_name,
      item.source_channel,
      item.target,
      item.source_message_id,
      item.target_message_id,
      item.grouped_id,
      item.source_message_url,
      item.target_message_url,
      item.message_type,
      item.message,
      item.error,
      item.bot_name,
    ]),
  )
}

function channelLine(value) {
  if (!value) return "-"
  if (Array.isArray(value)) return value.join("、")
  try {
    const parsed = JSON.parse(value)
    if (Array.isArray(parsed)) return parsed.join("、")
  } catch {
    return String(value)
  }
  return String(value)
}

function cloneProgress(row) {
  const done = row.sent_count ?? row.current_count ?? row.done_count
  const total = row.total_count ?? row.message_count
  if (done !== undefined && total !== undefined) return `${done}/${total}`
  return compactText(row.progress)
}

function updateKeyword(key, value) {
  keyword[key] = value
}

async function handleAuthSuccess(token, mode) {
  clearAuthorizedData()
  setToken(token)
  const authGeneration = getSessionGeneration()
  authReady.value = false
  authLoadError.value = ""
  const ready = await refreshCurrentUser({ silent: true })
  if (!isCurrentSession(authGeneration)) return
  if (!ready) {
    ElMessage.error("登录成功，但账号权限读取失败，请重新登录。")
    return
  }
  ElMessage.success(mode === "register" ? "注册成功" : "登录成功")
  await loadInitial()
  if (!isCurrentSession(authGeneration)) return
  if (mode === "register" && ["pending", "waiting"].includes(currentUser.value?.access_state)) {
    ElMessage.info("账号已创建，请等待管理员分配功能和使用时间。")
  }
}

function changeTab(tab) {
  if (!mobileNavKeys.value.includes(tab)) {
    ElMessage.warning("当前账号尚未开通该功能")
    ensureAccessibleRoute()
    return
  }
  if (tab !== "channels" && selectedChannelId.value) clearChannelSelection()
  activeTab.value = tab
  if (tab === "more") morePage.value = "menu"
  window.localStorage.setItem("mobile_active_tab", tab)
  return loadActive()
}

function canOpenMorePage(page) {
  if (["menu", "access"].includes(page)) return true
  const required = MORE_PAGE_FEATURES[page]
  return Array.isArray(required) && hasAnyFeature(currentUser.value, required)
}

function ensureAccessibleRoute() {
  if (selectedChannelId.value && !mobileNavKeys.value.includes("channels")) clearChannelSelection()
  if (!mobileNavKeys.value.includes(activeTab.value)) {
    activeTab.value = "more"
    window.localStorage.setItem("mobile_active_tab", "more")
  }
  if (activeTab.value === "more" && !canOpenMorePage(morePage.value)) {
    morePage.value = "access"
  }
  if (
    activeTab.value === "more"
    && currentUser.value?.role !== "admin"
    && (currentUser.value?.available === false || featureKeys.value.length === 0)
  ) {
    morePage.value = "access"
  }
}

async function refreshCurrentUser(options = {}) {
  const generation = getSessionGeneration()
  const refreshOwner = Symbol("permission-refresh")
  permissionRefreshOwner = refreshOwner
  permissionRefreshing.value = true
  authLoadError.value = ""
  try {
    const response = await getCurrentUser()
    if (!isCurrentSession(generation)) return false
    currentUser.value = response.data?.user || null
    if (!currentUser.value) throw new Error("未返回账号信息")
    authenticated.value = true
    ensureAccessibleRoute()
    return true
  } catch (error) {
    if (isCanceledRequest(error) || !isCurrentSession(generation)) return false
    const message = getErrorMessage(error, "账号权限读取失败，请检查网络后重试")
    if (error?.response?.status === 401) {
      clearAuthorizedData()
      setToken("")
      currentUser.value = null
      authenticated.value = false
      permissionRefreshOwner = null
      permissionRefreshing.value = false
      authReady.value = true
    } else {
      authenticated.value = Boolean(getToken())
      authLoadError.value = message
    }
    if (!options.silent) ElMessage.error(message)
    return false
  } finally {
    if (permissionRefreshOwner === refreshOwner && isCurrentSession(generation)) {
      permissionRefreshOwner = null
      permissionRefreshing.value = false
      authReady.value = true
    }
  }
}

async function retryAuthBootstrap() {
  const ready = await refreshCurrentUser()
  if (ready) await loadInitial()
}

async function logoutCurrentUser() {
  const generation = getSessionGeneration()
  try {
    if (getToken()) await logoutUser()
  } catch (error) {
    if (isCanceledRequest(error) || !isCurrentSession(generation)) return
    // 本地退出不应被网络错误阻塞。
  }
  if (!isCurrentSession(generation)) return
  if (selectedChannelId.value) clearChannelSelection()
  clearAuthorizedData()
  setToken("")
  currentUser.value = null
  authenticated.value = false
  authLoadError.value = ""
  activeTab.value = "more"
  morePage.value = "access"
  ElMessage.success("已退出登录")
}

async function refreshAccessAndData() {
  const ready = await refreshCurrentUser()
  if (!ready) return
  await loadInitial()
  ElMessage.success("授权状态已刷新")
}

async function selectMorePage(page) {
  if (!canOpenMorePage(page)) {
    ElMessage.warning("当前账号尚未开通该功能")
    morePage.value = "access"
    return
  }
  morePage.value = page
  await loadActive()
}

async function loadInitial() {
  const generation = getSessionGeneration()
  const loaders = new Map()
  const addLoader = (key, loader) => loaders.set(key, loader)
  const silent = { silent: true }

  if (hasFeature(currentUser.value, "dashboard")) addLoader("home", () => loadHome(silent))
  if (hasFeature(currentUser.value, "listener_tasks")) addLoader("listeners", () => loadListeners(silent))
  if (hasFeature(currentUser.value, "clone_tasks")) addLoader("clones", () => loadClones(silent))
  if (hasFeature(currentUser.value, "channels")) addLoader("channels", () => loadChannels(silent))
  if (hasFeature(currentUser.value, "support")) addLoader("support", () => loadSupportBots(silent))
  if (hasFeature(currentUser.value, "system_settings")) addLoader("send-settings", () => loadSendSettings(silent))

  if (hasAnyFeature(currentUser.value, ["bots", "listener_tasks", "clone_tasks", "channels", "support"])) {
    addLoader("bots", () => loadBots(silent))
  }
  if (hasAnyFeature(currentUser.value, ["accounts", "listener_tasks", "clone_tasks", "channels"])) {
    addLoader("accounts", () => loadAccounts(silent))
  }
  const contentProcessingEnabled = currentUser.value?.role === "admin" || currentUser.value?.plan_tier === "paid"
  if (contentProcessingEnabled && hasAnyFeature(currentUser.value, ["system_settings", "listener_tasks", "clone_tasks"])) {
    addLoader("templates", () => loadTemplates(silent))
  }
  if (contentProcessingEnabled && hasAnyFeature(currentUser.value, ["ai_settings", "listener_tasks", "clone_tasks"])) {
    addLoader("ai-settings", () => loadAiSettings(silent))
  }

  const results = await Promise.allSettled(Array.from(loaders.values(), (loader) => loader()))
  if (!isCurrentSession(generation)) return
  const failedCount = results.filter((item) => item.status === "fulfilled" && item.value === false).length
  if (failedCount) {
    ElMessage.warning(`部分数据加载失败（${failedCount} 项），请稍后刷新重试。`)
  }
  if (selectedChannelId.value && hasFeature(currentUser.value, "channels")) await loadChannelOverview()
}

async function openTaskFromAlert({ alert, taskType }) {
  const taskId = Number(alert?.task_id)
  if (!taskId || !["listener", "clone"].includes(taskType)) {
    ElMessage.warning("该告警没有可打开的任务")
    return
  }

  const isListener = taskType === "listener"
  const requiredFeature = isListener ? "listener_tasks" : "clone_tasks"
  if (!hasFeature(currentUser.value, requiredFeature)) {
    ElMessage.warning("当前账号没有查看该任务的权限")
    return
  }
  activeTab.value = isListener ? "listeners" : "clones"
  window.localStorage.setItem("mobile_active_tab", activeTab.value)
  if (isListener) listenerView.value = "tasks"
  else cloneView.value = "tasks"

  const loaded = isListener ? await loadListeners() : await loadClones()
  if (!loaded) return
  const tasks = isListener ? listeners.value : clones.value
  const task = tasks.find((item) => Number(item.id) === taskId)
  if (!task) {
    ElMessage.warning(`${isListener ? "监听" : "克隆"}任务 #${taskId} 已不存在或无权查看`)
    return
  }
  openEdit(taskType, task)
}

async function loadActive() {
  ensureAccessibleRoute()
  if (activeTab.value === "home" && hasFeature(currentUser.value, "dashboard")) return loadHome()
  if (activeTab.value === "listeners" && hasFeature(currentUser.value, "listener_tasks")) return loadListeners()
  if (activeTab.value === "clones" && hasFeature(currentUser.value, "clone_tasks")) return loadClones()
  if (activeTab.value === "channels" && hasFeature(currentUser.value, "channels")) return refreshChannelData()
  if (activeTab.value !== "more") return
  if (morePage.value === "access") return refreshAccessAndData()
  if (morePage.value === "bots" && hasFeature(currentUser.value, "bots")) return loadBots()
  if (morePage.value === "support" && hasFeature(currentUser.value, "support")) return loadSupportBots()
  if (morePage.value === "settings") {
    const jobs = []
    if (hasFeature(currentUser.value, "system_settings")) jobs.push(loadSendSettings(), loadTemplates())
    if (hasFeature(currentUser.value, "ai_settings")) jobs.push(loadAiSettings())
    return Promise.allSettled(jobs)
  }
  if (morePage.value === "accounts" && hasFeature(currentUser.value, "accounts")) return loadAccounts()
}

async function withLoading(key, fn, options = {}) {
  const generation = getSessionGeneration()
  const owner = Symbol(`loading-${key}`)
  const isActive = () => isCurrentSession(generation)
  loadingOwners.set(key, owner)
  loading[key] = true
  try {
    await fn(isActive)
    if (!isActive()) return false
    return true
  } catch (error) {
    if (isCanceledRequest(error) || !isCurrentSession(generation)) return false
    if (!options.silent) {
      ElMessage.error(getErrorMessage(error))
    }
    return false
  } finally {
    if (loadingOwners.get(key) === owner && isCurrentSession(generation)) {
      loadingOwners.delete(key)
      loading[key] = false
    }
  }
}

function loadHome(options) {
  return withLoading("home", async (isActive) => {
    const [statusRes, dashboardRes] = await Promise.all([getStatus(), getRuntimeDashboard()])
    if (!isActive()) return
    status.value = statusRes.data || {}
    dashboard.value = dashboardRes.data || {}
  }, options)
}

function loadListeners(options) {
  return withLoading("listeners", async (isActive) => {
    const response = await getListenerTasks()
    if (isActive()) listeners.value = pickList(response.data)
  }, options)
}

function loadClones(options) {
  return withLoading("clones", async (isActive) => {
    const response = await getCloneTasks()
    if (isActive()) clones.value = pickList(response.data)
  }, options)
}

function loadChannels(options) {
  return withLoading("channels", async (isActive) => {
    const response = await getMyChannels()
    if (isActive()) channels.value = pickList(response.data)
  }, options)
}

function loadBots(options) {
  return withLoading("bots", async (isActive) => {
    const request = hasFeature(currentUser.value, "bots") ? getBots() : getBotOptions()
    const response = await request
    if (isActive()) bots.value = pickList(response.data)
  }, options)
}

function loadSupportBots(options) {
  return withLoading("support", async (isActive) => {
    const response = await getSupportBots()
    if (isActive()) supportBots.value = pickList(response.data)
  }, options)
}

function loadTemplates(options) {
  return withLoading("templates", async (isActive) => {
    const response = await getContentTemplates()
    if (isActive()) templates.value = pickList(response.data)
  }, options)
}

function loadSendSettings(options) {
  return withLoading("settings", async (isActive) => {
    const response = await getSendSettings()
    if (isActive()) sendSettings.value = response.data || sendSettings.value
  }, options)
}

function loadAiSettings(options) {
  return withLoading("settings", async (isActive) => {
    const response = await getAiSettings()
    if (isActive()) aiSettings.value = response.data || aiSettings.value
  }, options)
}

function loadAccounts(options) {
  return withLoading("accounts", async (isActive) => {
    const request = hasFeature(currentUser.value, "accounts") ? getAccounts() : getAccountOptions()
    const response = await request
    if (isActive()) accounts.value = pickList(response.data)
  }, options)
}

function openEdit(type, row) {
  editType.value = type
  Object.keys(editForm).forEach((key) => delete editForm[key])
  Object.assign(editForm, JSON.parse(JSON.stringify(row || {})))
  if (type === "bot") {
    editForm.token = ""
  }
  if (type === "support") {
    editForm.bot_token = ""
  }
  if (type === "account") {
    editForm.session_path = ""
    editForm.proxy = ""
    editForm.clear_proxy = false
  }
  if (type === "channel" && !editForm.username && editForm.chat_id) {
    editForm.username = String(editForm.chat_id)
  }
  if (type === "channel") editForm.enabled = editForm.status !== "disabled"
  if (type === "template") {
    editForm.contents = (row.items || [])
      .map((item) => item.content || "")
      .filter(Boolean)
      .join("\n")
    if (row.type === "link") {
      Object.assign(editForm, parseLinkConfig((row.items || [])[0]?.content || row.content || ""))
    }
    if (row.type === "contact") {
      Object.assign(editForm, parseContactConfig((row.items || [])[0]?.content || row.content || ""))
    }
  }
  editVisible.value = true
}

async function openCreate(type, templateType = "") {
  if (["listener", "clone"].includes(type)) {
    const hasAccount = accounts.value.some((account) => account.enabled !== false)
    const hasBot = bots.value.some((bot) => bot.enabled !== false)
    if (!hasAccount || !hasBot) {
      const taskName = type === "listener" ? "监听" : "克隆"
      const missing = [!hasAccount ? "可用 Telegram 账号" : "", !hasBot ? "已启用 Bot" : ""].filter(Boolean)
      ElMessage.warning(`新增${taskName}任务前，请先配置：${missing.join("、")}`)
      return
    }
    const canConfigureContent = currentUser.value?.role === "admin" || currentUser.value?.plan_tier === "paid"
    if (canConfigureContent && !templates.value.some((template) => template.type === "filter" && template.enabled)) {
      try {
        await loadTemplates()
      } catch {
        // Request feedback is handled by the shared API layer; the form can still open.
      }
    }
  }
  editType.value = type
  Object.keys(editForm).forEach((key) => delete editForm[key])
  Object.assign(editForm, defaultForm(type))
  if (type === "template" && templateType) editForm.type = templateType
  editVisible.value = true
}

function openBotProfile(row) {
  botProfileTarget.value = row ? { ...row } : null
  botProfileVisible.value = Boolean(row?.id)
}

function defaultForm(type) {
  const firstAccount = accounts.value[0] || {}
  const firstBot = bots.value[0] || {}
  const map = {
    listener: {
      name: "",
      source_channel: "",
      target_channels: "[]",
      account_id: firstAccount.id || 1,
      bot_id: firstBot.id || null,
      enabled: true,
      status: "running",
      blocked_keywords: "[]",
      listen_required_keywords: "[]",
      replace_words: "{}",
      remove_contact_lines: true,
      selected_contact_template_group_id: null,
      selected_filter_template_group_id: defaultFilterTemplateGroupId(),
      filter_qr_code: true,
      album_wait_seconds: 3,
      ai_rewrite_enabled: false,
      ai_rewrite_provider: "grok",
      ai_rewrite_model: "",
      ai_rewrite_prompt: "",
      ai_rewrite_max_chars: 800,
      ai_rewrite_failure_mode: "fallback",
    },
    clone: {
      name: "",
      source_channel: "",
      start_message_url: "",
      end_message_url: "",
      target_channels: "[]",
      account_id: null,
      bot_id: firstBot.id || null,
      single_delay: 3,
      target_delay: 2,
      clone_limit: 100,
      album_delay: 8,
      enabled: true,
      enable_listener: false,
      blocked_keywords: "[]",
      replace_words: "{}",
      remove_contact_lines: true,
      selected_contact_template_group_id: null,
      selected_filter_template_group_id: defaultFilterTemplateGroupId(),
      filter_qr_code: true,
      status: "idle",
      ai_rewrite_enabled: false,
      ai_rewrite_provider: "grok",
      ai_rewrite_model: "",
      ai_rewrite_prompt: "",
      ai_rewrite_max_chars: 800,
      ai_rewrite_failure_mode: "fallback",
    },
    channel: {
      title: "",
      username: "",
      chat_id: "",
      channel_type: "channel",
      group_name: "",
      bot_id: firstBot.id || null,
      delivery_status: "",
      collection_status: "",
      remark: "",
      enabled: true,
      greeting_enabled: false,
      greeting_message: "",
      away_enabled: false,
      away_message: "",
      business_start_time: "09:00",
      business_end_time: "18:00",
      away_repeat_hours: 12,
      status: "enabled",
    },
    bot: {
      name: "",
      username: "",
      token: "",
      remark: "",
      enabled: true,
    },
    support: {
      name: "",
      bot_id: firstBot.id || null,
      bot_token: "",
      price: "",
      support_group_chat_id: "",
      polling_enabled: true,
      backend_base_url: "",
      welcome_message: "您好，欢迎咨询，请直接发送您的问题，客服会尽快回复您。",
      welcome_text_type: "plain",
      welcome_media_type: "text",
      welcome_media_file_id: "",
      off_hours_message: "",
      business_hours_enabled: false,
      business_start_hour: 9,
      business_end_hour: 22,
      status: "enabled",
    },
    template: {
      name: "",
      type: "footer",
      enabled: true,
      content: "",
      contents: "[]",
      remark: "",
      ...defaultLinkConfig(),
    },
    account: {
      name: "",
      username: "",
      phone: "",
      session_path: "data/sessions/collector_new",
      proxy: "",
      remark: "",
      enabled: true,
    },
  }
  return map[type] || {}
}

function channelLocation(id) {
  const url = new URL(window.location.href)
  if (id) url.searchParams.set("channel", String(id))
  else url.searchParams.delete("channel")
  return `${url.pathname}${url.search}${url.hash}`
}

function clearChannelSelection() {
  channelOverviewRequest += 1
  selectedChannelId.value = null
  channelOverview.value = null
  channelOverviewLoading.value = false
  channelOverviewError.value = ""
  channelOpenedInApp = false
  window.history.replaceState({}, "", channelLocation(null))
}

function openChannel(id) {
  const channelId = Number(id)
  if (!channelId || !hasFeature(currentUser.value, "channels")) return
  channelListScrollY = window.scrollY
  selectedChannelId.value = channelId
  channelOverview.value = null
  channelOverviewError.value = ""
  activeTab.value = "channels"
  channelView.value = "channels"
  window.history.pushState({ channelId }, "", channelLocation(channelId))
  channelOpenedInApp = true
  window.scrollTo(0, 0)
  return loadChannelOverview()
}

function closeChannel() {
  if (channelOpenedInApp) {
    channelOpenedInApp = false
    window.history.back()
    return
  }
  clearChannelSelection()
  nextTick(() => window.scrollTo(0, channelListScrollY))
}

function handleChannelPopState() {
  const id = Number(new URL(window.location.href).searchParams.get("channel")) || null
  channelOverviewRequest += 1
  selectedChannelId.value = id && hasFeature(currentUser.value, "channels") ? id : null
  channelOverview.value = null
  channelOverviewError.value = ""
  channelOverviewLoading.value = false
  channelOpenedInApp = false
  if (selectedChannelId.value) {
    activeTab.value = "channels"
    channelView.value = "channels"
    window.scrollTo(0, 0)
    loadChannelOverview()
  } else {
    nextTick(() => window.scrollTo(0, channelListScrollY))
  }
}

async function loadChannelOverview() {
  const id = selectedChannelId.value
  if (!id || !hasFeature(currentUser.value, "channels")) return false
  const requestId = ++channelOverviewRequest
  const generation = getSessionGeneration()
  channelOverviewLoading.value = true
  channelOverviewError.value = ""
  try {
    const response = await getMyChannelOverview(id)
    if (requestId !== channelOverviewRequest || !isCurrentSession(generation) || selectedChannelId.value !== id) return false
    channelOverview.value = response.data || null
    return true
  } catch (error) {
    if (requestId !== channelOverviewRequest || isCanceledRequest(error) || !isCurrentSession(generation)) return false
    channelOverviewError.value = getErrorMessage(error, "频道详情加载失败，请重试")
    return false
  } finally {
    if (requestId === channelOverviewRequest && isCurrentSession(generation)) channelOverviewLoading.value = false
  }
}

async function refreshChannelData() {
  await loadChannels()
  if (selectedChannelId.value) await loadChannelOverview()
}

async function openChannelTask(task) {
  const type = task?.type
  const required = type === "listener" ? "listener_tasks" : "clone_tasks"
  if (!["listener", "clone"].includes(type) || !hasFeature(currentUser.value, required)) {
    ElMessage.warning("当前账号无权查看该任务")
    return
  }
  clearChannelSelection()
  activeTab.value = type === "listener" ? "listeners" : "clones"
  window.localStorage.setItem("mobile_active_tab", activeTab.value)
  if (type === "listener") listenerView.value = "tasks"
  else cloneView.value = "tasks"
  const loaded = type === "listener" ? await loadListeners() : await loadClones()
  if (!loaded) return
  const item = (type === "listener" ? listeners.value : clones.value).find(row => Number(row.id) === Number(task.id))
  if (item) openEdit(type, item)
  else ElMessage.warning("该任务已不存在或无权查看")
}

function defaultFilterTemplateGroupId() {
  const candidates = templates.value.filter(
    (template) => template.type === "filter" && template.enabled && !template.parent_id,
  )
  const preferred = candidates.find((template) =>
    String(template.name || "").includes("通用过滤"),
  )
  return preferred?.id || candidates[0]?.id || null
}

function payloadFor(type) {
  const data = { ...editForm }
  if (type === "channel") {
    data.status = data.enabled ? "enabled" : "disabled"
    delete data.enabled
    const identifier = String(data.username || data.chat_id || "").trim()
    if (/^-100\d+$/.test(identifier)) {
      data.username = ""
      data.chat_id = identifier
      editForm.username = identifier
    } else {
      data.username = normalizeTelegramUsername(identifier)
      editForm.username = data.username
    }
  }
  if (["listener", "clone"].includes(type)) {
    data.target_channels = normalizeJsonList(data.target_channels)
    data.blocked_keywords = normalizeJsonList(data.blocked_keywords)
    data.replace_words = normalizeJsonObject(data.replace_words)
    if (currentUser.value?.role !== "admin" && currentUser.value?.plan_tier !== "paid") {
      Object.assign(data, {
        blocked_keywords: "[]",
        replace_words: "{}",
        footer: "",
        remove_contact_lines: false,
        filter_qr_code: false,
        ai_rewrite_enabled: false,
        ai_rewrite_model: "",
        ai_rewrite_prompt: "",
        ai_prompt_template_id: null,
        ai_rewrite_ratio: 0,
        use_random_head: false,
        use_random_body: false,
        use_random_footer: false,
        footer_leading_blank_line: false,
        selected_head_template_group_id: null,
        selected_body_template_group_id: null,
        selected_footer_template_group_id: null,
        selected_filter_template_group_id: null,
        selected_link_template_group_id: null,
        selected_contact_template_group_id: null,
        selected_head_template_id: null,
        selected_body_template_id: null,
        selected_footer_template_id: null,
      })
    }
  }
  if (type === "listener") {
    data.listen_required_keywords = normalizeJsonList(data.listen_required_keywords)
    if (currentUser.value?.role !== "admin" && currentUser.value?.plan_tier !== "paid") {
      data.listen_required_keywords = "[]"
    }
  }
  if (type === "template") {
    if (data.type === "link") {
      data.items = [{
        id: Array.isArray(data.items) && data.items[0]?.id ? data.items[0].id : null,
        name: data.name || "链接配置",
        content: JSON.stringify(buildLinkConfig(data)),
        enabled: data.enabled ?? true,
        weight: 1,
      }]
      cleanupLinkFields(data)
      delete data.content
      delete data.contents
      delete data.remark
      return data
    }
    if (data.type === "contact") {
      data.items = [{
        id: Array.isArray(data.items) && data.items[0]?.id ? data.items[0].id : null,
        name: data.name || "联系方式删除配置",
        content: JSON.stringify(buildContactConfig(data)),
        enabled: data.enabled ?? true,
        weight: 1,
      }]
      cleanupContactFields(data)
      delete data.content
      delete data.contents
      delete data.remark
      return data
    }
    const rawItems = Array.isArray(data.items) && data.items.length
      ? data.items
      : String(data.contents || data.content || "")
        .split(/\n+/)
        .map((content, index) => ({
          id: null,
          name: `内容 ${index + 1}`,
          content: content.trim(),
          enabled: true,
          weight: index + 1,
        }))
    data.items = rawItems
      .map((item, index) => ({
        id: item.id || null,
        name: item.name || `内容 ${index + 1}`,
        content: item.content || String(item || ""),
        enabled: item.enabled ?? true,
        weight: Number(item.weight || index + 1),
      }))
      .filter((item) => item.content.trim())
    delete data.content
    delete data.contents
    delete data.remark
  }
  if (type === "bot" && !String(data.token || "").trim()) {
    delete data.token
  }
  if (type === "support" && !String(data.bot_token || "").trim()) {
    delete data.bot_token
  }
  if (type === "account") {
    for (const key of ["phone", "phone_masked", "has_phone", "has_session_path", "has_proxy"]) {
      delete data[key]
    }
    if (data.id) {
      if (!String(data.session_path || "").trim()) delete data.session_path
      if (!String(data.proxy || "").trim()) delete data.proxy
    }
  }
  return data
}

function normalizeTelegramUsername(value) {
  const text = String(value || "").trim()
  if (!text) return ""

  const linkMatch = text.match(/^(?:https?:\/\/)?t\.me\/([^/?#]+)/i)
  const username = linkMatch?.[1] || text.replace(/^@/, "")
  if (!username || username.startsWith("+") || ["c", "joinchat"].includes(username.toLowerCase())) return text

  return `@${username.toLowerCase()}`
}

function normalizeTaskChannelKey(value) {
  let text = String(value || "").trim()
  if (!text) return ""
  if (/^-?\d+$/.test(text)) return text

  text = text.replace(/^https?:\/\//i, "").replace(/^telegram\.me\//i, "t.me/")
  if (/^t\.me\//i.test(text)) {
    const parts = text.replace(/^t\.me\//i, "").split(/[/?#]/).filter(Boolean)
    if (parts[0]?.toLowerCase() === "c" && /^\d+$/.test(parts[1] || "")) {
      return `-100${parts[1]}`
    }
    text = parts[0] || ""
  }

  return text.replace(/^@/, "").split("/", 1)[0].trim().toLowerCase()
}

function parseTaskChannels(value) {
  if (Array.isArray(value)) return value
  const text = String(value || "").trim()
  if (!text) return []
  try {
    const parsed = JSON.parse(text)
    return Array.isArray(parsed) ? parsed : [parsed]
  } catch {
    return text.split(/[\n,，]/).map((item) => item.trim()).filter(Boolean)
  }
}

function findListenerChannelConflict(sourceChannel, targetChannels) {
  const sourceKey = normalizeTaskChannelKey(sourceChannel)
  if (!sourceKey) return ""
  return parseTaskChannels(targetChannels).find(
    (target) => normalizeTaskChannelKey(target) === sourceKey,
  ) || ""
}

function buildMobileSubscriptionWarning(results) {
  return [
    "检测到源频道订阅风险：",
    "",
    ...results.map((item) => `${item.normalized_source || item.source_channel || "-"}：${item.message || "监听账号未订阅源频道，实时监听可能不稳定。"}`),
    "",
    "公开频道可能能读取历史，但不一定能稳定收到实时更新。是否继续保存？",
  ].join("\n")
}

async function confirmMobileListenerSourceSubscription(payload) {
  try {
    const res = await checkListenerSourceSubscription({
      account_id: Number(payload.account_id || 1),
      source_channels: [payload.source_channel],
    })
    const warnings = (res.data?.results || []).filter((item) => item.warning)

    if (!warnings.length) {
      return true
    }

    await ElMessageBox.confirm(
      buildMobileSubscriptionWarning(warnings),
      "源频道订阅提醒",
      {
        confirmButtonText: "继续保存",
        cancelButtonText: "返回修改",
        type: "warning",
      },
    )
    return true
  } catch (error) {
    if (error === "cancel" || error === "close") {
      return false
    }

    try {
      await ElMessageBox.confirm(
        `源频道订阅状态检测失败：${getErrorMessage(error, "检测失败")}\n\n继续保存后，若监听账号未订阅源频道，实时监听可能不稳定。是否继续保存？`,
        "源频道订阅检测失败",
        {
          confirmButtonText: "继续保存",
          cancelButtonText: "返回修改",
          type: "warning",
        },
      )
      return true
    } catch {
      return false
    }
  }
}

async function saveEdit() {
  saving.value = true
  try {
    const payload = payloadFor(editType.value)
    if (editType.value === "listener") {
      const conflict = findListenerChannelConflict(payload.source_channel, payload.target_channels)
      if (conflict) {
        throw new Error(`监听任务的源频道不能同时作为目标频道：${conflict}`)
      }
    }
    if (editType.value === "account") {
      if (!String(payload.name || "").trim() || (!editForm.id && !String(payload.session_path || "").trim())) {
        throw new Error(editForm.id ? "账号名称不能为空" : "账号名称和 Session 路径不能为空")
      }
      if (payload.greeting_enabled && !String(payload.greeting_message || "").trim()) {
        throw new Error("启用问候消息后必须填写问候内容")
      }
      if (payload.away_enabled && !String(payload.away_message || "").trim()) {
        throw new Error("启用离线消息后必须填写离线内容")
      }
      if (![payload.business_start_time, payload.business_end_time].every((value) => /^([01]\d|2[0-3]):[0-5]\d$/.test(String(value || "")))) {
        throw new Error("营业时间请使用 HH:mm 格式，例如 09:00")
      }
    }
    const isEdit = Boolean(editForm.id)
    let result = null
    if (editType.value === "listener") {
      const subscriptionConfirmed = await confirmMobileListenerSourceSubscription(payload)
      if (!subscriptionConfirmed) {
        return
      }
      result = isEdit ? await updateListenerTask(editForm.id, payload) : await createListenerTask(payload)
    }
    if (editType.value === "clone") {
      result = isEdit ? await updateCloneTask(editForm.id, payload) : await createCloneTask(payload)
    }
    if (editType.value === "channel") {
      result = isEdit ? await updateMyChannel(editForm.id, payload) : await createMyChannel(payload)
    }
    if (editType.value === "bot") {
      result = isEdit ? await updateBot(editForm.id, payload) : await createBot(payload)
    }
    if (editType.value === "support") {
      result = isEdit ? await updateSupportBot(editForm.id, payload) : await createSupportBot(payload)
    }
    if (editType.value === "template") {
      result = isEdit ? await updateContentTemplateRule(editForm.id, payload) : await createContentTemplateRule(payload)
    }
    if (editType.value === "account") {
      result = isEdit ? await updateAccount(editForm.id, payload) : await createAccount(payload)
    }
    if (editType.value === "channel") {
      const checked = result?.data || {}
      if (checked.auto_check_ok) {
        ElMessage.success("频道已保存并完成检测，空白信息已自动补全")
      } else {
        ElMessage.warning(`频道已保存，但自动检测失败：${checked.auto_check_message || "请检查 Bot 和频道权限"}`)
      }
    } else {
      ElMessage.success("保存成功")
    }
    editVisible.value = false
    await reloadType(editType.value)
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "保存失败"))
  } finally {
    saving.value = false
  }
}

async function reloadType(type) {
  if (type === "listener") return loadListeners()
  if (type === "clone") return loadClones()
  if (type === "channel") return refreshChannelData()
  if (type === "bot") return loadBots()
  if (type === "support") return loadSupportBots()
  if (type === "template") return loadTemplates()
  if (type === "account") return loadAccounts()
}

async function runAction(fn, successText, refreshFn) {
  const generation = getSessionGeneration()
  try {
    await fn()
    if (!isCurrentSession(generation)) return false
    ElMessage.success(successText)
    if (refreshFn) await refreshFn()
    return isCurrentSession(generation)
  } catch (error) {
    if (isCanceledRequest(error) || !isCurrentSession(generation)) return false
    ElMessage.error(getErrorMessage(error))
    return false
  }
}

async function toggleListener(item) {
  const fn = item.enabled ? stopListenerTask : startListenerTask
  await runAction(() => fn(item.id), item.enabled ? "已停止监听任务" : "已启动监听任务", loadListeners)
}

const catchupVisible = ref(false)
const catchupCheckingId = ref(null)
const catchupSubmitting = ref(false)
const catchupTaskId = ref(null)
const catchupPlan = ref({ catchup_count: 1 })
const catchupFormRef = ref(null)
const catchupForm = reactive({ limit: 1, interval_seconds: 60 })
const catchupError = ref("")

async function catchupListener(item) {
  const id = item.id
  if (catchupCheckingId.value !== null || catchupVisible.value) return
  catchupCheckingId.value = id
  try {
    const res = await checkListenerCatchup(id)
    const plan = res.data || {}
    if (!plan.ok) throw new Error(plan.message || "补齐检测失败")
    if (!plan.catchup_count) {
      ElMessage.success(plan.message || "未检测到需要补齐的内容")
      return
    }
    catchupTaskId.value = id
    catchupPlan.value = plan
    catchupForm.limit = plan.catchup_count
    catchupForm.interval_seconds = 60
    catchupError.value = ""
    catchupVisible.value = true
  } catch (error) {
    ElMessage.error(error?.response?.data?.message || error?.message || "补齐检测失败，请重试")
  } finally {
    catchupCheckingId.value = null
  }
}

async function submitListenerCatchup() {
  if (catchupSubmitting.value) return
  if (!await catchupFormRef.value?.validate().catch(() => false)) return
  catchupSubmitting.value = true
  catchupError.value = ""
  try {
    const res = await catchupListenerTask(catchupTaskId.value, {
      background: true,
      limit: catchupForm.limit,
      interval_seconds: catchupForm.interval_seconds,
    })
    if (!res.data?.ok) throw new Error(res.data?.message || "补齐任务提交失败")
    catchupVisible.value = false
    ElMessage.success(`补齐任务已加入队列，内容间隔 ${catchupForm.interval_seconds} 秒`)
  } catch (error) {
    catchupError.value = error?.response?.data?.message || error?.message || "补齐任务提交失败，请重试"
    return
  } finally {
    catchupSubmitting.value = false
  }
  if (hasFeature(currentUser.value, "dashboard")) await loadHome()
}

async function checkChannel(item) {
  try {
    const res = await checkMyChannel(item.id)
    detailText.value = JSON.stringify(res.data || {}, null, 2)
    detailVisible.value = true
    await refreshChannelData()
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "检测失败"))
  }
}

function openChannelSubmit(item) {
  if (!item.group_name) {
    ElMessage.warning("请先编辑频道并设置分组，再提交到搜索机器人")
    return
  }
  if (!searchBotPanelRef.value) {
    ElMessage.error("提交功能尚未加载，请刷新页面后重试")
    return
  }
  return searchBotPanelRef.value.openSubmitForChannel(item)
}

function openChannelSubmissionStatus(item) {
  if (!searchBotPanelRef.value) {
    ElMessage.error("频道提交状态尚未加载，请刷新页面后重试")
    return
  }
  return searchBotPanelRef.value.openChannelStatus(item)
}

async function batchCheckChannels() {
  await runAction(async () => {
    const res = await batchCheckMyChannels()
    detailText.value = JSON.stringify(res.data || {}, null, 2)
    detailVisible.value = true
  }, "批量检测已完成", loadChannels)
}

async function showLogs(type) {
  logType.value = type === "clone" ? "clone" : "listener"
  logLoading.value = true
  try {
    const res = logType.value === "listener"
      ? await getListenerSendEvents(200)
      : await getCloneSendEvents(200)
    logItems.value = pickList(res.data)
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "加载日志失败"))
  } finally {
    logLoading.value = false
  }
}

function changeTaskView(type, name) {
  if (name !== "logs") return
  logKeyword.value = ""
  return showLogs(type)
}

async function uploadWelcomeMedia(file) {
  uploadingMedia.value = true
  try {
    const raw = file?.file || file
    const res = await uploadSupportMedia(raw)
    editForm.welcome_media_file_id = res.data?.media_ref || res.data?.file_id || ""
    if (res.data?.media_type) {
      editForm.welcome_media_type = res.data.media_type
    }
    ElMessage.success("媒体上传成功")
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "媒体上传失败"))
  } finally {
    uploadingMedia.value = false
  }
}

function clearWelcomeMedia() {
  editForm.welcome_media_file_id = ""
  editForm.welcome_media_type = "text"
}

function openAccountLogin(account = null) {
  accountLoginTarget.value = account || null
  accountLoginVisible.value = true
}

async function startAccountLoginFlow(payload, done) {
  accountLoginLoading.value = true
  try {
    const res = await startAccountLogin(payload)
    const data = res.data || {}
    if (typeof done === "function") done(data)
    return data
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "发送验证码失败"))
    if (typeof done === "function") done({ ok: false })
    return { ok: false }
  } finally {
    accountLoginLoading.value = false
  }
}

async function verifyAccountLoginFlow(payload, done) {
  accountLoginLoading.value = true
  try {
    const res = await verifyAccountLogin(payload)
    const data = res.data || {}
    if (data.ok) {
      ElMessage.success("账号登录成功")
      accountLoginVisible.value = false
      await loadAccounts()
    }
    if (typeof done === "function") done(data)
    return data
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "登录验证失败"))
    if (typeof done === "function") done({ ok: false })
    return { ok: false }
  } finally {
    accountLoginLoading.value = false
  }
}

async function removeItem(type, item) {
  try {
    await ElMessageBox.confirm(`确认删除“${item.name || item.title || item.username || item.id}”？`, "删除确认", {
      confirmButtonText: "删除",
      cancelButtonText: "取消",
      type: "warning",
    })
    if (type === "listener") await deleteListenerTask(item.id)
    if (type === "clone") await deleteCloneTask(item.id)
    if (type === "channel") await deleteMyChannel(item.id)
    if (type === "bot") await deleteBot(item.id)
    if (type === "support") await deleteSupportBot(item.id)
    if (type === "template") await deleteContentTemplateRule(item.id)
    if (type === "account") await deleteAccount(item.id)
    ElMessage.success("删除成功")
    if (type === "channel" && selectedChannelId.value === Number(item.id)) clearChannelSelection()
    await reloadType(type)
  } catch (error) {
    if (error === "cancel") return
    ElMessage.error(getErrorMessage(error, "删除失败"))
  }
}

function testBotAction(item) {
  return runAction(() => testBot(item.id), "Bot 测试完成", loadBots)
}

function testSupportAction(item) {
  return runAction(() => testSupportBotItem(item.id), "客服机器人测试完成", loadSupportBots)
}

function toggleAccount(item) {
  return runAction(
    () => updateAccount(item.id, accountUpdatePayload(item, { enabled: !item.enabled })),
    item.enabled ? "已停用账号" : "已启用账号",
    loadAccounts,
  )
}

function accountUpdatePayload(item, overrides = {}) {
  return {
    name: item.name || "",
    username: item.username || "",
    enabled: item.enabled !== false,
    remark: item.remark || "",
    greeting_enabled: Boolean(item.greeting_enabled),
    greeting_message: item.greeting_message || "",
    away_enabled: Boolean(item.away_enabled),
    away_message: item.away_message || "",
    business_start_time: item.business_start_time || "09:00",
    business_end_time: item.business_end_time || "18:00",
    away_repeat_hours: Number(item.away_repeat_hours || 12),
    ...overrides,
  }
}

async function setDefaultAccount(item) {
  try {
    await ElMessageBox.confirm(
      `确定将“${item.name || `账号 #${item.id}`}”设为全局默认采集账号？`,
      "设置默认账号",
      {
        confirmButtonText: "设为默认",
        cancelButtonText: "取消",
        type: "info",
      },
    )
  } catch (error) {
    if (error === "cancel" || error === "close") return
    throw error
  }

  defaultAccountSettingId.value = item.id
  try {
    await updateAccount(item.id, {
      ...accountUpdatePayload(item, { enabled: true }),
      is_default: true,
    })
    ElMessage.success("全局默认账号已更新")
    await loadAccounts()
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "设置默认账号失败"))
  } finally {
    defaultAccountSettingId.value = null
  }
}

function toggleBot(item) {
  return runAction(() => updateBot(item.id, { enabled: !item.enabled }), item.enabled ? "已停用 Bot" : "已启用 Bot", loadBots)
}

function toggleSupportBot(item) {
  const next = !item.polling_enabled
  return runAction(() => updateSupportBot(item.id, { polling_enabled: next }), next ? "已启用客服机器人" : "已停用客服机器人", loadSupportBots)
}

function toggleTemplate(item) {
  return runAction(() => updateContentTemplateRule(item.id, { enabled: !item.enabled }), item.enabled ? "已停用模板" : "已启用模板", loadTemplates)
}

async function saveMobileSendSettings(payload) {
  const generation = getSessionGeneration()
  const owner = Symbol("loading-settings-save")
  loadingOwners.set("settings", owner)
  loading.settings = true
  try {
    await runAction(
      async () => {
        const res = await updateSendSettings({
          global_send_delay: Math.max(Number(payload.global_send_delay) || 0, 0),
          send_retry_count: Math.max(Number(payload.send_retry_count) || 0, 0),
          send_retry_delay: Math.max(Number(payload.send_retry_delay) || 0, 0),
        })
        sendSettings.value = res.data || sendSettings.value
      },
      "系统设置已保存",
      loadSendSettings,
    )
  } finally {
    if (loadingOwners.get("settings") === owner && isCurrentSession(generation)) {
      loadingOwners.delete("settings")
      loading.settings = false
    }
  }
}

async function saveMobileAiSettings(payload) {
  const generation = getSessionGeneration()
  const owner = Symbol("loading-settings-save")
  loadingOwners.set("settings", owner)
  loading.settings = true
  try {
    await runAction(async () => {
      aiSettings.value = (await updateAiSettings(payload)).data || aiSettings.value
    }, "AI 配置已保存", loadAiSettings)
  } finally {
    if (loadingOwners.get("settings") === owner && isCurrentSession(generation)) {
      loadingOwners.delete("settings")
      loading.settings = false
    }
  }
}

function normalizeJsonList(value) {
  if (Array.isArray(value)) return JSON.stringify(value)
  const text = String(value || "").trim()
  if (!text) return "[]"
  try {
    const parsed = JSON.parse(text)
    return JSON.stringify(Array.isArray(parsed) ? parsed : [parsed])
  } catch {
    return JSON.stringify(text.split(/[\n,，]/).map((item) => item.trim()).filter(Boolean))
  }
}

function normalizeJsonObject(value) {
  if (value && typeof value === "object" && !Array.isArray(value)) return JSON.stringify(value)
  const text = String(value || "").trim()
  if (!text) return "{}"
  try {
    return JSON.stringify(JSON.parse(text))
  } catch {
    return "{}"
  }
}

let handlingAccessRestriction = false

function closeRestrictedOverlays() {
  editVisible.value = false
  detailVisible.value = false
  accountLoginVisible.value = false
  botProfileVisible.value = false
  detailText.value = ""
  accountLoginTarget.value = null
  botProfileTarget.value = null
  editType.value = ""
  Object.keys(editForm).forEach((key) => delete editForm[key])
}

function clearAuthorizedData() {
  closeRestrictedOverlays()
  channelOverviewRequest += 1
  channelOverview.value = null
  channelOverviewLoading.value = false
  channelOverviewError.value = ""
  loadingOwners.clear()
  status.value = {}
  dashboard.value = {}
  listeners.value = []
  clones.value = []
  bots.value = []
  channels.value = []
  supportBots.value = []
  templates.value = []
  accounts.value = []
  logItems.value = []
  logKeyword.value = ""
  sendSettings.value = {
    global_send_delay: 3,
    send_retry_count: 2,
    send_retry_delay: 5,
  }
  aiSettings.value = { providers: {} }
  defaultAccountSettingId.value = null
  Object.keys(loading).forEach((key) => { loading[key] = false })
  Object.keys(keyword).forEach((key) => { keyword[key] = "" })
}

function handleSessionChanged(event) {
  clearAuthorizedData()
  ElMessage.closeAll()
  currentUser.value = null
  authLoadError.value = ""
  permissionRefreshOwner = null
  permissionRefreshing.value = false
  authenticated.value = Boolean(event?.detail?.authenticated)
  authReady.value = !authenticated.value
  handlingAccessRestriction = false
}

async function handleAccessRestricted(event) {
  if (!authenticated.value || handlingAccessRestriction) return
  const code = event?.detail?.code
  if (!["ACCESS_PENDING", "ACCESS_EXPIRED", "FEATURE_FORBIDDEN"].includes(code)) return
  clearAuthorizedData()

  if (["ACCESS_PENDING", "ACCESS_EXPIRED"].includes(code)) {
    handlingAccessRestriction = true
    try {
      const ready = await refreshCurrentUser({ silent: true })
      if (!ready && currentUser.value) {
        currentUser.value = {
          ...currentUser.value,
          access_state: code === "ACCESS_EXPIRED" ? "expired" : "pending",
          available: false,
        }
      }
      activeTab.value = "more"
      morePage.value = "access"
      window.localStorage.setItem("mobile_active_tab", "more")
    } finally {
      handlingAccessRestriction = false
    }
    return
  }
  handlingAccessRestriction = true
  try {
    const ready = await refreshCurrentUser({ silent: true })
    if (ready) {
      ensureAccessibleRoute()
      await loadInitial()
    }
  } finally {
    handlingAccessRestriction = false
  }
}

onMounted(async () => {
  window.addEventListener("popstate", handleChannelPopState)
  window.addEventListener("mobile-access-restricted", handleAccessRestricted)
  window.addEventListener(SESSION_STORAGE_CHANGED_EVENT, handleSessionChanged)
  window.addEventListener(SESSION_INVALIDATED_EVENT, handleSessionChanged)
  if (!getToken()) {
    authenticated.value = false
    authReady.value = true
    return
  }

  const ready = await refreshCurrentUser({ silent: true })
  if (ready) await loadInitial()
})

onUnmounted(() => {
  window.removeEventListener("popstate", handleChannelPopState)
  window.removeEventListener("mobile-access-restricted", handleAccessRestricted)
  window.removeEventListener(SESSION_STORAGE_CHANGED_EVENT, handleSessionChanged)
  window.removeEventListener(SESSION_INVALIDATED_EVENT, handleSessionChanged)
})

const HomePage = defineComponent({
  props: {
    status: Object,
    dashboard: Object,
    loading: Boolean,
  },
  setup(props) {
    const waitingKeyword = ref("")
    const recentKeyword = ref("")
    return () => {
      const stats = props.dashboard?.stats || {}
      const queue = props.dashboard?.queue || {}
      const waiting = searchRows(asArray(queue.waiting), waitingKeyword.value, "queue")
      const recent = searchRows(asArray(queue.recent), recentKeyword.value, "queue")
      return h("div", { class: "page" }, [
        h("section", { class: "section" }, [
          h("div", { class: "metric-grid" }, [
            metric("系统状态", props.status?.status || "unknown"),
            metric("排队任务", stats.waiting_count || 0),
            metric("克隆运行中", stats.clone_running_count || 0),
            metric("启用监听", stats.listener_enabled_count || 0),
          ]),
        ]),
        sectionList("排队任务", waiting, waitingKeyword.value.trim() ? "没有匹配的排队任务" : "暂无排队任务", (item) =>
          h(TaskCard, {
            title: item.task_name || `任务 #${item.task_id || "-"}`,
            subtitle: `${sourceTypeLabel(item.source_type)} / ${item.reason || "等待发送"}`,
            status: item.status,
            meta: [
              ["任务 ID", item.task_id || "-"],
              ["预计发送", item.estimated_send_at || "-"],
              ["排队时间", formatDate(item.queued_at)],
              ["等待原因", item.reason || "-"],
              ["目标频道", item.target_channel || "-"],
              ["源频道", item.source_channel || "-"],
              ["源消息", item.source_message_id || "-"],
              ["内容类型", item.message_type || "-"],
              ["相册 ID", item.grouped_id || "-"],
            ],
          }),
          h(resolve("TableSearch"), { modelValue: waitingKeyword.value, "onUpdate:modelValue": value => { waitingKeyword.value = value }, label: "搜索排队任务", placeholder: "搜索任务 / 频道 / 消息ID / 状态", count: waiting.length, total: asArray(queue.waiting).length }),
        ),
        sectionList("最近完成", recent, recentKeyword.value.trim() ? "没有匹配的完成记录" : "暂无最近完成记录", (item) =>
          h(TaskCard, {
            title: item.task_name || `任务 #${item.task_id || "-"}`,
            subtitle: item.error || item.target_channel || "-",
            status: item.status,
            meta: [
              ["任务 ID", item.task_id || "-"],
              ["完成时间", formatDate(item.finished_at)],
              ["来源", sourceTypeLabel(item.source_type)],
              ["状态", item.status || "-"],
              ["目标频道", item.target_channel || "-"],
              ["源消息", item.source_message_id || "-"],
              ["错误", item.error || "-"],
            ],
          }),
          h(resolve("TableSearch"), { modelValue: recentKeyword.value, "onUpdate:modelValue": value => { recentKeyword.value = value }, label: "搜索最近完成", placeholder: "搜索任务 / 频道 / 消息ID / 状态", count: recent.length, total: asArray(queue.recent).length }),
        ),
      ])
    }
  },
})

const ListPage = defineComponent({
  props: {
    requestActions: { type: Object, default: () => ({}) },
    title: String,
    placeholder: String,
    emptyTitle: String,
    keyword: String,
    items: Array,
    loading: Boolean,
  },
  emits: ["update:keyword"],
  setup(props, { emit: rawEmit, slots }) {
    const emit = useRequestEmit(rawEmit, props)
    return () => h("div", [
      h("div", { class: "search-bar" }, [
        h(resolve("el-input"), {
          modelValue: props.keyword,
          "onUpdate:modelValue": (value) => emit("update:keyword", value),
          placeholder: props.placeholder,
          "aria-label": `搜索${props.title}`,
          clearable: true,
        }),
      ]),
      h("div", { class: "page" }, [
        h("div", { class: "section-head" }, [
          h("div", [
            h("div", { class: "section-title" }, props.title),
            h("div", { class: "section-subtitle" }, `共 ${props.items?.length || 0} 条，列表按手机操作优化`),
          ]),
          slots.actions ? h("div", { class: "row-actions" }, slots.actions()) : null,
        ]),
        props.loading
          ? h(resolve("el-skeleton"), { rows: 6, animated: true })
          : props.items?.length
            ? h("div", { class: "card-list" }, props.items.flatMap((item) => slots.default({ item })))
            : h(EmptyState, { title: props.keyword?.trim() ? "没有匹配记录，请调整搜索内容" : props.emptyTitle }),
      ]),
    ])
  },
})

const TaskCard = defineComponent({
  props: {
    title: String,
    subtitle: String,
    status: [String, Boolean],
    enabled: Boolean,
    meta: Array,
  },
  setup(props, { slots }) {
    const expanded = ref(false)
    const visibleMeta = computed(() => expanded.value ? props.meta || [] : (props.meta || []).slice(0, 2))

    return () => h("article", {
      class: ["data-card", "expandable-card", { expanded: expanded.value }],
      onClick: () => { expanded.value = !expanded.value },
    }, [
      h("div", { class: "card-main" }, [
        h("div", { style: "min-width:0" }, [
          h("div", { class: "card-title" }, props.title || "-"),
          h("div", { class: "card-subtitle" }, props.subtitle || "-"),
        ]),
        h("div", { class: "card-side" }, [
          h(StatusPill, {
            status: props.status,
            label: typeof props.enabled === "boolean" ? enabledLabel(props.enabled) : "",
          }),
          h("span", {
            class: "card-toggle",
            "aria-label": expanded.value ? "收起" : "展开",
          }, [
            h(resolve("el-icon"), null, () => h(expanded.value ? ArrowUpBold : ArrowDownBold)),
          ]),
        ]),
      ]),
      h("div", { class: "card-meta" }, visibleMeta.value.map(([label, value]) =>
        h("div", { class: "meta-item", key: label }, [
          h("span", { class: "meta-label" }, label),
          h("span", { class: "meta-value" }, compactText(value)),
        ]),
      )),
      slots.default && expanded.value
        ? h("div", { class: "card-actions", onClick: (event) => event.stopPropagation() }, slots.default())
        : null,
    ])
  },
})

const LogDrawer = defineComponent({
  props: {
    requestActions: { type: Object, default: () => ({}) },
    type: String,
    items: Array,
    keyword: String,
    loading: Boolean,
  },
  emits: ["update:keyword", "refresh"],
  setup(props, { emit: rawEmit }) {
    const emit = useRequestEmit(rawEmit, props)
    return () => h("div", { class: "log-drawer" }, [
      h("div", { class: "search-bar" }, [
        h(resolve("el-input"), {
          modelValue: props.keyword,
          "onUpdate:modelValue": (value) => emit("update:keyword", value),
          placeholder: props.type === "clone" ? "搜索任务 / 目标 / 消息 / 错误" : "搜索任务 / 频道 / 消息 / 错误",
          "aria-label": props.type === "clone" ? "搜索克隆日志" : "搜索监听日志",
          clearable: true,
        }),
        h(resolve("request-button"), {
          plain: true,
          loading: props.loading,
          onClick: () => emit("refresh"),
        }, () => "刷新"),
      ]),
      h("div", { class: "section-head log-summary" }, [
        h("div", [
          h("div", { class: "section-title" }, props.type === "clone" ? "最近克隆发送结果" : "监听执行记录"),
          h("div", { class: "section-subtitle" }, `共 ${props.items?.length || 0} 条，按最新记录展示`),
        ]),
      ]),
      props.loading
        ? h(resolve("el-skeleton"), { rows: 8, animated: true })
        : props.items?.length
          ? h("div", { class: "card-list log-list" }, props.items.map((item, index) =>
            h(LogCard, { key: `${item.id || item.time || index}-${index}`, item, type: props.type }),
          ))
          : h(EmptyState, { title: props.keyword?.trim() ? "没有匹配日志，请调整搜索内容" : props.type === "clone" ? "暂无克隆日志" : "暂无监听日志" }),
    ])
  },
})

const LogCard = defineComponent({
  props: {
    item: Object,
    type: String,
  },
  setup(props) {
    const expanded = ref(false)
    const primaryStatus = computed(() => props.item?.event_type || props.item?.result || props.item?.status || "unknown")
    const title = computed(() => {
      const task = props.item?.task_name || (props.item?.task_id ? `任务 #${props.item.task_id}` : "")
      return task || (props.type === "clone" ? "克隆发送结果" : "监听执行记录")
    })
    const subtitle = computed(() => {
      const target = props.item?.target || props.item?.target_channel || ""
      const message = props.item?.message || props.item?.error || ""
      return compactText(target || message || props.item?.source_channel || "-")
    })
    const meta = computed(() => [
      ["时间", formatDate(props.item?.time || props.item?.created_at)],
      ["状态", primaryStatus.value],
      ["任务ID", props.item?.task_id],
      ["源频道", props.item?.source_channel],
      ["目标", props.item?.target || props.item?.target_channel],
      ["源消息", props.item?.source_message_id],
      ["目标消息", props.item?.target_message_id],
      ["相册ID", props.item?.grouped_id],
      ["Bot", props.item?.bot_name],
      ["消息", props.item?.message],
      ["错误", props.item?.error],
      ["源链接", props.item?.source_message_url],
      ["目标链接", props.item?.target_message_url],
    ])
    const visibleMeta = computed(() => expanded.value ? meta.value : meta.value.slice(0, 4))

    return () => h("article", {
      class: ["data-card", "log-card", { expanded: expanded.value }],
      onClick: () => { expanded.value = !expanded.value },
    }, [
      h("div", { class: "card-main" }, [
        h("div", { style: "min-width:0" }, [
          h("div", { class: "card-title" }, title.value),
          h("div", { class: "card-subtitle" }, subtitle.value),
        ]),
        h("div", { class: "card-side" }, [
          h(StatusPill, { status: primaryStatus.value }),
          h("span", { class: "card-toggle" }, [
            h(resolve("el-icon"), null, () => h(expanded.value ? ArrowUpBold : ArrowDownBold)),
          ]),
        ]),
      ]),
      h("div", { class: "card-meta" }, visibleMeta.value
        .filter(([, value]) => value !== undefined && value !== null && value !== "")
        .map(([label, value]) => h("div", { class: "meta-item", key: label }, [
          h("span", { class: "meta-label" }, label),
          h("span", { class: "meta-value" }, compactText(value)),
        ]))),
    ])
  },
})

const MorePage = defineComponent({
  props: {
    requestActions: { type: Object, default: () => ({}) },
    page: String,
    bots: Array,
    supportBots: Array,
    templates: Array,
    accounts: Array,
    defaultAccountSettingId: Number,
    settings: Object,
    aiSettings: Object,
    loading: Object,
    keyword: Object,
    allowedFeatures: { type: Array, default: () => [] },
    isAdmin: Boolean,
  },
  emits: [
    "select",
    "update-keyword",
    "edit",
    "delete",
    "test-bot",
    "manage-profile",
    "test-support",
    "toggle-account",
    "set-default-account",
    "toggle-bot",
    "toggle-support",
    "toggle-template",
    "save-settings",
    "save-ai-settings",
    "create",
    "login-account",
  ],
  setup(props, { emit: rawEmit }) {
    const emit = useRequestEmit(rawEmit, props)
    return () => {
      if (props.page === "menu") {
        const allowed = new Set(props.allowedFeatures || [])
        const hasSystem = props.isAdmin || allowed.has("system_settings")
        const hasAi = props.isAdmin || allowed.has("ai_settings")
        const settingsTitle = hasSystem && hasAi ? "系统与 AI 设置" : hasAi ? "AI 配置" : "系统设置"
        const settingsText = hasSystem && hasAi
          ? "维护发送设置、AI 配置和内容规则"
          : hasAi
            ? "维护 AI 服务和内容改写配置"
            : "维护发送设置和内容规则"
        const entries = [
          ["access", "授权信息", "查看账号状态、已开通功能和使用期限", null],
          ["alerts", "系统告警", "查看错误、警告并在系统内确认", "alerts"],
          ["bots", "Bot 管理", "测试、启用和维护分发 Bot", "bots"],
          ["support", "客服机器人", "查看状态、测试和调整欢迎语", "support"],
          ["settings", settingsTitle, settingsText, ["system_settings", "ai_settings"]],
          ["accounts", "Telegram 账号", "查看采集账号和 session 状态", "accounts"],
        ]
        const visibleEntries = entries.filter(([, , , feature]) => {
          if (!feature || props.isAdmin) return true
          const required = Array.isArray(feature) ? feature : [feature]
          return required.some((key) => allowed.has(key))
        })
        return h("div", { class: "page card-list" }, visibleEntries.map(([key, title, text]) =>
          h(resolve("request-button"), { native: true, type: "button", class: "data-card more-entry", onClick: () => emit("select", key) }, () => [
            h("div", { class: "card-title" }, title),
            h("div", { class: "card-subtitle" }, text),
          ]),
        ))
      }
      if (props.page === "settings") {
        return h("div", [
          h("div", { class: "search-bar" }, [
            h(resolve("request-button"), { plain: true, onClick: () => emit("select", "menu") }, () => "返回"),
          ]),
          h("div", { class: "page" }, [
            h(MobileSettingsPage, {
              settings: props.settings,
              aiSettings: props.aiSettings,
              templates: props.templates,
              saving: props.loading?.settings,
              showSystem: props.isAdmin || props.allowedFeatures?.includes("system_settings"),
              showAi: props.isAdmin || props.allowedFeatures?.includes("ai_settings"),
              requestActions: { 'save-settings': (payload) => emit("save-settings", payload), 'save-ai-settings': (payload) => emit("save-ai-settings", payload), 'create-template': (type) => emit("create", "template", type), 'edit-template': (item) => emit("edit", "template", item), 'delete-template': (item) => emit("delete", "template", item), 'toggle-template': (item) => emit("toggle-template", item) },





            }),
          ]),
        ])
      }
      const config = {
        bots: ["Bot 管理", "搜索 Bot 名称 / username", "bots", props.bots, props.loading?.bots],
        support: ["客服机器人", "搜索名称 / 群 ID / 错误", "support", props.supportBots, props.loading?.support],
        settings: ["系统设置", "搜索模板名称 / 类型", "templates", props.templates, props.loading?.templates || props.loading?.settings],
        accounts: ["账号管理", "搜索账号 / username / 手机号", "accounts", props.accounts, props.loading?.accounts],
      }[props.page]
      if (!config) {
        return h("div", { class: "page" }, [
          h(EmptyState, {
            title: "当前页面不可用",
            text: "请返回功能菜单，或刷新账号授权后重试。",
          }),
          h(resolve("request-button"), { type: "primary", onClick: () => emit("select", "menu") }, () => "返回功能菜单"),
        ])
      }
      return h("div", [
        h("div", { class: "search-bar" }, [
          h(resolve("request-button"), { plain: true, onClick: () => emit("select", "menu") }, () => "返回"),
          h(resolve("el-input"), {
            style: "margin-top:8px",
            modelValue: props.keyword[config[2]],
            "onUpdate:modelValue": (value) => emit("update-keyword", config[2], value),
            placeholder: config[1],
            "aria-label": `搜索${config[0]}`,
            clearable: true,
          }),
        ]),
        h("div", { class: "page" }, [
          h("div", { class: "section-head" }, [
            h("div", { class: "section-title" }, config[0]),
            h("div", { class: "row-actions" }, [
              props.page === "accounts"
                ? h(resolve("request-button"), { size: "small", type: "primary", onClick: () => emit("login-account", null) }, () => "登录账号")
                : h(resolve("request-button"), { size: "small", type: "primary", onClick: () => emit("create", props.page === "bots" ? "bot" : props.page === "support" ? "support" : "template") }, () => "新增"),
            ]),
          ]),
          config[4]
            ? h(resolve("el-skeleton"), { rows: 6, animated: true })
            : config[3]?.length
              ? h("div", { class: "card-list" }, config[3].map((item) => moreCard(
                props.page,
                item,
                emit,
                props.defaultAccountSettingId,
              )))
              : h(EmptyState, { title: props.keyword[config[2]]?.trim() ? "没有匹配记录，请调整搜索内容" : "暂无" + config[0] }),
        ]),
      ])
    }
  },
})

function moreCard(type, item, emit, defaultAccountSettingId = null) {
  if (type === "bots") {
    return h(TaskCard, {
      title: item.name || item.username || `Bot #${item.id}`,
      subtitle: item.username || item.bot_id || "-",
      status: item.last_error ? "error" : "enabled",
      enabled: item.enabled,
      meta: [
        ["ID", item.id],
        ["username", item.username],
        ["Bot ID", item.bot_id],
        ["启用状态", enabledLabel(item.enabled)],
        ["Token", item.has_token || item.token ? "已配置" : "-"],
        ["备注", item.remark],
        ["最后错误", item.last_error],
      ],
    }, () => [
      h(resolve("request-button"), { size: "small", type: "primary", plain: true, onClick: () => emit("edit", "bot", item) }, () => "编辑"),
      h(resolve("request-button"), { size: "small", plain: true, onClick: () => emit("manage-profile", item) }, () => "公开资料"),
      h(resolve("request-button"), { size: "small", plain: true, onClick: () => emit("test-bot", item) }, () => "测试"),
      h(resolve("request-button"), { size: "small", plain: true, onClick: () => emit("toggle-bot", item) }, () => item.enabled ? "停用" : "启用"),
      h(resolve("request-button"), { size: "small", type: "danger", plain: true, onClick: () => emit("delete", "bot", item) }, () => "删除"),
    ])
  }
  if (type === "support") {
    return h(TaskCard, {
      title: item.name || `客服机器人 #${item.id}`,
      subtitle: item.support_group_chat_id || item.bot_username || "-",
      status: item.status,
      enabled: item.polling_enabled,
      meta: [
        ["ID", item.id],
        ["价格", item.price],
        ["客服群", item.support_group_chat_id],
        ["Bot用户名", item.bot_username || item.bot_id],
        ["polling", item.polling_enabled ? "启用" : "停用"],
        ["状态", item.status],
        ["文本类型", item.welcome_parse_mode],
        ["欢迎语", item.welcome_text],
        ["最后错误", item.last_error],
      ],
    }, () => [
      h(resolve("request-button"), { size: "small", type: "primary", plain: true, onClick: () => emit("edit", "support", item) }, () => "编辑"),
      h(resolve("request-button"), { size: "small", plain: true, onClick: () => emit("test-support", item) }, () => "测试"),
      h(resolve("request-button"), { size: "small", plain: true, onClick: () => emit("toggle-support", item) }, () => item.polling_enabled ? "停用" : "启用"),
      h(resolve("request-button"), { size: "small", type: "danger", plain: true, onClick: () => emit("delete", "support", item) }, () => "删除"),
    ])
  }
  if (type === "settings") {
    return h(TaskCard, {
      title: item.name || `模板 #${item.id}`,
      subtitle: item.type || "-",
      status: item.enabled ? "enabled" : "disabled",
      enabled: item.enabled,
      meta: [
        ["ID", item.id],
        ["类型", item.type],
        ["启用状态", enabledLabel(item.enabled)],
        ["内容", item.content || item.contents],
        ["备注", item.remark],
      ],
    }, () => [
      h(resolve("request-button"), { size: "small", type: "primary", plain: true, onClick: () => emit("edit", "template", item) }, () => "编辑"),
      h(resolve("request-button"), { size: "small", plain: true, onClick: () => emit("toggle-template", item) }, () => item.enabled ? "停用" : "启用"),
      h(resolve("request-button"), { size: "small", type: "danger", plain: true, onClick: () => emit("delete", "template", item) }, () => "删除"),
    ])
  }
  return h(TaskCard, {
    title: item.name || item.username || `账号 #${item.id}`,
    subtitle: item.username || item.phone_masked || "-",
    status: item.enabled ? "enabled" : "disabled",
    enabled: item.enabled,
    meta: [
      ["ID", item.id],
      ["username", item.username],
      ["手机号", item.phone_masked || (item.has_phone ? "已配置" : "-")],
      ["启用状态", enabledLabel(item.enabled)],
      ["默认账号", item.is_default ? "全局默认" : "否"],
      ["问候消息", item.greeting_enabled ? "已开启" : "未开启"],
      ["离线消息", item.away_enabled ? "已开启" : "未开启"],
      ["Session", item.has_session_path ? "已配置" : "未配置"],
      ["代理", item.has_proxy ? "已配置" : "未配置"],
      ["备注", item.remark],
      ["最后错误", item.last_error],
    ],
  }, () => [
    item.is_default
      ? h(resolve("el-tag"), { size: "small", type: "success" }, () => "全局默认")
      : h(resolve("request-button"), {
        size: "small",
        type: "primary",
        plain: true,
        disabled: !item.enabled,
        loading: defaultAccountSettingId === item.id,
        onClick: () => emit("set-default-account", item),
      }, () => "设为默认"),
    h(resolve("request-button"), { size: "small", type: "primary", plain: true, onClick: () => emit("edit", "account", item) }, () => "编辑"),
    h(resolve("request-button"), { size: "small", plain: true, onClick: () => emit("login-account", item) }, () => "重新登录"),
    h(resolve("request-button"), { size: "small", plain: true, onClick: () => emit("toggle-account", item) }, () => item.enabled ? "停用" : "启用"),
    h(resolve("request-button"), { size: "small", type: "danger", plain: true, onClick: () => emit("delete", "account", item) }, () => "删除"),
  ])
}

const EditForm = defineComponent({
  props: {
    requestActions: { type: Object, default: () => ({}) },
    type: String,
    form: Object,
    saving: Boolean,
    bots: Array,
    accounts: Array,
    templates: Array,
    uploading: Boolean,
  },
  emits: ["cancel", "save", "upload-media", "clear-media"],
  setup(props, { emit: rawEmit }) {
    const emit = useRequestEmit(rawEmit, props)
    const activeStep = ref(0)
    const activePanels = ref(["basic"])

    return () => {
      const isCreate = !props.form?.id
      const baseSections = formSections(props.type, isCreate, props.form)
      const sections = isCreate
        ? [
          ...baseSections,
          {
            key: "confirm",
            title: "确认创建",
            tip: "请确认下面的配置是否符合预期，确认后系统会按这些设置创建。",
            fields: [],
            confirm: true,
          },
        ]
        : baseSections
      const step = Math.min(activeStep.value, Math.max(sections.length - 1, 0))
      const current = sections[step] || sections[0]

      if (isCreate) {
        return h("div", [
          h(resolve("el-steps"), {
            active: step,
            finishStatus: "success",
            simple: true,
            class: "mobile-steps",
          }, () => sections.map((section) => h(resolve("el-step"), {
            key: section.key,
            title: mobileStepTitle(section),
          }))),
          h("div", { class: "form-section-panel" }, [
            h("div", { class: "section-title" }, current?.title || "填写信息"),
            h("div", { class: "section-subtitle" }, current?.tip || ""),
            current?.confirm
              ? renderConfirmSummary(props)
              : h(resolve("el-form"), { labelPosition: "top" }, () => (current?.fields || []).map((field) =>
                h(resolve("el-form-item"), {
                  key: field.key,
                  label: field.label,
                  error: formFieldError(props.type, field, props.form),
                }, () => fieldRender(props, emit, field)),
              )),
          ]),
          h("div", { class: "form-actions" }, [
            h(resolve("request-button"), {
              disabled: step <= 0,
              onClick: () => { activeStep.value = Math.max(0, step - 1) },
            }, () => "上一步"),
            step < sections.length - 1
              ? h(resolve("request-button"), {
                type: "primary",
                onClick: () => {
                  if (!validateWizardStep(props.type, current, props.form)) return
                  activeStep.value = Math.min(sections.length - 1, step + 1)
                },
              }, () => "下一步")
              : h(resolve("request-button"), {
                type: "primary",
                loading: props.saving,
                onClick: () => emit("save"),
              }, () => "创建"),
          ]),
        ])
      }

      const panelKeys = sections.map((section) => section.key)
      if (!activePanels.value.some((key) => panelKeys.includes(key))) {
        activePanels.value = panelKeys.slice(0, 2)
      }

      return h("div", [
        h(resolve("el-collapse"), {
          modelValue: activePanels.value,
          "onUpdate:modelValue": (value) => { activePanels.value = value },
        }, () => sections.map((section) =>
          h(resolve("el-collapse-item"), {
            key: section.key,
            name: section.key,
            title: section.title,
          }, () => [
            section.tip ? h("div", { class: "section-subtitle form-tip" }, section.tip) : null,
            h(resolve("el-form"), { labelPosition: "top" }, () => section.fields.map((field) =>
              h(resolve("el-form-item"), {
                key: field.key,
                label: field.label,
                error: formFieldError(props.type, field, props.form),
              }, () => fieldRender(props, emit, field)),
            )),
          ]),
        )),
        h("div", { class: "form-actions" }, [
          h(resolve("request-button"), { onClick: () => emit("cancel") }, () => "取消"),
          h(resolve("request-button"), { type: "primary", loading: props.saving, onClick: () => emit("save") }, () => (
            props.type === "channel" ? "保存并检测" : "保存"
          )),
        ]),
      ])
    }
  },
})

function mobileStepTitle(section) {
  const labels = {
    channels: "频道",
    range: "范围",
    send: "发送",
    content: "内容",
    confirm: "确认",
    basic: "基础",
    delivery: "分发",
    "plan-notice": "原文",
    advanced: "高级",
  }
  return labels[section?.key] || section?.title || ""
}

function formFieldError(type, field, form) {
  if (type !== "listener" || field?.key !== "target_channels") return ""
  const conflict = findListenerChannelConflict(form?.source_channel, form?.target_channels)
  return conflict ? `源频道不能同时作为目标频道：${conflict}` : ""
}

const AccountLoginForm = defineComponent({
  props: {
    requestActions: { type: Object, default: () => ({}) },
    account: Object,
    loading: Boolean,
  },
  emits: ["cancel", "start", "verify"],
  setup(props, { emit: rawEmit }) {
    const emit = useRequestEmit(rawEmit, props)
    const step = ref(0)
    const loginId = ref("")
    const needPassword = ref(false)
    const form = reactive({
      account_id: props.account?.id || null,
      name: props.account?.name || "",
      phone: props.account?.phone || "",
      proxy: props.account?.proxy || "",
      remark: props.account?.remark || "",
      update_existing: Boolean(props.account?.id),
    })
    const verifyForm = reactive({
      code: "",
      password: "",
    })

    async function start() {
      if (!form.name || (!form.account_id && !form.phone)) {
        ElMessage.warning(form.account_id ? "账号名称不能为空" : "账号名称和手机号不能为空")
        return
      }
      const data = await emitAsync(emit, "start", { ...form })
      if (data?.ok && data.already_authorized) {
        step.value = 2
        return
      }
      if (data?.ok) {
        loginId.value = data.login_id
        step.value = 1
        ElMessage.success(data.message || "验证码已发送")
      }
      if (data?.need_password) {
        needPassword.value = true
      }
    }

    async function verify() {
      if (!verifyForm.code) {
        ElMessage.warning("请输入验证码")
        return
      }
      const data = await emitAsync(emit, "verify", {
        login_id: loginId.value,
        code: verifyForm.code,
        password: verifyForm.password,
      })
      if (data?.need_password) {
        needPassword.value = true
      }
      if (data?.ok) {
        step.value = 2
      }
    }

    return () => h("div", [
      step.value === 0 ? h(resolve("el-form"), { labelPosition: "top" }, [
        loginInput(form, "name", "账号名称"),
        loginInput(
          form,
          "phone",
          "手机号",
          "text",
          props.account?.has_phone
            ? `已配置 ${props.account.phone_masked || ""}，留空继续使用`
            : undefined,
        ),
        loginInput(
          form,
          "proxy",
          "代理",
          "password",
          props.account?.has_proxy ? "代理已配置，留空继续使用" : undefined,
        ),
        loginInput(form, "remark", "备注", "textarea"),
      ]) : null,
      step.value === 1 ? h(resolve("el-form"), { labelPosition: "top" }, [
        loginInput(verifyForm, "code", "验证码"),
        needPassword.value ? loginInput(verifyForm, "password", "二步验证密码", "password") : null,
      ]) : null,
      step.value === 2 ? h(resolve("el-result"), {
        icon: "success",
        title: "账号登录成功",
        subTitle: "请刷新账号列表确认状态。",
      }) : null,
      h("div", { class: "form-actions" }, [
        h(resolve("request-button"), { onClick: () => emit("cancel") }, () => "关闭"),
        step.value === 0
          ? h(resolve("request-button"), { type: "primary", loading: props.loading, onClick: start }, () => "发送验证码")
          : null,
        step.value === 1
          ? h(resolve("request-button"), { type: "primary", loading: props.loading, onClick: verify }, () => needPassword.value ? "提交密码" : "登录")
          : null,
      ]),
    ])
  },
})

function loginInput(target, key, label, type = "text", placeholderOverride = "") {
  return h(resolve("el-form-item"), { label }, () => h(resolve("el-input"), {
    modelValue: target[key],
    type: type === "password" ? "password" : type === "textarea" ? "textarea" : "text",
    rows: type === "textarea" ? 3 : undefined,
    placeholder: placeholderOverride || loginPlaceholder(key),
    showPassword: type === "password",
    "onUpdate:modelValue": (value) => { target[key] = value },
  }))
}

function loginPlaceholder(key) {
  const map = {
    name: "例如：采集账号，方便后台识别",
    phone: "填写 Telegram 手机号，例如 +8613800000000",
    proxy: "可留空，例如 socks5://127.0.0.1:7890",
    remark: "可留空，填写这个账号的用途",
    code: "填写 Telegram 收到的验证码",
    password: "填写 Telegram 二步验证密码",
  }
  return map[key] || "请输入内容"
}

function emitAsync(emit, event, payload) {
  return new Promise((resolvePromise) => {
    return emit(event, payload, resolvePromise)
  })
}

function validateWizardStep(type, section, form) {
  const requiredBySection = {
    listener: {
      basic: [
        ["name", "请填写任务名称"],
        ["source_channel", "请填写源频道"],
        ["target_channels", "请填写目标频道"],
      ],
      delivery: [
        ["account_id", "请选择监听账号"],
        ["bot_id", "请选择分发 Bot"],
      ],
    },
    clone: {
      channels: [
        ["name", "请填写任务名称"],
        ["source_channel", "请填写源频道"],
        ["target_channels", "请填写目标频道"],
      ],
      send: [
        ["bot_id", "请选择分发 Bot"],
      ],
    },
    channel: { basic: [] },
    bot: {
      basic: [
        ["name", "请填写 Bot 名称"],
      ],
    },
    support: {
      basic: [
        ["name", "请填写客服机器人名称"],
        ["support_group_chat_id", "请填写客服群 chat_id"],
      ],
    },
    template: {
      basic: [
        ["name", "请填写规则名称"],
        ["type", "请选择规则类型"],
      ],
    },
  }
  const rules = requiredBySection[type]?.[section?.key] || []
  if (type === "channel" && section?.key === "basic" && !String(form.username || "").trim() && !String(form.chat_id || "").trim()) {
    ElMessage.warning("请填写频道 username、链接或 chat_id")
    return false
  }
  for (const [key, message] of rules) {
    if (!String(form?.[key] || "").trim()) {
      ElMessage.warning(message)
      return false
    }
  }
  if (type === "listener" && section?.key === "basic") {
    const conflict = findListenerChannelConflict(form.source_channel, form.target_channels)
    if (conflict) {
      ElMessage.warning(`监听任务的源频道不能同时作为目标频道：${conflict}`)
      return false
    }
  }
  if (type === "bot" && section?.key === "basic" && !form.id && !String(form.token || "").trim()) {
    ElMessage.warning("请填写 Bot Token")
    return false
  }
  if (
    type === "support"
    && section?.key === "basic"
    && !form.bot_id
    && !form.has_bot_token
    && !String(form.bot_token || "").trim()
  ) {
    ElMessage.warning("请选择已有 Bot 或填写独立 Token")
    return false
  }
  if (type === "template" && section?.key === "basic") {
    if (form.type === "link") return true
    if (!String(form.contents || form.content || "").trim()) {
      ElMessage.warning("请填写至少一条规则内容")
      return false
    }
  }
  return true
}

function renderConfirmSummary(props) {
  const rows = formSummaryRows(props.type, props.form, props)
  return h("div", { class: "confirm-summary" }, [
    h("div", { class: "confirm-title" }, "创建摘要"),
    ...rows.map(([label, value]) => h("div", { class: "confirm-row", key: label }, [
      h("span", null, label),
      h("strong", null, compactText(value)),
    ])),
  ])
}

function formSummaryRows(type, form, props) {
  const botName = optionName(props.bots, form.bot_id)
  const accountName = optionName(props.accounts, form.account_id)
  const defaultAccountName = optionName(
    props.accounts,
    (props.accounts || []).find((item) => item.enabled && item.is_default)?.id,
  )
  const filterName = optionName(props.templates, form.selected_filter_template_group_id)
  const linkName = optionName(props.templates, form.selected_link_template_group_id)
  const contactName = optionName(props.templates, form.selected_contact_template_group_id)
  const commonContent = [
    ["删除联系方式", form.remove_contact_lines ? "开启" : "关闭"],
    ["过滤二维码", form.filter_qr_code ? "开启" : "关闭"],
    ["只监听内容", displayEditValue(form.listen_required_keywords, "textarea") || "全部监听"],
    ["过滤规则", filterName || "未选择"],
    ["链接规则", linkName || "未选择"],
    ["联系方式规则", contactName || "默认配置"],
  ]
  const map = {
    listener: [
      ["任务名称", form.name],
      ["源频道", form.source_channel],
      ["目标频道", displayEditValue(form.target_channels, "textarea")],
      ["监听账号", accountName],
      ["分发 Bot", botName],
      ...commonContent,
      ["创建后状态", form.enabled ? "启用" : "停用"],
    ],
    clone: [
      ["任务名称", form.name],
      ["源频道", form.source_channel],
      ["目标频道", displayEditValue(form.target_channels, "textarea")],
      ["开始链接", form.start_message_url || "从默认位置开始"],
      ["结束链接", form.end_message_url || "到当前最新内容"],
      ["克隆数量", form.clone_limit],
      ["采集账号", accountName || `${defaultAccountName || "未设置"}（全局默认）`],
      ["分发 Bot", botName],
      ["完成后监听", form.enable_listener ? "开启" : "关闭"],
      ...commonContent,
    ],
    channel: [
      ["频道名称", form.title],
      ["频道链接", form.username],
      ["分组", form.group_name],
      ["绑定 Bot", botName || "未绑定"],
      ["投放状态", form.delivery_status || "-"],
      ["收录状态", form.collection_status || "-"],
    ],
    bot: [
      ["Bot 名称", form.name],
      ["Token", form.token ? "已填写" : "未填写"],
      ["启用状态", form.enabled ? "启用" : "停用"],
    ],
    support: [
      ["客服机器人", form.name],
      ["Bot 来源", form.bot_id ? `复用 ${botName}` : "独立 Token"],
      ["价格", form.price],
      ["客服群", form.support_group_chat_id],
      ["欢迎语", form.welcome_message],
      ["媒体", form.welcome_media_file_id ? "已配置" : "无"],
      ["Polling", form.polling_enabled ? "开启" : "关闭"],
    ],
    template: [
      ["规则名称", form.name],
      ["类型", templateTypeLabel(form.type)],
      ["内容", form.type === "link" ? "链接处理配置" : displayEditValue(form.contents || form.content, "textarea")],
      ["启用状态", form.enabled ? "启用" : "停用"],
    ],
  }
  return map[type] || []
}

function optionName(items = [], id) {
  const item = (items || []).find((entry) => String(entry.id) === String(id))
  return item ? (item.name || item.title || item.username || `#${item.id}`) : ""
}

function templateTypeLabel(type) {
  const map = {
    head: "头部模板",
    body: "正文模板",
    footer: "底部模板",
    filter: "过滤规则",
    link: "链接规则",
    contact: "联系方式删除",
  }
  return map[type] || type || "-"
}

function formSections(type, isCreate, form) {
  const enabled = { key: "enabled", label: "启用", input: "switch" }
  const contentProcessingEnabled = currentUser.value?.role === "admin" || currentUser.value?.plan_tier === "paid"
  const freePlanNotice = {
    key: "plan-notice",
    title: "原文克隆",
    tip: "免费版不能配置内容处理、AI 改写和内容模板，系统将一比一直接克隆原内容。",
    fields: [],
  }
  const randomTemplateFields = [
    { key: "use_random_head", label: "随机头部", input: "switch" },
    { key: "selected_head_template_group_id", label: "头部模板", input: "template-head" },
    { key: "use_random_body", label: "随机正文", input: "switch" },
    { key: "selected_body_template_group_id", label: "正文模板", input: "template-body" },
    { key: "use_random_footer", label: "随机底部", input: "switch" },
    { key: "selected_footer_template_group_id", label: "底部模板", input: "template-footer" },
  ]
  const contentFields = [
    { key: "selected_filter_template_group_id", label: "通用过滤词", input: "template-filter" },
    { key: "selected_link_template_group_id", label: "链接配置", input: "template-link" },
    { key: "selected_contact_template_group_id", label: "联系方式配置", input: "template-contact" },
    { key: "listen_required_keywords", label: "只监听内容", input: "lines" },
    { key: "blocked_keywords", label: "补充过滤词", input: "lines" },
    { key: "remove_contact_lines", label: "删除联系方式", input: "switch" },
    { key: "filter_qr_code", label: "过滤二维码图片", input: "switch" },
  ]
  const aiRewriteFields = [
    { key: "ai_rewrite_enabled", label: "启用 AI 改写", input: "switch" },
    { key: "ai_rewrite_provider", label: "模型供应商", input: "ai-provider" },
    { key: "ai_rewrite_model", label: "模型名称（可选）", placeholder: "DeepSeek 默认 deepseek-v4-flash；Grok 默认 grok-4.6" },
    { key: "ai_rewrite_max_chars", label: "最大输出字数", input: "number" },
    { key: "ai_rewrite_failure_mode", label: "调用失败时", input: "ai-failure" },
    { key: "ai_rewrite_prompt", label: "改写提示词（可选）", input: "textarea", placeholder: "留空使用默认事实保真提示词；支持 {{content}} 和 {{max_chars}}。" },
  ]

  const listener = [
    {
      key: "basic",
      title: "基础信息",
      tip: "填写任务名称、源频道和目标频道，频道支持 @username 或 t.me 链接。",
      fields: [
        { key: "name", label: "任务名称" },
        { key: "source_channel", label: "源频道" },
        { key: "target_channels", label: "目标频道", input: "channels" },
      ],
    },
    {
      key: "delivery",
      title: "分发设置",
      fields: [
        { key: "account_id", label: "监听账号", input: "account" },
        { key: "bot_id", label: "分发 Bot", input: "bot" },
      ],
    },
    ...(contentProcessingEnabled
      ? [
          { key: "content", title: "内容处理", fields: contentFields },
          { key: "ai-rewrite", title: "AI 改写", tip: "先清洗内容，再调用所选模型。", fields: aiRewriteFields },
        ]
      : [freePlanNotice]),
    {
      key: "advanced",
      title: "高级设置",
      tip: "一般不用修改，只有需要随机模板、替换词或相册等待时再打开。",
      fields: [
        ...(contentProcessingEnabled ? [{ key: "replace_words", label: "替换词", input: "json" }] : []),
        { key: "album_wait_seconds", label: "相册等待秒", input: "number" },
        ...(contentProcessingEnabled ? randomTemplateFields : []),
        enabled,
      ],
    },
  ]

  const clone = [
    {
      key: "channels",
      title: "频道",
      fields: [
        { key: "name", label: "任务名称" },
        { key: "source_channel", label: "源频道" },
        { key: "target_channels", label: "目标频道", input: "channels" },
      ],
    },
    {
      key: "range",
      title: "克隆范围",
      tip: "开始/结束链接可留空；留空时按后端默认范围执行。",
      fields: [
        { key: "start_message_url", label: "开始内容链接" },
        { key: "end_message_url", label: "结束内容链接" },
        { key: "clone_limit", label: "克隆数量上限", input: "number" },
      ],
    },
    {
      key: "send",
      title: "发送设置",
      fields: [
        {
          key: "account_id",
          label: "采集账号（可选）",
          input: "account",
          placeholder: "可留空，使用账号管理中的全局默认账号",
        },
        { key: "bot_id", label: "分发 Bot", input: "bot" },
        { key: "single_delay", label: "内容间隔分钟", input: "number" },
        { key: "target_delay", label: "目标间隔秒", input: "number" },
        { key: "enable_listener", label: "完成后进入监听", input: "switch" },
      ],
    },
    ...(contentProcessingEnabled
      ? [
          { key: "content", title: "内容处理", fields: contentFields },
          { key: "ai-rewrite", title: "AI 改写", tip: "先清洗内容，再调用所选模型。", fields: aiRewriteFields },
        ]
      : [freePlanNotice]),
    {
      key: "advanced",
      title: "高级设置",
      fields: [
        ...(contentProcessingEnabled ? [{ key: "replace_words", label: "替换词", input: "json" }] : []),
        { key: "album_delay", label: "相册等待秒", input: "number" },
        ...(contentProcessingEnabled ? randomTemplateFields : []),
        enabled,
      ],
    },
  ]

  const channel = [{
    key: "basic",
    title: "频道信息",
    fields: [
      { key: "title", label: "频道名称" },
      { key: "username", label: "username / 链接" },
      { key: "group_name", label: "分组" },
      { key: "bot_id", label: "绑定 Bot", input: "bot" },
      { key: "delivery_status", label: "投放状态" },
      { key: "collection_status", label: "收录状态" },
      { key: "remark", label: "备注", input: "textarea" },
      enabled,
    ],
  }]

  const bot = [{
    key: "basic",
    title: "Bot 信息",
    fields: [
      { key: "name", label: "Bot 名称" },
      { key: "token", label: "Bot Token" },
      ...(isCreate ? [] : [{ key: "username", label: "username" }]),
      { key: "remark", label: "备注", input: "textarea" },
      enabled,
    ],
  }]

  const support = [
    {
      key: "basic",
      title: "基础配置",
      fields: [
        { key: "name", label: "客服机器人名称" },
        { key: "bot_id", label: "复用已有 Bot", input: "bot" },
        { key: "bot_token", label: "或填写独立 Token" },
        { key: "price", label: "价格" },
        { key: "support_group_chat_id", label: "客服群 chat_id" },
        { key: "polling_enabled", label: "启用 polling", input: "switch" },
      ],
    },
    {
      key: "welcome",
      title: "欢迎语",
      fields: [
        { key: "welcome_message", label: "欢迎语", input: "rich-textarea" },
        { key: "welcome_text_type", label: "文本类型", input: "welcome-type" },
        { key: "welcome_media_type", label: "媒体类型", input: "media-type" },
        { key: "welcome_media_file_id", label: "媒体文件", input: "media" },
      ],
    },
    {
      key: "business",
      title: "营业时间",
      fields: [
        { key: "business_hours_enabled", label: "启用营业时间", input: "switch" },
        { key: "business_start_hour", label: "开始小时", input: "number" },
        { key: "business_end_hour", label: "结束小时", input: "number" },
        { key: "off_hours_message", label: "非营业时间回复", input: "rich-textarea" },
      ],
    },
  ]

  const templateFields = [
    { key: "name", label: "规则名称" },
    { key: "type", label: "类型", input: "template-type" },
    form?.type === "link"
      ? { key: "link_config", label: "链接处理方式", input: "link-config" }
      : form?.type === "contact"
        ? { key: "contact_config", label: "联系方式删除配置", input: "contact-config" }
        : { key: "contents", label: "规则内容，一行一条", input: "rich-textarea" },
    enabled,
  ]

  const account = [
    {
      key: "basic",
      title: "账号信息",
      tip: form?.id
        ? "手机号、Session 路径和代理凭据不会回显；敏感字段留空会保持原配置。"
        : "新增账号请使用“登录账号”流程；这里主要用于编辑已有账号。",
      fields: [
        { key: "name", label: "账号名称" },
        { key: "username", label: "username" },
        {
          key: "session_path",
          label: "Session 路径",
          placeholder: form?.id && form?.has_session_path ? "已配置，留空保持不变" : "填写 Session 路径",
        },
        {
          key: "proxy",
          label: "代理",
          input: "password",
          placeholder: form?.id && form?.has_proxy ? "代理已配置，留空保持不变" : "可留空，例如 socks5://host:port",
        },
        ...(form?.id && form?.has_proxy
          ? [{ key: "clear_proxy", label: "清除当前代理", input: "switch" }]
          : []),
        { key: "remark", label: "备注", input: "textarea" },
        enabled,
      ],
    },
    {
      key: "auto-reply",
      title: "私聊自动回复",
      tip: "仅处理其他用户发来的私聊；群组、频道和机器人消息不会触发。营业时间按服务器本地时间判断。",
      fields: [
        { key: "greeting_enabled", label: "问候消息", input: "switch" },
        { key: "greeting_message", label: "问候内容", input: "textarea" },
        { key: "away_enabled", label: "离线消息", input: "switch" },
        { key: "away_message", label: "离线内容", input: "textarea" },
        { key: "business_start_time", label: "营业开始（HH:mm）", placeholder: "例如 09:00" },
        { key: "business_end_time", label: "营业结束（HH:mm）", placeholder: "例如 18:00" },
        { key: "away_repeat_hours", label: "离线消息重复间隔（小时）", input: "number" },
      ],
    },
  ]

  const map = {
    listener,
    clone,
    channel,
    bot,
    support,
    template: [{ key: "basic", title: "内容规则模板", fields: templateFields }],
    account,
  }

  const sections = map[type] || []
  if (!isCreate) return sections
  if (type === "listener") return sections.filter((item) => item.key !== "advanced")
  if (type === "clone") return sections.filter((item) => item.key !== "advanced")
  return sections
}

function legacyFieldRender(props, emit, field) {
  const form = props.form
  const placeholder = fieldPlaceholder(field)
  if (field.input === "switch") {
    return h(resolve("el-switch"), {
      modelValue: Boolean(form[field.key]),
      "onUpdate:modelValue": (value) => { form[field.key] = value },
    })
  }
  if (field.input === "bot" || field.input === "account" || ["template-filter", "template-link", "template-contact", "template-head", "template-body", "template-footer"].includes(field.input)) {
    return h(resolve("el-select"), {
      modelValue: form[field.key] || null,
      "onUpdate:modelValue": (value) => { form[field.key] = value },
      clearable: true,
      filterable: true,
      placeholder: "请选择",
      style: "width: 100%",
    }, () => selectOptions(props, field.input))
  }
  if (field.input === "template-type") {
    const options = [
      ["head", "头部"],
      ["body", "正文"],
      ["footer", "底部"],
      ["filter", "过滤关键词"],
      ["link", "链接配置"],
      ["contact", "联系方式删除"],
    ]
    return h(resolve("el-select"), {
      modelValue: form[field.key] || "footer",
      "onUpdate:modelValue": (value) => { form[field.key] = value },
      style: "width: 100%",
    }, () => options.map(([value, label]) => h(resolve("el-option"), { value, label })))
  }
  if (field.input === "welcome-type") {
    return h(resolve("el-select"), {
      modelValue: form[field.key] || "plain",
      "onUpdate:modelValue": (value) => { form[field.key] = value },
      style: "width: 100%",
    }, () => [
      h(resolve("el-option"), { value: "plain", label: "纯文本" }),
      h(resolve("el-option"), { value: "html", label: "HTML 富文本" }),
    ])
  }
  if (field.input === "media-type") {
    const options = ["text", "photo", "video", "document", "animation", "audio", "voice"]
    return h(resolve("el-select"), {
      modelValue: form[field.key] || "text",
      "onUpdate:modelValue": (value) => { form[field.key] = value },
      style: "width: 100%",
    }, () => options.map((value) => h(resolve("el-option"), { value, label: value })))
  }
  if (field.input === "media") {
    return h("div", { class: "media-upload-field" }, [
      h(resolve("el-input"), {
        modelValue: form[field.key] || "",
        "onUpdate:modelValue": (value) => { form[field.key] = value },
        placeholder: "上传后自动填入，也可以手动填写 file_id",
      }),
      h("div", { class: "inline-actions" }, [
        h(resolve("el-upload"), {
          showFileList: false,
          httpRequest: (request) => emit("upload-media", request),
        }, () => h(resolve("request-button"), { loading: props.uploading, plain: true }, () => "上传文件")),
        h(resolve("request-button"), { plain: true, onClick: () => emit("clear-media") }, () => "清空"),
      ]),
    ])
  }
  if (field.input === "channels" || field.input === "lines") {
    return h(resolve("el-input"), {
      modelValue: displayEditValue(form[field.key], "textarea"),
      type: "textarea",
      rows: 4,
      placeholder: field.input === "channels" ? "一行一个目标频道，例如 @channel 或 https://t.me/channel" : "一行一个关键词",
      "onUpdate:modelValue": (value) => { form[field.key] = value },
    })
  }
  if (field.input === "json") {
    return h(resolve("el-input"), {
      modelValue: typeof form[field.key] === "string" ? form[field.key] : JSON.stringify(form[field.key] || {}, null, 2),
      type: "textarea",
      rows: 4,
      placeholder: "高级替换词配置，一般不用填写",
      "onUpdate:modelValue": (value) => { form[field.key] = value },
    })
  }
  if (field.input === "contact-config") {
    return renderContactConfig(form)
  }
  if (field.input === "link-config") {
    return h("div", { class: "link-config-list" }, linkConfigFields().map((item) =>
      h("div", { class: "link-config-item", key: item.key }, [
        h("div", { class: "meta-label" }, item.label),
        h(resolve("el-select"), {
          modelValue: form[item.key] || defaultLinkConfig()[item.key],
          "onUpdate:modelValue": (value) => { form[item.key] = value },
          style: "width: 100%",
        }, () => linkActionOptions(item.key).map((option) =>
          h(resolve("el-option"), {
            value: option.value,
            label: option.label,
          }),
        )),
        form[item.key] === "replace"
          ? h(resolve("el-input"), {
            modelValue: form[`${item.key}_replacement`] || "",
            placeholder: "填写替换链接",
            style: "margin-top: 8px",
            "onUpdate:modelValue": (value) => { form[`${item.key}_replacement`] = value },
          })
          : null,
      ]),
    ))
  }
  if (field.input === "number") {
    return h(resolve("el-input-number"), {
      modelValue: Number(form[field.key] || 0),
      min: 0,
      controlsPosition: "right",
      style: "width: 100%",
      "onUpdate:modelValue": (value) => { form[field.key] = value },
    })
  }
  if (field.input === "rich-textarea") {
    return h("div", [
      h("div", { class: "rich-actions" }, richActions().map((action) =>
        h(resolve("request-button"), {
          size: "small",
          plain: true,
          onClick: () => { form[field.key] = `${form[field.key] || ""}${action.value}` },
        }, () => action.label),
      )),
      h(resolve("el-input"), {
        modelValue: displayEditValue(form[field.key], "textarea"),
        type: "textarea",
        rows: 5,
        "onUpdate:modelValue": (value) => { form[field.key] = value },
      }),
    ])
  }
  return h(resolve("el-input"), {
    modelValue: displayEditValue(form[field.key], field.input),
    type: field.input === "textarea" ? "textarea" : field.input === "password" ? "password" : "text",
    rows: field.input === "textarea" ? 4 : undefined,
    showPassword: field.input === "password",
    clearable: field.input !== "textarea",
    "onUpdate:modelValue": (value) => { form[field.key] = value },
  })
}

function fieldRender(props, emit, field) {
  const form = props.form
  const placeholder = fieldPlaceholder(field)
  if (field.input === "switch") {
    return h(resolve("el-switch"), {
      modelValue: Boolean(form[field.key]),
      "onUpdate:modelValue": (value) => { form[field.key] = value },
    })
  }
  if (field.input === "bot" || field.input === "account" || ["template-filter", "template-link", "template-contact", "template-head", "template-body", "template-footer"].includes(field.input)) {
    return h(resolve("el-select"), {
      modelValue: form[field.key] || null,
      "onUpdate:modelValue": (value) => { form[field.key] = value },
      clearable: true,
      filterable: true,
      placeholder,
      style: "width: 100%",
    }, () => selectOptions(props, field.input))
  }
  if (field.input === "template-type") {
    const options = [
      ["head", "头部"],
      ["body", "正文"],
      ["footer", "底部"],
      ["filter", "过滤关键词"],
      ["link", "链接配置"],
      ["contact", "联系方式删除"],
    ]
    return h(resolve("el-select"), {
      modelValue: form[field.key] || "footer",
      "onUpdate:modelValue": (value) => { form[field.key] = value },
      placeholder,
      style: "width: 100%",
    }, () => options.map(([value, label]) => h(resolve("el-option"), { value, label })))
  }
  if (field.input === "welcome-type") {
    return h(resolve("el-select"), {
      modelValue: form[field.key] || "plain",
      "onUpdate:modelValue": (value) => { form[field.key] = value },
      placeholder,
      style: "width: 100%",
    }, () => [
      h(resolve("el-option"), { value: "plain", label: "纯文本" }),
      h(resolve("el-option"), { value: "html", label: "HTML 富文本" }),
    ])
  }
  if (field.input === "media-type") {
    const options = ["text", "photo", "video", "document", "animation", "audio", "voice"]
    return h(resolve("el-select"), {
      modelValue: form[field.key] || "text",
      "onUpdate:modelValue": (value) => { form[field.key] = value },
      placeholder,
      style: "width: 100%",
    }, () => options.map((value) => h(resolve("el-option"), { value, label: value })))
  }
  if (field.input === "media") {
    return h("div", { class: "media-upload-field" }, [
      h(resolve("el-input"), {
        modelValue: form[field.key] || "",
        "onUpdate:modelValue": (value) => { form[field.key] = value },
        placeholder,
      }),
      h("div", { class: "inline-actions" }, [
        h(resolve("el-upload"), {
          showFileList: false,
          httpRequest: (request) => emit("upload-media", request),
        }, () => h(resolve("request-button"), { loading: props.uploading, plain: true }, () => "上传文件")),
        h(resolve("request-button"), { plain: true, onClick: () => emit("clear-media") }, () => "清空"),
      ]),
    ])
  }
  if (field.input === "channels" || field.input === "lines") {
    return h(resolve("el-input"), {
      modelValue: displayEditValue(form[field.key], "textarea"),
      type: "textarea",
      rows: 4,
      placeholder,
      "onUpdate:modelValue": (value) => { form[field.key] = value },
    })
  }
  if (field.input === "json") {
    return h(resolve("el-input"), {
      modelValue: typeof form[field.key] === "string" ? form[field.key] : JSON.stringify(form[field.key] || {}, null, 2),
      type: "textarea",
      rows: 4,
      placeholder,
      "onUpdate:modelValue": (value) => { form[field.key] = value },
    })
  }
  if (field.input === "contact-config") {
    return renderContactConfig(form)
  }
  if (field.input === "link-config") {
    return h("div", { class: "link-config-list" }, linkConfigFields().map((item) =>
      h("div", { class: "link-config-item", key: item.key }, [
        h("div", { class: "meta-label" }, item.label),
        h(resolve("el-select"), {
          modelValue: form[item.key] || defaultLinkConfig()[item.key],
          "onUpdate:modelValue": (value) => { form[item.key] = value },
          placeholder: "请选择处理方式",
          style: "width: 100%",
        }, () => linkActionOptions(item.key).map((option) =>
          h(resolve("el-option"), {
            value: option.value,
            label: option.label,
          }),
        )),
        form[item.key] === "replace"
          ? h(resolve("el-input"), {
            modelValue: form[`${item.key}_replacement`] || "",
            placeholder: "填写要替换成的新链接，例如 https://t.me/xxx",
            style: "margin-top: 8px",
            "onUpdate:modelValue": (value) => { form[`${item.key}_replacement`] = value },
          })
          : null,
      ]),
    ))
  }
  if (field.input === "number") {
    return h(resolve("el-input-number"), {
      modelValue: Number(form[field.key] || 0),
      min: 0,
      controlsPosition: "right",
      placeholder,
      style: "width: 100%",
      "onUpdate:modelValue": (value) => { form[field.key] = value },
    })
  }
  if (field.input === "rich-textarea") {
    return h("div", [
      h("div", { class: "rich-actions" }, richActions().map((action) =>
        h(resolve("request-button"), {
          size: "small",
          plain: true,
          onClick: () => { form[field.key] = `${form[field.key] || ""}${action.value}` },
        }, () => action.label),
      )),
      h(resolve("el-input"), {
        modelValue: displayEditValue(form[field.key], "textarea"),
        type: "textarea",
        rows: 5,
        placeholder,
        "onUpdate:modelValue": (value) => { form[field.key] = value },
      }),
    ])
  }
  if (field.input === "ai-failure") {
    return h(resolve("el-select"), {
      modelValue: form[field.key] || "fallback",
      "onUpdate:modelValue": (value) => { form[field.key] = value },
      placeholder,
      style: "width: 100%",
    }, () => [
      h(resolve("el-option"), { value: "fallback", label: "发送清洗后的原文" }),
      h(resolve("el-option"), { value: "skip", label: "跳过本条内容" }),
    ])
  }
  if (field.input === "ai-provider") {
    return h(resolve("el-select"), {
      modelValue: form[field.key] || "grok",
      "onUpdate:modelValue": (value) => { form[field.key] = value },
      placeholder,
      style: "width: 100%",
    }, () => [
      h(resolve("el-option"), { value: "grok", label: "Grok（xAI）" }),
      h(resolve("el-option"), { value: "deepseek", label: "DeepSeek" }),
    ])
  }
  return h(resolve("el-input"), {
    modelValue: displayEditValue(form[field.key], field.input),
    type: field.input === "textarea" ? "textarea" : field.input === "password" ? "password" : "text",
    rows: field.input === "textarea" ? 4 : undefined,
    placeholder,
    showPassword: field.input === "password",
    clearable: field.input !== "textarea",
    "onUpdate:modelValue": (value) => { form[field.key] = value },
  })
}

function fieldPlaceholder(field) {
  if (field.placeholder) return field.placeholder
  const map = {
    name: "填写一个方便识别的名称，例如：上海监听任务",
    source_channel: "填写源频道 @username 或 https://t.me/xxx",
    target_channels: "一行一个目标频道，例如 @channel 或 https://t.me/channel",
    start_message_url: "可留空；或填写源频道某条消息链接，例如 https://t.me/xxx/123",
    end_message_url: "可留空；或填写结束消息链接，例如 https://t.me/xxx/456",
    clone_limit: "填写最多克隆多少条，0 表示不限或按后端默认",
    single_delay: "填写同一目标每条内容间隔分钟数",
    target_delay: "填写不同目标之间的发送间隔秒数",
    album_wait_seconds: "填写相册等待秒数，例如 3",
    album_delay: "填写相册等待秒数，例如 3",
    listen_required_keywords: "一行一个必须命中的内容；留空表示全部监听",
    blocked_keywords: "一行一个过滤关键词，命中后不发送",
    replace_words: "高级替换配置，通常不用填写",
    title: "可留空，保存后自动读取频道名称",
    username: "填写 @username、频道链接或 chat_id；其余信息将自动补全",
    group_name: "填写分组名称，例如：长沙、上海、北京",
    delivery_status: "填写投放状态，例如：投放中、暂停、待确认",
    collection_status: "填写收录状态，例如：已收录、未收录、待检测",
    remark: "可留空，填写备注说明",
    token: "填写 BotFather 提供的 Bot Token",
    bot_token: "填写独立客服机器人的 Bot Token",
    support_group_chat_id: "填写客服群 chat_id，例如 -1001234567890",
    welcome_message: "填写用户启动机器人后看到的欢迎语",
    welcome_text_type: "选择欢迎语的解析方式",
    welcome_media_type: "选择欢迎语媒体类型，没有媒体就选 text",
    welcome_media_file_id: "上传文件后自动填入，也可以手动填写 Telegram file_id",
    off_hours_message: "填写非营业时间自动回复内容",
    business_start_hour: "填写 0-23，例如 9",
    business_end_hour: "填写 0-23，例如 22",
    contents: "一行一条规则；富文本可使用上方快捷按钮",
    type: "选择规则类型",
    account_id: "选择用于监听源频道的用户号",
    bot_id: "选择用于发送内容的 Bot",
    session_path: "填写 session 文件路径，例如 data/sessions/account_1",
    proxy: "可留空，例如 socks5://127.0.0.1:7890",
  }
  if (map[field.key]) return map[field.key]
  if (field.input === "channels") return "一行一个频道，支持 @username、链接或 chat_id"
  if (field.input === "lines") return "一行一条内容"
  if (field.input === "number") return `填写${field.label || "数字"}`
  if (field.input === "textarea" || field.input === "rich-textarea") return `填写${field.label || "内容"}`
  if (field.input && field.input !== "text") return `请选择${field.label || "选项"}`
  return `填写${field.label || "内容"}`
}

function selectOptions(props, inputType) {
  if (inputType === "bot") {
    return (props.bots || []).map((item) => h(resolve("el-option"), {
      key: item.id,
      value: item.id,
      label: `${item.name || item.username || "Bot"}${item.username ? ` / @${String(item.username).replace(/^@/, "")}` : ""}`,
    }))
  }
  if (inputType === "account") {
    return (props.accounts || []).map((item) => h(resolve("el-option"), {
      key: item.id,
      value: item.id,
      label: `${item.name || item.username || "账号"}${item.username ? ` / @${String(item.username).replace(/^@/, "")}` : ""}${item.is_default ? " [全局默认]" : ""}`,
      disabled: item.enabled === false,
    }))
  }
  const type = inputType.replace("template-", "")
  return (props.templates || [])
    .filter((item) => (item.type || "") === type)
    .map((item) => h(resolve("el-option"), {
      key: item.id,
      value: item.id,
      label: item.name || "未命名模板",
    }))
}

function defaultLinkConfig() {
  return {
    source_message_link: "target_link",
    missing_mapping: "downgrade",
    target_channel_link: "keep",
    external_channel_link: "downgrade",
    username_link: "downgrade",
    bot_link: "downgrade",
    external_url: "downgrade",
    invite_link: "downgrade",
    source_message_link_replacement: "",
    missing_mapping_replacement: "",
    target_channel_link_replacement: "",
    external_channel_link_replacement: "",
    username_link_replacement: "",
    bot_link_replacement: "",
    external_url_replacement: "",
    invite_link_replacement: "",
  }
}

function defaultContactConfig() {
  return {
    remove_phone: true,
    remove_links: true,
    remove_usernames: true,
    remove_keywords: true,
    keywords_text: [
      "微信",
      "微信号",
      "微",
      "vx",
      "v信",
      "wechat",
      "we chat",
      "wx",
      "电话",
      "手机",
      "联系",
      "联系方式",
      "客服",
      "tg",
      "telegram",
      "纸飞机",
      "飞机",
    ].join("\n"),
    custom_regex_text: "",
  }
}

function renderContactConfig(form) {
  return h("div", { class: "link-config-list" }, [
    h("div", { class: "switch-grid" }, [
      contactSwitch(form, "remove_phone", "删除手机号"),
      contactSwitch(form, "remove_links", "删除链接"),
      contactSwitch(form, "remove_usernames", "删除 @用户名"),
      contactSwitch(form, "remove_keywords", "删除命中关键词整行"),
    ]),
    h(resolve("el-input"), {
      modelValue: form.keywords_text || "",
      type: "textarea",
      rows: 6,
      placeholder: "一行一个关键词，例如：微信、vx、电话、客服",
      "onUpdate:modelValue": (value) => { form.keywords_text = value },
    }),
    h(resolve("el-input"), {
      modelValue: form.custom_regex_text || "",
      type: "textarea",
      rows: 4,
      placeholder: "一行一个正则，留空即可。高级用户使用",
      "onUpdate:modelValue": (value) => { form.custom_regex_text = value },
    }),
  ])
}

function contactSwitch(form, key, label) {
  if (form[key] === undefined) {
    form[key] = defaultContactConfig()[key]
  }
  return h("div", { class: "switch-row" }, [
    h("span", null, label),
    h(resolve("el-switch"), {
      modelValue: Boolean(form[key]),
      "onUpdate:modelValue": (value) => { form[key] = value },
    }),
  ])
}

function parseContactConfig(value) {
  try {
    const parsed = JSON.parse(value || "{}")
    return {
      ...defaultContactConfig(),
      remove_phone: Boolean(parsed.remove_phone ?? true),
      remove_links: Boolean(parsed.remove_links ?? true),
      remove_usernames: Boolean(parsed.remove_usernames ?? true),
      remove_keywords: Boolean(parsed.remove_keywords ?? true),
      keywords_text: Array.isArray(parsed.keywords) ? parsed.keywords.join("\n") : defaultContactConfig().keywords_text,
      custom_regex_text: Array.isArray(parsed.custom_regex) ? parsed.custom_regex.join("\n") : "",
    }
  } catch {
    return defaultContactConfig()
  }
}

function buildContactConfig(data) {
  return {
    remove_phone: Boolean(data.remove_phone ?? true),
    remove_links: Boolean(data.remove_links ?? true),
    remove_usernames: Boolean(data.remove_usernames ?? true),
    remove_keywords: Boolean(data.remove_keywords ?? true),
    keywords: splitNonEmptyLines(data.keywords_text),
    custom_regex: splitNonEmptyLines(data.custom_regex_text),
  }
}

function cleanupContactFields(data) {
  for (const key of ["remove_phone", "remove_links", "remove_usernames", "remove_keywords", "keywords_text", "custom_regex_text", "contact_config"]) {
    delete data[key]
  }
}

function splitNonEmptyLines(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function linkConfigFields() {
  return [
    { key: "source_message_link", label: "源频道内部消息链接" },
    { key: "missing_mapping", label: "找不到映射时" },
    { key: "target_channel_link", label: "目标频道链接" },
    { key: "external_channel_link", label: "外部频道链接" },
    { key: "username_link", label: "用户名链接" },
    { key: "bot_link", label: "Bot 链接" },
    { key: "external_url", label: "普通外部网址" },
    { key: "invite_link", label: "邀请链接" },
  ]
}

function linkActionOptions(key) {
  const options = [
    { label: "降级文本", value: "downgrade" },
    { label: "保留", value: "keep" },
    { label: "直接删除", value: "delete" },
    { label: "替换链接", value: "replace" },
  ]
  if (key === "source_message_link") {
    return [{ label: "目标链接", value: "target_link" }, ...options]
  }
  return options
}

function parseLinkConfig(value) {
  try {
    const parsed = JSON.parse(value || "{}")
    return {
      ...defaultLinkConfig(),
      ...(parsed || {}),
    }
  } catch {
    return defaultLinkConfig()
  }
}

function buildLinkConfig(data) {
  const config = {}
  for (const field of linkConfigFields()) {
    config[field.key] = data[field.key] || defaultLinkConfig()[field.key]
    config[`${field.key}_replacement`] = data[`${field.key}_replacement`] || ""
  }
  return config
}

function cleanupLinkFields(data) {
  for (const field of linkConfigFields()) {
    delete data[field.key]
    delete data[`${field.key}_replacement`]
  }
}

function richActions() {
  return [
    { label: "加粗", value: "<b>文字</b>" },
    { label: "斜体", value: "<i>文字</i>" },
    { label: "下划线", value: "<u>文字</u>" },
    { label: "删除线", value: "<s>文字</s>" },
    { label: "代码", value: "<code>代码</code>" },
    { label: "链接", value: '<a href="https://t.me/">链接</a>' },
  ]
}

function displayEditValue(value, input) {
  if (input !== "textarea") return value ?? ""
  if (Array.isArray(value)) return value.join("\n")
  if (typeof value === "string") {
    try {
      const parsed = JSON.parse(value)
      if (Array.isArray(parsed)) return parsed.join("\n")
    } catch {
      return value
    }
  }
  return value ?? ""
}

function sectionList(title, items, emptyTitle, render, search = null) {
  return h("section", { class: "section" }, [
    h("div", { class: "section-head" }, [h("div", { class: "section-title" }, title)]),
    search,
    items.length
      ? h("div", { class: "card-list" }, items.map((item) => render(item)))
      : h(EmptyState, { title: emptyTitle }),
  ])
}

function metric(label, value) {
  return h("div", { class: "metric-card" }, [
    h("div", { class: "metric-label" }, label),
    h("div", { class: "metric-value" }, compactText(value)),
  ])
}

function resolve(name) {
  return resolveComponent(name)
}
</script>








