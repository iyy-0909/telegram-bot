<template>
  <main v-if="authChecking" class="auth-resolving" aria-live="polite">
    <el-card class="auth-resolving__card">
      <el-icon class="auth-resolving__icon"><Loading /></el-icon>
      <strong>正在确认登录信息</strong>
      <span>请稍候，系统正在加载账号权限和使用期限。</span>
    </el-card>
  </main>

  <main
    v-else-if="isAuthenticated && !currentUser"
    class="auth-resolving auth-resolving--error"
    aria-live="polite"
  >
    <el-card class="auth-resolving__card">
      <el-alert
        type="error"
        show-icon
        :closable="false"
        title="暂时无法读取账号权限"
        :description="authError || '请检查网络后重试。你的登录状态仍已保留。'"
      />
      <div class="auth-resolving__actions">
        <request-button type="primary" @click="retryCurrentUser">重新加载</request-button>
        <request-button :loading="loggingOut" @click="handleLogout">退出登录</request-button>
      </div>
    </el-card>
  </main>

  <LoginPanel
    v-else-if="!isAuthenticated"
    :initial-error="authError"
    :request-actions="{ 'login': handleLogin }"
  />

  <div v-else>
    <MainLayout
      :status="status.status"
      :active-menu="activeMenu"
      :allowed-menus="availableMenus"
      :current-user="currentUser"
      :logging-out="loggingOut"
      :request-actions="{ 'change-menu': handleMenuChange, 'logout': handleLogout }"

    >
    <el-alert
      v-if="menuLoadError"
      type="error"
      show-icon
      :closable="false"
      title="当前页面加载失败"
      class="menu-load-error"
    >
      <div class="menu-load-error__content">
        <span>{{ menuLoadError }}</span>
        <request-button link type="primary" :loading="menuRetrying" @click="retryActiveMenu">
          重新加载
        </request-button>
      </div>
    </el-alert>

    <div v-if="activeMenu === 'home'">
      <RuntimeDashboard
        :dashboard="runtimeDashboard"
        :loading="pageLoading.runtime"
        :request-actions="{ 'refresh': loadRuntimeDashboard }"
      />
    </div>

    <div v-if="activeMenu === 'rules'">
      <!-- <StatusCards :status="status" /> -->

      <ListenerTaskTable
        :tasks="listenerTasks"
        :events="listenerTaskLogs"
        :loading="pageLoading.listenerTasks"
        :logs-loading="pageLoading.listenerLogs"
        :catchup-checking-id="catchupCheckingId"
        :catchup-busy="catchupVisible || catchupCheckingId !== null"
        :request-actions="{ 'add': openAddListenerTaskDialog, 'edit': openEditListenerTaskDialog, 'delete': deleteListenerTaskHandler, 'start': startListenerTaskHandler, 'stop': stopListenerTaskHandler, 'catchup': checkListenerCatchupHandlerV2, 'refresh-logs': loadListenerTaskLogs }"






      />
    </div>

    <div v-if="activeMenu === 'settings'">
      <SystemSettingsWorkspace
        :settings="sendSettings"
        :templates="contentTemplates"
        :loading="pageLoading.templates"
        :settings-saving="settingsSaving"
        :toggling-id="templateTogglingId"
        :request-actions="{ 'save-settings': saveSendSettings, 'add': openAddContentTemplateDialog, 'edit': openEditContentTemplateDialog, 'delete': deleteContentTemplateHandler, 'toggle': toggleContentTemplateHandler }"




      />
    </div>

    <div v-if="activeMenu === 'ai-settings'">
      <AiConfigWorkspace
        :settings="aiSettings"
        :settings-saving="aiSettingsSaving"
        :settings-loading="pageLoading.aiSettings"
        :prompts="aiPrompts"
        :loading="pageLoading.aiPrompts"
        :deleting-id="aiPromptDeletingId"
        :defaulting-id="aiPromptDefaultingId"
        :request-actions="{ 'refresh': refreshAiConfig, 'save-settings': saveAiSettings, 'add-prompt': openAddAiPromptDialog, 'edit-prompt': openEditAiPromptDialog, 'delete-prompt': deleteAiPromptHandler, 'set-default-prompt': setDefaultAiPromptHandler }"





      />
    </div>

    <div v-if="activeMenu === 'guide'">
      <el-alert
        v-if="accessNotice"
        type="warning"
        show-icon
        :closable="false"
        :title="accessNotice"
        class="access-notice"
      />
      <UserGuide :request-actions="{ 'navigate': handleMenuChange }" />
    </div>

    <div v-if="activeMenu === 'user-access'">
      <UserAccessManagement />
    </div>

    <div v-if="activeMenu === 'accounts'">
      <AccountTable
        :accounts="accounts"
        :loading="pageLoading.accounts"
        :default-setting-id="defaultAccountSettingId"
        :request-actions="{ 'login': openAccountLoginDialog, 'relogin': openAccountReloginDialog, 'edit': openEditAccountDialog, 'delete': deleteAccount, 'toggle': saveAccount, 'set-default': setDefaultAccount }"





      />
    </div>

    <div v-if="activeMenu === 'notifications'">
      <NotificationSettings />
    </div>

    <div v-if="activeMenu === 'alerts'">
      <ControlAlertCenter :request-actions="{ 'open-task': openTaskFromAlert }" />
    </div>

    <div v-if="activeMenu === 'bots'" class="bot-page">
      <BotTable
        :bots="bots"
        :loading="pageLoading.bots"
        :request-actions="{ 'add': openAddBotDialog, 'edit': openEditBotDialog, 'delete': deleteBotHandler, 'toggle': saveBotStatus, 'test': testBotHandler }"




      />

      <!-- 目标频道绑定已废弃：现在在克隆/监听任务中直接选择分发 Bot。
      <BotBindingTable
        :bindings="botBindings"
        :bots="bots"
        @add="openAddBotBindingDialog"
        @edit="openEditBotBindingDialog"
        @delete="deleteBotBindingHandler"
        @toggle="saveBotBindingStatus"
      />
      -->
    </div>

    <div v-if="activeMenu === 'support'">
      <SupportPanel :bots="bots" />
    </div>

    <div v-if="activeMenu === 'my-channels'">
      <MyChannelTable
        :bots="bots"
        :accounts="accounts"
        :accounts-loading="pageLoading.accounts"
        :active-tab="activeChannelTab"
        @update:active-tab="setActiveChannelTab"
      />
    </div>

    <div v-if="activeMenu === 'bulk-replace'">
      <BulkReplacePanel />
    </div>

    <div v-if="activeMenu === 'clone'">
      <CloneTaskTable
        :tasks="cloneTasks"
        :task-logs="cloneTaskLogs"
        :loading="pageLoading.cloneTasks"
        :logs-loading="pageLoading.cloneLogs"
        :request-actions="{ 'add': openAddCloneTaskDialog, 'edit': openEditCloneTaskDialog, 'delete': removeCloneTaskHandler, 'start': startCloneTaskHandler, 'pause': pauseCloneTaskHandler, 'resume': resumeCloneTaskHandler, 'stop': handleStopCloneTask, 'toggle-listener': handleToggleCloneListener, 'refresh-logs': loadCloneTaskLogs }"








      />
    </div>

    <ListenerTaskDialog
      :visible="listenerTaskDialogVisible"
      :form="currentListenerTask"
      :is-edit="isListenerTaskEdit"
      :existing-tasks="listenerTasks"
      :accounts="accounts"
      :bots="bots"
      :templates="contentTemplates"
      :ai-prompts="aiPrompts"
      :content-processing-enabled="contentProcessingEnabled"
      :channel-options-enabled="hasFeature('channels')"
      @update:visible="listenerTaskDialogVisible = $event"
      :request-actions="{ 'submit': submitListenerTask }"
    />

    <AccountDialog
      :visible="accountDialogVisible"
      :form="currentAccount"
      :is-edit="isAccountEdit"
      :saving="accountSaving"
      @update:visible="accountDialogVisible = $event"
      :request-actions="{ 'submit': submitAccount }"
    />

    <AccountLoginDialog
      :visible="accountLoginDialogVisible"
      :account="loginAccountTarget"
      @update:visible="accountLoginDialogVisible = $event"
      :request-actions="{ 'success': handleAccountLoginSuccess }"
    />

    <BotDialog
      :visible="botDialogVisible"
      :form="currentBot"
      :is-edit="isBotEdit"
      :saving="botSaving"
      @update:visible="botDialogVisible = $event"
      :request-actions="{ 'submit': submitBot }"
    />

    <BotBindingDialog
      :visible="botBindingDialogVisible"
      :form="currentBotBinding"
      :bots="bots"
      :is-edit="isBotBindingEdit"
      @update:visible="botBindingDialogVisible = $event"
      :request-actions="{ 'submit': submitBotBinding }"
    />

    <ContentTemplateDialog
      :visible="contentTemplateDialogVisible"
      :form="currentContentTemplate"
      :is-edit="isContentTemplateEdit"
      @update:visible="contentTemplateDialogVisible = $event"
      :request-actions="{ 'submit': submitContentTemplate }"
    />
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

    </MainLayout>

    <CloneTaskDialog
      :visible="cloneTaskDialogVisible"
      :form="currentCloneTask"
      :is-edit="isCloneTaskEdit"
      :bots="bots"
      :accounts="accounts"
      :templates="contentTemplates"
      :ai-prompts="aiPrompts"
      :content-processing-enabled="contentProcessingEnabled"
      :channel-options-enabled="hasFeature('channels')"
      @update:visible="cloneTaskDialogVisible = $event"
      :request-actions="{ 'submit': submitCloneTask }"
    />

    <AiPromptDialog
      :visible="aiPromptDialogVisible"
      :prompt="currentAiPrompt"
      :is-edit="isAiPromptEdit"
      :saving="aiPromptSaving"
      @update:visible="aiPromptDialogVisible = $event"
      :request-actions="{ 'submit': submitAiPrompt }"
    />
  </div>
</template>

<script setup>
import { ElMessage, ElMessageBox } from "element-plus"
import { Loading } from "@element-plus/icons-vue"
import { computed, ref, reactive, onMounted, onUnmounted } from "vue"

import MainLayout from "./layouts/MainLayout.vue"
import StatusCards from "./components/StatusCards.vue"
import ListenerTaskTable from "./components/ListenerTaskTable.vue"
import ListenerTaskDialog from "./components/ListenerTaskDialog.vue"
import AiConfigWorkspace from "./components/AiConfigWorkspace.vue"
import AiPromptDialog from "./components/AiPromptDialog.vue"
import SystemSettingsWorkspace from "./components/SystemSettingsWorkspace.vue"
import UserGuide from "./components/UserGuide.vue"
import LoginPanel from "./components/LoginPanel.vue"
import UserAccessManagement from "./components/UserAccessManagement.vue"
import ContentTemplateDialog from "./components/ContentTemplateDialog.vue"
import { knownContentRuleTypes } from "./config/contentRuleSections"
import {
  ACCESS_RESTRICTED_EVENT,
  AUTH_SESSION_CHANGED_EVENT,
  getAuthGeneration,
  getAuthToken,
  isAuthGenerationCurrent,
  isCanceledAuthRequest,
  replaceAuthToken,
} from "./authSession"

import AccountTable from "./components/AccountTable.vue"
import AccountDialog from "./components/AccountDialog.vue"
import AccountLoginDialog from "./components/AccountLoginDialog.vue"
import NotificationSettings from "./components/NotificationSettings.vue"
import ControlAlertCenter from "./components/ControlAlertCenter.vue"

import BotTable from "./components/BotTable.vue"
import BotDialog from "./components/BotDialog.vue"
import BotBindingTable from "./components/BotBindingTable.vue"
import BotBindingDialog from "./components/BotBindingDialog.vue"
import SupportPanel from "./components/SupportPanel.vue"
import MyChannelTable from "./components/MyChannelTable.vue"
import BulkReplacePanel from "./components/BulkReplacePanel.vue"
import RuntimeDashboard from "./components/RuntimeDashboard.vue"

import CloneTaskTable from "./components/CloneTaskTable.vue"
import CloneTaskDialog from "./components/CloneTaskDialog.vue"

import {
  getCloneTasks,
  getCloneSendEvents,
  createCloneTask,
  updateCloneTask,
  deleteCloneTask,
  startCloneTask,
  pauseCloneTask,
  resumeCloneTask,
} from "./api/cloneTasks"

import {
  getStatus,
  getRules,
  createRule,
  updateRule,
  removeRule,
  cloneRule,
  stopCloneTask,
} from "./api/rules"

import {
  getAccounts,
  getAccountOptions,
  updateAccount,
  removeAccount,
} from "./api/accounts"

import {
  getCurrentUser,
  logoutUser,
} from "./api/auth"

import {
  getBots,
  getBotOptions,
  createBot,
  updateBot,
  deleteBot,
  getBotBindings,
  createBotBinding,
  updateBotBinding,
  deleteBotBinding,
  testBot,
  sendBotTest
} from "./api/bots"

import {
  getAiSettings,
  getSendSettings,
  updateAiSettings,
  updateSendSettings,
} from "./api/settings"

import {
  getListenerTasks,
  checkListenerSourceSubscription,
  createListenerTask,
  updateListenerTask,
  deleteListenerTask,
  startListenerTask,
  stopListenerTask,
  getListenerSendEvents,
  checkListenerCatchup,
  catchupLatestListenerMessage,
} from "./api/listenerTasks"

import {
  getContentTemplates,
  createContentTemplateRule,
  updateContentTemplateRule,
  deleteContentTemplateRule,
} from "./api/contentTemplates"

import {
  getRuntimeDashboard,
} from "./api/runtime"

import {
  getAiPrompts,
  createAiPrompt,
  updateAiPrompt,
  setDefaultAiPrompt,
  deleteAiPrompt,
} from "./api/aiPrompts"



const initialToken = getAuthToken()
const status = ref({})
const isAuthenticated = ref(Boolean(initialToken))
const authChecking = ref(Boolean(initialToken))
const authError = ref("")
const currentUser = ref(null)
const loggingOut = ref(false)
const rules = ref([])
const listenerTasks = ref([])
const listenerTaskLogs = ref([])
const accounts = ref([])
const bots = ref([])
const botBindings = ref([])
const cloneTasks = ref([])
const cloneTaskLogs = ref([])
const contentTemplates = ref([])
const aiPrompts = ref([])
const runtimeDashboard = ref({})
const sendSettings = ref({
  global_send_delay: 3,
  send_retry_count: 2,
  send_retry_delay: 5,
})
const aiSettings = ref({ providers: {}, default_provider: "grok" })
const menuLoadError = ref("")
const menuRetrying = ref(false)
const pageLoading = reactive({
  listenerTasks: false,
  listenerLogs: false,
  accounts: false,
  bots: false,
  cloneTasks: false,
  cloneLogs: false,
  templates: false,
  aiSettings: false,
  aiPrompts: false,
  runtime: false,
})
const pageLoadingOwners = new Map()
let authCheckOwner = null
const defaultAccountSettingId = ref(null)

const MENU_STORAGE_KEY = "clonebot_active_menu"
const CHANNEL_TAB_STORAGE_KEY = "clonebot_channel_tab"
const CLONE_TASK_LOG_STORAGE_KEY = "clonebot_clone_task_logs"
const LISTENER_TASK_LOG_STORAGE_KEY = "clonebot_listener_task_logs"
const CLONE_TASK_LOG_LIMIT = 50
const LISTENER_TASK_LOG_LIMIT = 50
const AUTO_REFRESH_INTERVAL = 30 * 60 * 1000
const SEND_LOG_REFRESH_INTERVAL = 10 * 1000
const SECONDS_PER_MINUTE = 60

function purgeLegacyTaskLogCache() {
  window.localStorage.removeItem(CLONE_TASK_LOG_STORAGE_KEY)
  window.localStorage.removeItem(LISTENER_TASK_LOG_STORAGE_KEY)
}

function clearSessionData() {
  menuLoadSequence += 1
  pageLoadingOwners.clear()
  authCheckOwner = null
  status.value = {}
  rules.value = []
  listenerTasks.value = []
  listenerTaskLogs.value = []
  accounts.value = []
  bots.value = []
  botBindings.value = []
  cloneTasks.value = []
  cloneTaskLogs.value = []
  contentTemplates.value = []
  aiPrompts.value = []
  runtimeDashboard.value = {}
  sendSettings.value = {
    global_send_delay: 3,
    send_retry_count: 2,
    send_retry_delay: 5,
  }
  aiSettings.value = { providers: {}, default_provider: "grok" }
  menuLoadError.value = ""
  menuRetryOwner = null
  menuRetrying.value = false
  Object.keys(pageLoading).forEach((key) => { pageLoading[key] = false })
  defaultAccountSettingId.value = null
  accountSaving.value = false
  botSaving.value = false
  settingsSaving.value = false
  aiSettingsSaving.value = false
  aiPromptSaving.value = false
  aiPromptDeletingId.value = null
  aiPromptDefaultingId.value = null
  templateTogglingId.value = null

  dialogVisible.value = false
  listenerTaskDialogVisible.value = false
  accountDialogVisible.value = false
  accountLoginDialogVisible.value = false
  loginAccountTarget.value = null
  botDialogVisible.value = false
  botBindingDialogVisible.value = false
  cloneTaskDialogVisible.value = false
  contentTemplateDialogVisible.value = false
  aiPromptDialogVisible.value = false

  resetCurrentRule()
  resetCurrentListenerTask()
  resetCurrentAccount()
  resetCurrentBot()
  resetCurrentBotBinding()
  resetCurrentCloneTask()
  resetCurrentContentTemplate()
  resetCurrentAiPrompt()
  purgeLegacyTaskLogCache()
}

purgeLegacyTaskLogCache()

const MENU_FEATURES = {
  home: "dashboard",
  rules: "listener_tasks",
  clone: "clone_tasks",
  bots: "bots",
  "my-channels": "channels",
  "bulk-replace": "bulk_replace",
  support: "support",
  accounts: "accounts",
  notifications: "notifications",
  alerts: "alerts",
  "ai-settings": "ai_settings",
  settings: "system_settings",
  guide: "guide",
  "user-access": "user_management",
}
const FEATURE_DEPENDENCIES = {
  listener_tasks: ["accounts", "bots"],
  clone_tasks: ["accounts", "bots"],
  notifications: ["accounts"],
}
const VALID_MENUS = ["home", "rules", "clone", "bots", "my-channels", "bulk-replace", "support", "accounts", "notifications", "alerts", "ai-settings", "settings", "guide", "user-access"]
const VALID_CHANNEL_TABS = ["targets", "sources", "collections", "search-bots"]

function hasUsableAccess(user = currentUser.value) {
  if (user?.role === "admin") return true
  if (user?.available === false) return false
  return !["disabled", "expired", "inactive", "pending", "waiting"].includes(String(user?.access_state || "active").toLowerCase())
}

function hasFeature(featureKey) {
  if (featureKey === "guide") return true
  if (featureKey === "user_management") return currentUser.value?.role === "admin"
  if (currentUser.value?.role === "admin") return true
  if (!hasUsableAccess()) return false
  const granted = new Set(Array.isArray(currentUser.value?.feature_keys) ? currentUser.value.feature_keys : [])
  if (!granted.has(featureKey)) return false
  return (FEATURE_DEPENDENCIES[featureKey] || []).every((dependencyKey) => granted.has(dependencyKey))
}

function canOpenMenu(menu) {
  return VALID_MENUS.includes(menu) && hasFeature(MENU_FEATURES[menu])
}

const availableMenus = computed(() => VALID_MENUS.filter(canOpenMenu))
const contentProcessingEnabled = computed(() => (
  currentUser.value?.role === "admin" || currentUser.value?.plan_tier === "paid"
))
const defaultAiProvider = computed(() => (
  aiSettings.value?.default_provider === "deepseek" ? "deepseek" : "grok"
))
const availableBusinessMenus = computed(() => availableMenus.value.filter((menu) => !["guide", "user-access"].includes(menu)))
const accessNotice = computed(() => {
  if (currentUser.value?.role === "admin") return ""
  const state = String(currentUser.value?.access_state || "active").toLowerCase()
  if (state === "disabled") return "当前账号已停用，仅可查看使用教程，请联系管理员恢复使用。"
  if (state === "expired") return "当前账号已超过使用期限，仅可查看使用教程，请联系管理员延长使用时间。"
  if (["pending", "waiting"].includes(state)) return "当前账号尚待管理员授权，仅可查看使用教程，请联系管理员分配功能和使用期限。"
  if (!availableBusinessMenus.value.length) return "当前账号尚未开通业务功能，仅可查看使用教程，请联系管理员分配功能和使用期限。"
  return ""
})

function getSavedActiveMenu() {
  const queryMenu = new URLSearchParams(window.location.search).get("menu")
  if (VALID_MENUS.includes(queryMenu)) {
    return queryMenu
  }

  const saved = window.localStorage.getItem(MENU_STORAGE_KEY)

  if (VALID_MENUS.includes(saved)) {
    return saved
  }

  return "home"
}

const activeMenu = ref(getSavedActiveMenu())
const savedChannelTab = window.localStorage.getItem(CHANNEL_TAB_STORAGE_KEY)
const activeChannelTab = ref(VALID_CHANNEL_TABS.includes(savedChannelTab) ? savedChannelTab : "targets")

function setActiveChannelTab(tab) {
  const nextTab = VALID_CHANNEL_TABS.includes(tab) ? tab : "targets"
  activeChannelTab.value = nextTab
  window.localStorage.setItem(CHANNEL_TAB_STORAGE_KEY, nextTab)
}

const dialogVisible = ref(false)
const isEdit = ref(false)
const listenerTaskDialogVisible = ref(false)
const isListenerTaskEdit = ref(false)

const accountDialogVisible = ref(false)
const isAccountEdit = ref(false)
const accountSaving = ref(false)
const accountLoginDialogVisible = ref(false)
const loginAccountTarget = ref(null)

const botDialogVisible = ref(false)
const isBotEdit = ref(false)
const botSaving = ref(false)

const botBindingDialogVisible = ref(false)
const isBotBindingEdit = ref(false)

const cloneTaskDialogVisible = ref(false)
const isCloneTaskEdit = ref(false)

const contentTemplateDialogVisible = ref(false)
const isContentTemplateEdit = ref(false)
const settingsSaving = ref(false)
const aiSettingsSaving = ref(false)
const aiPromptDialogVisible = ref(false)
const isAiPromptEdit = ref(false)
const aiPromptSaving = ref(false)
const aiPromptDeletingId = ref(null)
const aiPromptDefaultingId = ref(null)
const templateTogglingId = ref(null)

let cloneRefreshTimer = null
let cloneLogRefreshTimer = null


const currentRule = reactive({
  id: null,
  source: "",
  target: "",
  enabled: true,
  blocked_keywords: "[]",
  replace_words: "{}",
  footer: "",
  remove_contact_lines: true,
  clone_task_id: null,
})

const currentListenerTask = reactive({
  id: null,
  name: "",
  source_channel: "",
  source_channels: [],
  target_channels: "[]",
  account_id: 1,
  bot_id: null,
  enabled: true,
  status: "running",
  blocked_keywords: "[]",
  listen_required_keywords: "[]",
  replace_words: "{}",
  footer: "",
  remove_contact_lines: true,
  filter_qr_code: true,
  use_random_head: false,
  use_random_body: false,
  use_random_footer: false,
  footer_leading_blank_line: true,
  selected_head_template_group_id: null,
  selected_body_template_group_id: null,
  selected_footer_template_group_id: null,
  selected_head_template_id: null,
  selected_body_template_id: null,
  selected_footer_template_id: null,
  selected_filter_template_group_id: null,
  selected_link_template_group_id: null,
  selected_contact_template_group_id: null,
  album_wait_seconds: 3,
  ai_rewrite_enabled: false,
  ai_rewrite_provider: "grok",
  ai_rewrite_model: "",
  ai_rewrite_prompt: "",
  ai_prompt_template_id: null,
  ai_rewrite_max_chars: 800,
  ai_rewrite_ratio: 70,
  ai_rewrite_failure_mode: "fallback",
})


const currentAccount = reactive({
  id: null,
  name: "",
  username: "",
  session_path: "",
  has_session_path: false,
  proxy: "",
  has_proxy: false,
  clear_proxy: false,
  enabled: true,
  is_default: false,
  remark: "",
  greeting_enabled: false,
  greeting_message: "",
  away_enabled: false,
  away_message: "",
  business_start_time: "09:00",
  business_end_time: "18:00",
  away_repeat_hours: 12,
})


const currentBot = reactive({
  id: null,
  name: "",
  token: "",
  enabled: true,
  remark: "",
  last_error: "",
})


const currentBotBinding = reactive({
  id: null,
  target_channel: "",
  bot_id: null,
  enabled: true,
  remark: "",
})


const currentCloneTask = reactive({
  id: null,
  name: "",
  source_channel: "",
  target_channels: "[]",
  account_id: null,
  bot_id: null,
  start_message_url: "",
  end_message_url: "",
  single_delay: 3,
  target_delay: 2,
  blocked_keywords: "[]",
  replace_words: "{}",
  footer: "",
  remove_contact_lines: true,
  filter_qr_code: true,
  enable_listener: false,
  use_random_head: false,
  use_random_body: false,
  use_random_footer: false,
  footer_leading_blank_line: true,
  selected_head_template_group_id: null,
  selected_body_template_group_id: null,
  selected_footer_template_group_id: null,
  selected_head_template_id: null,
  selected_body_template_id: null,
  selected_footer_template_id: null,
  selected_filter_template_group_id: null,
  selected_link_template_group_id: null,
  selected_contact_template_group_id: null,
  enabled: true,
  status: "idle",
  last_message_id: 0,
  ai_rewrite_enabled: false,
  ai_rewrite_provider: "grok",
  ai_rewrite_model: "",
  ai_rewrite_prompt: "",
  ai_prompt_template_id: null,
  ai_rewrite_max_chars: 800,
  ai_rewrite_ratio: 70,
  ai_rewrite_failure_mode: "fallback",
})


const currentContentTemplate = reactive({
  id: null,
  parent_id: null,
  name: "",
  type: "footer",
  content: "",
  enabled: true,
  weight: 1,
  items: [],
})

const currentAiPrompt = reactive({
  id: null,
  name: "",
  content: "",
  enabled: true,
  is_default: false,
})


async function loadStatus() {
  const generation = getAuthGeneration()
  const res = await getStatus()
  if (!isAuthGenerationCurrent(generation)) return false
  status.value = res.data
  return true
}

function beginPageLoad(key) {
  const load = {
    generation: getAuthGeneration(),
    owner: Symbol(`page-loading-${key}`),
  }
  pageLoadingOwners.set(key, load.owner)
  pageLoading[key] = true
  return load
}

function isPageLoadCurrent(load) {
  return isAuthGenerationCurrent(load.generation)
}

function finishPageLoad(key, load) {
  if (pageLoadingOwners.get(key) !== load.owner || !isPageLoadCurrent(load)) return
  pageLoadingOwners.delete(key)
  pageLoading[key] = false
}


async function loadRules() {
  const generation = getAuthGeneration()
  const res = await getRules()
  if (!isAuthGenerationCurrent(generation)) return false
  rules.value = res.data
  return true
}

async function loadListenerTasks() {
  const load = beginPageLoad("listenerTasks")
  try {
    const res = await getListenerTasks()
    if (!isPageLoadCurrent(load)) return false
    listenerTasks.value = res.data || []
    return true
  } finally {
    finishPageLoad("listenerTasks", load)
  }
}


async function loadListenerTaskLogs() {
  const load = beginPageLoad("listenerLogs")
  try {
    const res = await getListenerSendEvents(LISTENER_TASK_LOG_LIMIT)
    if (!isPageLoadCurrent(load)) return false
    listenerTaskLogs.value = res.data.events || []
    return true
  } catch (e) {
    if (isCanceledAuthRequest(e) || !isPageLoadCurrent(load)) return false
    listenerTaskLogs.value = []
    return false
  } finally {
    finishPageLoad("listenerLogs", load)
  }
}


async function loadAccounts() {
  const load = beginPageLoad("accounts")
  try {
    const res = hasFeature("accounts")
      ? await getAccounts()
      : await getAccountOptions()
    if (!isPageLoadCurrent(load)) return false
    const data = res.data
    accounts.value = Array.isArray(data)
      ? data
      : Array.isArray(data?.items)
        ? data.items
        : []
    return true
  } finally {
    finishPageLoad("accounts", load)
  }
}


async function loadBots() {
  const load = beginPageLoad("bots")
  try {
    const res = hasFeature("bots")
      ? await getBots()
      : await getBotOptions()
    if (!isPageLoadCurrent(load)) return false
    bots.value = res.data
    return true
  } finally {
    finishPageLoad("bots", load)
  }
}


async function loadBotBindings() {
  const generation = getAuthGeneration()
  const res = await getBotBindings()
  if (!isAuthGenerationCurrent(generation)) return false
  botBindings.value = res.data
  return true
}


async function loadBotPage() {
  const generation = getAuthGeneration()
  const botsLoaded = await loadBots()
  if (botsLoaded === false || !isAuthGenerationCurrent(generation)) return false
  return loadBotBindings()
}


async function loadCloneTasks() {
  const load = beginPageLoad("cloneTasks")
  try {
    const res = await getCloneTasks()
    if (!isPageLoadCurrent(load)) return false
    const tasks = res.data || []

    cloneTasks.value = tasks
    return true
  } finally {
    finishPageLoad("cloneTasks", load)
  }
}


function scheduleCloneTaskRefresh() {
  const generation = getAuthGeneration()
  ;[1000, 3000, 6000].forEach((delay) => {
    window.setTimeout(async () => {
      if (!isAuthGenerationCurrent(generation)) return
      try {
        await loadCloneTasks()
      } catch {}
    }, delay)
  })
}


async function loadCloneTaskLogs() {
  const load = beginPageLoad("cloneLogs")
  try {
    const res = await getCloneSendEvents(CLONE_TASK_LOG_LIMIT)
    if (!isPageLoadCurrent(load)) return false
    const events = (res.data.events || []).map(mapCloneSendEvent)

    cloneTaskLogs.value = events
    return true
  } catch (e) {
    if (isCanceledAuthRequest(e) || !isPageLoadCurrent(load)) return false
    cloneTaskLogs.value = []
    return false
  } finally {
    finishPageLoad("cloneLogs", load)
  }
}


function mapCloneSendEvent(event) {
  return {
    id: [
      event.time,
      event.task_id,
      event.target,
      event.source_message_id,
      event.target_message_url,
    ].join("_"),
    time: event.time || "",
    task_id: event.task_id ?? "",
    task_name: event.target || "",
    action: "目标发送成功",
    status: event.status || event.event_type || "success",
    result: event.status || event.event_type || "success",
    message: event.message || `Bot API 已成功发送到目标频道 ${event.target || ""}`,
    error: event.error || "",
    target: event.target || "",
    source_message_id: event.source_message_id ?? "",
    grouped_id: event.grouped_id ?? null,
    source_message_url: event.source_message_url || "",
    target_message_url: event.target_message_url || "",
  }
}


async function loadSendSettings() {
  const generation = getAuthGeneration()
  const res = await getSendSettings()
  if (!isAuthGenerationCurrent(generation)) return false
  sendSettings.value = res.data
  return true
}

async function loadAiSettings() {
  const load = beginPageLoad("aiSettings")
  try {
    const res = await getAiSettings()
    if (!isPageLoadCurrent(load)) return false
    aiSettings.value = res.data || { providers: {}, default_provider: "grok" }
    return true
  } finally {
    finishPageLoad("aiSettings", load)
  }
}

async function loadAiPrompts() {
  const load = beginPageLoad("aiPrompts")
  try {
    const res = await getAiPrompts()
    if (!isPageLoadCurrent(load)) return false
    aiPrompts.value = res.data || []
    return true
  } finally {
    finishPageLoad("aiPrompts", load)
  }
}

async function refreshAiConfig() {
  const generation = getAuthGeneration()
  await Promise.all([loadAiSettings(), loadAiPrompts()])
  return isAuthGenerationCurrent(generation)
}


async function loadContentTemplates() {
  const load = beginPageLoad("templates")
  try {
    const res = await getContentTemplates()
    if (!isPageLoadCurrent(load)) return false
    contentTemplates.value = res.data || []
    return true
  } finally {
    finishPageLoad("templates", load)
  }
}


async function loadRuntimeDashboard() {
  const load = beginPageLoad("runtime")
  try {
    const res = await getRuntimeDashboard()
    if (!isPageLoadCurrent(load)) return false
    runtimeDashboard.value = res.data || {}
    return true
  } finally {
    finishPageLoad("runtime", load)
  }
}


let menuLoadSequence = 0
let menuRetryOwner = null

async function loadMenuData(menu, generation) {
  const isCurrent = () => isAuthGenerationCurrent(generation)
  if (!isCurrent()) return false

  if (menu === "home") {
    await Promise.all([loadStatus(), loadRuntimeDashboard()])
    return isCurrent()
  }

  const statusLoad = hasFeature("dashboard")
    ? loadStatus().then(() => null).catch((error) => error)
    : Promise.resolve(null)

  if (menu === "rules") {
    await loadAccounts()
    if (!isCurrent()) return false
    await loadBots()
    if (!isCurrent()) return false
    if (contentProcessingEnabled.value) {
      await loadContentTemplates()
      if (!isCurrent()) return false
      await loadAiPrompts()
      if (!isCurrent()) return false
    }
    await loadListenerTasks()
    if (!isCurrent()) return false
    await loadListenerTaskLogs()
  }

  if (menu === "accounts") {
    await loadAccounts()
  }

  if (menu === "bots") {
    await loadBotPage()
  }

  if (menu === "support") {
    await loadBots()
  }

  if (menu === "my-channels") {
    await Promise.all([loadBots(), loadAccounts()])
  }

  if (menu === "clone") {
    await Promise.all([loadBots(), loadAccounts()])
    if (!isCurrent()) return false
    await loadCloneTasks()
    if (!isCurrent()) return false
    await loadCloneTaskLogs()
    if (!isCurrent()) return false
    if (contentProcessingEnabled.value) {
      await loadContentTemplates()
      if (!isCurrent()) return false
      await loadAiPrompts()
    }
  }

  if (menu === "settings") {
    await loadSendSettings()
    if (!isCurrent()) return false
    await loadContentTemplates()
  }

  if (menu === "ai-settings") {
    await refreshAiConfig()
  }

  const statusError = await statusLoad
  if (!isCurrent()) return false
  if (statusError) throw statusError
  return true
}

async function handleMenuChange(menu, options = {}) {
  const generation = getAuthGeneration()
  if (!canOpenMenu(menu)) {
    if (!options.silent && currentUser.value && VALID_MENUS.includes(menu)) {
      ElMessage.warning("当前账号未开通该功能，请联系管理员授权")
    }
    menu = availableMenus.value.includes("home")
      ? "home"
      : availableBusinessMenus.value[0] || "guide"
  }

  activeMenu.value = menu
  window.localStorage.setItem(MENU_STORAGE_KEY, menu)
  const requestId = ++menuLoadSequence
  if (!options.preserveError) menuLoadError.value = ""

  try {
    const loaded = await loadMenuData(menu, generation)
    if (!loaded || !isAuthGenerationCurrent(generation)) return false
    if (requestId === menuLoadSequence && activeMenu.value === menu) {
      menuLoadError.value = ""
    }
    return true
  } catch (error) {
    if (isCanceledAuthRequest(error) || !isAuthGenerationCurrent(generation)) return false
    const code = error?.response?.data?.code
    const accessEventWillRecover = ["ACCESS_PENDING", "ACCESS_EXPIRED", "FEATURE_FORBIDDEN"].includes(code)
    if (requestId === menuLoadSequence && activeMenu.value === menu && !accessEventWillRecover) {
      menuLoadError.value = authErrorText(error, "当前页面加载失败，请检查网络后重试")
    }
    return false
  }
}

async function retryActiveMenu() {
  if (menuRetrying.value) return
  const generation = getAuthGeneration()
  const owner = Symbol("menu-retry")
  menuRetryOwner = owner
  menuRetrying.value = true
  try {
    await handleMenuChange(activeMenu.value, { silent: true, preserveError: true })
  } finally {
    if (menuRetryOwner === owner && isAuthGenerationCurrent(generation)) {
      menuRetryOwner = null
      menuRetrying.value = false
    }
  }
}


// =========================
// 内容模板规则
// =========================

function resetCurrentContentTemplate() {
  Object.assign(currentContentTemplate, {
    id: null,
    parent_id: null,
    name: "",
    type: "footer",
    content: "",
    enabled: true,
    weight: 1,
    items: [
      {
        id: null,
        content: "",
        enabled: true,
        weight: 1,
      },
    ],
  })
}


function openAddContentTemplateDialog(type = "footer") {
  resetCurrentContentTemplate()
  currentContentTemplate.type = type || "footer"
  isContentTemplateEdit.value = false
  contentTemplateDialogVisible.value = true
}

async function openTaskFromAlert({ alert, taskType }) {
  const taskId = Number(alert?.task_id)
  if (!taskId || !["listener", "clone"].includes(taskType)) {
    ElMessage.warning("该告警没有可打开的任务")
    return
  }

  const requiredFeature = taskType === "listener" ? "listener_tasks" : "clone_tasks"
  if (!hasFeature(requiredFeature)) {
    ElMessage.warning("当前账号未开通对应任务功能")
    return
  }

  if (taskType === "listener") {
    await handleMenuChange("rules")
    const task = listenerTasks.value.find((item) => Number(item.id) === taskId)
    if (!task) {
      ElMessage.warning(`监听任务 #${taskId} 已不存在或无权查看`)
      return
    }
    await openEditListenerTaskDialog(task)
    return
  }

  await handleMenuChange("clone")
  const task = cloneTasks.value.find((item) => Number(item.id) === taskId)
  if (!task) {
    ElMessage.warning(`克隆任务 #${taskId} 已不存在或无权查看`)
    return
  }
  await openEditCloneTaskDialog(task)
}


function openEditContentTemplateDialog(row) {
  Object.assign(currentContentTemplate, {
    id: row.id,
    name: row.name || "",
    type: row.type || "footer",
    enabled: row.enabled ?? true,
    items: row.items || [],
  })

  isContentTemplateEdit.value = true
  contentTemplateDialogVisible.value = true
}


async function submitContentTemplate(formData) {
  Object.assign(currentContentTemplate, formData)

  if (!knownContentRuleTypes().has(currentContentTemplate.type)) {
    ElMessage.error("模板类型不正确")
    return
  }

  const items = (currentContentTemplate.items || [])
    .map((item, index) => ({
      id: normalizeTemplateId(item.id),
      name: item.name || `内容 ${index + 1}`,
      content: item.content || "",
      enabled: item.enabled ?? true,
      weight: toPositiveNumber(item.weight, 1),
    }))
    .filter((item) => item.content.trim())

  if (!items.length) {
    ElMessage.error("至少需要填写一条规则内容")
    return
  }

  const payload = {
    name: currentContentTemplate.name || "",
    type: currentContentTemplate.type,
    enabled: currentContentTemplate.enabled,
    items,
  }

  if (isContentTemplateEdit.value) {
    await updateContentTemplateRule(currentContentTemplate.id, payload)
    ElMessage.success("内容模板规则已保存")
  } else {
    await createContentTemplateRule(payload)
    ElMessage.success("内容模板规则已添加")
  }

  contentTemplateDialogVisible.value = false
  await loadContentTemplates()
}


async function toggleContentTemplateHandler(row, value) {
  const generation = getAuthGeneration()
  templateTogglingId.value = row.id
  try {
    await updateContentTemplateRule(row.id, {
      enabled: value,
    })
    if (!isAuthGenerationCurrent(generation)) return

    ElMessage.success(value ? "配置已启用" : "配置已停用")
    await loadContentTemplates()
  } catch (error) {
    if (isCanceledAuthRequest(error) || !isAuthGenerationCurrent(generation)) return
    throw error
  } finally {
    if (isAuthGenerationCurrent(generation) && templateTogglingId.value === row.id) {
      templateTogglingId.value = null
    }
  }
}


async function deleteContentTemplateHandler(id) {
  await ElMessageBox.confirm(
    "确定删除这个内容模板规则？删除后会同时删除规则下的全部内容。",
    "确认删除",
    {
      type: "warning",
    },
  )

  await deleteContentTemplateRule(id)
  ElMessage.success("内容模板规则已删除")
  await loadContentTemplates()
}


// =========================
// 监听任务
// =========================

function resetCurrentListenerTask() {
  Object.assign(currentListenerTask, {
    id: null,
    name: "",
    source_channel: "",
    source_channels: [],
    target_channels: "[]",
    account_id: accounts.value[0]?.id || 1,
    bot_id: bots.value.find((bot) => bot.enabled)?.id || null,
    enabled: true,
    status: "running",
    blocked_keywords: "[]",
    listen_required_keywords: "[]",
    replace_words: "{}",
    footer: "",
    remove_contact_lines: true,
    filter_qr_code: true,
    use_random_head: false,
    use_random_body: false,
    use_random_footer: false,
    footer_leading_blank_line: true,
    selected_head_template_group_id: null,
    selected_body_template_group_id: null,
    selected_footer_template_group_id: null,
    selected_head_template_id: null,
    selected_body_template_id: null,
    selected_footer_template_id: null,
    selected_filter_template_group_id: null,
    selected_link_template_group_id: null,
    selected_contact_template_group_id: null,
    album_wait_seconds: 3,
    ai_rewrite_enabled: false,
    ai_rewrite_provider: defaultAiProvider.value,
    ai_rewrite_model: "",
    ai_rewrite_prompt: "",
    ai_prompt_template_id: null,
    ai_rewrite_max_chars: 800,
    ai_rewrite_ratio: 70,
    ai_rewrite_failure_mode: "fallback",
  })
}


async function openAddListenerTaskDialog() {
  await loadBots()
  await loadAccounts()
  const hasAccount = accounts.value.some((account) => account.enabled !== false)
  const hasBot = bots.value.some((bot) => bot.enabled !== false)
  if (!hasAccount || !hasBot) {
    const missing = [!hasAccount ? "可用 Telegram 账号" : "", !hasBot ? "已启用 Bot" : ""].filter(Boolean)
    ElMessage.warning(`新增监听任务前，请先配置：${missing.join("、")}`)
    return
  }
  await loadListenerTasks()
  if (contentProcessingEnabled.value) {
    await Promise.all([loadContentTemplates(), loadAiPrompts(), loadAiSettings()])
  }
  resetCurrentListenerTask()
  isListenerTaskEdit.value = false
  listenerTaskDialogVisible.value = true
}


async function openEditListenerTaskDialog(row) {
  await loadBots()
  if (contentProcessingEnabled.value) {
    await loadContentTemplates()
    await loadAiPrompts()
  }
  Object.assign(currentListenerTask, {
    id: row.id,
    name: row.name || "",
    source_channel: row.source_channel || "",
    source_channels: [row.source_channel || ""].filter(Boolean),
    target_channels: row.target_channels || "[]",
    account_id: toPositiveNumber(row.account_id, 1),
    bot_id: normalizeTemplateId(row.bot_id),
    enabled: row.enabled ?? true,
    status: row.status || "running",
    blocked_keywords: row.blocked_keywords || "[]",
    listen_required_keywords: row.listen_required_keywords || "[]",
    replace_words: row.replace_words || "{}",
    footer: row.footer || "",
    remove_contact_lines: row.remove_contact_lines ?? true,
    filter_qr_code: row.filter_qr_code ?? true,
    use_random_head: row.use_random_head ?? false,
    use_random_body: row.use_random_body ?? false,
    use_random_footer: row.use_random_footer ?? false,
    footer_leading_blank_line: row.footer_leading_blank_line ?? true,
    selected_head_template_group_id: normalizeTemplateId(row.selected_head_template_group_id),
    selected_body_template_group_id: normalizeTemplateId(row.selected_body_template_group_id),
    selected_footer_template_group_id: normalizeTemplateId(row.selected_footer_template_group_id),
    selected_head_template_id: normalizeTemplateId(row.selected_head_template_id),
    selected_body_template_id: normalizeTemplateId(row.selected_body_template_id),
    selected_footer_template_id: normalizeTemplateId(row.selected_footer_template_id),
    selected_filter_template_group_id: normalizeTemplateId(row.selected_filter_template_group_id),
    selected_link_template_group_id: normalizeTemplateId(row.selected_link_template_group_id),
    selected_contact_template_group_id: normalizeTemplateId(row.selected_contact_template_group_id),
    album_wait_seconds: toPositiveNumber(row.album_wait_seconds, 3),
    ai_rewrite_enabled: row.ai_rewrite_enabled ?? false,
    ai_rewrite_provider: row.ai_rewrite_provider === "deepseek" ? "deepseek" : "grok",
    ai_rewrite_model: row.ai_rewrite_model || "",
    ai_rewrite_prompt: row.ai_rewrite_prompt || "",
    ai_prompt_template_id: normalizeTemplateId(row.ai_prompt_template_id),
    ai_rewrite_max_chars: toBoundedNumber(row.ai_rewrite_max_chars, 800, 100, 4000),
    ai_rewrite_ratio: toBoundedNumber(row.ai_rewrite_ratio, 70, 0, 100),
    ai_rewrite_failure_mode: row.ai_rewrite_failure_mode === "skip" ? "skip" : "fallback",
  })

  isListenerTaskEdit.value = true
  listenerTaskDialogVisible.value = true
}


function validateListenerTaskJson() {
  try {
    const targets = JSON.parse(currentListenerTask.target_channels || "[]")

    if (!Array.isArray(targets)) {
      ElMessage.error("目标频道格式错误")
      return false
    }

    JSON.parse(currentListenerTask.blocked_keywords || "[]")
    JSON.parse(currentListenerTask.listen_required_keywords || "[]")
    JSON.parse(currentListenerTask.replace_words || "{}")
    return true
  } catch {
    ElMessage.error("目标频道、过滤关键词或替换词 JSON 格式错误")
    return false
  }
}


function normalizeChannelList(value) {
  let items = []

  if (Array.isArray(value)) {
    items = value
  } else if (typeof value === "string") {
    const text = value.trim()

    if (text.startsWith("[") && text.endsWith("]")) {
      try {
        const parsed = JSON.parse(text)
        items = Array.isArray(parsed) ? parsed : [text]
      } catch {
        items = [text]
      }
    } else {
      items = text.split(/[\n,，]/)
    }
  }

  const seen = new Set()
  const result = []

  for (const item of items) {
    const channel = normalizeChannelInput(item)
    const key = channel.toLowerCase()

    if (!channel || seen.has(key)) {
      continue
    }

    seen.add(key)
    result.push(channel)
  }

  return result
}


function normalizeChannelInput(value) {
  let text = String(value || "").trim()

  if (!text) {
    return ""
  }

  if (/^-?\d+$/.test(text)) {
    return text
  }

  text = text.replace(/^https?:\/\//i, "")
  text = text.replace(/^telegram\.me\//i, "t.me/")

  if (/^t\.me\//i.test(text)) {
    const parts = text.replace(/^t\.me\//i, "").split(/[/?#]/).filter(Boolean)

    if (parts[0] === "c" && parts[1] && /^\d+$/.test(parts[1])) {
      return `-100${parts[1]}`
    }

    text = parts[0] || ""
  }

  if (text.startsWith("@")) {
    text = text.slice(1)
  }

  if (text.includes("/")) {
    text = text.split("/")[0]
  }

  text = text.trim()

  if (!text) {
    return ""
  }

  if (/^-?\d+$/.test(text)) {
    return text
  }

  return `@${text}`
}


function buildSubscriptionWarningMessage(results) {
  const lines = results.map((item) => {
    const source = item.normalized_source || item.source_channel || "-"
    return `${source}：${item.message || "监听账号未订阅源频道，实时监听可能不稳定。"}`
  })

  return [
    "检测到源频道订阅风险：",
    "",
    ...lines,
    "",
    "公开频道可能可以读取历史，但不一定能稳定收到实时监听更新。建议先用监听账号加入/订阅源频道。",
    "",
    "是否仍然继续保存？",
  ].join("\n")
}


async function confirmListenerSourceSubscription(accountId, sourceChannels) {
  const sources = normalizeChannelList(sourceChannels)

  if (!sources.length) {
    return false
  }

  try {
    const res = await checkListenerSourceSubscription({
      account_id: toPositiveNumber(accountId, 1),
      source_channels: sources,
    })
    const results = res.data?.results || []
    const warnings = results.filter((item) => item.warning)

    if (!warnings.length) {
      return true
    }

    await ElMessageBox.confirm(
      buildSubscriptionWarningMessage(warnings),
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
        `源频道订阅状态检测失败：${error?.response?.data?.detail || error?.response?.data?.message || error?.message || error}\n\n继续保存后，若监听账号未订阅源频道，实时监听可能不稳定。是否仍然继续保存？`,
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


async function submitListenerTask(formData) {
  Object.assign(currentListenerTask, formData)

  const sourceChannels = normalizeChannelList(
    currentListenerTask.source_channels?.length
      ? currentListenerTask.source_channels
      : currentListenerTask.source_channel,
  )
  const targetChannels = normalizeChannelList(currentListenerTask.target_channels)

  if (!currentListenerTask.name || !sourceChannels.length) {
    ElMessage.error("任务名称和源频道不能为空")
    return
  }

  if (!targetChannels.length) {
    ElMessage.error("目标频道不能为空")
    return
  }

  if (!validateListenerTaskJson()) return

  const subscriptionConfirmed = await confirmListenerSourceSubscription(
    currentListenerTask.account_id,
    sourceChannels,
  )

  if (!subscriptionConfirmed) {
    return
  }

  const payload = {
    name: currentListenerTask.name,
    source_channel: sourceChannels[0],
    target_channels: JSON.stringify(targetChannels),
    account_id: toPositiveNumber(currentListenerTask.account_id, 1),
    bot_id: normalizeTemplateId(currentListenerTask.bot_id),
    enabled: currentListenerTask.enabled,
    status: currentListenerTask.enabled ? "running" : "stopped",
    blocked_keywords: currentListenerTask.blocked_keywords || "[]",
    listen_required_keywords: currentListenerTask.listen_required_keywords || "[]",
    replace_words: currentListenerTask.replace_words || "{}",
    footer: "",
    remove_contact_lines: currentListenerTask.remove_contact_lines,
    filter_qr_code: currentListenerTask.filter_qr_code,
    use_random_head: currentListenerTask.use_random_head,
    use_random_body: currentListenerTask.use_random_body,
    use_random_footer: currentListenerTask.use_random_footer,
    footer_leading_blank_line: currentListenerTask.footer_leading_blank_line !== false,
    selected_head_template_group_id: currentListenerTask.use_random_head
      ? normalizeTemplateId(currentListenerTask.selected_head_template_group_id)
      : null,
    selected_body_template_group_id: currentListenerTask.use_random_body
      ? normalizeTemplateId(currentListenerTask.selected_body_template_group_id)
      : null,
    selected_footer_template_group_id: currentListenerTask.use_random_footer
      ? normalizeTemplateId(currentListenerTask.selected_footer_template_group_id)
      : null,
    selected_head_template_id: currentListenerTask.use_random_head
      ? normalizeTemplateId(currentListenerTask.selected_head_template_id)
      : null,
    selected_body_template_id: currentListenerTask.use_random_body
      ? normalizeTemplateId(currentListenerTask.selected_body_template_id)
      : null,
    selected_footer_template_id: currentListenerTask.use_random_footer
      ? normalizeTemplateId(currentListenerTask.selected_footer_template_id)
      : null,
    selected_filter_template_group_id: normalizeTemplateId(
      currentListenerTask.selected_filter_template_group_id,
    ),
    selected_link_template_group_id: normalizeTemplateId(
      currentListenerTask.selected_link_template_group_id,
    ),
    selected_contact_template_group_id: normalizeTemplateId(
      currentListenerTask.selected_contact_template_group_id,
    ),
    album_wait_seconds: toPositiveNumber(currentListenerTask.album_wait_seconds, 3),
    ai_rewrite_enabled: Boolean(currentListenerTask.ai_rewrite_enabled),
    ai_rewrite_provider: currentListenerTask.ai_rewrite_provider === "deepseek" ? "deepseek" : "grok",
    ai_rewrite_model: (currentListenerTask.ai_rewrite_model || "").trim(),
    ai_rewrite_prompt: "",
    ai_prompt_template_id: normalizeTemplateId(currentListenerTask.ai_prompt_template_id),
    ai_rewrite_max_chars: toBoundedNumber(currentListenerTask.ai_rewrite_max_chars, 800, 100, 4000),
    ai_rewrite_ratio: toBoundedNumber(currentListenerTask.ai_rewrite_ratio, 70, 0, 100),
    ai_rewrite_failure_mode: currentListenerTask.ai_rewrite_failure_mode === "skip" ? "skip" : "fallback",
  }

  if (isListenerTaskEdit.value) {
    await updateListenerTask(currentListenerTask.id, payload)

    for (const source of sourceChannels.slice(1)) {
      await createListenerTask({
        ...payload,
        name: `${payload.name} - ${source}`,
        source_channel: source,
      })
    }

    ElMessage.success(
      sourceChannels.length > 1
        ? `监听任务保存成功，并新增 ${sourceChannels.length - 1} 条源频道任务`
        : "监听任务保存成功",
    )
  } else {
    for (const source of sourceChannels) {
      await createListenerTask({
        ...payload,
        name: sourceChannels.length > 1 ? `${payload.name} - ${source}` : payload.name,
        source_channel: source,
      })
    }

    ElMessage.success(`监听任务添加成功，共创建 ${sourceChannels.length} 条任务`)
  }

  listenerTaskDialogVisible.value = false
  if (hasFeature("dashboard")) await loadStatus()
  await loadListenerTasks()
}


async function deleteListenerTaskHandler(id) {
  await ElMessageBox.confirm(
    "确定删除这个监听任务？",
    "确认删除",
    {
      type: "warning",
    },
  )

  const res = await deleteListenerTask(id)

  if (res.data && res.data.ok === false) {
    ElMessage.error(res.data.message || "删除失败")
    return
  }

  ElMessage.success("监听任务已删除")
  if (hasFeature("dashboard")) await loadStatus()
  await loadListenerTasks()
}


async function startListenerTaskHandler(id) {
  const res = await startListenerTask(id)

  if (res.data && res.data.ok === false) {
    ElMessage.error(res.data.message || "启动失败")
    return
  }

  ElMessage.success("监听任务已启动")
  await loadListenerTasks()
}


async function stopListenerTaskHandler(id) {
  const res = await stopListenerTask(id)

  if (res.data && res.data.ok === false) {
    ElMessage.error(res.data.message || "停止失败")
    return
  }

  ElMessage.success("监听任务已停止")
  await loadListenerTasks()
}


async function checkListenerCatchupHandler(id) {
  const res = await checkListenerCatchup(id)
  const data = res.data || {}

  if (data.consistent) {
    ElMessage.success(data.message || "源频道和目标频道最新内容一致")
  } else {
    ElMessage.warning(data.message || "源频道和目标频道最新内容不一致")
  }

  await loadListenerTaskLogs()
}


async function checkListenerCatchupHandlerV2Legacy(id) {
  try {
    const { value } = await ElMessageBox.prompt(
      "请输入需要补齐的内容条数。补齐会跳过去重逻辑，可能重复发送已发过的内容。",
      "确认补齐",
      {
        type: "warning",
        inputValue: "1",
        inputPattern: /^[1-9]\d*$/,
        inputErrorMessage: "请输入大于 0 的整数",
        confirmButtonText: "开始补齐",
        cancelButtonText: "取消",
      },
    )

    const limit = Math.min(Math.max(Number(value || 1), 1), 100)
    const catchupRes = await catchupLatestListenerMessage(id, {
      force: true,
      limit,
    })
    const catchupData = catchupRes.data || {}

    if (catchupData.ok) {
      ElMessage.success(catchupData.message || `已补齐发送 ${catchupData.sent_count || 0} 条`)
    } else {
      ElMessage.warning(catchupData.message || "补齐失败")
    }
  } catch (error) {
    if (error !== "cancel" && error !== "close") {
      ElMessage.error(
        error?.response?.data?.message
          || error?.message
          || "补齐任务提交失败，请稍后重试",
      )
    }
    await loadListenerTaskLogs()
    return
  }

  await loadListenerTaskLogs()
  await loadListenerTasks()
}

// 旧监听规则兼容
// =========================

const catchupVisible = ref(false)
const catchupCheckingId = ref(null)
const catchupSubmitting = ref(false)
const catchupTaskId = ref(null)
const catchupPlan = ref({ catchup_count: 1 })
const catchupFormRef = ref(null)
const catchupForm = reactive({ limit: 1, interval_seconds: 60 })
const catchupError = ref("")

async function checkListenerCatchupHandlerV2(id) {
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
    const res = await catchupLatestListenerMessage(catchupTaskId.value, {
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
  if (hasFeature("dashboard")) await loadRuntimeDashboard()
}

function resetCurrentRule() {
  currentRule.id = null
  currentRule.source = ""
  currentRule.target = ""
  currentRule.enabled = true
  currentRule.blocked_keywords = "[]"
  currentRule.replace_words = "{}"
  currentRule.footer = ""
  currentRule.remove_contact_lines = true
  currentRule.clone_task_id = null
}


function openAddDialog() {
  resetCurrentRule()
  isEdit.value = false
  dialogVisible.value = true
}


function openEditDialog(row) {
  currentRule.id = row.id
  currentRule.source = row.source || ""
  currentRule.target = row.target || ""
  currentRule.enabled = row.enabled ?? true
  currentRule.blocked_keywords = row.blocked_keywords || "[]"
  currentRule.replace_words = row.replace_words || "{}"
  currentRule.footer = row.footer || ""
  currentRule.remove_contact_lines = row.remove_contact_lines ?? true
  currentRule.clone_task_id = row.clone_task_id || null

  isEdit.value = true
  dialogVisible.value = true
}


function validateRuleJson() {
  try {
    JSON.parse(currentRule.blocked_keywords || "[]")
    JSON.parse(currentRule.replace_words || "{}")
    return true
  } catch {
    ElMessage.error("过滤关键词或替换词不是合法 JSON")
    return false
  }
}


async function submitRule(formData) {
  Object.assign(currentRule, formData)

  if (!currentRule.source || !currentRule.target) {
    ElMessage.error("源频道和目标频道不能为空")
    return
  }

  if (!validateRuleJson()) return

  const payload = {
    source: currentRule.source,
    target: currentRule.target,
    enabled: currentRule.enabled,
    blocked_keywords: currentRule.blocked_keywords || "[]",
    replace_words: currentRule.replace_words || "{}",
    footer: currentRule.footer || "",
    remove_contact_lines: currentRule.remove_contact_lines,
  }

  if (isEdit.value) {
    await updateRule(currentRule.id, payload)
    ElMessage.success("规则保存成功")
  } else {
    await createRule(payload)
    ElMessage.success("规则添加成功")
  }

  dialogVisible.value = false

  if (hasFeature("dashboard")) await loadStatus()
  await loadRules()
}


async function saveRule(row) {
  await updateRule(row.id, {
    source: row.source,
    target: row.target,
    enabled: row.enabled,
    blocked_keywords: row.blocked_keywords || "[]",
    replace_words: row.replace_words || "{}",
    footer: row.footer || "",
    remove_contact_lines: row.remove_contact_lines ?? true,
  })

  ElMessage.success("规则状态已更新")

  if (hasFeature("dashboard")) await loadStatus()
  await loadRules()
}


async function deleteRule(id) {
  await ElMessageBox.confirm(
    "确定删除这条规则？",
    "确认删除",
    {
      type: "warning",
    },
  )

  await removeRule(id)

  ElMessage.success("删除成功")

  if (hasFeature("dashboard")) await loadStatus()
  await loadRules()
}


async function startClone(rule) {
  await cloneRule(rule.id, 50, 5)
  ElMessage.success("克隆任务已开始，请查看日志")
}


// =========================
// 账号管理
// =========================

function resetCurrentAccount() {
  currentAccount.id = null
  currentAccount.name = ""
  currentAccount.username = ""
  currentAccount.session_path = ""
  currentAccount.has_session_path = false
  currentAccount.proxy = ""
  currentAccount.has_proxy = false
  currentAccount.clear_proxy = false
  currentAccount.enabled = true
  currentAccount.is_default = false
  currentAccount.remark = ""
  currentAccount.greeting_enabled = false
  currentAccount.greeting_message = ""
  currentAccount.away_enabled = false
  currentAccount.away_message = ""
  currentAccount.business_start_time = "09:00"
  currentAccount.business_end_time = "18:00"
  currentAccount.away_repeat_hours = 12
}


function openAccountLoginDialog() {
  loginAccountTarget.value = null
  accountLoginDialogVisible.value = true
}


function openAccountReloginDialog(row) {
  loginAccountTarget.value = { ...row }
  accountLoginDialogVisible.value = true
}


function openEditAccountDialog(row) {
  Object.assign(currentAccount, row)
  isAccountEdit.value = true
  accountDialogVisible.value = true
}


async function submitAccount(formData) {
  const generation = getAuthGeneration()
  Object.assign(currentAccount, formData)

  if (!currentAccount.id || !currentAccount.name) {
    ElMessage.error("账号名称不能为空")
    return
  }

  const autoReplyPayload = {
    greeting_enabled: currentAccount.greeting_enabled,
    greeting_message: currentAccount.greeting_message,
    away_enabled: currentAccount.away_enabled,
    away_message: currentAccount.away_message,
    business_start_time: currentAccount.business_start_time,
    business_end_time: currentAccount.business_end_time,
    away_repeat_hours: currentAccount.away_repeat_hours,
  }

  accountSaving.value = true
  try {
    await updateAccount(currentAccount.id, {
      name: currentAccount.name,
      username: currentAccount.username,
      proxy: currentAccount.proxy,
      clear_proxy: currentAccount.clear_proxy,
      enabled: currentAccount.enabled,
      remark: currentAccount.remark,
      ...autoReplyPayload,
    })
    if (!isAuthGenerationCurrent(generation)) return

    ElMessage.success("账号保存成功")

    accountDialogVisible.value = false
    await loadAccounts()
  } catch (error) {
    if (isCanceledAuthRequest(error) || !isAuthGenerationCurrent(generation)) return
    throw error
  } finally {
    if (isAuthGenerationCurrent(generation)) accountSaving.value = false
  }
}


async function handleAccountLoginSuccess() {
  await loadAccounts()
}


async function saveAccount(row) {
  await updateAccount(row.id, {
    name: row.name,
    username: row.username,
    enabled: row.enabled,
    remark: row.remark,
    greeting_enabled: row.greeting_enabled,
    greeting_message: row.greeting_message,
    away_enabled: row.away_enabled,
    away_message: row.away_message,
    business_start_time: row.business_start_time,
    business_end_time: row.business_end_time,
    away_repeat_hours: row.away_repeat_hours,
  })

  ElMessage.success("账号状态已更新")
}

async function setDefaultAccount(row) {
  const generation = getAuthGeneration()
  try {
    await ElMessageBox.confirm(
      `确定将“${row.name || `账号 #${row.id}`}”设为全局默认采集账号？以后新建克隆任务留空时会使用该账号。`,
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
  if (!isAuthGenerationCurrent(generation)) return

  defaultAccountSettingId.value = row.id
  try {
    await updateAccount(row.id, {
      name: row.name,
      username: row.username,
      enabled: true,
      remark: row.remark,
      is_default: true,
    })
    if (!isAuthGenerationCurrent(generation)) return
    ElMessage.success("全局默认账号已更新")
    await loadAccounts()
  } catch (error) {
    if (isCanceledAuthRequest(error) || !isAuthGenerationCurrent(generation)) return
    ElMessage.error(error?.response?.data?.detail || error?.message || "设置默认账号失败")
  } finally {
    if (isAuthGenerationCurrent(generation) && defaultAccountSettingId.value === row.id) {
      defaultAccountSettingId.value = null
    }
  }
}


async function deleteAccount(id) {
  await ElMessageBox.confirm(
    "确定删除这个账号？",
    "确认删除",
    {
      type: "warning",
    },
  )

  await removeAccount(id)

  ElMessage.success("账号已删除")

  await loadAccounts()
}


// =========================
// Bot 管理
// =========================

function resetCurrentBot() {
  currentBot.id = null
  currentBot.name = ""
  currentBot.token = ""
  currentBot.enabled = true
  currentBot.remark = ""
  currentBot.last_error = ""
}


function openAddBotDialog() {
  resetCurrentBot()
  isBotEdit.value = false
  botDialogVisible.value = true
}


function openEditBotDialog(row) {
  Object.assign(currentBot, {
    id: row.id,
    name: row.name || "",
    token: "",
    enabled: row.enabled ?? true,
    remark: row.remark || "",
    last_error: row.last_error || "",
  })

  isBotEdit.value = true
  botDialogVisible.value = true
}


async function submitBot(formData) {
  const generation = getAuthGeneration()
  Object.assign(currentBot, formData)

  if (!currentBot.name || (!isBotEdit.value && !currentBot.token)) {
    ElMessage.error(isBotEdit.value ? "Bot 名称不能为空" : "Bot 名称和 Token 不能为空")
    return
  }

  const payload = {
    name: currentBot.name,
    enabled: currentBot.enabled,
    remark: currentBot.remark || "",
  }

  if (currentBot.token) {
    payload.token = currentBot.token
  }

  botSaving.value = true
  try {
    if (isBotEdit.value) {
      await updateBot(currentBot.id, payload)
    } else {
      await createBot(payload)
    }
    if (!isAuthGenerationCurrent(generation)) return
    ElMessage.success(isBotEdit.value ? "Bot 保存成功" : "Bot 添加成功")

    botDialogVisible.value = false
    await loadBots()
  } catch (error) {
    if (isCanceledAuthRequest(error) || !isAuthGenerationCurrent(generation)) return
    ElMessage.error(error?.response?.data?.detail || error?.response?.data?.message || "Bot 保存失败")
  } finally {
    if (isAuthGenerationCurrent(generation)) botSaving.value = false
  }
}


async function saveBotStatus(row, value) {
  await updateBot(row.id, {
    enabled: value,
  })

  ElMessage.success(value ? "Bot 已启用" : "Bot 已停用")

  await loadBots()
}

async function testBotHandler(row) {
  try {
    const res = await testBot(row.id)

    if (res.data.ok) {
      ElMessage.success(`Bot 正常：@${res.data.bot.username}`)
    } else {
      ElMessage.error(res.data.message || "Bot 测试失败")
    }
  } catch (e) {
    if (isCanceledAuthRequest(e)) return
    ElMessage.error("Bot 测试失败")
  }
}

async function deleteBotHandler(id) {
  await ElMessageBox.confirm(
    "确定删除这个 Bot？删除后会同时删除相关目标频道绑定。",
    "确认删除",
    {
      type: "warning",
    },
  )

  await deleteBot(id)

  ElMessage.success("Bot 已删除")

  await loadBotPage()
}


// =========================
// 目标频道绑定 Bot
// =========================

function resetCurrentBotBinding() {
  currentBotBinding.id = null
  currentBotBinding.target_channel = ""
  currentBotBinding.bot_id = null
  currentBotBinding.enabled = true
  currentBotBinding.remark = ""
}


function openAddBotBindingDialog() {
  if (!bots.value.length) {
    ElMessage.warning("请先添加 Bot")
    return
  }

  resetCurrentBotBinding()
  isBotBindingEdit.value = false
  botBindingDialogVisible.value = true
}


function openEditBotBindingDialog(row) {
  Object.assign(currentBotBinding, {
    id: row.id,
    target_channel: row.target_channel || "",
    bot_id: row.bot_id || null,
    enabled: row.enabled ?? true,
    remark: row.remark || "",
  })

  isBotBindingEdit.value = true
  botBindingDialogVisible.value = true
}


async function submitBotBinding(formData) {
  Object.assign(currentBotBinding, formData)

  if (!currentBotBinding.target_channel) {
    ElMessage.error("目标频道不能为空")
    return
  }

  if (!currentBotBinding.bot_id) {
    ElMessage.error("请选择 Bot")
    return
  }

  const payload = {
    target_channel: currentBotBinding.target_channel,
    bot_id: currentBotBinding.bot_id,
    enabled: currentBotBinding.enabled,
    remark: currentBotBinding.remark || "",
  }

  if (isBotBindingEdit.value) {
    await updateBotBinding(currentBotBinding.id, payload)
    ElMessage.success("绑定保存成功")
  } else {
    await createBotBinding(payload)
    ElMessage.success("绑定添加成功")
  }

  botBindingDialogVisible.value = false

  await loadBotBindings()
}


async function saveBotBindingStatus(row, value) {
  await updateBotBinding(row.id, {
    enabled: value,
  })

  ElMessage.success(value ? "绑定已启用" : "绑定已停用")

  await loadBotBindings()
}


async function deleteBotBindingHandler(id) {
  await ElMessageBox.confirm(
    "确定删除这个绑定？",
    "确认删除",
    {
      type: "warning",
    },
  )

  await deleteBotBinding(id)

  ElMessage.success("绑定已删除")

  await loadBotBindings()
}


// =========================
// 克隆任务
// =========================

function resetCurrentCloneTask() {
  Object.assign(currentCloneTask, {
    id: null,
    name: "",
    source_channel: "",
    target_channels: "[]",
    account_id: null,
    bot_id: bots.value.find((bot) => bot.enabled)?.id || null,
    start_message_url: "",
    end_message_url: "",
    single_delay: 3,
    target_delay: 2,
    blocked_keywords: "[]",
    replace_words: "{}",
    footer: "",
    remove_contact_lines: true,
    filter_qr_code: true,
    enable_listener: false,
    use_random_head: false,
    use_random_body: false,
    use_random_footer: false,
    footer_leading_blank_line: true,
    selected_head_template_group_id: null,
    selected_body_template_group_id: null,
    selected_footer_template_group_id: null,
    selected_head_template_id: null,
    selected_body_template_id: null,
    selected_footer_template_id: null,
    selected_filter_template_group_id: null,
    selected_link_template_group_id: null,
    selected_contact_template_group_id: null,
    enabled: true,
    status: "idle",
    last_message_id: 0,
    ai_rewrite_enabled: false,
    ai_rewrite_provider: defaultAiProvider.value,
    ai_rewrite_model: "",
    ai_rewrite_prompt: "",
    ai_prompt_template_id: null,
    ai_rewrite_max_chars: 800,
    ai_rewrite_ratio: 70,
    ai_rewrite_failure_mode: "fallback",
  })
}


async function openAddCloneTaskDialog() {
  await loadBots()
  await loadAccounts()
  const hasAccount = accounts.value.some((account) => account.enabled !== false)
  const hasBot = bots.value.some((bot) => bot.enabled !== false)
  if (!hasAccount || !hasBot) {
    const missing = [!hasAccount ? "可用 Telegram 账号" : "", !hasBot ? "已启用 Bot" : ""].filter(Boolean)
    ElMessage.warning(`新增克隆任务前，请先配置：${missing.join("、")}`)
    return
  }
  if (contentProcessingEnabled.value) {
    await Promise.all([loadContentTemplates(), loadAiPrompts(), loadAiSettings()])
  }
  resetCurrentCloneTask()
  isCloneTaskEdit.value = false
  cloneTaskDialogVisible.value = true
}


async function openEditCloneTaskDialog(row) {
  await loadBots()
  await loadAccounts()
  if (contentProcessingEnabled.value) {
    await loadContentTemplates()
    await loadAiPrompts()
  }
  Object.assign(currentCloneTask, {
    id: row.id,
    name: row.name || "",
    source_channel: row.source_channel || "",
    target_channels: row.target_channels || "[]",
    account_id: normalizeTemplateId(row.account_id),
    bot_id: normalizeTemplateId(row.bot_id),
    start_message_url: row.start_message_url || "",
    end_message_url: row.end_message_url || "",
    single_delay: secondsToMinutes(row.single_delay, 1),
    target_delay: toPositiveNumber(row.target_delay, 2),
    blocked_keywords: row.blocked_keywords || "[]",
    replace_words: row.replace_words || "{}",
    footer: row.footer || "",
    remove_contact_lines: row.remove_contact_lines ?? true,
    filter_qr_code: row.filter_qr_code ?? true,
    enable_listener: row.enable_listener ?? false,
    use_random_head: row.use_random_head ?? false,
    use_random_body: row.use_random_body ?? false,
    use_random_footer: row.use_random_footer ?? false,
    footer_leading_blank_line: row.footer_leading_blank_line ?? true,
    selected_head_template_group_id: normalizeTemplateId(row.selected_head_template_group_id),
    selected_body_template_group_id: normalizeTemplateId(row.selected_body_template_group_id),
    selected_footer_template_group_id: normalizeTemplateId(row.selected_footer_template_group_id),
    selected_head_template_id: normalizeTemplateId(row.selected_head_template_id),
    selected_body_template_id: normalizeTemplateId(row.selected_body_template_id),
    selected_footer_template_id: normalizeTemplateId(row.selected_footer_template_id),
    selected_filter_template_group_id: normalizeTemplateId(row.selected_filter_template_group_id),
    selected_link_template_group_id: normalizeTemplateId(row.selected_link_template_group_id),
    selected_contact_template_group_id: normalizeTemplateId(row.selected_contact_template_group_id),
    enabled: row.enabled ?? true,
    status: row.status || "idle",
    last_message_id: row.last_message_id || 0,
    ai_rewrite_enabled: row.ai_rewrite_enabled ?? false,
    ai_rewrite_provider: row.ai_rewrite_provider === "deepseek" ? "deepseek" : "grok",
    ai_rewrite_model: row.ai_rewrite_model || "",
    ai_rewrite_prompt: row.ai_rewrite_prompt || "",
    ai_prompt_template_id: normalizeTemplateId(row.ai_prompt_template_id),
    ai_rewrite_max_chars: toBoundedNumber(row.ai_rewrite_max_chars, 800, 100, 4000),
    ai_rewrite_ratio: toBoundedNumber(row.ai_rewrite_ratio, 70, 0, 100),
    ai_rewrite_failure_mode: row.ai_rewrite_failure_mode === "skip" ? "skip" : "fallback",
  })

  isCloneTaskEdit.value = true
  cloneTaskDialogVisible.value = true
}


function validateCloneTaskJson() {
  try {
    JSON.parse(currentCloneTask.target_channels || "[]")
    JSON.parse(currentCloneTask.blocked_keywords || "[]")
    JSON.parse(currentCloneTask.replace_words || "{}")
    return true
  } catch {
    ElMessage.error("目标频道、过滤关键词或替换词 JSON 格式错误")
    return false
  }
}


function parseTelegramMessageId(value) {
  const text = (value || "").trim()

  if (!text) {
    return null
  }

  const match = text.match(/\/(\d+)(?:\?.*)?$/)

  if (!match) {
    return null
  }

  const messageId = Number(match[1])

  if (!Number.isInteger(messageId) || messageId < 1) {
    return null
  }

  return messageId
}


function validateCloneTaskMessageRange() {
  const startUrl = (currentCloneTask.start_message_url || "").trim()
  const endUrl = (currentCloneTask.end_message_url || "").trim()
  const startId = parseTelegramMessageId(startUrl)
  const endId = parseTelegramMessageId(endUrl)

  if (startUrl && !startId) {
    ElMessage.error("源频道开始内容链接格式不正确")
    return false
  }

  if (endUrl && !endId) {
    ElMessage.error("源频道结束内容链接格式不正确")
    return false
  }

  if (startId && endId && startId > endId) {
    ElMessage.error("开始内容链接的 message_id 不能大于结束内容链接")
    return false
  }

  return true
}


async function submitCloneTask(formData) {
  Object.assign(currentCloneTask, formData)

  const sourceChannel = normalizeChannelInput(currentCloneTask.source_channel)
  const targetChannels = normalizeChannelList(currentCloneTask.target_channels)

  if (!currentCloneTask.name || !sourceChannel) {
    ElMessage.error("任务名称和源频道不能为空")
    return
  }

  if (!validateCloneTaskJson()) return
  if (!validateCloneTaskMessageRange()) return

  const payload = {
    name: currentCloneTask.name,
    source_channel: sourceChannel,
    target_channels: JSON.stringify(targetChannels),
    account_id: normalizeTemplateId(currentCloneTask.account_id),
    bot_id: normalizeTemplateId(currentCloneTask.bot_id),
    start_message_url: (currentCloneTask.start_message_url || "").trim(),
    end_message_url: (currentCloneTask.end_message_url || "").trim(),
    single_delay: minutesToSeconds(currentCloneTask.single_delay, 1),
    target_delay: toPositiveNumber(currentCloneTask.target_delay, 2),
    blocked_keywords: currentCloneTask.blocked_keywords || "[]",
    replace_words: currentCloneTask.replace_words || "{}",
    footer: currentCloneTask.footer || "",
    remove_contact_lines: currentCloneTask.remove_contact_lines,
    filter_qr_code: currentCloneTask.filter_qr_code,
    enable_listener: currentCloneTask.enable_listener,
    use_random_head: currentCloneTask.use_random_head,
    use_random_body: currentCloneTask.use_random_body,
    use_random_footer: currentCloneTask.use_random_footer,
    footer_leading_blank_line: currentCloneTask.footer_leading_blank_line !== false,
    selected_head_template_group_id: currentCloneTask.use_random_head
      ? normalizeTemplateId(currentCloneTask.selected_head_template_group_id)
      : null,
    selected_body_template_group_id: currentCloneTask.use_random_body
      ? normalizeTemplateId(currentCloneTask.selected_body_template_group_id)
      : null,
    selected_footer_template_group_id: currentCloneTask.use_random_footer
      ? normalizeTemplateId(currentCloneTask.selected_footer_template_group_id)
      : null,
    selected_head_template_id: currentCloneTask.use_random_head
      ? normalizeTemplateId(currentCloneTask.selected_head_template_id)
      : null,
    selected_body_template_id: currentCloneTask.use_random_body
      ? normalizeTemplateId(currentCloneTask.selected_body_template_id)
      : null,
    selected_footer_template_id: currentCloneTask.use_random_footer
      ? normalizeTemplateId(currentCloneTask.selected_footer_template_id)
      : null,
    selected_filter_template_group_id: normalizeTemplateId(
      currentCloneTask.selected_filter_template_group_id,
    ),
    selected_link_template_group_id: normalizeTemplateId(
      currentCloneTask.selected_link_template_group_id,
    ),
    selected_contact_template_group_id: normalizeTemplateId(
      currentCloneTask.selected_contact_template_group_id,
    ),
    ai_rewrite_enabled: Boolean(currentCloneTask.ai_rewrite_enabled),
    ai_rewrite_provider: currentCloneTask.ai_rewrite_provider === "deepseek" ? "deepseek" : "grok",
    ai_rewrite_model: (currentCloneTask.ai_rewrite_model || "").trim(),
    ai_rewrite_prompt: "",
    ai_prompt_template_id: normalizeTemplateId(currentCloneTask.ai_prompt_template_id),
    ai_rewrite_max_chars: toBoundedNumber(currentCloneTask.ai_rewrite_max_chars, 800, 100, 4000),
    ai_rewrite_ratio: toBoundedNumber(currentCloneTask.ai_rewrite_ratio, 70, 0, 100),
    ai_rewrite_failure_mode: currentCloneTask.ai_rewrite_failure_mode === "skip" ? "skip" : "fallback",
    enabled: currentCloneTask.enabled,
  }

  if (isCloneTaskEdit.value) {
    await updateCloneTask(currentCloneTask.id, payload)
    ElMessage.success("克隆任务保存成功")
  } else {
    await createCloneTask(payload)
    ElMessage.success("克隆任务添加成功")
  }

  cloneTaskDialogVisible.value = false

  await loadCloneTasks()
  if (hasFeature("listener_tasks")) await loadListenerTasks()
  if (hasFeature("dashboard")) await loadStatus()
}


async function removeCloneTaskHandler(id) {
  const taskId = typeof id === "object" ? id.id : id

  await ElMessageBox.confirm(
    "确定删除这个克隆任务？",
    "确认删除",
    {
      type: "warning",
    },
  )

  const res = await deleteCloneTask(taskId)

  if (res.data && res.data.ok === false) {
    ElMessage.error(res.data.message || "删除失败")
    await loadCloneTasks()
    return
  }

  ElMessage.success("克隆任务已删除")

  await loadCloneTasks()
  if (hasFeature("listener_tasks")) await loadListenerTasks()
  if (hasFeature("dashboard")) await loadStatus()
}


async function startCloneTaskHandler(id) {
  try {
    const res = await startCloneTask(id)

    if (res.data && res.data.ok === false) {
      ElMessage.error(res.data.message || "克隆开始失败")
      await loadCloneTasks()
      return
    }

    ElMessage.success("克隆已开始")
    await loadCloneTasks()
  } catch (e) {
    throw e
  }
}


async function pauseCloneTaskHandler(id) {
  await pauseCloneTask(id)
  ElMessage.success("克隆已暂停")
  await loadCloneTasks()
}


async function resumeCloneTaskHandler(id) {
  await resumeCloneTask(id)
  ElMessage.success("克隆已继续")
  await loadCloneTasks()
}


async function handleStopCloneTask(id) {
  await stopCloneTask(id)
  ElMessage.success("已停止克隆任务")
  await loadCloneTasks()
  scheduleCloneTaskRefresh()
}


async function saveSendSettings(formData) {
  const generation = getAuthGeneration()
  settingsSaving.value = true
  try {
    const payload = {
      global_send_delay: toNonNegativeNumber(formData.global_send_delay, 3),
      send_retry_count: toNonNegativeNumber(formData.send_retry_count, 2),
      send_retry_delay: toNonNegativeNumber(formData.send_retry_delay, 5),
    }

    const res = await updateSendSettings(payload)
    if (!isAuthGenerationCurrent(generation)) return
    sendSettings.value = res.data
    ElMessage.success("发送设置已保存")
  } catch (error) {
    if (isCanceledAuthRequest(error) || !isAuthGenerationCurrent(generation)) return
    throw error
  } finally {
    if (isAuthGenerationCurrent(generation)) settingsSaving.value = false
  }
}

async function saveAiSettings(formData) {
  const generation = getAuthGeneration()
  aiSettingsSaving.value = true
  try {
    const res = await updateAiSettings(formData)
    if (!isAuthGenerationCurrent(generation)) return
    aiSettings.value = res.data || aiSettings.value
    ElMessage.success("AI 配置已保存")
  } catch (error) {
    if (isCanceledAuthRequest(error) || !isAuthGenerationCurrent(generation)) return
    ElMessage.error(getApiErrorMessage(error, "AI 配置保存失败，请检查后重试"))
  } finally {
    if (isAuthGenerationCurrent(generation)) aiSettingsSaving.value = false
  }
}

function resetCurrentAiPrompt() {
  Object.assign(currentAiPrompt, {
    id: null,
    name: "",
    content: "",
    content_type: "",
    enabled: true,
    is_default: false,
  })
}

function openAddAiPromptDialog() {
  resetCurrentAiPrompt()
  isAiPromptEdit.value = false
  aiPromptDialogVisible.value = true
}

function openEditAiPromptDialog(prompt) {
  Object.assign(currentAiPrompt, {
    id: prompt.id,
    name: prompt.name || "",
    content: prompt.content || "",
    content_type: prompt.content_type || "",
    enabled: prompt.enabled ?? true,
    is_default: prompt.is_default ?? false,
  })
  isAiPromptEdit.value = true
  aiPromptDialogVisible.value = true
}

async function submitAiPrompt(formData) {
  const generation = getAuthGeneration()
  aiPromptSaving.value = true
  try {
    if (isAiPromptEdit.value) {
      await updateAiPrompt(currentAiPrompt.id, formData)
    } else {
      await createAiPrompt(formData)
    }
    if (!isAuthGenerationCurrent(generation)) return
    ElMessage.success(isAiPromptEdit.value ? "提示词已保存" : "提示词已创建")
    aiPromptDialogVisible.value = false
    await loadAiPrompts()
  } catch (error) {
    if (isCanceledAuthRequest(error) || !isAuthGenerationCurrent(generation)) return
    ElMessage.error(getApiErrorMessage(error, "提示词保存失败"))
  } finally {
    if (isAuthGenerationCurrent(generation)) aiPromptSaving.value = false
  }
}

async function setDefaultAiPromptHandler(prompt) {
  const generation = getAuthGeneration()
  aiPromptDefaultingId.value = prompt.id
  try {
    await setDefaultAiPrompt(prompt.id)
    if (!isAuthGenerationCurrent(generation)) return
    ElMessage.success(`“${prompt.name}”已设为系统默认提示词`)
    await loadAiPrompts()
  } catch (error) {
    if (isCanceledAuthRequest(error) || !isAuthGenerationCurrent(generation)) return
    ElMessage.error(getApiErrorMessage(error, "设置默认提示词失败"))
  } finally {
    if (isAuthGenerationCurrent(generation) && aiPromptDefaultingId.value === prompt.id) {
      aiPromptDefaultingId.value = null
    }
  }
}

async function deleteAiPromptHandler(prompt) {
  const generation = getAuthGeneration()
  aiPromptDeletingId.value = prompt.id
  try {
    await deleteAiPrompt(prompt.id)
    if (!isAuthGenerationCurrent(generation)) return
    ElMessage.success("提示词已删除")
    await loadAiPrompts()
  } catch (error) {
    if (isCanceledAuthRequest(error) || !isAuthGenerationCurrent(generation)) return
    ElMessage.error(getApiErrorMessage(error, "删除提示词失败"))
  } finally {
    if (isAuthGenerationCurrent(generation) && aiPromptDeletingId.value === prompt.id) {
      aiPromptDeletingId.value = null
    }
  }
}

function getApiErrorMessage(error, fallback) {
  if (isCanceledAuthRequest(error)) return ""
  return error?.response?.data?.detail || error?.message || fallback
}


const handleToggleCloneListener = async (row, value) => {
  try {
    await updateCloneTask(row.id, {
      enable_listener: value,
    })

    ElMessage.success(value ? "已开启实时监听" : "已关闭实时监听")

    await loadCloneTasks()
    if (hasFeature("listener_tasks")) await loadListenerTasks()
    if (hasFeature("dashboard")) await loadStatus()
  } catch (e) {
    if (isCanceledAuthRequest(e)) return
    ElMessage.error("切换实时监听失败")
    await loadCloneTasks()
  }
}

function toPositiveNumber(value, fallback) {
  const numberValue = Number(value)

  if (!Number.isFinite(numberValue) || numberValue < 1) {
    return fallback
  }

  return Math.floor(numberValue)
}


function toBoundedNumber(value, fallback, minimum, maximum) {
  const numberValue = Number(value)
  const resolved = Number.isFinite(numberValue) ? Math.floor(numberValue) : fallback
  return Math.max(minimum, Math.min(maximum, resolved))
}


function normalizeTemplateId(value) {
  if (value === null || value === undefined || value === "") {
    return null
  }

  const numberValue = Number(value)
  return Number.isInteger(numberValue) && numberValue > 0 ? numberValue : null
}


function minutesToSeconds(value, fallbackMinutes) {
  return toPositiveNumber(value, fallbackMinutes) * SECONDS_PER_MINUTE
}


function secondsToMinutes(value, fallbackMinutes) {
  const seconds = toPositiveNumber(value, fallbackMinutes * SECONDS_PER_MINUTE)
  return Math.max(Math.ceil(seconds / SECONDS_PER_MINUTE), 1)
}


function toNonNegativeNumber(value, fallback) {
  const numberValue = Number(value)

  if (!Number.isFinite(numberValue) || numberValue < 0) {
    return fallback
  }

  return Math.floor(numberValue)
}


// =========================
// 生命周期
// =========================

async function handleLogin(token, mode) {
  stopRefreshTimers()
  clearSessionData()
  replaceAuthToken(token)
  const generation = getAuthGeneration()
  isAuthenticated.value = true
  authChecking.value = true
  authError.value = ""
  const ready = await resolveCurrentUser()
  if (!ready || !isAuthGenerationCurrent(generation)) return
  ElMessage.success(mode === "register" ? "注册成功" : "登录成功")
  await initializeAuthorizedApp(generation)
}

function authErrorText(error, fallback) {
  if (isCanceledAuthRequest(error)) return ""
  return error?.response?.data?.detail || error?.response?.data?.message || error?.message || fallback
}

async function resolveCurrentUser() {
  const generation = getAuthGeneration()
  const owner = Symbol("auth-check")
  authCheckOwner = owner
  authChecking.value = true
  authError.value = ""
  try {
    const response = await getCurrentUser()
    if (!isAuthGenerationCurrent(generation)) return false
    const user = response.data?.user
    if (!user?.username || !user?.role) {
      throw new Error("当前用户信息不完整，请重新登录")
    }
    currentUser.value = user
    isAuthenticated.value = true
    return true
  } catch (error) {
    if (isCanceledAuthRequest(error) || !isAuthGenerationCurrent(generation)) return false
    const message = authErrorText(error, "账号权限读取失败，请检查网络后重试")
    if (error?.response?.status === 401) {
      stopRefreshTimers()
      clearSessionData()
      replaceAuthToken("")
      currentUser.value = null
      isAuthenticated.value = false
      authCheckOwner = null
      authChecking.value = false
    } else {
      isAuthenticated.value = Boolean(getAuthToken())
    }
    authError.value = message
    return false
  } finally {
    if (authCheckOwner === owner && isAuthGenerationCurrent(generation)) {
      authCheckOwner = null
      authChecking.value = false
    }
  }
}

async function retryCurrentUser() {
  const generation = getAuthGeneration()
  const ready = await resolveCurrentUser()
  if (ready && isAuthGenerationCurrent(generation)) await initializeAuthorizedApp(generation)
}

function stopRefreshTimers() {
  if (cloneRefreshTimer) {
    clearInterval(cloneRefreshTimer)
    cloneRefreshTimer = null
  }
  if (cloneLogRefreshTimer) {
    clearInterval(cloneLogRefreshTimer)
    cloneLogRefreshTimer = null
  }
}

function startRefreshTimers() {
  stopRefreshTimers()
  const generation = getAuthGeneration()

  if (hasFeature("clone_tasks")) {
    cloneRefreshTimer = setInterval(async () => {
      if (!isAuthGenerationCurrent(generation)) return
      try {
        await loadCloneTasks()
      } catch {}
    }, AUTO_REFRESH_INTERVAL)
  }

  if (hasFeature("clone_tasks") || hasFeature("listener_tasks")) {
    cloneLogRefreshTimer = setInterval(async () => {
      if (!isAuthGenerationCurrent(generation)) return
      try {
        if (activeMenu.value === "clone" && hasFeature("clone_tasks")) {
          await loadCloneTaskLogs()
        }
        if (activeMenu.value === "rules" && hasFeature("listener_tasks")) {
          await loadListenerTaskLogs()
        }
      } catch {}
    }, SEND_LOG_REFRESH_INTERVAL)
  }
}

async function initializeAuthorizedApp(generation = getAuthGeneration()) {
  const loaded = await handleMenuChange(activeMenu.value, { silent: true })
  if (!loaded || !isAuthGenerationCurrent(generation)) return false
  startRefreshTimers()
  return true
}

async function handleLogout() {
  if (loggingOut.value) return
  const generation = getAuthGeneration()
  loggingOut.value = true
  try {
    await logoutUser()
  } catch (error) {
    if (isCanceledAuthRequest(error) || !isAuthGenerationCurrent(generation)) return
    ElMessage.warning(authErrorText(error, "服务器退出失败，已清除本地登录状态"))
  }
  if (!isAuthGenerationCurrent(generation)) return
  stopRefreshTimers()
  clearSessionData()
  replaceAuthToken("")
  currentUser.value = null
  isAuthenticated.value = false
  authChecking.value = false
  authError.value = ""
  activeMenu.value = "home"
  loggingOut.value = false
}

let refreshingAccessContext = false
async function handleAccessRestricted(event) {
  if (!isAuthenticated.value || refreshingAccessContext) return
  const generation = getAuthGeneration()
  const code = event?.detail?.code
  const message = event?.detail?.message || "当前账号没有此功能权限"

  if (["ACCESS_PENDING", "ACCESS_EXPIRED"].includes(code)) {
    currentUser.value = {
      ...currentUser.value,
      access_state: code === "ACCESS_EXPIRED" ? "expired" : "pending",
      available: false,
    }
    stopRefreshTimers()
    clearSessionData()
    await handleMenuChange("guide", { silent: true })
    if (!isAuthGenerationCurrent(generation)) return
    ElMessage.warning(message)
    return
  }

  if (code !== "FEATURE_FORBIDDEN") return
  refreshingAccessContext = true
  try {
    const response = await getCurrentUser()
    if (!isAuthGenerationCurrent(generation)) return
    if (response.data?.user) currentUser.value = response.data.user
    clearSessionData()
    await handleMenuChange(activeMenu.value, { silent: true })
    if (!isAuthGenerationCurrent(generation)) return
    startRefreshTimers()
    ElMessage.warning(message)
  } catch (error) {
    if (isCanceledAuthRequest(error) || !isAuthGenerationCurrent(generation)) return
    ElMessage.error(authErrorText(error, "刷新账号权限失败，请重新登录"))
  } finally {
    if (isAuthGenerationCurrent(generation)) refreshingAccessContext = false
  }
}

function handleAuthSessionChanged(event) {
  stopRefreshTimers()
  clearSessionData()
  ElMessage.closeAll()
  currentUser.value = null
  authError.value = ""
  loggingOut.value = false
  refreshingAccessContext = false
  isAuthenticated.value = Boolean(event?.detail?.authenticated)
  authChecking.value = isAuthenticated.value
}

onMounted(async () => {
  window.addEventListener(ACCESS_RESTRICTED_EVENT, handleAccessRestricted)
  window.addEventListener(AUTH_SESSION_CHANGED_EVENT, handleAuthSessionChanged)
  if (!getAuthToken()) {
    authChecking.value = false
    return
  }

  const generation = getAuthGeneration()
  const ready = await resolveCurrentUser()
  if (ready && isAuthGenerationCurrent(generation)) await initializeAuthorizedApp(generation)
})


onUnmounted(() => {
  window.removeEventListener(ACCESS_RESTRICTED_EVENT, handleAccessRestricted)
  window.removeEventListener(AUTH_SESSION_CHANGED_EVENT, handleAuthSessionChanged)
  stopRefreshTimers()

})
</script>

<style>
.auth-resolving {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background: var(--app-bg, #f3f4f6);
}

.auth-resolving__card {
  width: min(400px, 100%);
  text-align: center;
}

.auth-resolving__card .el-card__body {
  display: flex;
  align-items: center;
  flex-direction: column;
  gap: 8px;
  padding: 28px;
}

.auth-resolving__card span {
  color: var(--el-text-color-secondary, #6b7280);
  font-size: 13px;
}

.auth-resolving__icon {
  color: var(--el-color-primary, #409eff);
  font-size: 26px;
  animation: auth-resolving-rotate 0.9s linear infinite;
}

.auth-resolving--error .auth-resolving__card .el-card__body {
  align-items: stretch;
}

.auth-resolving__actions {
  display: flex;
  justify-content: center;
  gap: 8px;
}

.auth-resolving__actions .el-button {
  min-height: 40px;
  margin-left: 0;
}

.access-notice {
  margin-bottom: 14px;
}

.menu-load-error {
  margin-bottom: 14px;
}

.menu-load-error__content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.menu-load-error__content .el-button {
  flex: 0 0 auto;
  margin-left: 0;
}

@keyframes auth-resolving-rotate {
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .auth-resolving__icon {
    animation: none;
  }
}

body {
  margin: 0;
  background: #f3f4f6;
}

.bot-page {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
</style>
