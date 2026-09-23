<template>
  <section class="channel-explorer" :class="{ 'channel-explorer--detail': selectedId }">
    <template v-if="!selectedId">
      <div class="list-heading">
        <div>
          <h1>频道</h1>
          <p>查看投放、任务和搜索机器人收录情况</p>
        </div>
        <request-button type="primary" @click="emit('create')">新增</request-button>
      </div>

      <el-input
        :model-value="keyword"
        class="channel-search"
        size="large"
        clearable
        aria-label="搜索频道"
        placeholder="搜索频道名称、链接或分组"
        @update:model-value="emit('update:keyword', $event)"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>

      <div class="channel-filters" role="group" aria-label="筛选频道状态">
        <button
          v-for="item in filters"
          :key="item.key"
          type="button"
          :class="{ active: filter === item.key }"
          :aria-pressed="filter === item.key"
          @click="filter = item.key"
        >{{ item.label }}</button>
      </div>

      <div v-if="loading" class="channel-list-loading" role="status" aria-label="正在加载频道">
        <el-skeleton v-for="index in 5" :key="index" animated :rows="1" />
      </div>
      <div v-else-if="visibleChannels.length" class="channel-list" aria-label="频道列表">
        <button
          v-for="item in visibleChannels"
          :key="item.id"
          type="button"
          class="channel-row"
          :aria-label="`查看${item.title || item.username || `频道 ${item.id}`}的详情`"
          @click="emit('open', item.id)"
        >
          <span class="channel-avatar" aria-hidden="true">{{ avatarText(item) }}</span>
          <span class="channel-row-body">
            <span class="channel-row-top">
              <strong>{{ item.title || item.username || `频道 #${item.id}` }}</strong>
              <time>{{ shortDate(item.last_content_at || item.updated_at || item.last_check_at) }}</time>
            </span>
            <span class="channel-row-subtitle">{{ item.username || item.chat_id || '未设置频道标识' }}</span>
            <span class="channel-row-bottom">
              <span>{{ item.bot_name ? `Bot · ${item.bot_name}` : (item.group_name || '未分组') }}</span>
              <el-tag size="small" :type="collectionTag(item.collection_status)">{{ item.collection_status || '未收录' }}</el-tag>
            </span>
          </span>
          <el-icon class="channel-chevron" aria-hidden="true"><ArrowRight /></el-icon>
        </button>
      </div>
      <EmptyState
        v-else
        :title="keyword.trim() || filter !== 'all' ? '没有匹配的频道' : '还没有频道'"
        :text="keyword.trim() || filter !== 'all' ? '试着清空搜索或切换筛选。' : '点击新增频道，开始管理投放和收录。'"
      />
      <div class="list-bottom-action">
        <request-button plain :disabled="!channels.length" @click="emit('batch-check')">批量检测频道</request-button>
      </div>
    </template>

    <template v-else>
      <div v-if="overviewLoading && !overview" class="detail-loading" role="status" aria-label="正在加载频道详情">
        <el-skeleton animated :rows="9" />
      </div>
      <div v-else-if="overviewError" class="detail-error">
        <el-alert type="error" show-icon :closable="false" :title="overviewError" />
        <request-button type="primary" @click="emit('retry')">重新加载</request-button>
      </div>
      <template v-else-if="channel">
        <div class="detail-hero">
          <span class="channel-avatar channel-avatar--large" aria-hidden="true">{{ avatarText(channel) }}</span>
          <h1>{{ channel.title || channel.username || `频道 #${channel.id}` }}</h1>
          <p>{{ channel.username || channel.chat_id }}</p>
          <div class="detail-hero-tags">
            <StatusPill :status="channel.status" :label="channel.status === 'disabled' ? '已停用' : '正常'" />
            <el-tag :type="collectionTag(overview?.collection_status)">{{ overview?.collection_status || '未收录' }}</el-tag>
          </div>
        </div>

        <div class="detail-actions">
          <request-button plain @click="emit('check', channel)">检测</request-button>
          <request-button plain @click="emit('edit', channel)">编辑</request-button>
          <request-button type="primary" :disabled="channel.status === 'disabled' || !channel.group_name" @click="emit('submit', channel)">提交收录</request-button>
        </div>
        <p v-if="!channel.group_name" class="detail-hint">提交收录前，请先编辑频道并设置分组。</p>
        <p v-if="overviewLoading" class="detail-refreshing" role="status">正在更新频道详情…</p>

        <div class="detail-summary" aria-label="频道概况">
          <div><span>关联任务</span><strong>{{ overview?.tasks?.length || 0 }}</strong></div>
          <div><span>运行中</span><strong>{{ runningCount }}</strong></div>
          <div><span>收录机器人</span><strong>{{ collectedCount }}/{{ overview?.collections?.length || 0 }}</strong></div>
        </div>

        <section class="detail-section">
          <h2>任务与进度</h2>
          <p class="section-note">显示当前频道作为来源或目标的任务；累计发送量为整项任务的记录。</p>
          <div v-if="overview?.tasks?.length" class="detail-list">
            <article v-for="task in overview.tasks" :key="`${task.type}-${task.id}`" class="detail-list-item task-item">
              <div class="item-main">
                <span class="item-icon" aria-hidden="true">{{ task.type === 'clone' ? '克' : '听' }}</span>
                <div class="item-text">
                  <strong>{{ task.name }}</strong>
                  <span>{{ task.type === 'clone' ? '克隆任务' : '监听任务' }} · {{ task.roles.includes('target') ? '目标频道' : '来源频道' }}</span>
                </div>
                <StatusPill :status="task.status" :label="taskStatus(task)" />
              </div>
              <div class="item-detail">
                <span>发送 Bot：{{ task.bot_name || '由频道绑定或系统选择' }}</span>
                <span>任务累计发送：{{ task.sent_count }} 条</span>
                <span v-if="task.type === 'clone' && task.last_message_id">处理至源消息 #{{ task.last_message_id }}</span>
                <span v-if="task.type === 'listener' && task.last_received_at">最近收到：{{ formatDate(task.last_received_at) }}</span>
                <span v-if="task.last_error" class="item-error">{{ task.last_error }}</span>
              </div>
              <request-button plain size="small" @click="emit('open-task', task)">查看任务</request-button>
            </article>
          </div>
          <EmptyState v-else title="暂无关联任务" text="在监听或克隆任务中选择此频道后，会显示在这里。" />
          <p v-if="restrictedTasks" class="permission-note">当前账号无权查看部分任务，任务数量仅统计有权限查看的部分。</p>
        </section>

        <section class="detail-section">
          <h2>分发机器人</h2>
          <div v-if="overview?.bots?.length" class="detail-list">
            <div v-for="bot in overview.bots" :key="bot.id" class="detail-list-item bot-item">
              <span class="item-icon item-icon--bot" aria-hidden="true">B</span>
              <div class="item-text">
                <strong>{{ bot.name }}</strong>
                <span>{{ bot.username || `Bot #${bot.id}` }} · {{ bot.sources.join('、') }}</span>
              </div>
              <StatusPill :status="bot.enabled ? 'enabled' : 'disabled'" :label="bot.enabled ? '正常' : '已停用'" />
            </div>
          </div>
          <EmptyState v-else title="暂无明确绑定的 Bot" text="任务未指定 Bot 时，系统可能按频道绑定或默认规则选择。" />
        </section>

        <section class="detail-section">
          <div class="section-heading">
            <h2>搜索机器人收录</h2>
            <request-button plain size="small" @click="emit('submissions', channel)">查看记录</request-button>
          </div>
          <div v-if="overview?.collections?.length" class="detail-list">
            <div v-for="record in overview.collections" :key="record.search_bot_id" class="detail-list-item collection-item">
              <span class="item-icon item-icon--search" aria-hidden="true">搜</span>
              <div class="item-text">
                <strong>{{ record.name }}</strong>
                <span>{{ record.username || '搜索机器人' }} · {{ reviewLabel(record.review_status) }}</span>
                <span v-if="record.last_error" class="item-error">{{ record.last_error }}</span>
              </div>
              <el-tag size="small" :type="recordTag(record)">{{ recordLabel(record) }}</el-tag>
            </div>
          </div>
          <EmptyState v-else title="尚无收录记录" text="提交到搜索机器人后，可在这里查看审核与收录结果。" />
        </section>

        <section class="detail-section channel-facts">
          <h2>频道信息</h2>
          <dl>
            <div><dt>分组</dt><dd>{{ channel.group_name || '未分组' }}</dd></div>
            <div><dt>投放状态</dt><dd>{{ channel.delivery_status || '未知' }}</dd></div>
            <div><dt>最近内容</dt><dd>{{ formatDate(channel.last_content_at) }}</dd></div>
            <div><dt>最后检测</dt><dd>{{ formatDate(channel.last_check_at) }}</dd></div>
            <div><dt>频道 ID</dt><dd>{{ channel.chat_id || '-' }}</dd></div>
            <div v-if="channel.last_error"><dt>最近错误</dt><dd class="item-error">{{ channel.last_error }}</dd></div>
          </dl>
          <request-button type="danger" plain @click="emit('delete', channel)">删除频道</request-button>
        </section>
      </template>
    </template>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ArrowRight, Search } from '@element-plus/icons-vue'
import EmptyState from './EmptyState.vue'
import StatusPill from './StatusPill.vue'
import { formatDate } from '../utils/format'

const props = defineProps({
  channels: { type: Array, default: () => [] },
  items: { type: Array, default: () => [] },
  keyword: { type: String, default: '' },
  loading: Boolean,
  selectedId: { type: Number, default: null },
  overview: { type: Object, default: null },
  overviewLoading: Boolean,
  overviewError: { type: String, default: '' },
})
const emit = defineEmits([
  'update:keyword', 'open', 'retry', 'create', 'batch-check', 'edit', 'check',
  'submit', 'submissions', 'delete', 'open-task',
])
const filter = ref('all')
const filters = [
  { key: 'all', label: '全部' },
  { key: 'collected', label: '已收录' },
  { key: 'reviewing', label: '审核中' },
  { key: 'problem', label: '异常' },
]
const channel = computed(() => props.overview?.channel || props.channels.find(item => Number(item.id) === props.selectedId))
const visibleChannels = computed(() => props.items.filter((item) => {
  if (filter.value === 'collected') return item.collection_status === '已收录'
  if (filter.value === 'reviewing') return item.collection_status === '审核中'
  if (filter.value === 'problem') return item.status === 'error' || Boolean(item.last_error)
  return true
}).slice().sort((left, right) => {
  const leftTime = Date.parse(left.last_content_at || left.updated_at || left.last_check_at || '') || 0
  const rightTime = Date.parse(right.last_content_at || right.updated_at || right.last_check_at || '') || 0
  return rightTime - leftTime || Number(right.id) - Number(left.id)
}))
const runningCount = computed(() => (props.overview?.tasks || []).filter(task => task.status === 'running' || task.worker_running).length)
const collectedCount = computed(() => (props.overview?.collections || []).filter(row => row.collection_status === 'collected' && row.block_status !== 'blocked').length)
const restrictedTasks = computed(() => props.overview && (!props.overview.permissions?.listener_tasks || !props.overview.permissions?.clone_tasks))

function avatarText(item) {
  return String(item?.title || item?.username || '频').trim().slice(0, 1).toUpperCase()
}
function shortDate(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const now = new Date()
  if (date.toDateString() === now.toDateString()) return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  return `${date.getMonth() + 1}/${date.getDate()}`
}
function collectionTag(value) {
  if (value === '已收录') return 'success'
  if (value === '审核中') return 'warning'
  return 'info'
}
function taskStatus(task) {
  if (!task.enabled) return '已停用'
  return ({ running: '运行中', paused: '已暂停', stopped: '已停止', idle: '待启动', done: '已完成', error: '异常' })[task.status] || task.status || '未知'
}
function reviewLabel(value) {
  return ({ reviewing: '审核中', approved: '已通过', rejected: '已拒绝', pending: '待审核' })[value] || '审核状态未知'
}
function recordLabel(record) {
  if (record.block_status === 'blocked') return '已拉黑'
  if (record.collection_status === 'collected') return '已收录'
  if (record.review_status === 'reviewing') return '审核中'
  if (record.submit_status === 'failed') return '提交失败'
  return '未收录'
}
function recordTag(record) {
  const label = recordLabel(record)
  if (label === '已收录') return 'success'
  if (label === '审核中') return 'warning'
  if (label === '已拉黑' || label === '提交失败') return 'danger'
  return 'info'
}
</script>

<style scoped>
.channel-explorer { max-width: 820px; min-height: 60vh; margin: 0 auto; background: var(--panel); }
.channel-explorer--detail { max-width: 920px; padding-bottom: 32px; }
.list-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 22px 20px 14px; }
.list-heading h1, .detail-hero h1 { margin: 0; font-size: 23px; line-height: 1.25; }
.list-heading p { margin: 5px 0 0; color: var(--muted); font-size: 13px; }
.channel-search { display: block; padding: 0 16px 12px; }
.channel-filters { display: flex; gap: 8px; padding: 0 16px 12px; overflow-x: auto; }
.channel-filters button { flex: 0 0 auto; min-height: 42px; padding: 0 15px; border: 0; border-radius: 21px; background: var(--bg); color: var(--muted); font: inherit; }
.channel-filters button.active { background: color-mix(in srgb, var(--primary) 12%, var(--panel)); color: var(--primary); font-weight: 700; }
.channel-filters button:focus-visible, .channel-row:focus-visible { outline: 2px solid var(--primary); outline-offset: -2px; }
.channel-list-loading { padding: 4px 18px; }
.channel-list-loading :deep(.el-skeleton) { padding: 12px 0; }
.channel-row { display: flex; align-items: center; gap: 12px; width: 100%; min-height: 88px; padding: 10px 16px; border: 0; border-bottom: 1px solid var(--border); background: var(--panel); color: var(--text); text-align: left; font: inherit; }
.channel-row:hover { background: var(--bg); }
.channel-avatar { display: inline-flex; flex: 0 0 50px; align-items: center; justify-content: center; width: 50px; height: 50px; border-radius: 50%; background: var(--primary); color: white; font-size: 20px; font-weight: 700; }
.channel-row-body { display: block; flex: 1 1 auto; min-width: 0; }
.channel-row-top, .channel-row-bottom { display: flex; align-items: center; justify-content: space-between; gap: 9px; }
.channel-row-top strong { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 15px; }
.channel-row-top time { flex: 0 0 auto; color: var(--muted); font-size: 12px; }
.channel-row-subtitle, .channel-row-bottom > span:first-child { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--muted); font-size: 13px; }
.channel-row-subtitle { margin: 3px 0 5px; }
.channel-row-bottom > span:first-child { min-width: 0; }
.channel-chevron { flex: 0 0 auto; color: var(--soft); }
.list-bottom-action { padding: 16px; }
.detail-loading, .detail-error { padding: 24px 18px; }
.detail-error :deep(.el-button) { margin-top: 14px; }
.detail-hero { display: flex; flex-direction: column; align-items: center; padding: 28px 16px 20px; text-align: center; }
.channel-avatar--large { width: 72px; height: 72px; flex-basis: 72px; margin-bottom: 14px; font-size: 29px; }
.detail-hero p { margin: 5px 0 13px; color: var(--muted); overflow-wrap: anywhere; }
.detail-hero-tags { display: flex; gap: 8px; }
.detail-actions { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; padding: 0 16px 16px; }
.detail-actions :deep(.el-button) { margin-left: 0; min-height: 44px; }
.detail-hint, .detail-refreshing, .permission-note { padding: 0 18px; color: var(--muted); font-size: 13px; }
.detail-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); border-top: 8px solid var(--bg); border-bottom: 8px solid var(--bg); }
.detail-summary > div { padding: 14px 8px; text-align: center; }
.detail-summary > div + div { border-left: 1px solid var(--border); }
.detail-summary span { display: block; color: var(--muted); font-size: 12px; }
.detail-summary strong { display: block; margin-top: 5px; font-size: 21px; }
.detail-section { padding: 17px 18px 20px; border-bottom: 8px solid var(--bg); }
.detail-section h2 { margin: 0 0 11px; font-size: 16px; }
.section-note { margin: -4px 0 12px; color: var(--muted); font-size: 12px; }
.section-heading { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.detail-list-item { border-top: 1px solid var(--border); padding: 13px 0; }
.item-main, .bot-item, .collection-item { display: flex; align-items: center; gap: 10px; }
.item-icon { display: inline-flex; flex: 0 0 38px; align-items: center; justify-content: center; width: 38px; height: 38px; border-radius: 50%; background: color-mix(in srgb, var(--primary) 12%, var(--panel)); color: var(--primary); font-size: 14px; font-weight: 700; }
.item-icon--bot { background: color-mix(in srgb, var(--success) 12%, var(--panel)); color: var(--success); }
.item-icon--search { background: color-mix(in srgb, var(--warning) 12%, var(--panel)); color: var(--warning); }
.item-text { flex: 1 1 auto; min-width: 0; }
.item-text strong, .item-text span { display: block; overflow-wrap: anywhere; }
.item-text strong { font-size: 14px; }
.item-text span { margin-top: 3px; color: var(--muted); font-size: 12px; }
.item-main :deep(.el-tag), .bot-item :deep(.el-tag), .collection-item :deep(.el-tag) { flex: 0 0 auto; }
.item-detail { display: grid; gap: 3px; margin: 9px 0 8px 48px; color: var(--muted); font-size: 12px; }
.item-error, .item-text .item-error { color: var(--danger); overflow-wrap: anywhere; }
.task-item > :deep(.el-button) { margin-left: 48px; }
.channel-facts dl { margin: 0 0 16px; }
.channel-facts dl div { display: flex; justify-content: space-between; gap: 16px; padding: 10px 0; border-top: 1px solid var(--border); font-size: 13px; }
.channel-facts dt { flex: 0 0 auto; color: var(--muted); }
.channel-facts dd { margin: 0; text-align: right; overflow-wrap: anywhere; }
@media (min-width: 900px) { .channel-explorer { margin-top: 24px; border: 1px solid var(--border); border-radius: 12px; overflow: hidden; } }
@media (max-width: 420px) { .list-heading { padding: 18px 14px 12px; } .channel-row { padding: 9px 12px; gap: 10px; } .detail-section { padding-left: 14px; padding-right: 14px; } .detail-actions { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); } .detail-actions :deep(.el-button) { width: 100%; padding-left: 5px; padding-right: 5px; } }
</style>
