<template>
  <div class="page">
    <div class="toolbar">
      <div>
        <div class="title">我的频道</div>
        <div class="subtitle">统一管理所有目标频道，并检测 Bot 权限</div>
      </div>
      <div class="actions">
        <el-input v-model="filters.keyword" placeholder="搜索名称 / username / chat_id" clearable @keyup.enter="load" />
        <el-select v-model="filters.status" clearable placeholder="状态">
          <el-option label="enabled" value="enabled" />
          <el-option label="disabled" value="disabled" />
          <el-option label="error" value="error" />
        </el-select>
        <el-button @click="load">刷新</el-button>
        <el-button @click="batchCheck">批量检测</el-button>
        <el-button type="primary" @click="openCreate">新增频道</el-button>
      </div>
    </div>

    <el-table :data="channels" border>
      <el-table-column prop="title" label="频道名称" min-width="160" show-overflow-tooltip />
      <el-table-column prop="username" label="username" min-width="140" />
      <el-table-column prop="chat_id" label="chat_id" min-width="160" show-overflow-tooltip />
      <el-table-column prop="group_name" label="分组" min-width="120" />
      <el-table-column label="绑定 Bot" min-width="120">
        <template #default="{ row }">
          {{ botName(row.bot_id) }}
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'enabled' ? 'success' : row.status === 'error' ? 'danger' : 'info'">
            {{ row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="权限" min-width="220">
        <template #default="{ row }">
          <div class="perm">
            <el-tag size="small" :type="row.bot_is_member ? 'success' : 'danger'">在频道 {{ yesNo(row.bot_is_member) }}</el-tag>
            <el-tag size="small" :type="row.bot_is_admin ? 'success' : 'info'">管理员 {{ yesNo(row.bot_is_admin) }}</el-tag>
            <el-tag size="small" :type="row.can_post_messages ? 'success' : 'warning'">发帖 {{ yesNo(row.can_post_messages) }}</el-tag>
            <el-tag size="small" :type="row.can_manage_topics ? 'success' : 'info'">话题 {{ yesNo(row.can_manage_topics) }}</el-tag>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="last_check_at" label="最后检测" min-width="160" />
      <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip />
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" @click="check(row)">检测</el-button>
          <el-button size="small" @click="toggle(row)">
            {{ row.status === "disabled" ? "启用" : "禁用" }}
          </el-button>
          <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

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
          <el-select v-model="form.bot_id" clearable filterable placeholder="不选则使用系统默认 Bot">
            <el-option
              v-for="bot in enabledBots"
              :key="bot.id"
              :label="`${bot.name} (#${bot.id})`"
              :value="bot.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option label="enabled" value="enabled" />
            <el-option label="disabled" value="disabled" />
            <el-option label="error" value="error" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="3" />
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
  batchCheckMyChannels,
  checkMyChannel,
  createMyChannel,
  deleteMyChannel,
  getMyChannels,
  updateMyChannel,
} from "../api/myChannels"

const props = defineProps({
  bots: {
    type: Array,
    default: () => [],
  },
})

const channels = ref([])
const dialogVisible = ref(false)
const editing = ref(null)
const filters = reactive({
  keyword: "",
  status: "",
})
const form = reactive(emptyForm())
const enabledBots = computed(() => props.bots.filter((bot) => bot.enabled))

onMounted(load)

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

async function load() {
  const res = await getMyChannels(filters)
  channels.value = res.data.items || []
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

async function save() {
  if (!form.username && !form.chat_id) {
    ElMessage.error("username 和 chat_id 至少填写一个")
    return
  }

  if (editing.value?.id) {
    await updateMyChannel(editing.value.id, form)
    ElMessage.success("频道已保存")
  } else {
    await createMyChannel(form)
    ElMessage.success("频道已添加")
  }

  dialogVisible.value = false
  await load()
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
  await ElMessageBox.confirm("确定删除这个频道？旧任务字段不会被删除。", "确认删除", {
    type: "warning",
  })
  await deleteMyChannel(row.id)
  ElMessage.success("频道已删除")
  await load()
}

function botName(botId) {
  const bot = props.bots.find((item) => Number(item.id) === Number(botId))
  return bot ? `${bot.name} (#${bot.id})` : "默认 Bot"
}

function yesNo(value) {
  return value ? "是" : "否"
}
</script>

<style scoped>
.page {
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

.actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.actions .el-input {
  width: 260px;
}

.perm {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
}
</style>
