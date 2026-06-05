<template>
  <div class="support-page">
    <div class="page-hero">
      <div>
        <div class="title">客服机器人</div>
        <div class="subtitle">群内客服模式：每个 Bot 独立 polling、客服群、欢迎语和话题会话。</div>
      </div>
      <div class="summary">
        <div class="summary-item">
          <span>配置</span>
          <strong>{{ stats.total }}</strong>
        </div>
        <div class="summary-item success">
          <span>Polling</span>
          <strong>{{ stats.polling }}</strong>
        </div>
        <div class="summary-item danger">
          <span>异常</span>
          <strong>{{ stats.error }}</strong>
        </div>
      </div>
    </div>

    <div class="toolbar">
      <el-alert
        title="客服回复在 Telegram 客服群话题内完成，后台只负责配置和只读管理。"
        type="info"
        show-icon
        :closable="false"
        class="page-alert"
      />
      <el-button type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon>
        新增客服 Bot
      </el-button>
    </div>

    <el-card class="table-card">
      <el-table
        :data="items"
        v-loading="loading"
        border
        stripe
        height="492"
        empty-text="暂无客服 Bot，请点击“新增客服 Bot”创建客服接待配置。"
      >
        <el-table-column prop="name" label="名称" min-width="150" />
        <el-table-column label="Bot" min-width="160">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">
              {{ botLabel(row) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="客服群 chat_id" min-width="170">
          <template #default="{ row }">
            <span class="mono-text">{{ row.support_group_chat_id || "-" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="polling" width="100">
          <template #default="{ row }">
            <StatusTag :status="row.polling_enabled ? 'running' : 'stopped'" />
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <StatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="最后错误" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <ErrorText :message="row.last_error" />
          </template>
        </el-table-column>
        <el-table-column label="欢迎语" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.welcome_message || row.welcome_media_file_id || "-" }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button size="small" @click="openEdit(row)">
                <el-icon><Edit /></el-icon>
                编辑
              </el-button>
              <el-button size="small" @click="testBot(row)">
                <el-icon><CircleCheck /></el-icon>
                检测
              </el-button>
              <el-button size="small" @click="togglePolling(row)">
                {{ row.polling_enabled ? "停用" : "启用" }}
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

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑客服 Bot' : '新增客服 Bot'" width="760px">
      <el-form label-width="150px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="例如：杭州客服 Bot" />
        </el-form-item>

        <el-form-item label="复用已有 Bot">
          <BotSelect v-model="form.bot_id" :bots="props.bots" placeholder="选择 Bot" />
        </el-form-item>

        <el-form-item label="或填写 Bot Token">
          <el-input
            v-model="form.bot_token"
            type="password"
            show-password
            autocomplete="new-password"
            :placeholder="form.id ? '留空表示不修改 Token' : '填写独立客服 Bot Token'"
          />
          <div class="field-tip">
            已保存的 Token 不会回显，避免在浏览器中泄露。需要更换时再填写新 Token。
          </div>
        </el-form-item>

        <el-form-item label="客服群 chat_id">
          <el-input v-model="form.support_group_chat_id" placeholder="-100..." />
        </el-form-item>

        <el-form-item label="polling">
          <el-switch v-model="form.polling_enabled" />
        </el-form-item>

        <el-form-item label="后台链接">
          <el-input v-model="form.backend_base_url" placeholder="http://127.0.0.1:5173" />
        </el-form-item>

        <el-divider content-position="left">欢迎语</el-divider>

        <el-form-item label="欢迎文本">
          <el-input v-model="form.welcome_message" type="textarea" :rows="3" />
        </el-form-item>

        <el-form-item label="欢迎媒体类型">
          <el-select v-model="form.welcome_media_type">
            <el-option label="纯文本" value="text" />
            <el-option label="图片 photo" value="photo" />
            <el-option label="视频 video" value="video" />
            <el-option label="文件 document" value="document" />
            <el-option label="动画 animation" value="animation" />
            <el-option label="音频 audio" value="audio" />
            <el-option label="语音 voice" value="voice" />
          </el-select>
        </el-form-item>

        <el-form-item label="欢迎媒体">
          <div class="upload-field">
            <div class="upload-actions">
              <el-upload
                accept="image/*,video/*,audio/*,.pdf,.doc,.docx,.xls,.xlsx,.zip,.rar,.7z,.txt"
                :show-file-list="false"
                :http-request="uploadWelcomeMedia"
                :before-upload="beforeWelcomeMediaUpload"
              >
                <el-button :loading="uploadingMedia">
                  上传媒体
                </el-button>
              </el-upload>
              <el-button
                v-if="form.welcome_media_file_id"
                @click="clearWelcomeMedia"
              >
                清空媒体
              </el-button>
            </div>
            <div class="field-tip">
              上传后 /start 时优先发送媒体，欢迎文本作为 caption。已配置：{{ welcomeMediaLabel }}
            </div>
          </div>
        </el-form-item>

        <el-divider content-position="left">非营业时间</el-divider>

        <el-form-item label="非营业回复">
          <el-input v-model="form.off_hours_message" type="textarea" :rows="3" />
        </el-form-item>

        <el-form-item label="营业时间">
          <div class="row">
            <el-switch v-model="form.business_hours_enabled" />
            <el-input-number v-model="form.business_start_hour" :min="0" :max="23" />
            <span>至</span>
            <el-input-number v-model="form.business_end_hour" :min="0" :max="23" />
          </div>
        </el-form-item>

        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option label="enabled" value="enabled" />
            <el-option label="disabled" value="disabled" />
            <el-option label="error" value="error" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import { CircleCheck, Delete, Edit, Plus } from "@element-plus/icons-vue"
import {
  createSupportBot,
  deleteSupportBot,
  getSupportBots,
  testSupportBotItem,
  updateSupportBot,
  uploadSupportMedia,
} from "../api/support"
import BotSelect from "./BotSelect.vue"
import ErrorText from "./ErrorText.vue"
import StatusTag from "./StatusTag.vue"

const props = defineProps({
  bots: {
    type: Array,
    default: () => [],
  },
})

const items = ref([])
const dialogVisible = ref(false)
const loading = ref(false)
const saving = ref(false)
const uploadingMedia = ref(false)
const form = reactive(emptyForm())
const stats = computed(() => ({
  total: items.value.length,
  polling: items.value.filter((item) => item.polling_enabled).length,
  error: items.value.filter((item) => item.status === "error").length,
}))
const welcomeMediaLabel = computed(() => {
  const value = form.welcome_media_file_id || ""
  if (!value) return "未上传"
  return value.replace("support_upload:", "")
})

onMounted(load)

function emptyForm() {
  return {
    id: null,
    name: "",
    bot_id: null,
    bot_token: "",
    has_bot_token: false,
    support_group_chat_id: "",
    polling_enabled: false,
    welcome_message: "您好，欢迎咨询，请直接发送您的问题，客服会尽快回复您。",
    welcome_media_type: "text",
    welcome_media_file_id: "",
    off_hours_message: "您好，当前客服不在线，我们会尽快回复您。",
    business_hours_enabled: false,
    business_start_hour: 9,
    business_end_hour: 22,
    backend_base_url: "",
    status: "enabled",
  }
}

async function load() {
  loading.value = true
  try {
    const res = await getSupportBots()
    items.value = res.data.items || []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row) {
  Object.assign(form, {
    ...emptyForm(),
    ...row,
    bot_id: row.bot_id || null,
    bot_token: "",
    polling_enabled: Boolean(row.polling_enabled),
    business_hours_enabled: Boolean(row.business_hours_enabled),
    business_start_hour: Number(row.business_start_hour || 9),
    business_end_hour: Number(row.business_end_hour || 22),
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.name.trim()) {
    ElMessage.warning("请填写名称")
    return
  }
  if (!form.bot_id && !form.has_bot_token && !form.bot_token.trim()) {
    ElMessage.warning("请选择已有 Bot 或填写 Bot Token")
    return
  }

  const payload = {
    ...form,
    name: form.name.trim(),
    support_group_chat_id: form.support_group_chat_id.trim(),
  }

  if (form.bot_token.trim()) {
    payload.bot_token = form.bot_token.trim()
  } else {
    delete payload.bot_token
  }

  saving.value = true
  try {
    if (form.id) {
      await updateSupportBot(form.id, payload)
      ElMessage.success("客服 Bot 已保存")
    } else {
      await createSupportBot(payload)
      ElMessage.success("客服 Bot 已新增")
    }

    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

function beforeWelcomeMediaUpload(file) {
  const maxSize = 50 * 1024 * 1024
  if (file.size > maxSize) {
    ElMessage.warning("欢迎媒体不能超过 50MB")
    return false
  }
  form.welcome_media_type = inferWelcomeMediaType(file)
  return true
}

function inferWelcomeMediaType(file) {
  const type = file.type || ""
  const name = file.name || ""
  if (type.startsWith("image/")) {
    return name.toLowerCase().endsWith(".gif") ? "animation" : "photo"
  }
  if (type.startsWith("video/")) return "video"
  if (type.startsWith("audio/")) return "audio"
  return "document"
}

async function uploadWelcomeMedia(options) {
  uploadingMedia.value = true
  try {
    const res = await uploadSupportMedia(options.file)
    form.welcome_media_file_id = res.data.media_ref || ""
    ElMessage.success("欢迎媒体已上传")
    options.onSuccess?.(res.data)
  } catch (error) {
    const message = error?.response?.data?.detail
      || error?.response?.data?.message
      || error?.message
      || "上传欢迎媒体失败"
    ElMessage.error(message)
    options.onError?.(error)
  } finally {
    uploadingMedia.value = false
  }
}

function clearWelcomeMedia() {
  form.welcome_media_file_id = ""
}

async function testBot(row) {
  const res = await testSupportBotItem(row.id)
  if (res.data.ok) {
    const bot = res.data.bot || {}
    const permission = res.data.group_permission
    const suffix = permission
      ? permission.ok
        ? "，客服群话题权限正常"
        : `，${permission.message || "客服群权限异常"}`
      : ""
    ElMessage.success(`检测成功：@${bot.username || bot.first_name || bot.id}${suffix}`)
  } else {
    ElMessage.error(res.data.message || "检测失败")
  }
}

async function togglePolling(row) {
  await updateSupportBot(row.id, {
    polling_enabled: !row.polling_enabled,
    status: row.status === "disabled" ? "enabled" : row.status,
  })
  await load()
}

async function remove(row) {
  await ElMessageBox.confirm("确定删除这个客服 Bot 配置？历史客户和消息不会删除。", "确认删除", {
    type: "warning",
  })
  const res = await deleteSupportBot(row.id)
  if (res.data.ok) {
    ElMessage.success("客服 Bot 已删除")
    await load()
  }
}

function botLabel(row) {
  const bot = props.bots.find((item) => Number(item.id) === Number(row.bot_id))
  if (bot) return `${bot.name} (#${bot.id})`
  return row.has_bot_token ? "自定义 Token" : "-"
}
</script>

<style scoped>
.support-page {
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

.toolbar {
  align-items: stretch;
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

.summary {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.summary-item {
  min-width: 78px;
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

.page-alert {
  flex: 1;
}

.table-card {
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.mono-text {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: #606266;
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

.field-tip {
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
  line-height: 1.4;
}

.upload-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.upload-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.row {
  display: flex;
  align-items: center;
  gap: 10px;
}
</style>
