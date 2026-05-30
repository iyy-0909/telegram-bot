<template>
  <div class="page">
    <div class="page-hero">
      <div>
        <div class="title">我的频道</div>
        <div class="subtitle">统一管理目标频道和克隆源频道，创建任务时减少手动输入错误。</div>
      </div>
      <div class="summary">
        <div class="summary-item">
          <span>目标频道</span>
          <strong>{{ channelStats.total }}</strong>
        </div>
        <div class="summary-item success">
          <span>可用</span>
          <strong>{{ channelStats.enabled }}</strong>
        </div>
        <div class="summary-item danger">
          <span>异常</span>
          <strong>{{ channelStats.error }}</strong>
        </div>
        <div class="summary-item">
          <span>克隆频道</span>
          <strong>{{ cloneChannels.length }}</strong>
        </div>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="channel-tabs">
      <el-tab-pane label="我的频道" name="targets">
        <div class="toolbar">
          <div class="actions">
            <el-input
              v-model="filters.keyword"
              placeholder="搜索名称 / username / chat_id"
              clearable
              @keyup.enter="load"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-select v-model="filters.status" clearable placeholder="状态" class="status-filter">
              <el-option label="enabled" value="enabled" />
              <el-option label="disabled" value="disabled" />
              <el-option label="error" value="error" />
            </el-select>
            <el-button @click="load">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            <el-button @click="batchCheck">
              <el-icon><Connection /></el-icon>
              批量检测
            </el-button>
            <el-button type="primary" @click="openCreate">
              <el-icon><Plus /></el-icon>
              新增频道
            </el-button>
          </div>
        </div>

        <el-card class="table-card">
          <el-table
            :data="channels"
            v-loading="loading"
            border
            stripe
            empty-text="暂无频道，请点击“新增频道”添加你的目标频道。"
          >
            <el-table-column prop="title" label="频道名称" min-width="160" show-overflow-tooltip />
            <el-table-column label="username" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">
                <CopyText
                  v-if="row.username"
                  :value="row.username"
                  :text="row.username"
                  tone="primary"
                />
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="group_name" label="分组" min-width="120" />
            <el-table-column label="绑定 Bot" min-width="130">
              <template #default="{ row }">
                <CopyText
                  v-if="botUsername(row)"
                  :value="botUsername(row)"
                  :text="botUsername(row)"
                  tone="primary"
                />
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <StatusTag :status="row.status" />
              </template>
            </el-table-column>
            <el-table-column label="权限" min-width="220">
              <template #default="{ row }">
                <div class="perm">
                  <el-tag size="small" :type="row.bot_is_member ? 'success' : 'danger'">在频道 {{ yesNo(row.bot_is_member) }}</el-tag>
                  <el-tag size="small" :type="row.bot_is_admin ? 'success' : 'info'">管理员 {{ yesNo(row.bot_is_admin) }}</el-tag>
                  <el-tag size="small" :type="row.can_post_messages ? 'success' : 'warning'">发帖 {{ yesNo(row.can_post_messages) }}</el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="最后检测" min-width="160">
              <template #default="{ row }">
                {{ formatDateTime(row.last_check_at) }}
              </template>
            </el-table-column>
            <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip />
            <el-table-column label="操作" width="280" fixed="right">
              <template #default="{ row }">
                <div class="row-actions">
                  <el-button size="small" @click="openEdit(row)">
                    <el-icon><Edit /></el-icon>
                    编辑
                  </el-button>
                  <el-button size="small" @click="check(row)">
                    <el-icon><Connection /></el-icon>
                    检测
                  </el-button>
                  <el-button size="small" @click="toggle(row)">
                    {{ row.status === "disabled" ? "启用" : "禁用" }}
                  </el-button>
                  <el-button size="small" type="danger" plain @click="remove(row)">
                    <el-icon><Delete /></el-icon>
                    删除
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="克隆频道" name="sources">
        <div class="toolbar">
          <div class="actions">
            <el-input
              v-model="cloneFilters.keyword"
              placeholder="搜索频道名 / 链接 / 分组"
              clearable
              @keyup.enter="loadCloneChannels"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-input
              v-model="cloneFilters.group_name"
              placeholder="分组"
              clearable
              class="status-filter"
              @keyup.enter="loadCloneChannels"
            />
            <el-button @click="loadCloneChannels">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
            <el-button type="primary" @click="openCloneCreate">
              <el-icon><Plus /></el-icon>
              新增克隆频道
            </el-button>
          </div>
        </div>

        <el-card class="table-card">
          <el-table
            :data="cloneChannels"
            v-loading="cloneLoading"
            border
            stripe
            empty-text="暂无克隆频道，请点击“新增克隆频道”添加源频道。"
          >
            <el-table-column prop="title" label="频道名" min-width="170" show-overflow-tooltip />
            <el-table-column label="频道链接" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                <CopyText
                  v-if="row.channel_link"
                  :value="row.channel_link"
                  :text="row.channel_link"
                  tone="primary"
                />
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="group_name" label="分组" min-width="120" />
            <el-table-column prop="channel_type" label="频道类型" min-width="120" show-overflow-tooltip />
            <el-table-column prop="remark" label="备注" min-width="180" show-overflow-tooltip />
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <div class="row-actions">
                  <el-button size="small" @click="openCloneEdit(row)">
                    <el-icon><Edit /></el-icon>
                    编辑
                  </el-button>
                  <el-button size="small" type="danger" plain @click="removeClone(row)">
                    <el-icon><Delete /></el-icon>
                    删除
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="dialogVisible" :title="editing?.id ? '编辑频道' : '新增频道'" width="620px">
      <el-form label-width="110px">
        <el-form-item label="频道名称">
          <el-input v-model="form.title" />
        </el-form-item>
        <el-form-item label="username">
          <el-input v-model="form.username" placeholder="@channel_username" />
        </el-form-item>
        <el-form-item label="chat_id">
          <el-input v-model="form.chat_id" placeholder="-100xxxxxxxxxx，可选" />
        </el-form-item>
        <el-form-item label="分组">
          <el-input v-model="form.group_name" />
        </el-form-item>
        <el-form-item label="默认 Bot">
          <BotSelect v-model="form.bot_id" :bots="props.bots" placeholder="不选则使用系统默认 Bot" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option label="正常" value="enabled" />
            <el-option label="已禁用" value="disabled" />
            <el-option label="异常" value="error" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="cloneDialogVisible" :title="cloneEditing?.id ? '编辑克隆频道' : '新增克隆频道'" width="620px">
      <el-form label-width="110px">
        <el-form-item label="频道名">
          <el-input v-model="cloneForm.title" placeholder="例如：上海新闻源" />
        </el-form-item>
        <el-form-item label="频道链接" required>
          <el-input v-model="cloneForm.channel_link" placeholder="@source_channel / https://t.me/source_channel" />
        </el-form-item>
        <el-form-item label="分组">
          <el-input v-model="cloneForm.group_name" placeholder="例如：上海" />
        </el-form-item>
        <el-form-item label="频道类型">
          <el-input v-model="cloneForm.channel_type" placeholder="例如：新闻 / 房产 / 招聘" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="cloneForm.remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cloneDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="cloneSaving" @click="saveClone">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import {
  Connection,
  Delete,
  Edit,
  Plus,
  Refresh,
  Search,
} from "@element-plus/icons-vue"
import {
  batchCheckMyChannels,
  checkMyChannel,
  createCloneChannel,
  createMyChannel,
  deleteCloneChannel,
  deleteMyChannel,
  getCloneChannels,
  getMyChannels,
  updateCloneChannel,
  updateMyChannel,
} from "../api/myChannels"
import BotSelect from "./BotSelect.vue"
import CopyText from "./CopyText.vue"
import StatusTag from "./StatusTag.vue"

const props = defineProps({
  bots: {
    type: Array,
    default: () => [],
  },
})

const activeTab = ref("targets")
const channels = ref([])
const cloneChannels = ref([])
const dialogVisible = ref(false)
const cloneDialogVisible = ref(false)
const editing = ref(null)
const cloneEditing = ref(null)
const loading = ref(false)
const cloneLoading = ref(false)
const saving = ref(false)
const cloneSaving = ref(false)
const filters = reactive({
  keyword: "",
  status: "",
})
const cloneFilters = reactive({
  keyword: "",
  group_name: "",
})
const form = reactive(emptyForm())
const cloneForm = reactive(emptyCloneForm())
const channelStats = computed(() => ({
  total: channels.value.length,
  enabled: channels.value.filter((channel) => channel.status === "enabled").length,
  error: channels.value.filter((channel) => channel.status === "error").length,
}))

onMounted(async () => {
  await Promise.all([load(), loadCloneChannels()])
})

function emptyForm() {
  return {
    title: "",
    username: "",
    chat_id: "",
    group_name: "",
    bot_id: null,
    status: "enabled",
    remark: "",
    tags: "[]",
  }
}

function emptyCloneForm() {
  return {
    title: "",
    channel_link: "",
    group_name: "",
    channel_type: "",
    remark: "",
  }
}

async function load() {
  loading.value = true
  try {
    const res = await getMyChannels(filters)
    channels.value = res.data.items || []
  } finally {
    loading.value = false
  }
}

async function loadCloneChannels() {
  cloneLoading.value = true
  try {
    const res = await getCloneChannels(cloneFilters)
    cloneChannels.value = res.data.items || []
  } finally {
    cloneLoading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row) {
  editing.value = row
  Object.assign(form, {
    title: row.title || "",
    username: row.username || "",
    chat_id: row.chat_id || "",
    group_name: row.group_name || "",
    bot_id: row.bot_id || null,
    status: row.status || "enabled",
    remark: row.remark || "",
    tags: row.tags || "[]",
  })
  dialogVisible.value = true
}

function openCloneCreate() {
  cloneEditing.value = null
  Object.assign(cloneForm, emptyCloneForm())
  cloneDialogVisible.value = true
}

function openCloneEdit(row) {
  cloneEditing.value = row
  Object.assign(cloneForm, {
    title: row.title || "",
    channel_link: row.channel_link || "",
    group_name: row.group_name || "",
    channel_type: row.channel_type || "",
    remark: row.remark || "",
  })
  cloneDialogVisible.value = true
}

async function save() {
  if (!form.username && !form.chat_id) {
    ElMessage.error("username 和 chat_id 至少填写一个")
    return
  }

  saving.value = true
  try {
    if (editing.value?.id) {
      await updateMyChannel(editing.value.id, form)
      ElMessage.success("频道已保存")
    } else {
      await createMyChannel(form)
      ElMessage.success("频道已添加")
    }

    dialogVisible.value = false
    await load()
  } catch (error) {
    ElMessage.error(readError(error, "保存频道失败"))
  } finally {
    saving.value = false
  }
}

async function saveClone() {
  if (!cloneForm.channel_link.trim()) {
    ElMessage.error("频道链接不能为空")
    return
  }

  cloneSaving.value = true
  try {
    if (cloneEditing.value?.id) {
      await updateCloneChannel(cloneEditing.value.id, cloneForm)
      ElMessage.success("克隆频道已保存")
    } else {
      await createCloneChannel(cloneForm)
      ElMessage.success("克隆频道已添加")
    }

    cloneDialogVisible.value = false
    await loadCloneChannels()
  } catch (error) {
    ElMessage.error(readError(error, "保存克隆频道失败"))
  } finally {
    cloneSaving.value = false
  }
}

async function check(row) {
  const res = await checkMyChannel(row.id)
  if (res.data.ok) {
    ElMessage.success("检测完成")
  } else {
    ElMessage.warning(res.data.message || "检测失败")
  }
  await load()
}

async function batchCheck() {
  await batchCheckMyChannels()
  ElMessage.success("批量检测完成")
  await load()
}

async function toggle(row) {
  await updateMyChannel(row.id, {
    status: row.status === "disabled" ? "enabled" : "disabled",
  })
  await load()
}

async function remove(row) {
  await ElMessageBox.confirm(
    "确定删除这个频道？旧任务字段不会被删除。",
    "确认删除",
    { type: "warning" },
  )
  await deleteMyChannel(row.id)
  ElMessage.success("频道已删除")
  await load()
}

async function removeClone(row) {
  await ElMessageBox.confirm(
    "确定删除这个克隆频道？已有克隆任务里的源频道字段不会被删除。",
    "确认删除",
    { type: "warning" },
  )
  await deleteCloneChannel(row.id)
  ElMessage.success("克隆频道已删除")
  await loadCloneChannels()
}

function botUsername(rowOrBotId) {
  const row = typeof rowOrBotId === "object"
    ? rowOrBotId
    : channels.value.find((channel) => Number(channel.bot_id) === Number(rowOrBotId))
  const botId = typeof rowOrBotId === "object" ? rowOrBotId?.bot_id : rowOrBotId

  if (row?.bot_username) {
    const username = String(row.bot_username).trim()
    return username.startsWith("@") ? username : `@${username}`
  }

  if (row?.bot_link) {
    const match = String(row.bot_link).trim().match(/t\.me\/([^/?#]+)/i)
    if (match) return `@${match[1]}`
  }

  const bot = props.bots.find((item) => Number(item.id) === Number(botId))

  if (!bot) {
    return row?.bot_name || (botId ? `#${botId}` : "")
  }

  const username = String(bot.username || "").trim()

  if (username) {
    return username.startsWith("@") ? username : `@${username}`
  }

  const link = String(bot.bot_link || "").trim()
  const match = link.match(/t\.me\/([^/?#]+)/i)

  return match ? `@${match[1]}` : ""
}

function formatDateTime(value) {
  if (!value) {
    return "-"
  }

  const text = String(value).trim()
  const normalized = text.includes("T") ? text : text.replace(" ", "T")
  const date = new Date(normalized)

  if (Number.isNaN(date.getTime())) {
    return text.replace("T", " ").slice(0, 19)
  }

  const pad = (number) => String(number).padStart(2, "0")
  return [
    date.getFullYear(),
    pad(date.getMonth() + 1),
    pad(date.getDate()),
  ].join("-") + " " + [
    pad(date.getHours()),
    pad(date.getMinutes()),
    pad(date.getSeconds()),
  ].join(":")
}

function yesNo(value) {
  return value ? "是" : "否"
}

function readError(error, fallback) {
  return error?.response?.data?.detail
    || error?.response?.data?.message
    || error?.message
    || fallback
}
</script>

<style scoped>
.page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.page-hero,
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.page-hero {
  padding: 18px 20px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #ffffff;
}

.title {
  font-size: 18px;
  font-weight: 700;
}

.subtitle {
  margin-top: 4px;
  color: #6b7280;
  font-size: 13px;
}

.channel-tabs {
  padding: 0 2px;
}

.actions {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.actions .el-input {
  width: 260px;
}

.status-filter {
  width: 150px;
}

.summary {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.summary-item {
  min-width: 74px;
  padding: 8px 12px;
  border-radius: 8px;
  background: #f5f7fa;
  border: 1px solid #e5e7eb;
}

.summary-item span {
  display: block;
  color: #909399;
  font-size: 12px;
}

.summary-item strong {
  display: block;
  margin-top: 2px;
  font-size: 18px;
  color: #303133;
}

.summary-item.success strong {
  color: #67c23a;
}

.summary-item.danger strong {
  color: #f56c6c;
}

.table-card {
  margin-top: 12px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.perm {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.row-actions .el-button {
  margin-left: 0;
}
</style>
