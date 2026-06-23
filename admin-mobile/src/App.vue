<template>
  <div v-if="!authenticated" class="login-page">
    <div class="login-card">
      <div class="login-title">移动运营台</div>
      <div class="login-subtitle">请输入后台密码，登录后可在手机上处理常用运营动作。</div>
      <el-form @submit.prevent="handleLogin">
        <el-form-item>
          <el-input
            v-model="password"
            type="password"
            size="large"
            show-password
            placeholder="后台密码"
            @keyup.enter="handleLogin"
          />
        </el-form-item>
        <el-button type="primary" size="large" :loading="loginLoading" style="width: 100%" @click="handleLogin">
          登录
        </el-button>
      </el-form>
    </div>
  </div>

  <MobileLayout v-else :active="activeTab" @change="changeTab" @refresh="loadActive">
    <HomePage
      v-if="activeTab === 'home'"
      :status="status"
      :dashboard="dashboard"
      :loading="loading.home"
    />

    <ListPage
      v-else-if="activeTab === 'listeners'"
      title="监听任务"
      placeholder="搜索任务名 / 源频道 / 目标频道 / https://t.me/..."
      empty-title="暂无监听任务"
      :keyword="keyword.listeners"
      :items="filteredListeners"
      :loading="loading.listeners"
      @update:keyword="keyword.listeners = $event"
    >
      <template #actions>
        <el-button size="small" type="primary" @click="openCreate('listener')">新增</el-button>
        <el-button size="small" plain @click="showLogs('listener')">日志</el-button>
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
          <el-button size="small" type="primary" plain @click="openEdit('listener', item)">编辑</el-button>
          <el-button size="small" :type="item.enabled ? 'warning' : 'success'" plain @click="toggleListener(item)">
            {{ item.enabled ? "停止" : "启动" }}
          </el-button>
          <el-button size="small" plain @click="catchupListener(item)">补齐</el-button>
          <el-button size="small" type="danger" plain @click="removeItem('listener', item)">删除</el-button>
        </TaskCard>
      </template>
    </ListPage>

    <ListPage
      v-else-if="activeTab === 'clones'"
      title="克隆任务"
      placeholder="搜索任务名 / 源频道 / 目标频道 / https://t.me/..."
      empty-title="暂无克隆任务"
      :keyword="keyword.clones"
      :items="filteredClones"
      :loading="loading.clones"
      @update:keyword="keyword.clones = $event"
    >
      <template #actions>
        <el-button size="small" type="primary" @click="openCreate('clone')">新增</el-button>
        <el-button size="small" plain @click="showLogs('clone')">日志</el-button>
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
          <el-button size="small" type="primary" plain @click="openEdit('clone', item)">编辑</el-button>
          <el-button size="small" type="success" plain @click="runAction(() => startCloneTask(item.id), '已启动克隆任务', loadClones)">启动</el-button>
          <el-button size="small" type="warning" plain @click="runAction(() => pauseCloneTask(item.id), '已暂停克隆任务', loadClones)">暂停</el-button>
          <el-button size="small" plain @click="runAction(() => resumeCloneTask(item.id), '已继续克隆任务', loadClones)">继续</el-button>
          <el-button size="small" type="danger" plain @click="runAction(() => stopCloneTask(item.id), '已停止克隆任务', loadClones)">停止</el-button>
          <el-button size="small" type="danger" plain @click="removeItem('clone', item)">删除</el-button>
        </TaskCard>
      </template>
    </ListPage>

    <ListPage
      v-else-if="activeTab === 'channels'"
      title="我的频道"
      placeholder="搜索频道名 / username / 分组 / https://t.me/..."
      empty-title="暂无频道"
      :keyword="keyword.channels"
      :items="filteredChannels"
      :loading="loading.channels"
      @update:keyword="keyword.channels = $event"
    >
      <template #actions>
        <el-button size="small" type="primary" @click="openCreate('channel')">新增</el-button>
        <el-button size="small" plain @click="batchCheckChannels">批量检测</el-button>
      </template>
      <template #default="{ item }">
        <TaskCard
          :title="item.title || item.username || `频道 #${item.id}`"
          :subtitle="item.username || item.chat_id"
          :status="item.status"
          :meta="[
            ['频道 ID', item.id],
            ['分组', compactText(item.group_name)],
            ['绑定 Bot', compactText(item.bot_name || item.bot_id)],
            ['投放状态', compactText(item.delivery_status)],
            ['收录状态', compactText(item.collection_status)],
            ['chat_id', compactText(item.chat_id)],
            ['频道类型', compactText(item.channel_type)],
            ['成员数', compactText(item.member_count)],
            ['创建者', compactText(item.creator_username || item.creator_name || item.creator_user_id)],
            ['最后检测', formatDate(item.last_checked_at || item.checked_at)],
            ['克隆状态', compactText(item.clone_status)],
            ['备注', compactText(item.remark)],
          ]"
        >
          <el-button size="small" type="primary" plain @click="openEdit('channel', item)">编辑</el-button>
          <el-button size="small" plain @click="checkChannel(item)">检测</el-button>
          <el-button size="small" type="danger" plain @click="removeItem('channel', item)">删除</el-button>
        </TaskCard>
      </template>
    </ListPage>

    <MorePage
      v-else
      :page="morePage"
      :bots="filteredBots"
      :support-bots="filteredSupportBots"
      :templates="filteredTemplates"
      :accounts="filteredAccounts"
      :settings="sendSettings"
      :loading="loading"
      :keyword="keyword"
      @select="morePage = $event"
      @update-keyword="updateKeyword"
      @edit="openEdit"
      @delete="removeItem"
      @test-bot="testBotAction"
      @test-support="testSupportAction"
      @toggle-account="toggleAccount"
      @toggle-bot="toggleBot"
      @toggle-support="toggleSupportBot"
      @toggle-template="toggleTemplate"
      @save-settings="saveMobileSendSettings"
      @create="openCreate"
      @login-account="openAccountLogin"
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
        @cancel="editVisible = false"
        @save="saveEdit"
        @upload-media="uploadWelcomeMedia"
        @clear-media="clearWelcomeMedia"
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
        @cancel="accountLoginVisible = false"
        @start="startAccountLoginFlow"
        @verify="verifyAccountLoginFlow"
      />
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

    <el-drawer
      v-model="logVisible"
      class="form-sheet log-sheet"
      direction="btt"
      size="88%"
      :title="logTitle"
      destroy-on-close
    >
      <LogDrawer
        :type="logType"
        :items="filteredLogItems"
        :keyword="logKeyword"
        :loading="logLoading"
        @update:keyword="logKeyword = $event"
        @refresh="showLogs(logType)"
      />
    </el-drawer>
  </MobileLayout>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, reactive, ref, resolveComponent } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import { ArrowDownBold, ArrowUpBold } from "@element-plus/icons-vue"
import MobileLayout from "./components/MobileLayout.vue"
import StatusPill from "./components/StatusPill.vue"
import EmptyState from "./components/EmptyState.vue"
import { getErrorMessage, getToken, setToken } from "./api/client"
import {
  catchupListenerTask,
  checkListenerCatchup,
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
  getAccounts,
  getBots,
  getCloneTasks,
  getCloneSendEvents,
  getContentTemplates,
  getContentTemplateRules,
  getListenerTasks,
  getListenerSendEvents,
  getMyChannels,
  getRuntimeDashboard,
  getSendSettings,
  getStatus,
  getSupportBots,
  loginAdmin,
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
import { matchesSearch } from "./utils/search"

const authenticated = ref(Boolean(getToken()))
const password = ref("")
const loginLoading = ref(false)
const activeTab = ref(window.localStorage.getItem("mobile_active_tab") || "home")
const morePage = ref("menu")
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
const logVisible = ref(false)
const logLoading = ref(false)
const logType = ref("listener")
const logKeyword = ref("")
const logItems = ref([])

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
    listener: "编辑监听任务",
    clone: "编辑克隆任务",
    channel: "编辑频道",
    bot: "编辑 Bot",
    support: "编辑客服机器人",
    template: "编辑内容模板",
    account: "编辑账号",
  }
  return map[editType.value] || "编辑"
})

const filteredListeners = computed(() => filterItems(listeners.value, keyword.listeners, ["name", "source_channel", "target_channels", "status"]))
const filteredClones = computed(() => filterItems(clones.value, keyword.clones, ["name", "source_channel", "target_channels", "status"]))
const filteredChannels = computed(() => filterItems(channels.value, keyword.channels, ["title", "username", "group_name", "remark", "status"]))
const filteredBots = computed(() => filterItems(bots.value, keyword.bots, ["name", "username", "remark", "last_error"]))
const filteredSupportBots = computed(() => filterItems(supportBots.value, keyword.support, ["name", "bot_username", "support_group_chat_id", "last_error"]))
const templateGroups = computed(() => templates.value
  .filter((template) => !template.parent_id)
  .map((group) => ({
    ...group,
    items: templates.value.filter((template) => template.parent_id === group.id),
  }))
  .sort((a, b) => (b.id || 0) - (a.id || 0)))
const filteredTemplates = computed(() => filterItems(templateGroups.value, keyword.templates, ["name", "type", "content", "remark", "items"]))
const filteredAccounts = computed(() => filterItems(accounts.value, keyword.accounts, ["name", "username", "phone", "remark"]))
const logTitle = computed(() => logType.value === "clone" ? "克隆日志" : "监听日志")
const filteredLogItems = computed(() => filterLogItems(logItems.value, logKeyword.value))

function pickList(data) {
  if (Array.isArray(data)) return data
  if (Array.isArray(data?.items)) return data.items
  if (Array.isArray(data?.data)) return data.data
  return []
}

function filterItems(items, value, fields) {
  const text = String(value || "").trim()
  if (!text) return items
  return items.filter((item) =>
    matchesSearch(fields.map((field) => item?.[field]), text),
  )
}

function filterLogItems(items, value) {
  const text = String(value || "").trim()
  if (!text) return items
  return (items || []).filter((item) =>
    matchesSearch([
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
    ], text),
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

async function handleLogin() {
  if (!password.value.trim()) {
    ElMessage.warning("请输入后台密码")
    return
  }
  loginLoading.value = true
  try {
    const res = await loginAdmin(password.value.trim())
    const token = res.data?.token
    if (!token) throw new Error("登录成功但后端没有返回 token")
    setToken(token)
    authenticated.value = true
    password.value = ""
    await loadInitial()
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "登录失败"))
  } finally {
    loginLoading.value = false
  }
}

function changeTab(tab) {
  activeTab.value = tab
  window.localStorage.setItem("mobile_active_tab", tab)
  loadActive()
}

async function loadInitial() {
  await Promise.allSettled([
    loadHome(),
    loadListeners(),
    loadClones(),
    loadChannels(),
    loadBots(),
    loadAccounts(),
    loadSendSettings(),
    loadTemplates(),
    loadSupportBots(),
  ])
}

async function loadActive() {
  if (activeTab.value === "home") return loadHome()
  if (activeTab.value === "listeners") return loadListeners()
  if (activeTab.value === "clones") return loadClones()
  if (activeTab.value === "channels") return loadChannels()
  if (morePage.value === "bots") return loadBots()
  if (morePage.value === "support") return loadSupportBots()
  if (morePage.value === "settings") return Promise.allSettled([loadSendSettings(), loadTemplates()])
  if (morePage.value === "accounts") return loadAccounts()
  return Promise.allSettled([loadBots(), loadSupportBots(), loadTemplates(), loadAccounts()])
}

async function withLoading(key, fn) {
  loading[key] = true
  try {
    await fn()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  } finally {
    loading[key] = false
  }
}

function loadHome() {
  return withLoading("home", async () => {
    const [statusRes, dashboardRes] = await Promise.all([getStatus(), getRuntimeDashboard()])
    status.value = statusRes.data || {}
    dashboard.value = dashboardRes.data || {}
  })
}

function loadListeners() {
  return withLoading("listeners", async () => {
    listeners.value = pickList((await getListenerTasks()).data)
  })
}

function loadClones() {
  return withLoading("clones", async () => {
    clones.value = pickList((await getCloneTasks()).data)
  })
}

function loadChannels() {
  return withLoading("channels", async () => {
    channels.value = pickList((await getMyChannels()).data)
  })
}

function loadBots() {
  return withLoading("bots", async () => {
    bots.value = pickList((await getBots()).data)
  })
}

function loadSupportBots() {
  return withLoading("support", async () => {
    supportBots.value = pickList((await getSupportBots()).data)
  })
}

function loadTemplates() {
  return withLoading("templates", async () => {
    templates.value = pickList((await getContentTemplates()).data)
  })
}

function loadSendSettings() {
  return withLoading("settings", async () => {
    sendSettings.value = (await getSendSettings()).data || sendSettings.value
  })
}

function loadAccounts() {
  return withLoading("accounts", async () => {
    accounts.value = pickList((await getAccounts()).data)
  })
}

function openEdit(type, row) {
  editType.value = type
  Object.keys(editForm).forEach((key) => delete editForm[key])
  Object.assign(editForm, JSON.parse(JSON.stringify(row || {})))
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

function openCreate(type) {
  editType.value = type
  Object.keys(editForm).forEach((key) => delete editForm[key])
  Object.assign(editForm, defaultForm(type))
  editVisible.value = true
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
      filter_qr_code: true,
      album_wait_seconds: 3,
    },
    clone: {
      name: "",
      source_channel: "",
      start_message_url: "",
      end_message_url: "",
      target_channels: "[]",
      account_id: firstAccount.id || 1,
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
      filter_qr_code: true,
      status: "idle",
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
      prompt_check_after_save: true,
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

function payloadFor(type) {
  const data = { ...editForm }
  delete data.prompt_check_after_save
  if (["listener", "clone"].includes(type)) {
    data.target_channels = normalizeJsonList(data.target_channels)
    data.blocked_keywords = normalizeJsonList(data.blocked_keywords)
    data.replace_words = normalizeJsonObject(data.replace_words)
  }
  if (type === "listener") {
    data.listen_required_keywords = normalizeJsonList(data.listen_required_keywords)
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
  return data
}

async function saveEdit() {
  saving.value = true
  try {
    const payload = payloadFor(editType.value)
    const isEdit = Boolean(editForm.id)
    let result = null
    if (editType.value === "listener") {
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
    ElMessage.success("保存成功")
    editVisible.value = false
    await reloadType(editType.value)
    if (editType.value === "channel" && !isEdit && editForm.prompt_check_after_save) {
      const created = result?.data || {}
      const id = created.id || created.item?.id
      if (id) {
        try {
          await ElMessageBox.confirm("频道已保存，是否立即检测频道信息？", "频道检测", {
            confirmButtonText: "立即检测",
            cancelButtonText: "稍后",
            type: "info",
          })
          await checkChannel({ id })
        } catch (error) {
          if (error !== "cancel") {
            ElMessage.error(getErrorMessage(error, "检测失败"))
          }
        }
      }
    }
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "保存失败"))
  } finally {
    saving.value = false
  }
}

async function reloadType(type) {
  if (type === "listener") return loadListeners()
  if (type === "clone") return loadClones()
  if (type === "channel") return loadChannels()
  if (type === "bot") return loadBots()
  if (type === "support") return loadSupportBots()
  if (type === "template") return loadTemplates()
  if (type === "account") return loadAccounts()
}

async function runAction(fn, successText, refreshFn) {
  try {
    await fn()
    ElMessage.success(successText)
    if (refreshFn) await refreshFn()
  } catch (error) {
    ElMessage.error(getErrorMessage(error))
  }
}

async function toggleListener(item) {
  const fn = item.enabled ? stopListenerTask : startListenerTask
  await runAction(() => fn(item.id), item.enabled ? "已停止监听任务" : "已启动监听任务", loadListeners)
}

async function catchupListener(item) {
  try {
    const res = await checkListenerCatchup(item.id)
    const count = res.data?.missing_count ?? res.data?.catchup_count ?? res.data?.count ?? 0
    await ElMessageBox.confirm(`检测到可补齐 ${count} 条内容，是否加入排队列表？`, "一键补齐", {
      confirmButtonText: "加入队列",
      cancelButtonText: "取消",
      type: count > 0 ? "warning" : "info",
    })
    await catchupListenerTask(item.id, { background: true })
    ElMessage.success("补齐任务已加入首页排队列表")
    await loadHome()
  } catch (error) {
    if (error === "cancel") return
    ElMessage.error(getErrorMessage(error, "补齐失败"))
  }
}

async function checkChannel(item) {
  try {
    const res = await checkMyChannel(item.id)
    detailText.value = JSON.stringify(res.data || {}, null, 2)
    detailVisible.value = true
    await loadChannels()
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "检测失败"))
  }
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
  logVisible.value = true
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
  return runAction(() => updateAccount(item.id, { ...item, enabled: !item.enabled }), item.enabled ? "已停用账号" : "已启用账号", loadAccounts)
}

function toggleBot(item) {
  return runAction(() => updateBot(item.id, { ...item, enabled: !item.enabled }), item.enabled ? "已停用 Bot" : "已启用 Bot", loadBots)
}

function toggleSupportBot(item) {
  const next = !item.polling_enabled
  return runAction(() => updateSupportBot(item.id, { ...item, polling_enabled: next }), next ? "已启用客服机器人" : "已停用客服机器人", loadSupportBots)
}

function toggleTemplate(item) {
  return runAction(() => updateContentTemplateRule(item.id, { enabled: !item.enabled }), item.enabled ? "已停用模板" : "已启用模板", loadTemplates)
}

async function saveMobileSendSettings(payload) {
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

onMounted(() => {
  if (authenticated.value) {
    loadInitial()
  }
})

const HomePage = defineComponent({
  props: {
    status: Object,
    dashboard: Object,
    loading: Boolean,
  },
  setup(props) {
    return () => {
      const stats = props.dashboard?.stats || {}
      const queue = props.dashboard?.queue || {}
      const waiting = asArray(queue.waiting).slice(0, 10)
      const recent = asArray(queue.recent).slice(0, 10)
      return h("div", { class: "page" }, [
        h("section", { class: "section" }, [
          h("div", { class: "metric-grid" }, [
            metric("系统状态", props.status?.status || "unknown"),
            metric("排队任务", stats.waiting_count || 0),
            metric("克隆运行中", stats.clone_running_count || 0),
            metric("启用监听", stats.listener_enabled_count || 0),
          ]),
        ]),
        sectionList("排队任务", waiting, "暂无排队任务", (item) =>
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
        ),
        sectionList("最近完成", recent, "暂无最近完成记录", (item) =>
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
        ),
      ])
    }
  },
})

const ListPage = defineComponent({
  props: {
    title: String,
    placeholder: String,
    emptyTitle: String,
    keyword: String,
    items: Array,
    loading: Boolean,
  },
  emits: ["update:keyword"],
  setup(props, { emit, slots }) {
    return () => h("div", [
      h("div", { class: "search-bar" }, [
        h(resolve("el-input"), {
          modelValue: props.keyword,
          "onUpdate:modelValue": (value) => emit("update:keyword", value),
          placeholder: props.placeholder,
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
            : h(EmptyState, { title: props.emptyTitle }),
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
            "aria-label": expanded.value ? "鏀惰捣" : "灞曞紑",
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
    type: String,
    items: Array,
    keyword: String,
    loading: Boolean,
  },
  emits: ["update:keyword", "refresh"],
  setup(props, { emit }) {
    return () => h("div", { class: "log-drawer" }, [
      h("div", { class: "search-bar" }, [
        h(resolve("el-input"), {
          modelValue: props.keyword,
          "onUpdate:modelValue": (value) => emit("update:keyword", value),
          placeholder: props.type === "clone" ? "搜索任务 / 目标 / 消息 / 错误" : "搜索任务 / 频道 / 消息 / 错误",
          clearable: true,
        }),
        h(resolve("el-button"), {
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
          : h(EmptyState, { title: props.type === "clone" ? "暂无克隆日志" : "暂无监听日志" }),
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
    page: String,
    bots: Array,
    supportBots: Array,
    templates: Array,
    accounts: Array,
    settings: Object,
    loading: Object,
    keyword: Object,
  },
  emits: [
    "select",
    "update-keyword",
    "edit",
    "delete",
    "test-bot",
    "test-support",
    "toggle-account",
    "toggle-bot",
    "toggle-support",
    "toggle-template",
    "save-settings",
    "create",
    "login-account",
  ],
  setup(props, { emit }) {
    const entries = [
      ["bots", "Bot 管理", "测试、启用和维护分发 Bot"],
      ["support", "客服机器人", "查看状态、测试和调整欢迎语"],
      ["settings", "系统设置", "发送设置、联系方式和内容规则模板"],
      ["accounts", "账号管理", "查看采集账号和 session 状态"],
    ]
    return () => {
      if (props.page === "menu") {
        return h("div", { class: "page card-list" }, entries.map(([key, title, text]) =>
          h("article", { class: "data-card", onClick: () => emit("select", key) }, [
            h("div", { class: "card-title" }, title),
            h("div", { class: "card-subtitle" }, text),
          ]),
        ))
      }
      const config = {
        bots: ["Bot 管理", "搜索 Bot 名称 / username", "bots", props.bots, props.loading?.bots],
        support: ["客服机器人", "搜索名称 / 群 ID / 错误", "support", props.supportBots, props.loading?.support],
        settings: ["系统设置", "搜索模板名称 / 类型", "templates", props.templates, props.loading?.templates || props.loading?.settings],
        accounts: ["账号管理", "搜索账号 / username / 手机号", "accounts", props.accounts, props.loading?.accounts],
      }[props.page]
      return h("div", [
        h("div", { class: "search-bar" }, [
          h(resolve("el-button"), { plain: true, onClick: () => emit("select", "menu") }, () => "返回"),
          h(resolve("el-input"), {
            style: "margin-top:8px",
            modelValue: props.keyword[config[2]],
            "onUpdate:modelValue": (value) => emit("update-keyword", config[2], value),
            placeholder: config[1],
            clearable: true,
          }),
        ]),
        props.page === "settings"
          ? h("div", { class: "page" }, [
            h("article", { class: "data-card settings-editor" }, [
              h("div", { class: "card-title" }, "发送设置"),
              h(resolve("el-form"), { labelPosition: "top" }, () => [
                h(resolve("el-form-item"), { label: "全局发送间隔秒" }, () => h(resolve("el-input-number"), {
                  modelValue: props.settings?.global_send_delay ?? 3,
                  min: 0,
                  controlsPosition: "right",
                  style: "width:100%",
                  "onUpdate:modelValue": (value) => { props.settings.global_send_delay = value },
                })),
                h(resolve("el-form-item"), { label: "发送异常重试次数" }, () => h(resolve("el-input-number"), {
                  modelValue: props.settings?.send_retry_count ?? 2,
                  min: 0,
                  controlsPosition: "right",
                  style: "width:100%",
                  "onUpdate:modelValue": (value) => { props.settings.send_retry_count = value },
                })),
                h(resolve("el-form-item"), { label: "重试等待秒" }, () => h(resolve("el-input-number"), {
                  modelValue: props.settings?.send_retry_delay ?? 5,
                  min: 0,
                  controlsPosition: "right",
                  style: "width:100%",
                  "onUpdate:modelValue": (value) => { props.settings.send_retry_delay = value },
                })),
                h(resolve("el-button"), {
                  type: "primary",
                  style: "width:100%",
                  onClick: () => emit("save-settings", props.settings),
                }, () => "保存发送设置"),
              ]),
            ]),
          ])
          : null,
        h("div", { class: "page" }, [
          h("div", { class: "section-head" }, [
            h("div", { class: "section-title" }, config[0]),
            h("div", { class: "row-actions" }, [
              props.page === "accounts"
                ? h(resolve("el-button"), { size: "small", type: "primary", onClick: () => emit("login-account", null) }, () => "登录账号")
                : h(resolve("el-button"), { size: "small", type: "primary", onClick: () => emit("create", props.page === "bots" ? "bot" : props.page === "support" ? "support" : "template") }, () => "新增"),
            ]),
          ]),
          config[4]
            ? h(resolve("el-skeleton"), { rows: 6, animated: true })
            : config[3]?.length
              ? h("div", { class: "card-list" }, config[3].map((item) => moreCard(props.page, item, emit)))
              : h(EmptyState, { title: "暂无" + config[0] }),
        ]),
      ])
    }
  },
})

function moreCard(type, item, emit) {
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
      h(resolve("el-button"), { size: "small", type: "primary", plain: true, onClick: () => emit("edit", "bot", item) }, () => "编辑"),
      h(resolve("el-button"), { size: "small", plain: true, onClick: () => emit("test-bot", item) }, () => "测试"),
      h(resolve("el-button"), { size: "small", plain: true, onClick: () => emit("toggle-bot", item) }, () => item.enabled ? "停用" : "启用"),
      h(resolve("el-button"), { size: "small", type: "danger", plain: true, onClick: () => emit("delete", "bot", item) }, () => "删除"),
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
      h(resolve("el-button"), { size: "small", type: "primary", plain: true, onClick: () => emit("edit", "support", item) }, () => "编辑"),
      h(resolve("el-button"), { size: "small", plain: true, onClick: () => emit("test-support", item) }, () => "测试"),
      h(resolve("el-button"), { size: "small", plain: true, onClick: () => emit("toggle-support", item) }, () => item.polling_enabled ? "停用" : "启用"),
      h(resolve("el-button"), { size: "small", type: "danger", plain: true, onClick: () => emit("delete", "support", item) }, () => "删除"),
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
      h(resolve("el-button"), { size: "small", type: "primary", plain: true, onClick: () => emit("edit", "template", item) }, () => "编辑"),
      h(resolve("el-button"), { size: "small", plain: true, onClick: () => emit("toggle-template", item) }, () => item.enabled ? "停用" : "启用"),
      h(resolve("el-button"), { size: "small", type: "danger", plain: true, onClick: () => emit("delete", "template", item) }, () => "删除"),
    ])
  }
  return h(TaskCard, {
    title: item.name || item.username || `账号 #${item.id}`,
    subtitle: item.username || item.phone || "-",
    status: item.enabled ? "enabled" : "disabled",
    enabled: item.enabled,
    meta: [
      ["ID", item.id],
      ["username", item.username],
      ["手机号", item.phone],
      ["启用状态", enabledLabel(item.enabled)],
      ["Session", item.session_path],
      ["代理", item.proxy],
      ["备注", item.remark],
      ["最后错误", item.last_error],
    ],
  }, () => [
    h(resolve("el-button"), { size: "small", type: "primary", plain: true, onClick: () => emit("edit", "account", item) }, () => "编辑"),
    h(resolve("el-button"), { size: "small", plain: true, onClick: () => emit("login-account", item) }, () => "重新登录"),
    h(resolve("el-button"), { size: "small", plain: true, onClick: () => emit("toggle-account", item) }, () => item.enabled ? "停用" : "启用"),
    h(resolve("el-button"), { size: "small", type: "danger", plain: true, onClick: () => emit("delete", "account", item) }, () => "删除"),
  ])
}

const EditForm = defineComponent({
  props: {
    type: String,
    form: Object,
    saving: Boolean,
    bots: Array,
    accounts: Array,
    templates: Array,
    uploading: Boolean,
  },
  emits: ["cancel", "save", "upload-media", "clear-media"],
  setup(props, { emit }) {
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
            title: section.title,
          }))),
          h("div", { class: "form-section-panel" }, [
            h("div", { class: "section-title" }, current?.title || "填写信息"),
            h("div", { class: "section-subtitle" }, current?.tip || ""),
            current?.confirm
              ? renderConfirmSummary(props)
              : h(resolve("el-form"), { labelPosition: "top" }, (current?.fields || []).map((field) =>
                fieldRender(props, emit, field),
              )),
          ]),
          h("div", { class: "form-actions" }, [
            h(resolve("el-button"), {
              disabled: step <= 0,
              onClick: () => { activeStep.value = Math.max(0, step - 1) },
            }, () => "上一步"),
            step < sections.length - 1
              ? h(resolve("el-button"), {
                type: "primary",
                onClick: () => {
                  if (!validateWizardStep(props.type, current, props.form)) return
                  activeStep.value = Math.min(sections.length - 1, step + 1)
                },
              }, () => "下一步")
              : h(resolve("el-button"), {
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
            h(resolve("el-form"), { labelPosition: "top" }, section.fields.map((field) =>
              fieldRender(props, emit, field),
            )),
          ]),
        )),
        h("div", { class: "form-actions" }, [
          h(resolve("el-button"), { onClick: () => emit("cancel") }, () => "取消"),
          h(resolve("el-button"), { type: "primary", loading: props.saving, onClick: () => emit("save") }, () => "保存"),
        ]),
      ])
    }
  },
})

const AccountLoginForm = defineComponent({
  props: {
    account: Object,
    loading: Boolean,
  },
  emits: ["cancel", "start", "verify"],
  setup(props, { emit }) {
    const step = ref(0)
    const loginId = ref("")
    const needPassword = ref(false)
    const form = reactive({
      account_id: props.account?.id || null,
      name: props.account?.name || "",
      phone: props.account?.phone || "",
      session_path: props.account?.session_path || "data/sessions/collector_new",
      proxy: props.account?.proxy || "",
      remark: props.account?.remark || "",
      update_existing: Boolean(props.account?.id),
    })
    const verifyForm = reactive({
      code: "",
      password: "",
    })

    async function start() {
      if (!form.name || !form.phone || !form.session_path) {
        ElMessage.warning("账号名称、手机号、Session 路径不能为空")
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
        loginInput(form, "phone", "手机号"),
        loginInput(form, "session_path", "Session 路径"),
        loginInput(form, "proxy", "代理"),
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
        h(resolve("el-button"), { onClick: () => emit("cancel") }, () => "关闭"),
        step.value === 0
          ? h(resolve("el-button"), { type: "primary", loading: props.loading, onClick: start }, () => "发送验证码")
          : null,
        step.value === 1
          ? h(resolve("el-button"), { type: "primary", loading: props.loading, onClick: verify }, () => needPassword.value ? "提交密码" : "登录")
          : null,
      ]),
    ])
  },
})

function loginInput(target, key, label, type = "text") {
  return h(resolve("el-form-item"), { label }, () => h(resolve("el-input"), {
    modelValue: target[key],
    type: type === "password" ? "password" : type === "textarea" ? "textarea" : "text",
    rows: type === "textarea" ? 3 : undefined,
    placeholder: loginPlaceholder(key),
    showPassword: type === "password",
    "onUpdate:modelValue": (value) => { target[key] = value },
  }))
}

function loginPlaceholder(key) {
  const map = {
    name: "例如：采集账号，方便后台识别",
    phone: "填写 Telegram 手机号，例如 +8613800000000",
    session_path: "可留空自动生成，或填写 data/sessions/xxx",
    proxy: "可留空，例如 socks5://127.0.0.1:7890",
    remark: "可留空，填写这个账号的用途",
    code: "填写 Telegram 收到的验证码",
    password: "填写 Telegram 二步验证密码",
  }
  return map[key] || "请输入内容"
}

function emitAsync(emit, event, payload) {
  return new Promise((resolvePromise) => {
    emit(event, payload, resolvePromise)
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
    channel: {
      basic: [
        ["title", "请填写频道名称"],
        ["username", "请填写频道 username 或链接"],
      ],
    },
    bot: {
      basic: [
        ["name", "请填写 Bot 名称"],
        ["token", "请填写 Bot Token"],
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
  for (const [key, message] of rules) {
    if (!String(form?.[key] || "").trim()) {
      ElMessage.warning(message)
      return false
    }
  }
  if (type === "support" && section?.key === "basic" && !form.bot_id && !String(form.bot_token || "").trim()) {
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
    { key: "content", title: "内容处理", fields: contentFields },
    {
      key: "advanced",
      title: "高级设置",
      tip: "一般不用修改，只有需要随机模板、替换词或相册等待时再打开。",
      fields: [
        { key: "replace_words", label: "替换词", input: "json" },
        { key: "album_wait_seconds", label: "相册等待秒", input: "number" },
        ...randomTemplateFields,
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
        { key: "bot_id", label: "分发 Bot", input: "bot" },
        { key: "single_delay", label: "内容间隔分钟", input: "number" },
        { key: "target_delay", label: "目标间隔秒", input: "number" },
        { key: "enable_listener", label: "完成后进入监听", input: "switch" },
      ],
    },
    { key: "content", title: "内容处理", fields: contentFields },
    {
      key: "advanced",
      title: "高级设置",
      fields: [
        { key: "replace_words", label: "替换词", input: "json" },
        { key: "album_delay", label: "相册等待秒", input: "number" },
        ...randomTemplateFields,
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

  const account = [{
    key: "basic",
    title: "账号信息",
    tip: "新增账号请使用“登录账号”流程；这里主要用于编辑已有账号。",
    fields: [
      { key: "name", label: "账号名称" },
      { key: "username", label: "username" },
      { key: "session_path", label: "Session 路径" },
      { key: "proxy", label: "代理" },
      { key: "remark", label: "备注", input: "textarea" },
      enabled,
    ],
  }]

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
        }, () => h(resolve("el-button"), { loading: props.uploading, plain: true }, () => "上传文件")),
        h(resolve("el-button"), { plain: true, onClick: () => emit("clear-media") }, () => "清空"),
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
        h(resolve("el-button"), {
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
    type: field.input === "textarea" ? "textarea" : "text",
    rows: field.input === "textarea" ? 4 : undefined,
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
        }, () => h(resolve("el-button"), { loading: props.uploading, plain: true }, () => "上传文件")),
        h(resolve("el-button"), { plain: true, onClick: () => emit("clear-media") }, () => "清空"),
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
        h(resolve("el-button"), {
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
  return h(resolve("el-input"), {
    modelValue: displayEditValue(form[field.key], field.input),
    type: field.input === "textarea" ? "textarea" : "text",
    rows: field.input === "textarea" ? 4 : undefined,
    placeholder,
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
    title: "填写频道名称，例如：长沙投放频道",
    username: "填写 @username、频道链接或 chat_id",
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
      label: `${item.name || item.username || "账号"}${item.username ? ` / @${String(item.username).replace(/^@/, "")}` : ""}`,
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

function sectionList(title, items, emptyTitle, render) {
  return h("section", { class: "section" }, [
    h("div", { class: "section-head" }, [h("div", { class: "section-title" }, title)]),
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








