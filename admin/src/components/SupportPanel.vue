<template>
  <div class="support-page">
    <div class="toolbar">
      <div>
        <div class="title">客服机器人</div>
        <div class="subtitle">每个客服 Bot 独立 polling、独立客服群和欢迎语</div>
      </div>
      <el-button type="primary" @click="openCreate">新增客服 Bot</el-button>
    </div>

    <el-alert
      title="客户列表、会话记录和快捷回复第一版先隐藏。客服回复在 Telegram 客服群/话题内完成。"
      type="info"
      show-icon
      :closable="false"
    />

    <el-table :data="items" border>
      <el-table-column prop="name" label="名称" min-width="150" />
      <el-table-column label="Bot" min-width="160">
        <template #default="{ row }">
          {{ botLabel(row) }}
        </template>
      </el-table-column>
      <el-table-column prop="support_group_chat_id" label="客服群 chat_id" min-width="170" />
      <el-table-column label="polling" width="100">
        <template #default="{ row }">
          <el-tag :type="row.polling_enabled ? 'success' : 'info'">
            {{ row.polling_enabled ? "开启" : "关闭" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'enabled' ? 'success' : row.status === 'error' ? 'danger' : 'info'">
            {{ row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="last_error" label="最后错误" min-width="220" show-overflow-tooltip />
      <el-table-column label="欢迎语" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          {{ row.welcome_message || row.welcome_media_file_id || "-" }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" @click="testBot(row)">检测</el-button>
          <el-button size="small" @click="togglePolling(row)">
            {{ row.polling_enabled ? "停用" : "启用" }}
          </el-button>
          <el-button size="small" type="danger" plain @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑客服 Bot' : '新增客服 Bot'" width="760px">
      <el-form label-width="150px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="例如：杭州客服 Bot" />
        </el-form-item>

        <el-form-item label="复用已有 Bot">
          <el-select v-model="form.bot_id" clearable filterable placeholder="选择 Bot">
            <el-option
              v-for="bot in enabledBots"
              :key="bot.id"
              :label="`${bot.name} (#${bot.id})`"
              :value="bot.id"
            />
          </el-select>
        </el-form-item>

        <el-form-item label="或填写 Bot Token">
          <el-input v-model="form.bot_token" type="password" show-password />
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

        <el-form-item label="欢迎媒体 file_id">
          <el-input
            v-model="form.welcome_media_file_id"
            placeholder="可为空。填写后 /start 时优先发送媒体，欢迎文本作为 caption"
          />
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
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import {
  createSupportBot,
  deleteSupportBot,
  getSupportBots,
  testSupportBotItem,
  updateSupportBot,
} from "../api/support"

const props = defineProps({
  bots: {
    type: Array,
    default: () => [],
  },
})

const items = ref([])
const dialogVisible = ref(false)
const form = reactive(emptyForm())
const enabledBots = computed(() => props.bots.filter((bot) => bot.enabled))

onMounted(load)

function emptyForm() {
  return {
    id: null,
    name: "",
    bot_id: null,
    bot_token: "",
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
  const res = await getSupportBots()
  items.value = res.data.items || []
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
  if (!form.bot_id && !form.bot_token.trim()) {
    ElMessage.warning("请选择已有 Bot 或填写 Bot Token")
    return
  }

  const payload = {
    ...form,
    name: form.name.trim(),
    bot_token: form.bot_token.trim(),
    support_group_chat_id: form.support_group_chat_id.trim(),
  }

  if (form.id) {
    await updateSupportBot(form.id, payload)
    ElMessage.success("客服 Bot 已保存")
  } else {
    await createSupportBot(payload)
    ElMessage.success("客服 Bot 已新增")
  }

  dialogVisible.value = false
  await load()
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
  return row.bot_token ? "自定义 Token" : "-"
}
</script>

<style scoped>
.support-page {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
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

.row {
  display: flex;
  align-items: center;
  gap: 10px;
}
</style>
