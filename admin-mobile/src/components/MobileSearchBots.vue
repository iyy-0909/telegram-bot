<template>
  <section class="search-page">
    <div v-show="pageVisible">
      <div class="search-header">
        <div>
          <h2>搜索机器人</h2>
          <p>统一管理搜索机器人，并保留频道改投记录。</p>
        </div>
        <el-button circle type="primary" aria-label="新增搜索机器人" title="新增搜索机器人" @click="openBotCreate"><el-icon><Plus /></el-icon></el-button>
      </div>

      <el-tabs v-model="view" stretch>
      <el-tab-pane label="机器人" name="bots">
        <div class="filter-row">
          <el-input v-model="keyword" clearable placeholder="搜索机器人或链接"><template #prefix><el-icon><Search /></el-icon></template></el-input>
        </div>
        <div v-loading="loading" class="card-list">
          <div v-for="bot in visibleBots" :key="bot.id" class="bot-card">
            <div class="card-head">
              <div class="card-title"><strong>{{ bot.name }}</strong><span>{{ bot.username }}</span></div>
              <StatusPill :status="bot.status" />
            </div>
            <dl>
              <div><dt>月活</dt><dd>{{ bot.monthly_active_users ?? "需手动维护" }}</dd></div>
              <div><dt>当前收录</dt><dd>{{ bot.current_channel_count || 0 }}</dd></div>
              <div><dt>拉黑记录</dt><dd>{{ bot.blocked_channel_count || 0 }}</dd></div>
              <div><dt>最后检测</dt><dd>{{ formatDate(bot.last_check_at) }}</dd></div>
            </dl>
            <div class="icon-actions">
              <el-button circle plain aria-label="编辑机器人" title="编辑机器人" @click="openBotEdit(bot)"><el-icon><Edit /></el-icon></el-button>
              <el-button circle plain :loading="checkingId === bot.id" aria-label="检测机器人" title="检测机器人" @click="detect(bot)"><el-icon><Connection /></el-icon></el-button>
              <el-button circle type="danger" plain aria-label="删除机器人" title="删除机器人" @click="removeBot(bot)"><el-icon><Delete /></el-icon></el-button>
            </div>
          </div>
          <EmptyState v-if="!loading && !visibleBots.length" title="暂无搜索机器人" description="点击右上角加号，添加该城市使用的搜索机器人。" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="提交记录" name="records">
        <div class="filter-row">
          <el-input v-model="recordKeyword" clearable placeholder="搜索频道或机器人"><template #prefix><el-icon><Search /></el-icon></template></el-input>
        </div>
        <div v-loading="recordLoading" class="card-list">
          <div v-for="row in visibleRecords" :key="row.id" class="bot-card">
            <div class="card-head"><div class="card-title"><strong>{{ row.channel_title || row.channel_username }}</strong><span>{{ row.search_bot_name }} / {{ row.search_bot_username }}</span></div><el-tag :type="statusType(row.block_status)">{{ statusLabel(row.block_status) }}</el-tag></div>
            <div class="group-line"><el-icon><Location /></el-icon>{{ row.group_name }}</div>
            <dl>
              <div><dt>执行状态</dt><dd>{{ statusLabel(row.submit_status) }}</dd></div>
              <div><dt>审核</dt><dd>{{ statusLabel(row.review_status) }}</dd></div>
              <div><dt>收录</dt><dd>{{ statusLabel(row.collection_status) }}</dd></div>
              <div><dt>当前有效</dt><dd>{{ row.is_current ? "是" : "否" }}</dd></div>
              <div><dt>权限验证</dt><dd>{{ permissionStatusLabel(row.permission_status) }}</dd></div>
              <div><dt>实际权限</dt><dd>{{ adminRightLabels(row.applied_admin_rights || row.admin_rights).join("、") || "最小权限" }}</dd></div>
            </dl>
            <div v-if="row.last_error" class="error-line">{{ row.last_error }}</div>
            <div class="icon-actions">
              <el-button circle type="primary" plain aria-label="更新状态" title="更新状态" @click="openStatus(row)"><el-icon><EditPen /></el-icon></el-button>
              <el-button circle plain aria-label="调整频道权限" title="调整频道权限" @click="openPermissionEdit(row)"><el-icon><Setting /></el-icon></el-button>
            </div>
          </div>
          <EmptyState v-if="!recordLoading && !visibleRecords.length" title="暂无提交记录" description="可由系统提交，也可登记已在 Telegram 手动完成的提交。" />
        </div>
      </el-tab-pane>
      </el-tabs>
    </div>

    <el-drawer v-model="botDrawer" direction="btt" size="92%" :title="editingBot?.id ? '编辑搜索机器人' : '新增搜索机器人'" destroy-on-close>
      <el-form ref="botFormRef" :model="botForm" :rules="botRules" label-position="top">
        <el-form-item label="机器人名称" prop="name"><el-input v-model="botForm.name" placeholder="例如：上海搜群机器人A" /></el-form-item>
        <el-form-item label="机器人 ID" prop="username"><el-input v-model="botForm.username" placeholder="@jisou 或 https://t.me/jisou" /></el-form-item>
        <el-form-item label="默认操作账号（选填）" prop="account_id"><el-select v-model="botForm.account_id" clearable filterable placeholder="不使用系统添加时可留空"><el-option v-for="account in enabledAccounts" :key="account.id" :label="account.name || account.username || `账号 #${account.id}`" :value="account.id" /></el-select><small>该账号必须拥有目标频道的添加成员和添加管理员权限。</small></el-form-item>
        <el-form-item label="月活（人工维护）"><el-input-number v-model="botForm.monthly_active_users" :min="0" /></el-form-item>
        <el-form-item label="状态"><el-select v-model="botForm.status"><el-option label="正常" value="enabled" /><el-option label="已停用" value="disabled" /><el-option label="异常" value="error" /></el-select></el-form-item>
        <el-form-item label="备注"><el-input v-model="botForm.remark" type="textarea" :rows="2" placeholder="记录机器人规则或限制" /></el-form-item>
      </el-form>
      <div class="drawer-actions"><el-button @click="botDrawer = false">取消</el-button><el-button type="primary" :loading="saving" @click="saveBot">保存</el-button></div>
    </el-drawer>

    <el-drawer
      v-model="channelStatusDrawer"
      direction="btt"
      size="92%"
      title="频道提交状态"
      destroy-on-close
      @closed="openPendingSubmit"
    >
      <div class="channel-status-head">
        <div class="card-title">
          <strong>{{ channelStatusChannel?.title || channelStatusChannel?.username || "当前频道" }}</strong>
          <span>{{ channelStatusChannel?.username || channelStatusChannel?.chat_id || "-" }}</span>
        </div>
        <el-tag :type="channelStatusChannel?.collection_status === '已收录' ? 'success' : 'info'">
          {{ channelStatusChannel?.collection_status || "未收录" }}
        </el-tag>
      </div>
      <el-alert
        v-if="channelStatusChannel && !channelStatusChannel.group_name"
        type="warning"
        :closable="false"
        show-icon
        title="当前频道尚未设置分组，设置后才能提交到搜索机器人。"
      />
      <div v-loading="recordLoading" class="channel-status-list">
        <article v-for="row in channelStatusRecords" :key="row.id" class="bot-card submission-card">
          <div class="card-head">
            <div class="card-title">
              <strong>{{ row.search_bot_name || row.search_bot_username }}</strong>
              <span>{{ row.search_bot_username || "-" }}</span>
            </div>
            <el-tag :type="statusType(row.block_status)">{{ statusLabel(row.block_status) }}</el-tag>
          </div>
          <div class="submission-status-grid">
            <span>执行 <el-tag size="small" :type="statusType(row.submit_status)">{{ statusLabel(row.submit_status) }}</el-tag></span>
            <span>审核 <el-tag size="small" :type="statusType(row.review_status)">{{ statusLabel(row.review_status) }}</el-tag></span>
            <span>收录 <el-tag size="small" :type="statusType(row.collection_status)">{{ statusLabel(row.collection_status) }}</el-tag></span>
            <span>权限 <el-tag size="small" :type="row.permission_status === 'applied' ? 'success' : 'warning'">{{ permissionStatusLabel(row.permission_status) }}</el-tag></span>
          </div>
          <div v-if="row.last_error" class="error-line">{{ row.last_error }}</div>
          <div class="icon-actions">
            <el-button circle type="primary" plain aria-label="更新状态" title="更新状态" @click="openStatus(row)"><el-icon><EditPen /></el-icon></el-button>
            <el-button circle plain aria-label="调整频道权限" title="调整频道权限" @click="openPermissionEdit(row)"><el-icon><Setting /></el-icon></el-button>
          </div>
        </article>
        <EmptyState
          v-if="!recordLoading && !channelStatusRecords.length"
          title="暂无提交记录"
          description="可以登记手动提交，或由系统将搜索机器人添加为频道管理员。"
        />
      </div>
      <div class="drawer-actions">
        <el-button @click="channelStatusDrawer = false">关闭</el-button>
        <el-button
          type="primary"
          :disabled="!channelStatusChannel?.group_name || channelStatusChannel?.status === 'disabled'"
          @click="openSubmitForChannel(channelStatusChannel)"
        >
          提交到搜索机器人
        </el-button>
      </div>
    </el-drawer>

    <el-drawer v-model="submitDrawer" direction="btt" size="92%" title="提交频道" destroy-on-close>
      <el-alert type="info" :closable="false" :title="submitForm.submission_mode === 'manual' ? '登记已在 Telegram 手动完成的提交，不执行 Telegram 操作。' : '将搜索机器人添加为频道管理员，并授予下方选择的频道权限。'" />
      <el-form ref="submitFormRef" :model="submitForm" :rules="submitRules" label-position="top" class="drawer-form">
        <el-form-item label="提交方式"><el-radio-group v-model="submitForm.submission_mode" class="mode-switch"><el-radio-button value="queue">自动添加机器人</el-radio-button><el-radio-button value="manual">手动登记</el-radio-button></el-radio-group></el-form-item>
        <el-form-item label="我的频道" prop="my_channel_id"><el-select v-model="submitForm.my_channel_id" filterable placeholder="选择频道"><el-option v-for="channel in enabledChannels" :key="channel.id" :label="`${channel.title || channel.username} / ${channel.group_name}`" :value="channel.id" /></el-select></el-form-item>
        <el-form-item label="搜索机器人" prop="search_bot_id"><el-select v-model="submitForm.search_bot_id" filterable placeholder="选择搜索机器人"><el-option v-for="bot in availableBots" :key="bot.id" :label="`${bot.name} / ${bot.username}`" :value="bot.id" /></el-select></el-form-item>
        <el-form-item v-if="submitForm.submission_mode === 'queue'" label="操作账号（选填）"><el-select v-model="submitForm.account_id" clearable filterable placeholder="留空则使用机器人默认操作账号"><el-option v-for="account in enabledAccounts" :key="account.id" :label="account.name || account.username || `账号 #${account.id}`" :value="account.id" /></el-select><small>{{ selectedSubmitBot?.account_id ? `已配置默认操作账号：${selectedSubmitBot.account_name || `#${selectedSubmitBot.account_id}`}` : "请选择拥有目标频道管理权限的账号。" }}</small></el-form-item>
        <div class="permission-panel">
          <div class="permission-head">
            <strong>搜索机器人在频道中的权限</strong>
            <small v-if="submitForm.submission_mode === 'queue'">已选择 {{ selectedAdminRightLabels.length }} 项，提交后会回查 Telegram 实际权限。</small>
            <small v-else>登记手动授予的权限，保存后标记为人工登记、未验证。</small>
          </div>
          <el-button-group class="permission-presets">
            <el-button size="small" @click="applyPermissionPreset('minimal')">最小</el-button>
            <el-button size="small" @click="applyPermissionPreset('common')">常用</el-button>
            <el-button size="small" @click="applyPermissionPreset('all')">全部</el-button>
          </el-button-group>
          <div v-for="section in visibleSubmitPermissionSections" :key="section.title" class="permission-section">
            <span>{{ section.title }}</span>
            <el-checkbox v-for="item in section.items" :key="item.key" v-model="submitForm.admin_rights[item.key]">{{ item.label }}</el-checkbox>
          </div>
          <el-alert v-if="submitForm.admin_rights.add_admins" type="warning" :closable="false" show-icon title="机器人将可以继续授权其他管理员，请确认确实需要。" />
        </div>
        <template v-if="submitForm.submission_mode === 'manual'">
          <el-form-item label="审核状态"><el-select v-model="submitForm.review_status"><el-option label="待审核" value="pending" /><el-option label="审核中" value="reviewing" /><el-option label="已通过" value="approved" /><el-option label="已拒绝" value="rejected" /><el-option label="未知" value="unknown" /></el-select></el-form-item>
          <el-form-item label="收录状态"><el-select v-model="submitForm.collection_status"><el-option label="未知" value="unknown" /><el-option label="已收录" value="collected" /><el-option label="未收录" value="not_collected" /></el-select></el-form-item>
          <el-form-item label="拉黑状态"><el-select v-model="submitForm.block_status"><el-option label="正常" value="normal" /><el-option label="已拉黑" value="blocked" /><el-option label="未知" value="unknown" /></el-select></el-form-item>
          <el-form-item label="当前有效收录"><el-switch v-model="submitForm.is_current" :disabled="submitForm.block_status === 'blocked'" /></el-form-item>
        </template>
      </el-form>
      <div class="drawer-actions"><el-button :disabled="submitting" @click="submitDrawer = false">取消</el-button><el-button type="primary" :loading="submitting" @click="submitChannel">{{ submitForm.submission_mode === "manual" ? "登记记录" : "立即提交" }}</el-button></div>
    </el-drawer>

    <el-drawer v-model="statusDrawer" direction="btt" size="68%" title="更新提交状态" destroy-on-close>
      <el-form :model="statusForm" label-position="top">
        <el-form-item label="审核状态"><el-select v-model="statusForm.review_status"><el-option label="未知" value="unknown" /><el-option label="待审核" value="pending" /><el-option label="审核中" value="reviewing" /><el-option label="已通过" value="approved" /><el-option label="已拒绝" value="rejected" /></el-select></el-form-item>
        <el-form-item label="收录状态"><el-select v-model="statusForm.collection_status"><el-option label="未知" value="unknown" /><el-option label="已收录" value="collected" /><el-option label="未收录" value="not_collected" /></el-select></el-form-item>
        <el-form-item label="拉黑状态"><el-select v-model="statusForm.block_status"><el-option label="未知" value="unknown" /><el-option label="正常" value="normal" /><el-option label="已拉黑" value="blocked" /></el-select></el-form-item>
        <el-form-item label="当前有效收录"><el-switch v-model="statusForm.is_current" :disabled="statusForm.block_status === 'blocked'" /></el-form-item>
      </el-form>
      <el-alert v-if="statusForm.block_status === 'blocked'" type="warning" :closable="false" title="保存后可从记录卡片改投其他可用机器人。" />
      <div class="drawer-actions"><el-button @click="statusDrawer = false">取消</el-button><el-button type="primary" :loading="savingStatus" @click="saveStatus">保存</el-button></div>
    </el-drawer>

    <el-drawer v-model="permissionDrawer" direction="btt" size="92%" title="调整搜索机器人频道权限" destroy-on-close>
      <el-alert type="info" :closable="false" title="保存后立即更新 Telegram 频道权限，并回查实际结果。" />
      <el-form :model="permissionForm" label-position="top" class="drawer-form">
        <el-form-item label="操作账号（选填）"><el-select v-model="permissionForm.account_id" clearable filterable placeholder="留空则使用原提交账号或机器人默认账号"><el-option v-for="account in enabledAccounts" :key="account.id" :label="account.name || account.username || `账号 #${account.id}`" :value="account.id" /></el-select></el-form-item>
        <div class="permission-panel">
          <div class="permission-head"><strong>{{ permissionRecord?.search_bot_name }}</strong><small>{{ permissionRecord?.channel_title }}，只显示当前频道类型支持的权限。</small></div>
          <el-button-group class="permission-presets">
            <el-button size="small" @click="applyAdjustmentPreset('minimal')">最小</el-button>
            <el-button size="small" @click="applyAdjustmentPreset('common')">常用</el-button>
            <el-button size="small" @click="applyAdjustmentPreset('all')">全部</el-button>
          </el-button-group>
          <div v-for="section in visibleAdjustmentPermissionSections" :key="section.title" class="permission-section">
            <span>{{ section.title }}</span>
            <el-checkbox v-for="item in section.items" :key="item.key" v-model="permissionForm.admin_rights[item.key]">{{ item.label }}</el-checkbox>
          </div>
          <el-alert v-if="permissionForm.admin_rights.add_admins" type="warning" :closable="false" title="机器人将能够继续授权其他管理员，请确认确实需要。" />
        </div>
      </el-form>
      <div class="drawer-actions"><el-button :disabled="savingPermissions" @click="permissionDrawer = false">取消</el-button><el-button type="primary" :loading="savingPermissions" @click="savePermissions">应用并回查</el-button></div>
    </el-drawer>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import { Connection, Delete, Edit, EditPen, Location, Plus, Search, Setting } from "@element-plus/icons-vue"
import EmptyState from "./EmptyState.vue"
import StatusPill from "./StatusPill.vue"
import { checkSearchBot, createSearchBot, createSearchBotSubmission, deleteSearchBot, getAccounts, getMyChannels, getSearchBots, getSearchBotSubmissions, updateSearchBot, updateSearchBotSubmission, updateSearchBotSubmissionPermissions } from "../api"
import { getErrorMessage } from "../api/client"
import { matchesSearch } from "../utils/search"

defineProps({
  pageVisible: {
    type: Boolean,
    default: true,
  },
})
const emit = defineEmits(["submission-changed"])
const view = ref("bots")
const bots = ref([]), channels = ref([]), accounts = ref([]), records = ref([])
const keyword = ref(""), recordKeyword = ref("")
const loading = ref(false), recordLoading = ref(false), checkingId = ref(null)
const botDrawer = ref(false), submitDrawer = ref(false), statusDrawer = ref(false), permissionDrawer = ref(false), channelStatusDrawer = ref(false)
const pendingSubmitOpen = ref(false)
const saving = ref(false), submitting = ref(false), savingStatus = ref(false), savingPermissions = ref(false)
const editingBot = ref(null), editingRecord = ref(null), permissionRecord = ref(null), channelStatusChannel = ref(null)
const botFormRef = ref(null), submitFormRef = ref(null)
const permissionSections = [
  { title: "内容管理", items: [{ key: "post_messages", label: "发布消息" }, { key: "edit_messages", label: "编辑消息" }, { key: "delete_messages", label: "删除消息" }, { key: "pin_messages", label: "置顶消息" }, { key: "post_stories", label: "发布动态" }, { key: "edit_stories", label: "编辑动态" }, { key: "delete_stories", label: "删除动态" }] },
  { title: "频道管理", items: [{ key: "change_info", label: "修改频道信息" }, { key: "invite_users", label: "邀请用户" }, { key: "ban_users", label: "管理用户" }, { key: "manage_call", label: "管理视频聊天" }, { key: "manage_topics", label: "管理话题" }, { key: "manage_direct_messages", label: "管理频道私信" }] },
  { title: "高级权限", items: [{ key: "add_admins", label: "添加管理员" }, { key: "anonymous", label: "匿名管理" }, { key: "manage_ranks", label: "管理管理员头衔" }] },
]
const allPermissionOptions = permissionSections.flatMap((section) => section.items)
const botForm = reactive(emptyBot()), submitForm = reactive(emptySubmit()), statusForm = reactive({ review_status: "unknown", collection_status: "unknown", block_status: "unknown", is_current: false }), permissionForm = reactive({ account_id: null, admin_rights: emptyAdminRights() })
const botRules = { name: [{ required: true, message: "请填写机器人名称", trigger: "blur" }], username: [{ required: true, message: "请填写机器人 ID", trigger: "blur" }] }
const submitRules = { my_channel_id: [{ required: true, message: "请选择频道", trigger: "change" }], search_bot_id: [{ required: true, message: "请选择搜索机器人", trigger: "change" }] }
const enabledAccounts = computed(() => accounts.value.filter((item) => item.enabled !== false))
const enabledChannels = computed(() => channels.value.filter((item) => item.status !== "disabled" && item.group_name))
const selectedSubmitBot = computed(() => bots.value.find((item) => Number(item.id) === Number(submitForm.search_bot_id)))
const selectedSubmitChannel = computed(() => channels.value.find((item) => Number(item.id) === Number(submitForm.my_channel_id)))
const availableBots = computed(() => bots.value.filter((item) => item.status === "enabled"))
const visibleBots = computed(() => bots.value.filter((item) => matchesSearch([item.name, item.username, item.bot_link], keyword.value)))
const visibleRecords = computed(() => records.value.filter((item) => matchesSearch([item.channel_title, item.channel_username, item.search_bot_name, item.search_bot_username, item.group_name], recordKeyword.value)))
const channelStatusRecords = computed(() => records.value.filter((item) => Number(item.my_channel_id) === Number(channelStatusChannel.value?.id)))
const selectedAdminRightLabels = computed(() => allPermissionOptions.filter((item) => submitForm.admin_rights?.[item.key]).map((item) => item.label))
const visibleSubmitPermissionSections = computed(() => permissionSectionsFor(selectedSubmitChannel.value?.channel_type))
const visibleAdjustmentPermissionSections = computed(() => permissionSectionsFor(permissionRecord.value?.channel_type))
onMounted(loadAll)
function emptyBot() { return { name: "", username: "", account_id: null, monthly_active_users: null, status: "enabled", submit_template: "{{channel_link}}", remark: "" } }
function emptyAdminRights() { return Object.fromEntries(allPermissionOptions.map((item) => [item.key, false])) }
function emptySubmit() { return { my_channel_id: null, search_bot_id: null, account_id: null, submission_mode: "queue", review_status: "pending", collection_status: "unknown", block_status: "normal", is_current: false, admin_rights: emptyAdminRights() } }
function applyPermissionPreset(preset) {
  const available = visibleSubmitPermissionSections.value.flatMap((section) => section.items)
  const enabled = preset === "all" ? new Set(available.map((item) => item.key)) : preset === "common" ? new Set(["post_messages", "edit_messages", "delete_messages"].filter((key) => available.some((item) => item.key === key))) : new Set()
  Object.assign(submitForm.admin_rights, emptyAdminRights())
  for (const key of enabled) submitForm.admin_rights[key] = true
}
function permissionSectionsFor(channelType) {
  const type = String(channelType || "").toLowerCase()
  const isGroup = ["group", "supergroup", "megagroup", "forum"].some((value) => type.includes(value))
  const isBroadcast = !isGroup && ["channel", "broadcast"].some((value) => type.includes(value))
  const unsupported = isGroup ? new Set(["post_messages", "edit_messages", "post_stories", "edit_stories", "delete_stories", "manage_direct_messages"]) : isBroadcast ? new Set(["ban_users", "pin_messages", "manage_topics"]) : new Set()
  return permissionSections.map((section) => ({ ...section, items: section.items.filter((item) => !unsupported.has(item.key)) })).filter((section) => section.items.length)
}
function applyAdjustmentPreset(preset) {
  const available = visibleAdjustmentPermissionSections.value.flatMap((section) => section.items)
  const enabled = preset === "all" ? new Set(available.map((item) => item.key)) : preset === "common" ? new Set(["post_messages", "edit_messages", "delete_messages"].filter((key) => available.some((item) => item.key === key))) : new Set()
  Object.assign(permissionForm.admin_rights, emptyAdminRights())
  for (const key of enabled) permissionForm.admin_rights[key] = true
}
function adminRightLabels(rights) { const value = rights && typeof rights === "object" ? rights : {}; return allPermissionOptions.filter((item) => value[item.key]).map((item) => item.label) }
async function loadAll() { loading.value = true; recordLoading.value = true; try { const [botRes, channelRes, accountRes, recordRes] = await Promise.all([getSearchBots(), getMyChannels(), getAccounts(), getSearchBotSubmissions()]); bots.value = botRes.data.items || []; channels.value = channelRes.data.items || []; accounts.value = Array.isArray(accountRes.data) ? accountRes.data : accountRes.data.items || []; records.value = recordRes.data.items || []; if (channelStatusChannel.value?.id) channelStatusChannel.value = channels.value.find((item) => Number(item.id) === Number(channelStatusChannel.value.id)) || channelStatusChannel.value } catch (error) { ElMessage.error(getErrorMessage(error, "加载搜索机器人失败")) } finally { loading.value = false; recordLoading.value = false } }
function openBotCreate() { editingBot.value = null; Object.assign(botForm, emptyBot()); botDrawer.value = true }
function openBotEdit(bot) { editingBot.value = bot; Object.assign(botForm, { ...emptyBot(), ...bot }); botDrawer.value = true }
async function saveBot() { if (!(await botFormRef.value?.validate().catch(() => false))) return; saving.value = true; try { editingBot.value?.id ? await updateSearchBot(editingBot.value.id, botForm) : await createSearchBot(botForm); ElMessage.success("搜索机器人已保存"); botDrawer.value = false; await loadAll() } catch (error) { ElMessage.error(getErrorMessage(error, "保存失败")) } finally { saving.value = false } }
async function detect(bot) { checkingId.value = bot.id; try { const res = await checkSearchBot(bot.id); res.data.ok ? ElMessage.success(res.data.message) : ElMessage.warning(res.data.message); await loadAll() } catch (error) { ElMessage.error(getErrorMessage(error, "检测失败")) } finally { checkingId.value = null } }
async function removeBot(bot) { try { await ElMessageBox.confirm(`确定删除“${bot.name}”？已有提交记录时只能停用。`, "删除机器人", { type: "warning" }); await deleteSearchBot(bot.id); ElMessage.success("已删除"); await loadAll() } catch (error) { if (error !== "cancel" && error !== "close") ElMessage.error(getErrorMessage(error, "删除失败")) } }
async function openSubmitForChannel(channel) { if (!channel?.id) return; channelStatusChannel.value = channel; if (!bots.value.length || !channels.value.length) await loadAll(); Object.assign(submitForm, emptySubmit(), { my_channel_id: channel.id }); if (channelStatusDrawer.value) { pendingSubmitOpen.value = true; channelStatusDrawer.value = false; return } submitDrawer.value = true }
function openPendingSubmit() { if (!pendingSubmitOpen.value) return; pendingSubmitOpen.value = false; submitDrawer.value = true }
async function openChannelStatus(channel) { if (!channel?.id) return; channelStatusChannel.value = channel; channelStatusDrawer.value = true; await loadAll() }
async function submitChannel() { if (!(await submitFormRef.value?.validate().catch(() => false))) return; const bot = selectedSubmitBot.value; if (submitForm.submission_mode === "queue" && !submitForm.account_id && !bot?.account_id) return ElMessage.warning("请选择操作账号，或先为机器人配置默认操作账号"); submitting.value = true; try { const response = await createSearchBotSubmission(submitForm); const item = response.data?.item; if (item?.submit_status === "failed") throw new Error(item.last_error || "添加失败"); ElMessage.success(submitForm.submission_mode === "manual" ? "手动提交记录已登记" : "搜索机器人已添加到频道"); submitDrawer.value = false; await loadAll(); channelStatusDrawer.value = true; emit("submission-changed") } catch (error) { ElMessage.error(getErrorMessage(error, "提交失败")) } finally { submitting.value = false } }
function openStatus(row) { editingRecord.value = row; Object.assign(statusForm, { review_status: row.review_status || "unknown", collection_status: row.collection_status || "unknown", block_status: row.block_status || "unknown", is_current: Boolean(row.is_current) }); statusDrawer.value = true }
async function saveStatus() { savingStatus.value = true; try { await updateSearchBotSubmission(editingRecord.value.id, statusForm); ElMessage.success("状态已更新"); statusDrawer.value = false; await loadAll(); emit("submission-changed") } catch (error) { ElMessage.error(getErrorMessage(error, "保存状态失败")) } finally { savingStatus.value = false } }
function openPermissionEdit(row) { permissionRecord.value = row; Object.assign(permissionForm, { account_id: row.account_id || null, admin_rights: { ...emptyAdminRights(), ...(row.applied_admin_rights || row.admin_rights || {}) } }); permissionDrawer.value = true }
async function savePermissions() { savingPermissions.value = true; try { const response = await updateSearchBotSubmissionPermissions(permissionRecord.value.id, permissionForm); if (!response.data?.ok) throw new Error(response.data?.message || "Telegram 权限回查未通过"); ElMessage.success("频道权限已更新并通过回查"); permissionDrawer.value = false; await loadAll(); emit("submission-changed") } catch (error) { ElMessage.error(getErrorMessage(error, "调整权限失败")) } finally { savingPermissions.value = false } }
function formatDate(value) { return value ? String(value).replace("T", " ").slice(0, 16) : "-" }
function statusLabel(status) { return ({ enabled: "正常", disabled: "已停用", error: "异常", queued: "排队中", submitting: "添加中", success: "已添加", manual: "手动登记", failed: "失败", unknown: "未知", pending: "待审核", reviewing: "审核中", approved: "已通过", rejected: "已拒绝", collected: "已收录", not_collected: "未收录", normal: "正常", blocked: "已拉黑" })[status] || status || "未知" }
function statusType(status) { if (["success", "approved", "collected", "normal"].includes(status)) return "success"; if (["failed", "rejected", "blocked"].includes(status)) return "danger"; if (["queued", "submitting", "pending", "reviewing"].includes(status)) return "warning"; return "info" }
function permissionStatusLabel(status) { return ({ pending: "待应用", applying: "应用中", applied: "已验证", mismatch: "权限不一致", failed: "应用失败", unverified: "人工登记" })[status] || "未验证" }
defineExpose({ openSubmitForChannel, openChannelStatus })
</script>

<style scoped>
.search-page { min-width: 0; }
.search-header, .card-head, .icon-actions, .filter-row, .group-line, .drawer-actions, .channel-status-head { display: flex; align-items: center; }
.search-header { justify-content: space-between; margin-bottom: 6px; }
.search-header h2 { margin: 0; font-size: 18px; }
.search-header p { margin: 4px 0 0; color: var(--el-text-color-secondary); font-size: 12px; }
.filter-row { gap: 8px; margin-bottom: 10px; }
.filter-row .el-select { width: 120px; }
.card-list { min-height: 180px; display: grid; gap: 10px; }
.bot-card { padding: 14px; border: 1px solid var(--el-border-color-light); border-radius: 8px; background: var(--el-bg-color); }
.card-head { justify-content: space-between; gap: 10px; }
.card-title { min-width: 0; }
.card-title strong, .card-title span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card-title span { margin-top: 3px; color: var(--el-text-color-secondary); font-size: 12px; }
.group-line { gap: 4px; margin-top: 10px; color: var(--el-text-color-regular); font-size: 13px; }
dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin: 12px 0; }
dl div { min-width: 0; padding: 7px 8px; background: var(--el-fill-color-lighter); border-radius: 6px; }
dt { color: var(--el-text-color-secondary); font-size: 11px; }
dd { margin: 3px 0 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px; }
.icon-actions { justify-content: center; gap: 10px; border-top: 1px solid var(--el-border-color-lighter); padding-top: 11px; }
.icon-actions .el-button { margin-left: 0; }
.error-line { margin-bottom: 10px; color: var(--el-color-danger); font-size: 12px; line-height: 1.5; }
.drawer-form { margin-top: 12px; }
.drawer-actions { position: sticky; bottom: 0; justify-content: flex-end; gap: 8px; padding: 12px 0 max(4px, env(safe-area-inset-bottom)); background: var(--el-bg-color); }
.drawer-actions .el-button { min-width: 96px; }
.channel-status-head { justify-content: space-between; gap: 12px; margin-bottom: 14px; }
.channel-status-list { display: grid; gap: 10px; min-height: 160px; margin-top: 12px; padding-bottom: 6px; }
.submission-card { padding: 12px; }
.submission-status-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin: 12px 0; }
.submission-status-grid span { display: flex; align-items: center; justify-content: space-between; gap: 6px; min-width: 0; padding: 7px 8px; background: var(--el-fill-color-lighter); border-radius: 6px; font-size: 12px; }
.el-select, .el-input-number { width: 100%; }
small { display: block; margin-top: 5px; color: var(--el-text-color-secondary); line-height: 1.5; }
.mode-switch { width: 100%; display: flex; }
.mode-switch :deep(.el-radio-button) { flex: 1; }
.mode-switch :deep(.el-radio-button__inner) { width: 100%; }
.permission-panel { margin-bottom: 16px; padding: 12px; border: 1px solid var(--el-border-color); border-radius: 6px; }
.permission-head { margin-bottom: 10px; }
.permission-head strong { display: block; font-size: 14px; }
.permission-presets { display: flex; width: 100%; }
.permission-presets .el-button { flex: 1; }
.permission-section { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 2px 8px; margin-top: 12px; }
.permission-section > span { grid-column: 1 / -1; color: var(--el-text-color-secondary); font-size: 12px; }
.permission-section :deep(.el-checkbox) { margin-right: 0; min-width: 0; }
.permission-panel .el-alert { margin-top: 10px; }
</style>
