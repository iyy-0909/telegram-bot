<template>
  <el-dialog :model-value="visible" title="同步账号管理的频道" width="min(1000px, calc(100vw - 24px))" top="5vh" class="managed-channel-sync-dialog"
    :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy"
    @update:model-value="$emit('update:visible', $event)">
    <el-alert title="读取当前用户的 Telegram 账号所创建或管理的频道；普通成员频道和群组不会导入。同步仅更新管理关系，勾选后才加入“我的频道”。"
      type="info" :closable="false" show-icon />
    <div class="sync-controls">
      <el-select v-model="accountId" placeholder="选择 Telegram 账号" aria-label="同步 Telegram 账号" :disabled="busy" filterable>
        <el-option label="全部已启用账号" :value="0" />
        <el-option v-for="account in accounts" :key="account.id" :label="`${account.name}${account.enabled ? '' : '（已停用）'}`" :value="account.id" :disabled="!account.enabled" />
      </el-select>
      <el-button type="primary" :loading="syncing" :disabled="loading || importing || !accounts.some(a => a.enabled)" @click="sync">同步管理关系</el-button>
      <el-button :loading="loading" :disabled="syncing || importing" @click="load">刷新结果</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="sync-feedback" />
    <el-alert v-if="progress" :title="progress" :type="syncing ? 'info' : syncFailed ? 'warning' : 'success'" :closable="false" class="sync-feedback" />
    <div v-loading="loading" class="sync-body">
      <el-empty v-if="!loading && !accounts.length" description="暂无 Telegram 账号，请先在账号管理中登录账号。" />
      <template v-else>
        <div class="account-states" aria-label="账号同步状态">
          <div v-for="account in accounts" :key="account.id" class="account-state">
            <strong>{{ account.name }}</strong>
            <el-tag size="small" :type="account.status === 'success' ? 'success' : 'warning'">{{ statusLabel(account.status) }}</el-tag>
            <span>{{ account.last_error || (account.last_success_at ? `上次成功：${new Date(account.last_success_at).toLocaleString('zh-CN', { hour12: false })}` : '尚未同步') }}</span>
          </div>
        </div>
        <el-input v-model="keyword" placeholder="筛选频道名称、用户名或 ID" aria-label="筛选同步频道" clearable class="sync-search" :disabled="busy" @input="clearSelection" />
        <el-table ref="tableRef" :data="filteredItems" row-key="chat_id" height="320" border stripe
          empty-text="未发现符合条件的频道，请先同步账号或调整筛选。" @selection-change="selection = $event">
          <el-table-column type="selection" width="48" :selectable="selectable" />
          <el-table-column prop="title" label="频道名称" min-width="160" show-overflow-tooltip />
          <el-table-column prop="username" label="用户名" min-width="145" show-overflow-tooltip />
          <el-table-column prop="chat_id" label="频道 ID" min-width="150" show-overflow-tooltip />
          <el-table-column label="管理账号 / 身份" min-width="220">
            <template #default="{ row }"><ChannelAccountRoles :members="row.managed_accounts" /></template>
          </el-table-column>
          <el-table-column label="导入状态" width="120">
            <template #default="{ row }">
              <el-tag :type="row.existing_id ? 'success' : canImport(row) ? 'info' : 'warning'" size="small">{{ row.existing_id ? '已在我的频道' : canImport(row) ? '待选择导入' : '需重新同步' }}</el-tag>
            </template>
          </el-table-column>
        </el-table>
        <p class="sync-note">结果超过 24 小时或同步失败时标记为未确认。新导入频道的 Bot 权限仍需单独绑定、检测。</p>
      </template>
    </div>
    <template #footer>
      <div class="sync-footer">
        <span>已选择 {{ selection.length }} 个频道（每次最多 200 个）</span>
        <el-button :disabled="busy" @click="$emit('update:visible', false)">关闭</el-button>
        <el-button type="primary" :loading="importing" :disabled="loading || syncing || !selection.length || selection.length > 200" @click="importSelected">导入所选频道</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getManagedChannelDiscovery, syncManagedAccountChannels, importManagedChannels } from '../api/myChannels'
import ChannelAccountRoles from './ChannelAccountRoles.vue'
import { searchRows } from '../utils/search'
const props = defineProps({ visible: Boolean })
const emit = defineEmits(['update:visible', 'changed'])
const accounts = ref([]), items = ref([]), selection = ref([]), accountId = ref(0), keyword = ref('')
const loading = ref(false), syncing = ref(false), importing = ref(false), error = ref(''), progress = ref(''), tableRef = ref(null), syncFailed = ref(false)
const busy = computed(() => syncing.value || importing.value)
const filteredItems = computed(() => searchRows(items.value, keyword.value, 'channels', row => [
  (row.managed_accounts || []).map(member => [member.account_name, member.username, member.role]),
  row.existing_id ? '已在我的频道' : canImport(row) ? '待选择导入' : '需重新同步',
]))
const readError = (err, fallback) => err?.response?.data?.detail || err?.message || fallback
const statusLabel = status => ({ success: '已同步', error: '未确认 · 同步失败', disabled: '未确认 · 已停用', offline: '未确认 · 账号离线', stale: '未确认 · 待更新', unknown: '未同步' })[status] || '未确认'
const canImport = row => row.managed_accounts.some(member => member.status === 'success')
const selectable = row => !busy.value && !row.existing_id && canImport(row)
function clearSelection() { tableRef.value?.clearSelection(); selection.value = [] }
watch(() => props.visible, visible => { if (visible) { progress.value = ''; error.value = ''; load() } })
async function load() {
  loading.value = true
  error.value = ''
  clearSelection()
  try {
    const { data } = await getManagedChannelDiscovery()
    accounts.value = data.accounts || []
    items.value = data.items || []
  } catch (err) { error.value = readError(err, '加载失败，请重试'); items.value = []; accounts.value = [] }
  finally { loading.value = false }
}
async function sync() {
  syncing.value = true
  syncFailed.value = false
  error.value = ''
  clearSelection()
  const targets = accounts.value.filter(a => a.enabled && (!accountId.value || a.id === accountId.value))
  let failed = 0
  const failures = []
  try {
    for (const [index, account] of targets.entries()) {
      progress.value = `正在同步 ${account.name}（${index + 1}/${targets.length}），请稍候…`
      try {
        const { data } = await syncManagedAccountChannels(account.id)
        if (!data.ok) { failed += 1; failures.push(`${account.name}：${data.message || '同步失败'}`) }
      } catch (err) { failed += 1; failures.push(`${account.name}：${readError(err, '同步失败')}`) }
    }
    await load()
    syncFailed.value = failed > 0
    progress.value = `同步结束：${targets.length - failed} 个成功，${failed} 个失败。`
    if (failed) error.value ||= failures.join('；')
    emit('changed')
  } finally { syncing.value = false }
}
async function importSelected() {
  importing.value = true
  error.value = ''
  try {
    const { data } = await importManagedChannels(selection.value.map(row => row.chat_id))
    ElMessage.success(`已导入 ${data.added} 个频道，${data.matched} 个已存在频道已关联`)
    await load()
    emit('changed')
  } catch (err) { error.value = readError(err, '导入失败，请重试') }
  finally { importing.value = false }
}
</script>

<style scoped>
:global(.managed-channel-sync-dialog .el-dialog__body) { max-height: calc(85vh - 140px); overflow: auto; }
.sync-controls, .sync-footer { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.sync-controls { margin: 16px 0; }
.sync-controls .el-select { width: 260px; }
.sync-footer { justify-content: flex-end; }
.sync-footer > span { margin-right: auto; color: var(--el-text-color-secondary); }
.sync-feedback, .sync-search { margin-bottom: 12px; }
.sync-body { min-height: 120px; }
.account-states { max-height: 145px; overflow: auto; margin-bottom: 12px; }
.account-state { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; padding: 4px 0; overflow-wrap: anywhere; }
.account-state > span:not(.el-tag), .sync-note { color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.6; }
@media (max-width: 600px) { .sync-controls .el-select { width: 100%; } .sync-footer > span { width: 100%; text-align: left; } }
</style>
