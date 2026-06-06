<template>
  <LoginPanel
    v-if="!isAuthenticated"
    @login="handleLogin"
  />

  <div v-else>
    <MainLayout
      :status="status.status"
      :active-menu="activeMenu"
      @change-menu="handleMenuChange"
    >
    <div v-if="activeMenu === 'home'">
      <RuntimeDashboard
        :dashboard="runtimeDashboard"
        :loading="pageLoading.runtime"
        @refresh="loadRuntimeDashboard"
      />
    </div>

    <div v-if="activeMenu === 'rules'">
      <!-- <StatusCards :status="status" /> -->

      <ListenerTaskTable
        :tasks="listenerTasks"
        :events="listenerTaskLogs"
        :loading="pageLoading.listenerTasks"
        :logs-loading="pageLoading.listenerLogs"
        @add="openAddListenerTaskDialog"
        @edit="openEditListenerTaskDialog"
        @delete="deleteListenerTaskHandler"
        @start="startListenerTaskHandler"
        @stop="stopListenerTaskHandler"
        @catchup="checkListenerCatchupHandlerV2"
        @refresh-logs="loadListenerTaskLogs"
      />
    </div>

    <div v-if="activeMenu === 'settings'">
      <SendSettingsPanel
        :settings="sendSettings"
        @submit="saveSendSettings"
      />
    </div>

    <div v-if="activeMenu === 'templates'">
      <ContentTemplateTable
        :templates="contentTemplates"
        :loading="pageLoading.templates"
        @add="openAddContentTemplateDialog"
        @edit="openEditContentTemplateDialog"
        @delete="deleteContentTemplateHandler"
        @toggle="toggleContentTemplateHandler"
      />
    </div>

    <div v-if="activeMenu === 'guide'">
      <UserGuide />
    </div>

    <div v-if="activeMenu === 'accounts'">
      <AccountTable
        :accounts="accounts"
        :loading="pageLoading.accounts"
        @add="openAddAccountDialog"
        @login="openAccountLoginDialog"
        @relogin="openAccountReloginDialog"
        @edit="openEditAccountDialog"
        @delete="deleteAccount"
        @toggle="saveAccount"
      />
    </div>

    <div v-if="activeMenu === 'bots'" class="bot-page">
      <BotTable
        :bots="bots"
        :loading="pageLoading.bots"
        @add="openAddBotDialog"
        @edit="openEditBotDialog"
        @delete="deleteBotHandler"
        @toggle="saveBotStatus"
        @test="testBotHandler"
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
      <MyChannelTable :bots="bots" />
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
        @add="openAddCloneTaskDialog"
        @edit="openEditCloneTaskDialog"
        @delete="removeCloneTaskHandler"
        @start="startCloneTaskHandler"
        @pause="pauseCloneTaskHandler"
        @resume="resumeCloneTaskHandler"
        @stop="handleStopCloneTask"
        @toggle-listener="handleToggleCloneListener"
        @refresh-logs="loadCloneTaskLogs"
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
      @update:visible="listenerTaskDialogVisible = $event"
      @submit="submitListenerTask"
    />

    <AccountDialog
      :visible="accountDialogVisible"
      :form="currentAccount"
      :is-edit="isAccountEdit"
      @update:visible="accountDialogVisible = $event"
      @submit="submitAccount"
    />

    <AccountLoginDialog
      :visible="accountLoginDialogVisible"
      :account="loginAccountTarget"
      @update:visible="accountLoginDialogVisible = $event"
      @success="handleAccountLoginSuccess"
    />

    <BotDialog
      :visible="botDialogVisible"
      :form="currentBot"
      :is-edit="isBotEdit"
      @update:visible="botDialogVisible = $event"
      @submit="submitBot"
    />

    <BotBindingDialog
      :visible="botBindingDialogVisible"
      :form="currentBotBinding"
      :bots="bots"
      :is-edit="isBotBindingEdit"
      @update:visible="botBindingDialogVisible = $event"
      @submit="submitBotBinding"
    />

    <ContentTemplateDialog
      :visible="contentTemplateDialogVisible"
      :form="currentContentTemplate"
      :is-edit="isContentTemplateEdit"
      @update:visible="contentTemplateDialogVisible = $event"
      @submit="submitContentTemplate"
    />
    </MainLayout>

    <CloneTaskDialog
      :visible="cloneTaskDialogVisible"
      :form="currentCloneTask"
      :is-edit="isCloneTaskEdit"
      :bots="bots"
      :accounts="accounts"
      :templates="contentTemplates"
      @update:visible="cloneTaskDialogVisible = $event"
      @submit="submitCloneTask"
    />
  </div>
</template>

<script setup>
import { ElMessage, ElMessageBox } from "element-plus"
import { ref, reactive, onMounted, onUnmounted } from "vue"

import MainLayout from "./layouts/MainLayout.vue"
import StatusCards from "./components/StatusCards.vue"
import ListenerTaskTable from "./components/ListenerTaskTable.vue"
import ListenerTaskDialog from "./components/ListenerTaskDialog.vue"
import SendSettingsPanel from "./components/SendSettingsPanel.vue"
import UserGuide from "./components/UserGuide.vue"
import LoginPanel from "./components/LoginPanel.vue"
import ContentTemplateTable from "./components/ContentTemplateTable.vue"
import ContentTemplateDialog from "./components/ContentTemplateDialog.vue"

import AccountTable from "./components/AccountTable.vue"
import AccountDialog from "./components/AccountDialog.vue"
import AccountLoginDialog from "./components/AccountLoginDialog.vue"

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
  createAccount,
  updateAccount,
  removeAccount,
} from "./api/accounts"

import {
  getBots,
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
  getSendSettings,
  updateSendSettings,
} from "./api/settings"

import {
  getListenerTasks,
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



const status = ref({})
const isAuthenticated = ref(Boolean(localStorage.getItem("admin_token")))
const rules = ref([])
const listenerTasks = ref([])
const listenerTaskLogs = ref([])
const accounts = ref([])
const bots = ref([])
const botBindings = ref([])
const cloneTasks = ref([])
const cloneTaskLogs = ref([])
const contentTemplates = ref([])
const runtimeDashboard = ref({})
const sendSettings = ref({
  global_send_delay: 3,
  send_retry_count: 2,
  send_retry_delay: 5,
})
const pageLoading = reactive({
  listenerTasks: false,
  listenerLogs: false,
  accounts: false,
  bots: false,
  cloneTasks: false,
  cloneLogs: false,
  templates: false,
  runtime: false,
})

const MENU_STORAGE_KEY = "clonebot_active_menu"
const CLONE_TASK_LOG_STORAGE_KEY = "clonebot_clone_task_logs"
const LISTENER_TASK_LOG_STORAGE_KEY = "clonebot_listener_task_logs"
const CLONE_TASK_LOG_LIMIT = 50
const LISTENER_TASK_LOG_LIMIT = 50
const AUTO_REFRESH_INTERVAL = 30 * 60 * 1000
const SEND_LOG_REFRESH_INTERVAL = AUTO_REFRESH_INTERVAL
const SECONDS_PER_MINUTE = 60
const VALID_MENUS = ["home", "rules", "clone", "bots", "my-channels", "bulk-replace", "support", "accounts", "settings", "templates", "guide"]

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

const dialogVisible = ref(false)
const isEdit = ref(false)
const listenerTaskDialogVisible = ref(false)
const isListenerTaskEdit = ref(false)

const accountDialogVisible = ref(false)
const isAccountEdit = ref(false)
const accountLoginDialogVisible = ref(false)
const loginAccountTarget = ref(null)

const botDialogVisible = ref(false)
const isBotEdit = ref(false)

const botBindingDialogVisible = ref(false)
const isBotBindingEdit = ref(false)

const cloneTaskDialogVisible = ref(false)
const isCloneTaskEdit = ref(false)

const contentTemplateDialogVisible = ref(false)
const isContentTemplateEdit = ref(false)

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
  replace_words: "{}",
  footer: "",
  remove_contact_lines: true,
  filter_qr_code: true,
  use_random_head: false,
  use_random_body: false,
  use_random_footer: false,
  selected_head_template_group_id: null,
  selected_body_template_group_id: null,
  selected_footer_template_group_id: null,
  selected_head_template_id: null,
  selected_body_template_id: null,
  selected_footer_template_id: null,
  selected_filter_template_group_id: null,
  selected_link_template_group_id: null,
  album_wait_seconds: 3,
})


const currentAccount = reactive({
  id: null,
  name: "",
  username: "",
  session_path: "",
  proxy: "",
  enabled: true,
  remark: "",
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
  account_id: 1,
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
  selected_head_template_group_id: null,
  selected_body_template_group_id: null,
  selected_footer_template_group_id: null,
  selected_head_template_id: null,
  selected_body_template_id: null,
  selected_footer_template_id: null,
  selected_filter_template_group_id: null,
  selected_link_template_group_id: null,
  enabled: true,
  status: "idle",
  last_message_id: 0,
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


async function loadStatus() {
  const res = await getStatus()
  status.value = res.data
}


async function loadRules() {
  const res = await getRules()
  rules.value = res.data
}

async function loadListenerTasks() {
  pageLoading.listenerTasks = true
  try {
    const res = await getListenerTasks()
    listenerTasks.value = res.data || []
  } finally {
    pageLoading.listenerTasks = false
  }
}


async function loadListenerTaskLogs() {
  pageLoading.listenerLogs = true
  try {
    const res = await getListenerSendEvents(LISTENER_TASK_LOG_LIMIT)
    listenerTaskLogs.value = res.data.events || []
    saveListenerTaskLogs()
  } catch (e) {
    listenerTaskLogs.value = getCachedListenerTaskLogs()
    console.error("加载监听发送缓存失败", e)
  } finally {
    pageLoading.listenerLogs = false
  }
}


function getCachedListenerTaskLogs() {
  try {
    const saved = JSON.parse(
      window.localStorage.getItem(LISTENER_TASK_LOG_STORAGE_KEY) || "[]",
    )

    return Array.isArray(saved)
      ? saved.slice(0, LISTENER_TASK_LOG_LIMIT)
      : []
  } catch {
    return []
  }
}


function saveListenerTaskLogs() {
  window.localStorage.setItem(
    LISTENER_TASK_LOG_STORAGE_KEY,
    JSON.stringify(listenerTaskLogs.value.slice(0, LISTENER_TASK_LOG_LIMIT)),
  )
}


async function loadAccounts() {
  pageLoading.accounts = true
  try {
    const res = await getAccounts()
    accounts.value = res.data
  } finally {
    pageLoading.accounts = false
  }
}


async function loadBots() {
  pageLoading.bots = true
  try {
    const res = await getBots()
    bots.value = res.data
  } finally {
    pageLoading.bots = false
  }
}


async function loadBotBindings() {
  const res = await getBotBindings()
  botBindings.value = res.data
}


async function loadBotPage() {
  await loadBots()
  await loadBotBindings()
}


async function loadCloneTasks() {
  pageLoading.cloneTasks = true
  try {
    const res = await getCloneTasks()
    const tasks = res.data || []

    cloneTasks.value = tasks
  } finally {
    pageLoading.cloneTasks = false
  }
}


function scheduleCloneTaskRefresh() {
  ;[1000, 3000, 6000].forEach((delay) => {
    window.setTimeout(async () => {
      try {
        await loadCloneTasks()
      } catch (e) {
        console.error("刷新克隆任务状态失败", e)
      }
    }, delay)
  })
}


async function loadCloneTaskLogs() {
  pageLoading.cloneLogs = true
  try {
    const res = await getCloneSendEvents(CLONE_TASK_LOG_LIMIT)
    const events = (res.data.events || []).map(mapCloneSendEvent)

    cloneTaskLogs.value = events
    saveCloneTaskLogs()
  } catch (e) {
    cloneTaskLogs.value = getCachedCloneTaskLogs()
    console.error("加载克隆任务缓存失败", e)
  } finally {
    pageLoading.cloneLogs = false
  }
}


function getCachedCloneTaskLogs() {
  try {
    const saved = JSON.parse(
      window.localStorage.getItem(CLONE_TASK_LOG_STORAGE_KEY) || "[]",
    )

    return Array.isArray(saved)
      ? saved.slice(-CLONE_TASK_LOG_LIMIT)
      : []
  } catch {
    return []
  }
}


function saveCloneTaskLogs() {
  window.localStorage.setItem(
    CLONE_TASK_LOG_STORAGE_KEY,
    JSON.stringify(cloneTaskLogs.value.slice(0, CLONE_TASK_LOG_LIMIT)),
  )
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
  const res = await getSendSettings()
  sendSettings.value = res.data
}


async function loadContentTemplates() {
  pageLoading.templates = true
  try {
    const res = await getContentTemplates()
    contentTemplates.value = res.data || []
  } finally {
    pageLoading.templates = false
  }
}


async function loadRuntimeDashboard() {
  pageLoading.runtime = true
  try {
    const res = await getRuntimeDashboard()
    runtimeDashboard.value = res.data || {}
  } finally {
    pageLoading.runtime = false
  }
}


async function handleMenuChange(menu) {
  if (!VALID_MENUS.includes(menu)) {
    menu = "home"
  }

  activeMenu.value = menu
  window.localStorage.setItem(MENU_STORAGE_KEY, menu)

  if (menu === "home") {
    await loadRuntimeDashboard()
  }

  if (menu === "rules") {
    await loadStatus()
    await loadAccounts()
    await loadBots()
    await loadContentTemplates()
    await loadListenerTasks()
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
    await loadBots()
  }

  if (menu === "clone") {
    await loadBots()
    await loadCloneTasks()
    await loadCloneTaskLogs()
    await loadContentTemplates()
  }

  if (menu === "settings") {
    await loadSendSettings()
  }

  if (menu === "templates") {
    await loadContentTemplates()
  }
}


// =========================
// 内容模板规则
// =========================

function resetCurrentContentTemplate() {
  Object.assign(currentContentTemplate, {
    id: null,
    name: "",
    type: "footer",
    enabled: true,
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


function openAddContentTemplateDialog() {
  resetCurrentContentTemplate()
  isContentTemplateEdit.value = false
  contentTemplateDialogVisible.value = true
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

  if (!["head", "body", "footer", "filter", "link"].includes(currentContentTemplate.type)) {
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
  await updateContentTemplateRule(row.id, {
    enabled: value,
  })

  ElMessage.success(value ? "模板已启用" : "模板已停用")
  await loadContentTemplates()
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
    replace_words: "{}",
    footer: "",
    remove_contact_lines: true,
    filter_qr_code: true,
    use_random_head: false,
    use_random_body: false,
    use_random_footer: false,
    selected_head_template_group_id: null,
    selected_body_template_group_id: null,
    selected_footer_template_group_id: null,
    selected_head_template_id: null,
    selected_body_template_id: null,
    selected_footer_template_id: null,
    selected_filter_template_group_id: null,
    selected_link_template_group_id: null,
    album_wait_seconds: 3,
  })
}


async function openAddListenerTaskDialog() {
  await loadBots()
  await loadAccounts()
  await loadListenerTasks()
  await loadContentTemplates()
  resetCurrentListenerTask()
  isListenerTaskEdit.value = false
  listenerTaskDialogVisible.value = true
}


async function openEditListenerTaskDialog(row) {
  await loadBots()
  await loadContentTemplates()
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
    replace_words: row.replace_words || "{}",
    footer: row.footer || "",
    remove_contact_lines: row.remove_contact_lines ?? true,
    filter_qr_code: row.filter_qr_code ?? true,
    use_random_head: row.use_random_head ?? false,
    use_random_body: row.use_random_body ?? false,
    use_random_footer: row.use_random_footer ?? false,
    selected_head_template_group_id: normalizeTemplateId(row.selected_head_template_group_id),
    selected_body_template_group_id: normalizeTemplateId(row.selected_body_template_group_id),
    selected_footer_template_group_id: normalizeTemplateId(row.selected_footer_template_group_id),
    selected_head_template_id: normalizeTemplateId(row.selected_head_template_id),
    selected_body_template_id: normalizeTemplateId(row.selected_body_template_id),
    selected_footer_template_id: normalizeTemplateId(row.selected_footer_template_id),
    selected_filter_template_group_id: normalizeTemplateId(row.selected_filter_template_group_id),
    selected_link_template_group_id: normalizeTemplateId(row.selected_link_template_group_id),
    album_wait_seconds: toPositiveNumber(row.album_wait_seconds, 3),
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

  const payload = {
    name: currentListenerTask.name,
    source_channel: sourceChannels[0],
    target_channels: JSON.stringify(targetChannels),
    account_id: toPositiveNumber(currentListenerTask.account_id, 1),
    bot_id: normalizeTemplateId(currentListenerTask.bot_id),
    enabled: currentListenerTask.enabled,
    status: currentListenerTask.enabled ? "running" : "stopped",
    blocked_keywords: currentListenerTask.blocked_keywords || "[]",
    replace_words: currentListenerTask.replace_words || "{}",
    footer: "",
    remove_contact_lines: currentListenerTask.remove_contact_lines,
    filter_qr_code: currentListenerTask.filter_qr_code,
    use_random_head: currentListenerTask.use_random_head,
    use_random_body: currentListenerTask.use_random_body,
    use_random_footer: currentListenerTask.use_random_footer,
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
    album_wait_seconds: toPositiveNumber(currentListenerTask.album_wait_seconds, 3),
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
  await loadStatus()
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
  await loadStatus()
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


async function checkListenerCatchupHandlerV2(id) {
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
  } catch {
    await loadListenerTaskLogs()
    return
  }

  await loadListenerTaskLogs()
  await loadListenerTasks()
}

// 旧监听规则兼容
// =========================

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

  await loadStatus()
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

  await loadStatus()
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

  await loadStatus()
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
  currentAccount.proxy = ""
  currentAccount.enabled = true
  currentAccount.remark = ""
}


function openAddAccountDialog() {
  resetCurrentAccount()
  isAccountEdit.value = false
  accountDialogVisible.value = true
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
  Object.assign(currentAccount, formData)

  if (!currentAccount.name || !currentAccount.session_path) {
    ElMessage.error("账号名称和 Session 路径不能为空")
    return
  }

  if (isAccountEdit.value) {
    await updateAccount(currentAccount.id, {
      name: currentAccount.name,
      username: currentAccount.username,
      session_path: currentAccount.session_path,
      proxy: currentAccount.proxy,
      enabled: currentAccount.enabled,
      remark: currentAccount.remark,
    })

    ElMessage.success("账号保存成功")
  } else {
    await createAccount({
      name: currentAccount.name,
      username: currentAccount.username,
      session_path: currentAccount.session_path,
      proxy: currentAccount.proxy,
      remark: currentAccount.remark,
    })

    ElMessage.success("账号添加成功")
  }

  accountDialogVisible.value = false
  await loadAccounts()
}


async function handleAccountLoginSuccess() {
  await loadAccounts()
}


async function saveAccount(row) {
  await updateAccount(row.id, {
    name: row.name,
    username: row.username,
    session_path: row.session_path,
    proxy: row.proxy,
    enabled: row.enabled,
    remark: row.remark,
  })

  ElMessage.success("账号状态已更新")
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

  if (isBotEdit.value) {
    await updateBot(currentBot.id, payload)
    ElMessage.success("Bot 保存成功")
  } else {
    await createBot(payload)
    ElMessage.success("Bot 添加成功")
  }

  botDialogVisible.value = false

  await loadBots()
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
    console.error(e)
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
    account_id: 1,
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
    selected_head_template_group_id: null,
    selected_body_template_group_id: null,
    selected_footer_template_group_id: null,
    selected_head_template_id: null,
    selected_body_template_id: null,
    selected_footer_template_id: null,
    selected_filter_template_group_id: null,
    selected_link_template_group_id: null,
    enabled: true,
    status: "idle",
    last_message_id: 0,
  })
}


async function openAddCloneTaskDialog() {
  await loadBots()
  await loadAccounts()
  await loadContentTemplates()
  resetCurrentCloneTask()
  isCloneTaskEdit.value = false
  cloneTaskDialogVisible.value = true
}


async function openEditCloneTaskDialog(row) {
  await loadBots()
  await loadAccounts()
  await loadContentTemplates()
  Object.assign(currentCloneTask, {
    id: row.id,
    name: row.name || "",
    source_channel: row.source_channel || "",
    target_channels: row.target_channels || "[]",
    account_id: toPositiveNumber(row.account_id, 1),
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
    selected_head_template_group_id: normalizeTemplateId(row.selected_head_template_group_id),
    selected_body_template_group_id: normalizeTemplateId(row.selected_body_template_group_id),
    selected_footer_template_group_id: normalizeTemplateId(row.selected_footer_template_group_id),
    selected_head_template_id: normalizeTemplateId(row.selected_head_template_id),
    selected_body_template_id: normalizeTemplateId(row.selected_body_template_id),
    selected_footer_template_id: normalizeTemplateId(row.selected_footer_template_id),
    selected_filter_template_group_id: normalizeTemplateId(row.selected_filter_template_group_id),
    selected_link_template_group_id: normalizeTemplateId(row.selected_link_template_group_id),
    enabled: row.enabled ?? true,
    status: row.status || "idle",
    last_message_id: row.last_message_id || 0,
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
    account_id: toPositiveNumber(currentCloneTask.account_id, 1),
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
  await loadListenerTasks()
  await loadStatus()
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
  await loadListenerTasks()
  await loadStatus()
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
  const payload = {
    global_send_delay: toNonNegativeNumber(formData.global_send_delay, 3),
    send_retry_count: toNonNegativeNumber(formData.send_retry_count, 2),
    send_retry_delay: toNonNegativeNumber(formData.send_retry_delay, 5),
  }

  const res = await updateSendSettings(payload)
  sendSettings.value = res.data
  ElMessage.success("发送设置已保存")
}


const handleToggleCloneListener = async (row, value) => {
  try {
    await updateCloneTask(row.id, {
      enable_listener: value,
    })

    ElMessage.success(value ? "已开启实时监听" : "已关闭实时监听")

    await loadCloneTasks()
    await loadListenerTasks()
    await loadStatus()
  } catch (e) {
    console.error(e)
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

async function handleLogin(token) {
  localStorage.setItem("admin_token", token)
  isAuthenticated.value = true
  ElMessage.success("登录成功")
  window.location.reload()
}


onMounted(async () => {
  if (!isAuthenticated.value) {
    return
  }

  loadCloneTaskLogs()
  loadListenerTaskLogs()
  await handleMenuChange(activeMenu.value)
  await loadCloneTasks()
  await loadListenerTasks()
  await loadSendSettings()
  await loadContentTemplates()

  cloneRefreshTimer = setInterval(async () => {
    try {
      await loadCloneTasks()
    } catch (e) {
      console.error("自动刷新克隆任务失败", e)
    }
  }, AUTO_REFRESH_INTERVAL)

  cloneLogRefreshTimer = setInterval(async () => {
    try {
      if (activeMenu.value === "clone") {
        await loadCloneTaskLogs()
      }

      if (activeMenu.value === "rules") {
        await loadListenerTaskLogs()
      }
    } catch (e) {
      console.error("自动刷新发送缓存失败", e)
    }
  }, SEND_LOG_REFRESH_INTERVAL)

})


onUnmounted(() => {
  if (cloneRefreshTimer) {
    clearInterval(cloneRefreshTimer)
    cloneRefreshTimer = null
  }

  if (cloneLogRefreshTimer) {
    clearInterval(cloneLogRefreshTimer)
    cloneLogRefreshTimer = null
  }

})
</script>

<style>
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
