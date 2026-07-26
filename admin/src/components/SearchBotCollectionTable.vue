<template>
  <div class="collection-panel">
    <div class="collection-toolbar">
      <el-select
        v-model="selectedGroup"
        filterable
        clearable
        placeholder="请先选择频道分组"
        class="group-select"
        @change="loadSubmissions"
      >
        <el-option v-for="group in groupOptions" :key="group" :label="group" :value="group" />
      </el-select>
      <el-button :loading="loading" :disabled="!selectedGroup" @click="loadAll">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>

    <el-empty
      v-if="!selectedGroup"
      :image-size="84"
      description="请选择频道分组，查看该分组在各搜索机器人中的提交和收录情况"
      class="group-empty"
    />

    <template v-else>
      <div class="collection-summary">
        <div><span>分组频道</span><strong>{{ groupChannels.length }}</strong></div>
        <div><span>已提交机器人</span><strong class="success-text">{{ summary.submittedBots }}</strong></div>
        <div><span>已收录频道</span><strong class="success-text">{{ summary.collectedChannels }}</strong></div>
        <div><span>已拉黑频道</span><strong class="danger-text">{{ summary.blockedChannels }}</strong></div>
        <div><span>未提交机器人</span><strong>{{ summary.missingBots }}</strong></div>
      </div>

      <el-table
        v-loading="loading"
        :data="rows"
        row-key="id"
        border
        stripe
        height="520"
        style="width: 100%"
      >
        <template #empty>
          <el-empty :image-size="72" description="当前分组暂无可展示的搜索机器人" />
        </template>
        <el-table-column prop="name" label="机器人名称" min-width="150" show-overflow-tooltip />
        <el-table-column label="机器人 ID" min-width="165">
          <template #default="{ row }">
            <CopyText :value="row.username" :text="row.username" tone="primary" />
          </template>
        </el-table-column>
        <el-table-column label="状态" width="92" align="center">
          <template #default="{ row }"><StatusTag :status="row.status" /></template>
        </el-table-column>
        <el-table-column label="已收录频道链接" min-width="235">
          <template #default="{ row }">
            <el-tooltip
              v-if="row.collectedLinks.length"
              placement="top"
              :content="row.collectedLinks.join('、')"
            >
              <div class="channel-link-cell">
                <CopyText
                  :value="row.collectedLinks[0]"
                  :text="row.collectedLinks[0]"
                  tone="primary"
                />
                <span v-if="row.collectedLinks.length > 1" class="more-count">
                  +{{ row.collectedLinks.length - 1 }}
                </span>
              </div>
            </el-tooltip>
            <span v-else class="muted-text">暂无已收录频道</span>
          </template>
        </el-table-column>
        <el-table-column label="频道情况" min-width="190">
          <template #default="{ row }">
            <div class="channel-progress">
              <span>已提交 {{ row.submittedCount }} / {{ groupChannels.length }}</span>
              <el-tag v-if="row.failedCount" type="danger" size="small">
                失败 {{ row.failedCount }}
              </el-tag>
              <el-tag v-else-if="row.pendingCount" type="warning" size="small">
                处理中 {{ row.pendingCount }}
              </el-tag>
              <el-tag v-else :type="row.submittedCount ? 'success' : 'info'" size="small">
                {{ row.submittedCount ? "已提交" : "未提交" }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="当前收录" width="100" align="center">
          <template #default="{ row }">
            <strong :class="{ 'success-text': row.collectedCount > 0 }">{{ row.collectedCount }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="当前拉黑" width="100" align="center">
          <template #default="{ row }">
            <strong :class="{ 'danger-text': row.blockedCount > 0 }">{{ row.blockedCount }}</strong>
          </template>
        </el-table-column>
        <el-table-column label="最后检测" min-width="160">
          <template #default="{ row }">
            <span v-if="row.last_check_at">{{ formatDateTime(row.last_check_at) }}</span>
            <span v-else class="muted-text">未检测</span>
          </template>
        </el-table-column>
      </el-table>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
import { Refresh } from "@element-plus/icons-vue"
import {
  getMyChannels,
  getSearchBots,
  getSearchBotSubmissions,
} from "../api/myChannels"
import CopyText from "./CopyText.vue"
import StatusTag from "./StatusTag.vue"

const bots = ref([])
const channels = ref([])
const submissions = ref([])
const selectedGroup = ref("")
const loading = ref(false)

const groupOptions = computed(() => Array.from(new Set(
  channels.value
    .map((item) => String(item.group_name || "").trim())
    .filter(Boolean),
)).sort((a, b) => a.localeCompare(b, "zh-Hans-CN")))

const groupChannels = computed(() => channels.value.filter(
  (item) => item.group_name === selectedGroup.value,
))

const latestRecords = computed(() => {
  const latest = new Map()
  submissions.value.forEach((record) => {
    const key = `${record.search_bot_id}:${record.my_channel_id}`
    const current = latest.get(key)
    if (!current || Number(record.id || 0) > Number(current.id || 0)) latest.set(key, record)
  })
  return Array.from(latest.values())
})

const rows = computed(() => bots.value.map((bot) => {
  const records = latestRecords.value.filter(
    (record) => Number(record.search_bot_id) === Number(bot.id),
  )
  const submitted = records.filter((record) => ["success", "manual"].includes(record.submit_status))
  const collected = records.filter((record) => record.collection_status === "collected")
  const current = records.filter((record) => record.is_current)
  const blocked = records.filter((record) => record.block_status === "blocked")
  const pending = records.filter((record) => ["queued", "submitting"].includes(record.submit_status))
  const failed = records.filter((record) => record.submit_status === "failed")

  return {
    ...bot,
    submittedCount: submitted.length,
    collectedCount: current.length,
    blockedCount: blocked.length,
    pendingCount: pending.length,
    failedCount: failed.length,
    collectedLinks: Array.from(new Set(collected.map(channelLink).filter(Boolean))),
  }
}).sort((a, b) => {
  if (a.submittedCount !== b.submittedCount) return b.submittedCount - a.submittedCount
  if (a.collectedCount !== b.collectedCount) return b.collectedCount - a.collectedCount
  return String(a.name || "").localeCompare(String(b.name || ""), "zh-Hans-CN")
}))

const summary = computed(() => ({
  submittedBots: rows.value.filter((row) => row.submittedCount > 0).length,
  collectedChannels: new Set(
    latestRecords.value
      .filter((record) => record.collection_status === "collected")
      .map((record) => record.my_channel_id),
  ).size,
  blockedChannels: new Set(
    latestRecords.value
      .filter((record) => record.block_status === "blocked")
      .map((record) => record.my_channel_id),
  ).size,
  missingBots: rows.value.filter((row) => row.submittedCount === 0).length,
}))

onMounted(loadBaseData)

async function loadBaseData() {
  loading.value = true
  try {
    const [botResponse, channelResponse] = await Promise.all([
      getSearchBots(),
      getMyChannels(),
    ])
    bots.value = botResponse.data.items || []
    channels.value = channelResponse.data.items || []
  } catch (error) {
    ElMessage.error(readError(error, "加载机器人收录数据失败"))
  } finally {
    loading.value = false
  }
}

async function loadSubmissions() {
  submissions.value = []
  if (!selectedGroup.value) return

  loading.value = true
  try {
    const response = await getSearchBotSubmissions({ group_name: selectedGroup.value })
    submissions.value = response.data.items || []
  } catch (error) {
    ElMessage.error(readError(error, "加载分组收录状态失败"))
  } finally {
    loading.value = false
  }
}

async function loadAll() {
  await loadBaseData()
  if (!selectedGroup.value) return
  if (!groupOptions.value.includes(selectedGroup.value)) {
    selectedGroup.value = ""
    submissions.value = []
    return
  }
  await loadSubmissions()
}

function channelLink(record) {
  const username = String(record.channel_username || "").trim().replace(/^@/, "")
  return username ? `https://t.me/${username}` : ""
}

function formatDateTime(value) {
  if (!value) return "-"
  const text = String(value).replace("T", " ")
  return text.slice(0, 19)
}

function readError(error, fallback) {
  return error?.response?.data?.detail || error?.response?.data?.message || error?.message || fallback
}
</script>

<style scoped>
.collection-panel { min-height: 600px; }
.collection-toolbar { display: flex; align-items: center; gap: 10px; padding: 14px 0; }
.group-select { width: 260px; }
.group-empty { min-height: 500px; display: flex; align-items: center; justify-content: center; }
.collection-summary {
  display: grid;
  grid-template-columns: repeat(5, minmax(120px, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}
.collection-summary > div {
  min-height: 62px;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-blank);
}
.collection-summary span { display: block; color: var(--el-text-color-secondary); font-size: 12px; }
.collection-summary strong { display: block; margin-top: 5px; font-size: 19px; }
.channel-link-cell, .channel-progress { display: flex; align-items: center; gap: 8px; min-width: 0; white-space: nowrap; }
.more-count { flex: none; color: var(--el-text-color-secondary); font-size: 12px; }
.muted-text { color: var(--el-text-color-secondary); }
.success-text { color: var(--el-color-success); }
.danger-text { color: var(--el-color-danger); }
@media (max-width: 900px) {
  .collection-summary { grid-template-columns: repeat(3, minmax(120px, 1fr)); }
}
</style>
