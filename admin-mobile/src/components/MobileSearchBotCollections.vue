<template>
  <section class="collection-page">
    <div class="group-filter">
      <el-select
        v-model="selectedGroup"
        filterable
        clearable
        placeholder="请先选择频道分组"
        @change="loadSubmissions"
      >
        <el-option v-for="group in groupOptions" :key="group" :label="group" :value="group" />
      </el-select>
      <el-button circle :loading="loading" :disabled="!selectedGroup" aria-label="刷新" @click="loadAll">
        <el-icon><Refresh /></el-icon>
      </el-button>
    </div>

    <EmptyState
      v-if="!selectedGroup"
      title="请选择频道分组"
      text="选择分组后，查看该分组在各搜索机器人中的提交和收录情况。"
    />

    <template v-else>
      <div class="summary-grid">
        <div><span>频道</span><strong>{{ groupChannels.length }}</strong></div>
        <div><span>已提交机器人</span><strong>{{ summary.submittedBots }}</strong></div>
        <div><span>已收录频道</span><strong>{{ summary.collectedChannels }}</strong></div>
        <div><span>已拉黑频道</span><strong>{{ summary.blockedChannels }}</strong></div>
        <div><span>未提交机器人</span><strong>{{ summary.missingBots }}</strong></div>
      </div>

      <div v-loading="loading" class="collection-list">
        <article v-for="row in rows" :key="row.id" class="collection-card">
          <div class="card-head">
            <div>
              <strong>{{ row.name }}</strong>
              <span>{{ row.username }}</span>
            </div>
            <StatusPill :status="row.status" :label="statusLabel(row.status)" />
          </div>

          <dl>
            <div class="wide">
              <dt>已收录频道链接</dt>
              <dd v-if="row.collectedLinks.length" class="link-list">
                <el-link
                  v-for="link in row.collectedLinks"
                  :key="link"
                  :href="link"
                  target="_blank"
                  type="primary"
                >
                  {{ link }}
                </el-link>
              </dd>
              <dd v-else>暂无已收录频道</dd>
            </div>
            <div>
              <dt>频道情况</dt>
              <dd>已提交 {{ row.submittedCount }} / {{ groupChannels.length }}</dd>
            </div>
            <div>
              <dt>当前收录</dt>
              <dd>{{ row.collectedCount }}</dd>
            </div>
            <div>
              <dt>当前拉黑</dt>
              <dd>{{ row.blockedCount }}</dd>
            </div>
            <div>
              <dt>提交异常</dt>
              <dd>{{ row.failedCount + row.pendingCount }}</dd>
            </div>
            <div class="wide">
              <dt>最后检测</dt>
              <dd>{{ formatDate(row.last_check_at) }}</dd>
            </div>
          </dl>
        </article>
        <EmptyState
          v-if="!loading && !rows.length"
          title="当前分组暂无搜索机器人"
          text="请先在搜索机器人页添加机器人。"
        />
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue"
import { ElMessage } from "element-plus"
import { Refresh } from "@element-plus/icons-vue"
import { getMyChannels, getSearchBots, getSearchBotSubmissions } from "../api"
import { getErrorMessage } from "../api/client"
import EmptyState from "./EmptyState.vue"
import StatusPill from "./StatusPill.vue"

const bots = ref([])
const channels = ref([])
const submissions = ref([])
const selectedGroup = ref("")
const loading = ref(false)

const groupOptions = computed(() => Array.from(new Set(
  channels.value.map((item) => String(item.group_name || "").trim()).filter(Boolean),
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
  return {
    ...bot,
    submittedCount: submitted.length,
    collectedCount: current.length,
    blockedCount: records.filter((record) => record.block_status === "blocked").length,
    failedCount: records.filter((record) => record.submit_status === "failed").length,
    pendingCount: records.filter((record) => ["queued", "submitting"].includes(record.submit_status)).length,
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
    const [botResponse, channelResponse] = await Promise.all([getSearchBots(), getMyChannels()])
    bots.value = botResponse.data.items || []
    channels.value = channelResponse.data.items || []
  } catch (error) {
    ElMessage.error(getErrorMessage(error, "加载机器人收录数据失败"))
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
    ElMessage.error(getErrorMessage(error, "加载分组收录状态失败"))
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

function formatDate(value) {
  return value ? String(value).replace("T", " ").slice(0, 19) : "未检测"
}

function statusLabel(status) {
  return ({ enabled: "正常", disabled: "已停用", error: "异常" })[status] || "未知"
}
</script>

<style scoped>
.collection-page { padding-bottom: 88px; }
.group-filter { display: flex; align-items: center; gap: 10px; padding: 12px 10px; }
.group-filter .el-select { flex: 1; }
.summary-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; padding: 0 10px 10px; }
.summary-grid > div { padding: 10px; border: 1px solid var(--el-border-color-lighter); background: var(--el-bg-color); }
.summary-grid span { display: block; color: var(--el-text-color-secondary); font-size: 12px; }
.summary-grid strong { display: block; margin-top: 4px; font-size: 18px; }
.collection-list { display: grid; gap: 10px; min-height: 220px; padding: 0 10px; }
.collection-card { padding: 13px; border: 1px solid var(--el-border-color-lighter); background: var(--el-bg-color); border-radius: 6px; }
.card-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; }
.card-head > div { min-width: 0; }
.card-head strong, .card-head span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.card-head span { margin-top: 3px; color: var(--el-text-color-secondary); font-size: 12px; }
dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; margin: 12px 0 0; }
dl > div { min-width: 0; padding: 8px; background: var(--el-fill-color-lighter); }
dl .wide { grid-column: 1 / -1; }
dt { color: var(--el-text-color-secondary); font-size: 12px; }
dd { margin: 4px 0 0; overflow: hidden; text-overflow: ellipsis; font-size: 13px; }
.link-list { display: grid; justify-items: start; gap: 4px; }
.link-list .el-link { max-width: 100%; }
@media (min-width: 680px) {
  .summary-grid { grid-template-columns: repeat(5, minmax(0, 1fr)); }
  .collection-list { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
