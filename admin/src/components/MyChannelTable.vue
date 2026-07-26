<template>
  <div class="page">
    <el-tabs v-model="currentTab" class="channel-tabs">
      <el-tab-pane label="我的频道" name="targets">
        <div class="toolbar">
          <div class="actions">
            <el-input
              v-model="filters.keyword"
              placeholder="搜索名称 / username / chat_id / https://t.me/..."
              clearable
              @keyup.enter="load"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-select
              v-model="filters.group_name"
              clearable
              filterable
              placeholder="分组"
              class="status-filter"
              @change="load"
            >
              <el-option
                v-for="group in groupOptions"
                :key="group"
                :label="group"
                :value="group"
              />
            </el-select>
            <el-select v-model="filters.status" clearable placeholder="状态" class="status-filter" @change="load">
              <el-option label="正常" value="enabled" />
              <el-option label="已禁用" value="disabled" />
              <el-option label="异常" value="error" />
            </el-select>
            <el-select
              v-model="filters.collection_status"
              clearable
              placeholder="收录状态"
              class="status-filter"
              @change="load"
            >
              <el-option label="已收录" value="collected" />
              <el-option label="审核中" value="reviewing" />
              <el-option label="未收录" value="not_collected" />
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
            height="492"
            empty-text="暂无频道，请点击“新增频道”添加你的目标频道。"
          >
            <el-table-column prop="title" label="频道名称" min-width="160" show-overflow-tooltip />
            <el-table-column label="username" min-width="150" show-overflow-tooltip>
              <template #default="{ row }">
                <CopyText v-if="row.username" :value="row.username" :text="row.username" tone="primary" />
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="创建人用户名" min-width="155" show-overflow-tooltip>
              <template #default="{ row }">
                <CopyText
                  v-if="row.can_view_creator && row.creator_username"
                  :value="row.creator_username"
                  :text="row.creator_username"
                  tone="primary"
                />
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="group_name" label="分组" min-width="120" show-overflow-tooltip />
            <el-table-column label="绑定 Bot" min-width="130" show-overflow-tooltip>
              <template #default="{ row }">
                <CopyText v-if="botUsername(row)" :value="botUsername(row)" :text="botUsername(row)" tone="primary" />
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <StatusTag :status="row.status" />
              </template>
            </el-table-column>
            <el-table-column prop="delivery_status" label="投放状态" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">{{ row.delivery_status || "-" }}</template>
            </el-table-column>
            <el-table-column prop="collection_status" label="收录状态" min-width="120" show-overflow-tooltip>
              <template #default="{ row }">
                <el-tag :type="collectionStatusType(row.collection_status)" size="small">
                  {{ row.collection_status || "未收录" }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip />
            <el-table-column label="操作" width="382" fixed="right">
              <template #default="{ row }">
                <div class="row-actions">
                  <el-button size="small" type="primary" :disabled="row.status === 'disabled'" @click="openChannelSubmit(row)">提交</el-button>
                  <el-button size="small" type="info" plain @click="openChannelSubmissionStatus(row)">查看</el-button>
                  <el-button size="small" @click="openEdit(row)">
                    <el-icon><Edit /></el-icon>
                    编辑
                  </el-button>
                  <el-button size="small" :loading="checkingId === row.id" @click="check(row)">
                    <el-icon><Connection /></el-icon>
                    检测
                  </el-button>
                  <el-button size="small" @click="toggle(row)">
                    {{ row.status === "disabled" ? "启用" : "停用" }}
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
              placeholder="搜索频道名 / 链接 / 分组 / https://t.me/..."
              clearable
              @keyup.enter="loadCloneChannels"
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-select
              v-model="cloneFilters.group_name"
              clearable
              filterable
              placeholder="分组"
              class="status-filter"
              @change="loadCloneChannels"
            >
              <el-option
                v-for="group in cloneGroupOptions"
                :key="group"
                :label="group"
                :value="group"
              />
            </el-select>
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
            height="492"
            empty-text="暂无克隆频道，请点击“新增克隆频道”添加源频道。"
          >
            <el-table-column prop="title" label="频道名" min-width="170" show-overflow-tooltip />
            <el-table-column label="频道链接" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                <CopyText v-if="row.channel_link" :value="row.channel_link" :text="row.channel_link" tone="primary" />
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column prop="group_name" label="分组" min-width="120" show-overflow-tooltip />
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

      <el-tab-pane label="机器人收录" name="collections">
        <SearchBotCollectionTable />
      </el-tab-pane>

      <el-tab-pane label="搜索机器人" name="search-bots">
        <SearchBotPanel
          ref="searchBotPanelRef"
          :accounts="accounts"
          :accounts-loading="accountsLoading"
          @submission-changed="handleSubmissionChanged"
        />
      </el-tab-pane>
    </el-tabs>

    <el-dialog
      v-model="submissionStatusDialogVisible"
      title="频道提交状态"
      width="min(1060px, calc(100vw - 24px))"
      append-to-body
      destroy-on-close
    >
      <div class="submission-dialog-heading">
        <div>
          <strong>{{ submissionStatusChannel?.title || submissionStatusChannel?.username || "当前频道" }}</strong>
          <span>{{ submissionStatusChannel?.username || submissionStatusChannel?.chat_id || "-" }}</span>
        </div>
        <el-tag
          :type="collectionStatusType(submissionStatusChannel?.collection_status)"
          size="small"
        >
          {{ submissionStatusChannel?.collection_status || "未收录" }}
        </el-tag>
      </div>

      <el-table
        v-loading="submissionStatusLoading"
        :data="channelSubmissionRows"
        border
        stripe
        max-height="420"
        empty-text="该频道暂无搜索机器人提交记录"
      >
        <el-table-column label="搜索机器人" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="submission-bot-cell">
              <span>{{ row.search_bot_name || "未命名机器人" }}</span>
              <CopyText
                v-if="row.search_bot_username"
                :value="row.search_bot_username"
                :text="row.search_bot_username"
                tone="primary"
              />
              <small>{{ formatDateTime(row.updated_at || row.last_checked_at) }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="提交账号" min-width="155" show-overflow-tooltip>
          <template #default="{ row }">{{ submissionAccountLabel(row) }}</template>
        </el-table-column>
        <el-table-column label="提交进度" min-width="350">
          <template #default="{ row }">
            <div class="submission-status-strip">
              <span>执行 <el-tag :type="submissionStatusType(row.submit_status)" size="small">{{ submissionStatusLabel(row.submit_status) }}</el-tag></span>
              <span>审核 <el-tag :type="submissionStatusType(row.review_status)" size="small">{{ submissionStatusLabel(row.review_status) }}</el-tag></span>
              <span>收录 <el-tag :type="submissionStatusType(row.collection_status)" size="small">{{ submissionStatusLabel(row.collection_status) }}</el-tag></span>
              <span>拉黑 <el-tag :type="submissionStatusType(row.block_status)" size="small">{{ submissionStatusLabel(row.block_status) }}</el-tag></span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="Telegram 实际权限" min-width="205" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="submission-permission-cell">
              <el-tag :type="permissionVerificationType(row.permission_status)" size="small">{{ permissionVerificationLabel(row.permission_status) }}</el-tag>
              <span>{{ submissionPermissionSummary(effectiveSubmissionRights(row)) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right" align="center">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button size="small" type="primary" plain @click="openChannelSubmissionEdit(row)">更新状态</el-button>
              <el-button size="small" @click="openChannelPermissionEdit(row)">调整权限</el-button>
            </div>
          </template>
        </el-table-column>
        <template #empty>
          <el-empty
            :description="submissionStatusChannel?.group_name
              ? '该频道还没有搜索机器人提交记录'
              : '该频道未设置分组，完善分组后才能提交到搜索机器人'"
          >
            <el-button
              type="primary"
              :disabled="submissionStatusChannel?.status === 'disabled'"
              @click="submitFromStatusDialog"
            >
              {{ submissionStatusChannel?.group_name ? "提交到搜索机器人" : "先设置频道分组" }}
            </el-button>
          </el-empty>
        </template>
      </el-table>

      <template #footer>
        <el-button type="primary" @click="submissionStatusDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="dialogVisible" :title="editing?.id ? '编辑频道' : '新增频道'" width="720px">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="频道名称">
          <el-input v-model="form.title" class="description-field" placeholder="例如：北京投放频道" />
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-select v-model="form.status" class="description-field">
            <el-option label="正常" value="enabled" />
            <el-option label="已禁用" value="disabled" />
            <el-option label="异常" value="error" />
          </el-select>
        </el-descriptions-item>
        <el-descriptions-item label="username">
          <el-input
            v-model="form.username"
            class="description-field"
            placeholder="@channel_username 或 https://t.me/channel_username"
            @blur="normalizeChannelUsername"
          />
        </el-descriptions-item>
        <el-descriptions-item label="chat_id">
          <el-input v-model="form.chat_id" class="description-field" placeholder="-100xxxxxxxxxx，可选" />
        </el-descriptions-item>
        <el-descriptions-item label="频道类型">
          <el-input v-model="form.channel_type" class="description-field" placeholder="例如：channel / supergroup" />
        </el-descriptions-item>
        <el-descriptions-item label="分组">
          <el-input v-model="form.group_name" class="description-field" placeholder="例如：北京" />
        </el-descriptions-item>
        <el-descriptions-item label="绑定 Bot">
          <BotSelect v-model="form.bot_id" :bots="props.bots" class="description-field" placeholder="不选则使用系统默认 Bot" />
        </el-descriptions-item>
        <el-descriptions-item label="最后检测">{{ formatDateTime(editing?.last_check_at) }}</el-descriptions-item>
        <el-descriptions-item label="投放状态">
          <el-input v-model="form.delivery_status" class="description-field" placeholder="例如：投放中 / 暂停 / 待投放" />
        </el-descriptions-item>
        <el-descriptions-item label="收录状态">
          <div class="readonly-field">
            <el-input v-model="form.collection_status" class="description-field" disabled />
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="克隆状态" :span="2">{{ editing?.clone_status || "-" }}</el-descriptions-item>
        <el-descriptions-item label="成员数">{{ formatMemberCount(editing) }}</el-descriptions-item>
        <el-descriptions-item label="频道创建者">{{ formatCreator(editing) }}</el-descriptions-item>
        <el-descriptions-item label="权限" :span="2">
          <div class="detail-tags">
            <el-tag size="small" :type="editing?.bot_is_member ? 'success' : 'danger'">在频道 {{ yesNo(editing?.bot_is_member) }}</el-tag>
            <el-tag size="small" :type="editing?.bot_is_admin ? 'success' : 'info'">管理员 {{ yesNo(editing?.bot_is_admin) }}</el-tag>
            <el-tag size="small" :type="editing?.can_post_messages ? 'success' : 'warning'">发帖 {{ yesNo(editing?.can_post_messages) }}</el-tag>
            <el-tag size="small" :type="editing?.can_edit_messages ? 'success' : 'info'">编辑 {{ yesNo(editing?.can_edit_messages) }}</el-tag>
            <el-tag size="small" :type="editing?.can_delete_messages ? 'success' : 'info'">删除 {{ yesNo(editing?.can_delete_messages) }}</el-tag>
            <el-tag size="small" :type="editing?.can_manage_topics ? 'success' : 'info'">话题 {{ yesNo(editing?.can_manage_topics) }}</el-tag>
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="查看能力" :span="2">
          <div class="detail-tags">
            <el-tag size="small" :type="editing?.can_view_member_count ? 'success' : 'warning'">频道人数 {{ editing?.can_view_member_count ? "可查看" : "不可查看" }}</el-tag>
            <el-tag size="small" :type="editing?.can_view_creator ? 'success' : 'warning'">频道创建者 {{ editing?.can_view_creator ? "可查看" : "不可查看" }}</el-tag>
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="备注" :span="2">
          <el-input v-model="form.remark" class="description-field" type="textarea" :rows="3" placeholder="运营备注，可选" />
        </el-descriptions-item>
        <el-descriptions-item label="最近错误" :span="2">{{ editing?.last_error || "-" }}</el-descriptions-item>
      </el-descriptions>
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
          <el-input v-model="cloneForm.remark" type="textarea" :rows="3" placeholder="源频道备注，可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="cloneDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="cloneSaving" @click="saveClone">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="checkDialogVisible" title="频道检测信息" width="720px">
      <el-descriptions v-if="checkInfo" :column="2" border>
        <el-descriptions-item label="频道名称">{{ checkInfo.title || "-" }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <StatusTag :status="checkInfo.status" />
        </el-descriptions-item>
        <el-descriptions-item label="username">{{ checkInfo.username || "-" }}</el-descriptions-item>
        <el-descriptions-item label="chat_id">{{ checkInfo.chat_id || "-" }}</el-descriptions-item>
        <el-descriptions-item label="频道类型">{{ checkInfo.channel_type || "-" }}</el-descriptions-item>
        <el-descriptions-item label="分组">{{ checkInfo.group_name || "-" }}</el-descriptions-item>
        <el-descriptions-item label="绑定 Bot">{{ botUsername(checkInfo) || "-" }}</el-descriptions-item>
        <el-descriptions-item label="最后检测">{{ formatDateTime(checkInfo.last_check_at) }}</el-descriptions-item>
        <el-descriptions-item label="投放状态">{{ checkInfo.delivery_status || "-" }}</el-descriptions-item>
        <el-descriptions-item label="收录状态">{{ checkInfo.collection_status || "-" }}</el-descriptions-item>
        <el-descriptions-item label="克隆状态" :span="2">{{ checkInfo.clone_status || "-" }}</el-descriptions-item>
        <el-descriptions-item label="成员数">{{ formatMemberCount(checkInfo) }}</el-descriptions-item>
        <el-descriptions-item label="频道创建者">{{ formatCreator(checkInfo) }}</el-descriptions-item>
        <el-descriptions-item label="权限" :span="2">
          <div class="detail-tags">
            <el-tag size="small" :type="checkInfo.bot_is_member ? 'success' : 'danger'">在频道 {{ yesNo(checkInfo.bot_is_member) }}</el-tag>
            <el-tag size="small" :type="checkInfo.bot_is_admin ? 'success' : 'info'">管理员 {{ yesNo(checkInfo.bot_is_admin) }}</el-tag>
            <el-tag size="small" :type="checkInfo.can_post_messages ? 'success' : 'warning'">发帖 {{ yesNo(checkInfo.can_post_messages) }}</el-tag>
            <el-tag size="small" :type="checkInfo.can_edit_messages ? 'success' : 'info'">编辑 {{ yesNo(checkInfo.can_edit_messages) }}</el-tag>
            <el-tag size="small" :type="checkInfo.can_delete_messages ? 'success' : 'info'">删除 {{ yesNo(checkInfo.can_delete_messages) }}</el-tag>
            <el-tag size="small" :type="checkInfo.can_manage_topics ? 'success' : 'info'">话题 {{ yesNo(checkInfo.can_manage_topics) }}</el-tag>
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="查看能力" :span="2">
          <div class="detail-tags">
            <el-tag size="small" :type="checkInfo.can_view_member_count ? 'success' : 'warning'">频道人数 {{ checkInfo.can_view_member_count ? "可查看" : "不可查看" }}</el-tag>
            <el-tag size="small" :type="checkInfo.can_view_creator ? 'success' : 'warning'">频道创建者 {{ checkInfo.can_view_creator ? "可查看" : "不可查看" }}</el-tag>
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="最近错误" :span="2">{{ checkInfo.last_error || "-" }}</el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button type="primary" @click="checkDialogVisible = false">关闭</el-button>
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
  getSearchBotSubmissions,
  updateCloneChannel,
  updateMyChannel,
} from "../api/myChannels"
import BotSelect from "./BotSelect.vue"
import CopyText from "./CopyText.vue"
import StatusTag from "./StatusTag.vue"
import SearchBotPanel from "./SearchBotPanel.vue"
import SearchBotCollectionTable from "./SearchBotCollectionTable.vue"

const props = defineProps({
  bots: {
    type: Array,
    default: () => [],
  },
  accounts: {
    type: Array,
    default: () => [],
  },
  accountsLoading: {
    type: Boolean,
    default: false,
  },
  activeTab: {
    type: String,
    default: "targets",
  },
})

const emit = defineEmits(["update:active-tab"])
const currentTab = computed({
  get: () => props.activeTab,
  set: (value) => emit("update:active-tab", value),
})
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
const checkingId = ref(null)
const searchBotPanelRef = ref(null)
const checkDialogVisible = ref(false)
const checkInfo = ref(null)
const submissionStatusDialogVisible = ref(false)
const submissionStatusLoading = ref(false)
const submissionStatusChannel = ref(null)
const channelSubmissionRows = ref([])
const filters = reactive({
  keyword: "",
  group_name: "",
  status: "",
  collection_status: "",
})
const cloneFilters = reactive({
  keyword: "",
  group_name: "",
})
const form = reactive(emptyForm())
const cloneForm = reactive(emptyCloneForm())

const groupOptions = computed(() => uniqueGroups(channels.value))
const cloneGroupOptions = computed(() => uniqueGroups(cloneChannels.value))

onMounted(async () => {
  await Promise.all([load(), loadCloneChannels()])
})

function emptyForm() {
  return {
    title: "",
    username: "",
    chat_id: "",
    channel_type: "",
    group_name: "",
    bot_id: null,
    status: "enabled",
    delivery_status: "",
    collection_status: "",
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

function uniqueGroups(list) {
  return Array.from(new Set(
    list
      .map((item) => String(item.group_name || "").trim())
      .filter(Boolean),
  )).sort((a, b) => a.localeCompare(b, "zh-Hans-CN"))
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

function openChannelSubmit(row) {
  if (!searchBotPanelRef.value) {
    ElMessage.error("提交功能初始化失败，请刷新页面后重试")
    return
  }

  searchBotPanelRef.value.openSubmitForChannel(row)
}

async function openChannelSubmissionStatus(row) {
  submissionStatusChannel.value = row
  channelSubmissionRows.value = []
  submissionStatusDialogVisible.value = true
  submissionStatusLoading.value = true

  try {
    const res = await getSearchBotSubmissions({ my_channel_id: row.id })
    channelSubmissionRows.value = res.data.items || []
  } catch (error) {
    ElMessage.error(readError(error, "加载频道提交状态失败"))
  } finally {
    submissionStatusLoading.value = false
  }
}

function submitFromStatusDialog() {
  const channel = submissionStatusChannel.value
  submissionStatusDialogVisible.value = false
  if (!channel) return
  if (!channel.group_name) {
    ElMessage.warning("请先设置频道分组，再提交到搜索机器人")
    openEdit(channel)
    return
  }
  openChannelSubmit(channel)
}

function openChannelSubmissionEdit(row) {
  if (!searchBotPanelRef.value) {
    ElMessage.error("状态更新功能初始化失败，请刷新页面后重试")
    return
  }
  submissionStatusDialogVisible.value = false
  searchBotPanelRef.value.openSubmissionEdit(row)
}

function openChannelPermissionEdit(row) {
  if (!searchBotPanelRef.value) {
    ElMessage.error("权限调整功能初始化失败，请刷新页面后重试")
    return
  }
  submissionStatusDialogVisible.value = false
  searchBotPanelRef.value.openPermissionEdit(row)
}

async function handleSubmissionChanged() {
  await load()
}

function submissionPermissionSummary(rights) {
  const labels = {
    post_messages: "发布消息",
    edit_messages: "编辑消息",
    delete_messages: "删除消息",
    pin_messages: "置顶消息",
    change_info: "修改频道信息",
    invite_users: "邀请用户",
    ban_users: "管理用户",
    manage_call: "管理视频聊天",
    manage_topics: "管理话题",
    add_admins: "添加管理员",
    anonymous: "匿名管理",
    post_stories: "发布动态",
    edit_stories: "编辑动态",
    delete_stories: "删除动态",
    manage_direct_messages: "管理频道私信",
    manage_ranks: "管理管理员头衔",
  }
  const selected = Object.entries(rights || {})
    .filter(([, enabled]) => enabled)
    .map(([key]) => labels[key] || key)
  return selected.length ? selected.join("、") : "最小权限"
}

function submissionAccountLabel(row) {
  if (row.account_name) return `${row.account_name}（系统账号）`
  if (row.account_id) return `系统账号 #${row.account_id}`
  if (row.manual_account_id) return `账号 ID ${row.manual_account_id}`
  return "-"
}

function effectiveSubmissionRights(row) {
  const actual = row?.applied_admin_rights
  return actual && Object.keys(actual).length ? actual : (row?.admin_rights || {})
}

function permissionVerificationLabel(status) {
  return ({
    pending: "待应用",
    applying: "应用中",
    applied: "已验证",
    mismatch: "不一致",
    failed: "应用失败",
    unverified: "人工登记",
  })[status] || "未验证"
}

function permissionVerificationType(status) {
  if (status === "applied") return "success"
  if (["mismatch", "failed"].includes(status)) return "danger"
  if (["pending", "applying"].includes(status)) return "warning"
  return "info"
}

function submissionOverallState(row) {
  if (row.block_status === "blocked") return { label: "已拉黑", type: "danger" }
  if (row.collection_status === "collected") return { label: "已收录", type: "success" }
  if (row.submit_status === "failed") return { label: "提交失败", type: "danger" }
  if (row.review_status === "reviewing") return { label: "审核中", type: "warning" }
  if (row.review_status === "pending") return { label: "待审核", type: "warning" }
  if (row.review_status === "rejected") return { label: "已拒绝", type: "danger" }
  if (row.collection_status === "not_collected") return { label: "未收录", type: "info" }
  if (row.review_status === "approved") return { label: "已通过", type: "success" }
  if (row.submit_status === "submitting") return { label: "提交中", type: "warning" }
  if (row.submit_status === "success") return { label: "已提交", type: "info" }
  if (row.submit_status === "manual") return { label: "手动登记", type: "info" }
  return { label: "状态未知", type: "info" }
}

function collectionStatusType(status) {
  if (status === "已收录") return "success"
  if (status === "审核中") return "warning"
  return "info"
}

function submissionStatusLabel(status) {
  return ({
    queued: "排队中",
    submitting: "提交中",
    success: "已提交",
    manual: "手动登记",
    failed: "提交失败",
    unknown: "未知",
    pending: "待审核",
    reviewing: "审核中",
    approved: "已通过",
    rejected: "已拒绝",
    collected: "已收录",
    not_collected: "未收录",
    normal: "正常",
    blocked: "已拉黑",
  })[status] || status || "未知"
}

function submissionStatusType(status) {
  if (["success", "approved", "collected", "normal"].includes(status)) return "success"
  if (["failed", "rejected", "blocked"].includes(status)) return "danger"
  if (["queued", "submitting", "pending", "reviewing"].includes(status)) return "warning"
  return "info"
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
    channel_type: row.channel_type || "",
    group_name: row.group_name || "",
    bot_id: row.bot_id || null,
    status: row.status || "enabled",
    delivery_status: row.delivery_status || "",
    collection_status: row.collection_status || "",
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
  normalizeChannelUsername()

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

function normalizeChannelUsername() {
  const value = String(form.username || "").trim()
  if (!value) return

  const linkMatch = value.match(/^(?:https?:\/\/)?t\.me\/([^/?#]+)/i)
  const username = linkMatch?.[1] || value.replace(/^@/, "")
  if (!username || username.startsWith("+") || ["c", "joinchat"].includes(username.toLowerCase())) return

  form.username = `@${username.toLowerCase()}`
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
  checkingId.value = row.id
  try {
    const res = await checkMyChannel(row.id)
    checkInfo.value = res.data.item || row
    checkDialogVisible.value = true
    if (res.data.ok) {
      ElMessage.success("检测完成")
    } else {
      ElMessage.warning(res.data.message || "检测失败")
    }
    await load()
  } finally {
    checkingId.value = null
  }
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

function formatMemberCount(row) {
  if (!row || !row.can_view_member_count) {
    return "不可查看"
  }

  return row.member_count === null || row.member_count === undefined
    ? "不可查看"
    : String(row.member_count)
}

function formatCreator(row) {
  if (!row || !row.can_view_creator) {
    return "不可查看"
  }

  const username = row.creator_username || ""
  const name = row.creator_name || ""
  const userId = row.creator_user_id || ""
  const parts = [name, username, userId ? `ID：${userId}` : ""].filter(Boolean)

  return parts.length ? parts.join(" / ") : "不可查看"
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

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
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
  width: 320px;
}

.status-filter {
  width: 150px;
}

.table-card {
  margin-top: 12px;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.row-actions .el-button {
  margin-left: 0;
}

.submission-dialog-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
}

.submission-dialog-heading > div,
.submission-bot-cell,
.readonly-field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.submission-dialog-heading span,
.readonly-field > span {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.5;
}

.submission-bot-cell {
  gap: 2px;
}

.submission-bot-cell small {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.submission-status-strip {
  display: flex;
  align-items: center;
  gap: 8px;
  white-space: nowrap;
}

.submission-status-strip > span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.submission-permission-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  white-space: nowrap;
}

.submission-permission-cell > span {
  overflow: hidden;
  text-overflow: ellipsis;
}

.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.description-field {
  width: 100%;
}

@media (max-width: 900px) {
  .toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .actions {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    justify-content: stretch;
  }

  .actions .el-input,
  .status-filter {
    width: 100%;
  }

}

@media (max-width: 520px) {
  .detail-tags {
    gap: 4px;
  }
}
</style>
