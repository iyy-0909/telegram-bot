<template>
  <section class="user-access-page">
    <header class="page-header">
      <div>
        <h2>后台管理</h2>
        <p>管理登录账号版本、使用期限，以及免费版每日广告。</p>
      </div>
      <el-button :icon="Refresh" :loading="loading" @click="loadData">刷新</el-button>
    </header>

    <el-alert
      type="info"
      show-icon
      :closable="false"
      title="系统仅提供免费版和付费版两套固定权限"
      description="免费版不限任务、账号和 Bot 数量，内容按原文克隆并每日发送一次广告；付费版开放主要运营功能且不发送广告。"
    />

    <div class="table-panel">
      <div class="filters">
        <el-input v-model="filters.keyword" :prefix-icon="Search" clearable placeholder="搜索用户名" aria-label="搜索用户名" />
        <el-select v-model="filters.plan" aria-label="版本筛选">
          <el-option label="全部版本" value="all" />
          <el-option label="免费版" value="free" />
          <el-option label="付费版" value="paid" />
        </el-select>
        <el-select v-model="filters.state" aria-label="状态筛选">
          <el-option label="全部状态" value="all" />
          <el-option label="正常" value="active" />
          <el-option label="即将到期" value="expiring" />
          <el-option label="已到期" value="expired" />
          <el-option label="已停用" value="disabled" />
        </el-select>
      </div>

      <el-alert v-if="loadError" type="error" show-icon :closable="false" class="load-error">
        <template #title>{{ loadError }}</template>
        <el-button link type="primary" @click="loadData">重新加载</el-button>
      </el-alert>

      <el-table v-else v-loading="loading" :data="pagedUsers" border height="500" row-key="id" empty-text="当前筛选条件下没有账号。">
        <el-table-column label="用户名" min-width="165" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="username-cell">
              <strong>{{ row.username || `用户 #${row.id}` }}</strong>
              <el-tag size="small" :type="row.role === 'admin' ? 'warning' : 'info'">{{ row.role === "admin" ? "管理员" : "用户" }}</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="版本" width="104" align="center">
          <template #default="{ row }"><el-tag size="small" :type="planTagType(row)">{{ planLabel(row) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="状态" width="104" align="center">
          <template #default="{ row }"><el-tag size="small" :type="stateTagType(row)">{{ stateLabel(row) }}</el-tag></template>
        </el-table-column>
        <el-table-column label="免费版广告" min-width="230" show-overflow-tooltip>
          <template #default="{ row }">
            <div v-if="row.role !== 'admin' && normalizedPlan(row) === 'free'" class="ad-cell">
              <span>{{ row.advertisement_send_time || "12:00" }} 每日发送</span>
              <small>{{ row.advertisement_text || DEFAULT_AD_TEXT }}</small>
            </div>
            <span v-else class="muted-text">不发送广告</span>
          </template>
        </el-table-column>
        <el-table-column label="使用期限" min-width="190">
          <template #default="{ row }">
            <div class="expiry-cell"><span>{{ expiryLabel(row) }}</span><small v-if="remainingLabel(row)">{{ remainingLabel(row) }}</small></div>
          </template>
        </el-table-column>
        <el-table-column label="最后登录" width="168"><template #default="{ row }">{{ formatTime(row.last_login_at) }}</template></el-table-column>
        <el-table-column label="操作" width="116" fixed="right">
          <template #default="{ row }"><el-button link type="primary" @click="openDrawer(row)">{{ row.role === "admin" ? "查看" : "配置" }}</el-button></template>
        </el-table-column>
      </el-table>

      <el-pagination v-if="filteredUsers.length > pageSize" v-model:current-page="page" background layout="prev, pager, next, total" :page-size="pageSize" :total="filteredUsers.length" />
    </div>

    <el-drawer v-model="drawerVisible" class="user-access-drawer" :title="drawerTitle" size="600px" destroy-on-close>
      <template v-if="selectedUser">
        <el-alert v-if="isSelectedAdmin" type="warning" show-icon :closable="false" title="管理员始终拥有全部功能，不受版本和使用期限限制。" class="drawer-alert" />

        <el-form label-position="top" class="access-form">
          <section class="form-section">
            <div class="section-heading"><h3>账号状态</h3><p>停用后，现有登录会立即失效。</p></div>
            <el-radio-group v-model="form.status" :disabled="isSelectedAdmin || saving">
              <el-radio-button value="active">正常</el-radio-button><el-radio-button value="disabled">停用</el-radio-button>
            </el-radio-group>
          </section>

          <section class="form-section">
            <div class="section-heading"><h3>账号版本</h3><p>版本权限由系统固定，不能单独勾选功能。</p></div>
            <el-radio-group v-model="form.plan_tier" class="plan-options" :disabled="isSelectedAdmin || saving">
              <el-radio v-for="plan in plans" :key="plan.key" :value="plan.key" border>
                <span class="plan-option"><strong>{{ plan.name }}</strong><small>{{ plan.description }}</small></span>
              </el-radio>
            </el-radio-group>
            <div v-if="selectedPlan" class="plan-summary">
              <el-tag :type="form.plan_tier === 'paid' ? 'success' : 'info'">{{ selectedPlan.content_processing_enabled ? "可配置内容处理" : "按原文直接克隆" }}</el-tag>
              <el-tag :type="selectedPlan.advertisement_required ? 'warning' : 'success'">{{ selectedPlan.advertisement_required ? "每日强制广告" : "无广告" }}</el-tag>
            </div>
          </section>

          <section v-if="form.plan_tier === 'free' && !isSelectedAdmin" class="form-section">
            <div class="section-heading"><h3>每日广告</h3><p>发送到该用户已启用任务的每个目标频道，同一目标每天一次。</p></div>
            <el-form-item label="广告内容">
              <el-input v-model="form.advertisement_text" type="textarea" :rows="5" maxlength="4000" show-word-limit placeholder="请输入免费版广告内容" :disabled="saving" />
            </el-form-item>
            <el-form-item label="每日发送时间">
              <el-time-picker v-model="form.advertisement_send_time" value-format="HH:mm" format="HH:mm" placeholder="选择发送时间" :disabled="saving" class="time-picker" />
            </el-form-item>
            <el-alert type="warning" show-icon :closable="false" title="免费版广告不能关闭；发送失败时当天最多自动重试 5 次。" />
          </section>

          <section class="form-section">
            <div class="section-heading"><h3>使用期限</h3><p>可永久使用，也可设置明确到期时间。</p></div>
            <el-radio-group v-model="expiryMode" :disabled="isSelectedAdmin || saving" @change="handleExpiryModeChange">
              <el-radio value="permanent">永久有效</el-radio><el-radio value="custom">限时使用</el-radio>
            </el-radio-group>
            <template v-if="expiryMode === 'custom'">
              <div class="quick-days">
                <el-button v-for="days in quickDayOptions" :key="days" size="small" :disabled="saving" @click="setQuickDays(days)">{{ days === 365 ? "1 年" : `${days} 天` }}</el-button>
              </div>
              <el-date-picker v-model="form.access_expires_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" format="YYYY-MM-DD HH:mm" placeholder="选择到期日期和时间" :disabled="isSelectedAdmin || saving" :disabled-date="disablePastDate" class="expiry-picker" />
              <div v-if="dateError" class="field-error">{{ dateError }}</div>
            </template>
          </section>
        </el-form>
      </template>

      <template #footer>
        <div class="drawer-footer">
          <el-button :disabled="saving" @click="drawerVisible = false">关闭</el-button>
          <el-button v-if="!isSelectedAdmin" type="primary" :loading="saving" @click="saveAccess">保存配置</el-button>
        </div>
      </template>
    </el-drawer>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue"
import { Refresh, Search } from "@element-plus/icons-vue"
import { ElMessage } from "element-plus"
import { getAdminUsers, getFeatureCatalog, updateAdminUserAccess } from "../api/userAccess"

const DEFAULT_AD_TEXT = "本消息由 Telegram 运营系统免费版自动发送。"
const FALLBACK_PLANS = [
  { key: "free", name: "免费版", description: "不限任务和资源数量，原文克隆，每日发送一次广告。", advertisement_required: true, content_processing_enabled: false },
  { key: "paid", name: "付费版", description: "开放主要运营和内容处理功能，不发送广告。", advertisement_required: false, content_processing_enabled: true },
]
const users = ref([])
const plans = ref(FALLBACK_PLANS)
const loading = ref(false)
const loadError = ref("")
const drawerVisible = ref(false)
const selectedUser = ref(null)
const saving = ref(false)
const expiryMode = ref("permanent")
const dateError = ref("")
const page = ref(1)
const pageSize = 10
const quickDayOptions = [1, 7, 30, 90, 365]
const filters = reactive({ keyword: "", plan: "all", state: "all" })
const form = reactive({ status: "active", plan_tier: "free", advertisement_text: DEFAULT_AD_TEXT, advertisement_send_time: "12:00", access_expires_at: null })

const isSelectedAdmin = computed(() => selectedUser.value?.role === "admin")
const drawerTitle = computed(() => selectedUser.value ? `${isSelectedAdmin.value ? "查看" : "配置"}账号 · ${selectedUser.value.username}` : "配置账号")
const selectedPlan = computed(() => plans.value.find((item) => item.key === form.plan_tier))
const filteredUsers = computed(() => {
  const keyword = filters.keyword.trim().toLowerCase()
  return users.value.filter((user) => {
    if (keyword && !String(user.username || "").toLowerCase().includes(keyword)) return false
    if (filters.plan !== "all" && normalizedPlan(user) !== filters.plan) return false
    return filters.state === "all" || normalizedState(user) === filters.state
  })
})
const pagedUsers = computed(() => filteredUsers.value.slice((page.value - 1) * pageSize, page.value * pageSize))

watch(filters, () => { page.value = 1 })
watch(filteredUsers, (items) => { page.value = Math.min(page.value, Math.max(Math.ceil(items.length / pageSize), 1)) })

function readError(error, fallback) { return error?.response?.data?.detail || error?.response?.data?.message || error?.message || fallback }
function normalizeList(data, keys = []) {
  if (Array.isArray(data)) return data
  for (const key of keys) if (Array.isArray(data?.[key])) return data[key]
  return []
}
function normalizedPlan(user) { return user?.role === "admin" || user?.plan_tier === "paid" ? "paid" : "free" }
function planLabel(user) { return user?.role === "admin" ? "管理员" : normalizedPlan(user) === "paid" ? "付费版" : "免费版" }
function planTagType(user) { return user?.role === "admin" ? "warning" : normalizedPlan(user) === "paid" ? "success" : "info" }
function normalizedState(user) {
  if (user?.status === "disabled" || user?.access_state === "disabled") return "disabled"
  if (user?.access_state === "expired" || isExpired(user?.access_expires_at)) return "expired"
  if (isExpiring(user?.access_expires_at)) return "expiring"
  return "active"
}
function stateLabel(user) { return ({ active: "正常", expiring: "即将到期", expired: "已到期", disabled: "已停用" })[normalizedState(user)] }
function stateTagType(user) { return ({ active: "success", expiring: "warning", expired: "danger", disabled: "info" })[normalizedState(user)] }
function isExpired(value) { const time = value ? new Date(value).getTime() : NaN; return Number.isFinite(time) && time <= Date.now() }
function isExpiring(value) { const time = value ? new Date(value).getTime() : NaN; return Number.isFinite(time) && time > Date.now() && time - Date.now() <= 259200000 }
function expiryLabel(user) { return user?.role === "admin" ? "管理员长期有效" : user?.access_expires_at ? formatTime(user.access_expires_at) : "永久有效" }
function remainingLabel(user) {
  if (user?.role === "admin" || !user?.access_expires_at) return ""
  const milliseconds = new Date(user.access_expires_at).getTime() - Date.now()
  if (!Number.isFinite(milliseconds)) return ""
  if (milliseconds <= 0) return "已超过使用期限"
  const days = Math.ceil(milliseconds / 86400000)
  return days <= 1 ? "不足 1 天" : `剩余 ${days} 天`
}
function formatTime(value) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value).replace("T", " ").slice(0, 19)
  const pad = (number) => String(number).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}
function toPickerValue(value) {
  if (!value) return null
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value).slice(0, 19)
  const pad = (number) => String(number).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

async function loadData() {
  loading.value = true
  loadError.value = ""
  try {
    const [usersResponse, catalogResponse] = await Promise.all([getAdminUsers(), getFeatureCatalog()])
    users.value = normalizeList(usersResponse.data, ["items", "users"])
    const receivedPlans = normalizeList(catalogResponse.data, ["plans"])
    plans.value = receivedPlans.length ? receivedPlans : FALLBACK_PLANS
  } catch (error) {
    loadError.value = readError(error, "加载后台管理数据失败")
  } finally {
    loading.value = false
  }
}
function openDrawer(user) {
  selectedUser.value = user
  form.status = user.status === "disabled" ? "disabled" : "active"
  form.plan_tier = normalizedPlan(user)
  form.advertisement_text = user.advertisement_text || DEFAULT_AD_TEXT
  form.advertisement_send_time = user.advertisement_send_time || "12:00"
  form.access_expires_at = toPickerValue(user.access_expires_at)
  expiryMode.value = user.access_expires_at ? "custom" : "permanent"
  dateError.value = ""
  drawerVisible.value = true
}
function handleExpiryModeChange(mode) { dateError.value = ""; if (mode === "permanent") form.access_expires_at = null; else if (!form.access_expires_at) setQuickDays(30) }
function setQuickDays(days) { form.access_expires_at = toPickerValue(new Date(Date.now() + days * 86400000)); expiryMode.value = "custom"; dateError.value = "" }
function disablePastDate(date) { const today = new Date(); today.setHours(0, 0, 0, 0); return date.getTime() < today.getTime() }
function validateForm() {
  dateError.value = ""
  if (form.plan_tier === "free" && !String(form.advertisement_text || "").trim()) { ElMessage.warning("请输入免费版广告内容"); return false }
  if (form.plan_tier === "free" && !/^([01]\d|2[0-3]):[0-5]\d$/.test(form.advertisement_send_time || "")) { ElMessage.warning("请选择每日广告发送时间"); return false }
  if (expiryMode.value === "permanent") return true
  const expiresAt = form.access_expires_at ? new Date(form.access_expires_at) : null
  if (!expiresAt || Number.isNaN(expiresAt.getTime()) || expiresAt.getTime() <= Date.now()) { dateError.value = "到期时间必须晚于当前时间"; return false }
  return true
}
async function saveAccess() {
  if (!selectedUser.value || isSelectedAdmin.value || !validateForm()) return
  saving.value = true
  try {
    const payload = { status: form.status, plan_tier: form.plan_tier, access_expires_at: expiryMode.value === "permanent" ? null : new Date(form.access_expires_at).toISOString() }
    if (form.plan_tier === "free") {
      payload.advertisement_text = form.advertisement_text.trim()
      payload.advertisement_send_time = form.advertisement_send_time
    }
    const response = await updateAdminUserAccess(selectedUser.value.id, payload)
    const updatedUser = response.data?.user
    if (updatedUser) {
      const index = users.value.findIndex((item) => item.id === updatedUser.id)
      if (index >= 0) users.value.splice(index, 1, updatedUser)
    }
    ElMessage.success("账号配置已保存")
    drawerVisible.value = false
  } catch (error) {
    ElMessage.error(readError(error, "保存账号配置失败"))
  } finally {
    saving.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.user-access-page { min-width: 0; }
.page-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.page-header h2 { margin: 0; font-size: 20px; }
.page-header p { margin: 4px 0 0; color: var(--el-text-color-secondary); font-size: 13px; }
.table-panel { margin-top: 14px; padding: 16px; border: 1px solid var(--el-border-color); border-radius: 8px; background: var(--el-bg-color); }
.filters { display: grid; grid-template-columns: minmax(240px, 1fr) 160px 160px; gap: 10px; max-width: 780px; margin-bottom: 14px; }
.load-error { margin-bottom: 14px; }
.username-cell { display: flex; align-items: center; gap: 8px; min-width: 0; }
.username-cell strong { overflow: hidden; text-overflow: ellipsis; }
.ad-cell, .expiry-cell { display: flex; min-width: 0; flex-direction: column; line-height: 1.45; }
.ad-cell small, .expiry-cell small { overflow: hidden; color: var(--el-text-color-secondary); text-overflow: ellipsis; white-space: nowrap; }
.muted-text { color: var(--el-text-color-secondary); }
.el-pagination { justify-content: flex-end; margin-top: 14px; }
.drawer-alert { margin-bottom: 16px; }
.access-form { display: grid; min-width: 0; gap: 16px; }
.form-section { min-width: 0; padding: 16px; border: 1px solid var(--el-border-color); border-radius: 8px; }
.section-heading { margin-bottom: 14px; }
.section-heading h3 { margin: 0; font-size: 16px; }
.section-heading p { margin: 4px 0 0; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; }
.plan-options { display: grid; grid-template-columns: minmax(0, 1fr); gap: 10px; width: 100%; min-width: 0; }
.plan-options :deep(.el-radio) { width: 100%; max-width: 100%; height: auto; min-width: 0; min-height: 70px; margin: 0; padding: 12px; }
.plan-options :deep(.el-radio__label) { min-width: 0; white-space: normal; }
.plan-option { display: flex; min-width: 0; flex-direction: column; gap: 4px; overflow-wrap: anywhere; }
.plan-option small { color: var(--el-text-color-secondary); line-height: 1.45; }
.plan-summary { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.quick-days { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0; }
.quick-days .el-button { margin-left: 0; }
.expiry-picker, .time-picker { width: 100% !important; }
.field-error { margin-top: 6px; color: var(--el-color-danger); font-size: 12px; }
.drawer-footer { display: flex; justify-content: flex-end; gap: 8px; }
@media (max-width: 900px) {
  .page-header { align-items: stretch; flex-direction: column; }
  .filters { grid-template-columns: 1fr; max-width: none; }
  .table-panel { padding: 12px; overflow: hidden; }
  :global(.user-access-drawer) { width: 100% !important; }
}
@media (max-width: 520px) {
  .form-section { padding: 12px; }
}
</style>
