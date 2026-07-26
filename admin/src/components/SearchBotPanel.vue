<template>
  <div class="search-bot-panel">
    <div class="panel-summary">
      <div><span>搜索机器人</span><strong>{{ bots.length }}</strong></div>
      <div><span>正常</span><strong class="success-text">{{ enabledCount }}</strong></div>
      <div><span>当前收录</span><strong>{{ currentCount }}</strong></div>
      <div><span>拉黑记录</span><strong class="danger-text">{{ blockedCount }}</strong></div>
    </div>

    <el-tabs v-model="panelView" class="inner-tabs">
      <el-tab-pane label="机器人管理" name="bots">
        <div class="toolbar">
          <div class="filters">
            <el-input v-model="botFilters.keyword" clearable placeholder="搜索机器人名称 / @username / https://t.me/..." @keyup.enter="loadBots">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-select v-model="botFilters.status" clearable placeholder="机器人状态" @change="loadBots">
              <el-option label="正常" value="enabled" />
              <el-option label="已停用" value="disabled" />
              <el-option label="异常" value="error" />
            </el-select>
            <el-button :loading="botLoading" @click="refreshAll"><el-icon><Refresh /></el-icon>刷新</el-button>
          </div>
          <el-button type="primary" @click="openBotCreate"><el-icon><Plus /></el-icon>新增机器人</el-button>
        </div>

        <el-table
          :data="visibleBots"
          v-loading="botLoading"
          row-key="id"
          border
          stripe
          height="520"
          style="width: 100%"
        >
          <template #empty>
            <el-empty :image-size="72" description="暂无搜索机器人">
              <el-button type="primary" @click="openBotCreate"><el-icon><Plus /></el-icon>新增机器人</el-button>
            </el-empty>
          </template>
          <el-table-column prop="name" label="机器人名称" min-width="160" show-overflow-tooltip />
          <el-table-column label="机器人 ID" min-width="165">
            <template #default="{ row }"><CopyText :value="row.username" :text="row.username" tone="primary" /></template>
          </el-table-column>
          <el-table-column label="状态" width="88" align="center">
            <template #default="{ row }"><StatusTag :status="row.status" /></template>
          </el-table-column>
          <el-table-column prop="remark" label="备注" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.remark">{{ row.remark }}</span>
              <span v-else class="muted-text">-</span>
            </template>
          </el-table-column>
          <el-table-column label="频道情况" min-width="145">
            <template #default="{ row }">
              <div class="channel-metrics">
                <span><small>当前收录</small><strong>{{ row.current_channel_count || 0 }}</strong></span>
                <span :class="{ 'metric-danger': Number(row.blocked_channel_count || 0) > 0 }"><small>拉黑</small><strong>{{ row.blocked_channel_count || 0 }}</strong></span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作账号" min-width="115" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.account_name">{{ row.account_name }}</span>
              <span v-else-if="row.account_id">账号 #{{ row.account_id }}</span>
              <span v-else class="muted-text">未配置</span>
            </template>
          </el-table-column>
          <el-table-column label="最后检测" min-width="155" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.last_check_at" class="no-wrap">{{ formatDateTime(row.last_check_at) }}</span>
              <span v-else class="muted-text">未检测</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="170" fixed="right" align="center">
            <template #default="{ row }">
              <div class="row-actions">
                <el-button size="small" @click="openBotEdit(row)">编辑</el-button>
                <el-button size="small" type="warning" plain :loading="checkingId === row.id" @click="detectBot(row)">检测</el-button>
                <el-button size="small" type="danger" @click="removeBot(row)">删除</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="频道提交记录" name="submissions">
        <div class="toolbar">
          <div class="filters">
            <el-input v-model="submissionFilters.keyword" clearable placeholder="搜索频道 / 机器人 / @username / https://t.me/..." @keyup.enter="loadSubmissions">
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <el-select v-model="submissionFilters.group_name" clearable filterable placeholder="分组" @change="loadSubmissions">
              <el-option v-for="group in groupOptions" :key="group" :label="group" :value="group" />
            </el-select>
            <el-select v-model="submissionFilters.block_status" clearable placeholder="拉黑状态" @change="loadSubmissions">
              <el-option label="正常" value="normal" />
              <el-option label="已拉黑" value="blocked" />
              <el-option label="未知" value="unknown" />
            </el-select>
            <el-button :loading="submissionLoading" @click="loadSubmissions"><el-icon><Refresh /></el-icon>刷新</el-button>
          </div>
        </div>

        <el-table
          :data="submissions"
          v-loading="submissionLoading"
          row-key="id"
          border
          stripe
          height="520"
          style="width: 100%"
        >
          <template #empty>
            <el-empty :image-size="72" description="暂无频道提交记录" />
          </template>
          <el-table-column prop="group_name" label="分组" min-width="100" show-overflow-tooltip />
          <el-table-column prop="channel_title" label="频道" min-width="155" show-overflow-tooltip />
          <el-table-column label="频道链接" min-width="170">
            <template #default="{ row }"><CopyText v-if="row.channel_username" :value="row.channel_username" :text="row.channel_username" tone="primary" /><span v-else>{{ row.channel_chat_id || "-" }}</span></template>
          </el-table-column>
          <el-table-column prop="search_bot_name" label="搜索机器人" min-width="145" show-overflow-tooltip />
          <el-table-column label="提交账号" min-width="145" show-overflow-tooltip>
            <template #default="{ row }">{{ submissionAccountLabel(row) }}</template>
          </el-table-column>
          <el-table-column label="执行状态" width="105"><template #default="{ row }"><el-tag :type="statusType(row.submit_status)">{{ statusLabel(row.submit_status) }}</el-tag></template></el-table-column>
          <el-table-column label="审核" width="105"><template #default="{ row }"><el-tag :type="statusType(row.review_status)">{{ statusLabel(row.review_status) }}</el-tag></template></el-table-column>
          <el-table-column label="收录" width="105"><template #default="{ row }"><el-tag :type="statusType(row.collection_status)">{{ statusLabel(row.collection_status) }}</el-tag></template></el-table-column>
          <el-table-column label="拉黑" width="105"><template #default="{ row }"><el-tag :type="statusType(row.block_status)">{{ statusLabel(row.block_status) }}</el-tag></template></el-table-column>
          <el-table-column label="当前有效" width="105"><template #default="{ row }"><el-tag :type="row.is_current ? 'success' : 'info'">{{ row.is_current ? "是" : "否" }}</el-tag></template></el-table-column>
          <el-table-column label="提交时间" min-width="160"><template #default="{ row }">{{ formatDateTime(row.submitted_at || row.created_at) }}</template></el-table-column>
          <el-table-column label="操作" width="260" fixed="right" align="center">
            <template #default="{ row }">
              <div class="row-actions submission-actions">
                <el-button size="small" type="primary" @click="openSubmissionEdit(row)">更新状态</el-button>
                <el-button size="small" @click="openPermissionEdit(row)">调整权限</el-button>
                <el-button size="small" type="warning" plain :disabled="row.submit_status === 'queued' || row.submit_status === 'submitting'" @click="openResubmit(row)">改投</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog
      v-model="botDialogVisible"
      class="search-bot-dialog"
      :title="editingBot?.id ? '编辑搜索机器人' : '新增搜索机器人'"
      width="min(680px, calc(100vw - 24px))"
      append-to-body
      destroy-on-close
    >
      <el-form ref="botFormRef" :model="botForm" :rules="botRules" label-position="top">
        <div class="form-grid">
          <el-form-item label="机器人名称" prop="name"><el-input v-model="botForm.name" placeholder="例如：上海搜群机器人A" /></el-form-item>
          <el-form-item label="机器人 ID" prop="username"><el-input v-model="botForm.username" placeholder="例如：@jisou 或 https://t.me/jisou" /></el-form-item>
          <el-form-item label="默认操作账号（选填）" prop="account_id">
            <el-select
              v-model="botForm.account_id"
              clearable
              filterable
              :loading="props.accountsLoading"
              placeholder="不使用系统添加时可留空"
            >
              <el-option v-for="account in enabledAccounts" :key="account.id" :label="accountLabel(account)" :value="account.id" />
            </el-select>
            <div class="field-help">系统添加时，该账号必须拥有目标频道的添加成员和添加管理员权限。</div>
          </el-form-item>
          <el-form-item label="状态" prop="status"><el-select v-model="botForm.status"><el-option label="正常" value="enabled" /><el-option label="已停用" value="disabled" /><el-option label="异常" value="error" /></el-select></el-form-item>
        </div>
        <el-form-item label="备注"><el-input v-model="botForm.remark" type="textarea" :rows="2" placeholder="记录机器人提交规则或使用限制" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="botDialogVisible = false">取消</el-button><el-button type="primary" :loading="savingBot" @click="saveBot">保存</el-button></template>
    </el-dialog>

    <el-dialog
      v-model="submitDialogVisible"
      class="submit-channel-dialog"
      title="提交频道到搜索机器人"
      width="min(760px, calc(100vw - 24px))"
      append-to-body
      destroy-on-close
    >
      <el-alert type="info" :closable="false" show-icon :title="submitForm.submission_mode === 'manual' ? '仅登记已经在 Telegram 手动完成的提交，不会执行 Telegram 操作。' : '将搜索机器人添加为 Telegram 频道管理员，并授予下方选择的频道权限。'" />
      <el-form ref="submitFormRef" :model="submitForm" :rules="submitRules" label-position="top" class="dialog-form">
        <el-form-item label="提交方式">
          <el-radio-group v-model="submitForm.submission_mode" class="mode-switch" @change="handleSubmissionModeChange">
            <el-radio-button value="queue">自动添加机器人</el-radio-button>
            <el-radio-button value="manual">手动登记</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="我的频道" prop="my_channel_id">
          <el-select v-model="submitForm.my_channel_id" filterable placeholder="选择需要提交的频道">
            <el-option v-for="channel in enabledChannels" :key="channel.id" :label="channelLabel(channel)" :value="channel.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="搜索机器人" prop="search_bot_id">
          <el-select v-model="submitForm.search_bot_id" filterable placeholder="选择可用的搜索机器人">
            <el-option v-for="bot in availableSubmitBots" :key="bot.id" :label="`${bot.name} / ${bot.username}`" :value="bot.id" />
          </el-select>
          <div v-if="selectedChannel" class="field-help">当前频道分组：{{ selectedChannel.group_name || "未设置" }}</div>
        </el-form-item>
        <el-form-item v-if="submitForm.submission_mode === 'queue'" label="操作账号（选填）" prop="account_id">
          <el-select
            v-model="submitForm.account_id"
            clearable
            filterable
            :loading="props.accountsLoading"
            placeholder="留空则使用机器人默认操作账号"
          >
            <el-option v-for="account in enabledAccounts" :key="account.id" :label="accountLabel(account)" :value="account.id" />
          </el-select>
          <div class="field-help">{{ selectedSubmitBot?.account_id ? `当前机器人已配置默认操作账号：${selectedSubmitBot.account_name || `#${selectedSubmitBot.account_id}`}` : "当前机器人没有默认操作账号，请选择拥有目标频道管理权限的账号。" }}</div>
        </el-form-item>
        <template v-if="submitForm.submission_mode === 'manual'">
          <el-form-item label="提交收录账号来源">
            <el-radio-group v-model="manualAccountSource" class="mode-switch" @change="handleManualAccountSourceChange">
              <el-radio-button value="system" :disabled="!enabledAccounts.length">系统账号</el-radio-button>
              <el-radio-button value="manual">手动输入 ID</el-radio-button>
            </el-radio-group>
            <div class="field-help">优先选择系统已有账号；系统中没有时，再手动填写 Telegram 数字 ID。</div>
          </el-form-item>
          <el-form-item v-if="manualAccountSource === 'system'" label="提交收录账号" prop="account_id">
            <el-select
              v-model="submitForm.account_id"
              clearable
              filterable
              :loading="props.accountsLoading"
              placeholder="选择系统账号"
            >
              <el-option v-for="account in enabledAccounts" :key="account.id" :label="accountLabel(account)" :value="account.id" />
            </el-select>
          </el-form-item>
          <el-form-item v-else label="系统外账号 ID" prop="manual_account_id">
            <el-input
              v-model="submitForm.manual_account_id"
              inputmode="numeric"
              maxlength="20"
              placeholder="填写 Telegram 数字 ID，例如 5397112677"
              @input="submitFormRef?.clearValidate('manual_account_id')"
            />
          </el-form-item>
        </template>
        <div class="permission-panel">
          <div class="permission-heading">
            <div>
              <strong>搜索机器人在频道中的权限</strong>
              <span v-if="submitForm.submission_mode === 'queue'">已选择 {{ selectedAdminRightLabels.length }} 项；提交后会从 Telegram 回查实际权限。</span>
              <span v-else>登记你在 Telegram 手动授予的权限，系统会标记为“人工登记、未验证”。</span>
            </div>
            <el-button-group>
              <el-button size="small" @click="applyPermissionPreset('minimal')">最小权限</el-button>
              <el-button size="small" @click="applyPermissionPreset('common')">常用权限</el-button>
              <el-button size="small" @click="applyPermissionPreset('all')">全部权限</el-button>
            </el-button-group>
          </div>

          <div v-for="section in submitPermissionSections" :key="section.title" class="permission-section">
            <span class="permission-section-title">{{ section.title }}</span>
            <div class="permission-options">
              <el-checkbox
                v-for="item in section.items"
                :key="item.key"
                v-model="submitForm.admin_rights[item.key]"
              >
                {{ item.label }}
              </el-checkbox>
            </div>
          </div>

          <el-alert
            v-if="submitForm.admin_rights.add_admins"
            type="warning"
            :closable="false"
            show-icon
            title="已选择“添加管理员”：机器人将可以继续授权其他管理员，请确认确实需要。"
          />
        </div>
        <div v-if="submitForm.submission_mode === 'manual'" class="form-grid manual-status-grid">
          <el-form-item label="审核状态"><el-select v-model="submitForm.review_status"><el-option label="待审核" value="pending" /><el-option label="审核中" value="reviewing" /><el-option label="已通过" value="approved" /><el-option label="已拒绝" value="rejected" /><el-option label="未知" value="unknown" /></el-select></el-form-item>
          <el-form-item label="收录状态"><el-select v-model="submitForm.collection_status"><el-option label="未知" value="unknown" /><el-option label="已收录" value="collected" /><el-option label="未收录" value="not_collected" /></el-select></el-form-item>
          <el-form-item label="拉黑状态"><el-select v-model="submitForm.block_status"><el-option label="正常" value="normal" /><el-option label="已拉黑" value="blocked" /><el-option label="未知" value="unknown" /></el-select></el-form-item>
          <el-form-item label="当前有效收录"><el-switch v-model="submitForm.is_current" :disabled="submitForm.block_status === 'blocked'" active-text="是" inactive-text="否" /></el-form-item>
        </div>
      </el-form>
      <template #footer><el-button :disabled="submitting" @click="submitDialogVisible = false">取消</el-button><el-button type="primary" :loading="submitting" @click="submitChannel">{{ submitForm.submission_mode === "manual" ? "登记记录" : "立即提交" }}</el-button></template>
    </el-dialog>

    <el-dialog
      v-model="statusDialogVisible"
      title="更新频道提交状态"
      width="min(600px, calc(100vw - 24px))"
      append-to-body
      destroy-on-close
    >
      <el-descriptions v-if="editingSubmission" :column="1" border>
        <el-descriptions-item label="频道">{{ editingSubmission.channel_title }} / {{ editingSubmission.channel_username || editingSubmission.channel_chat_id }}</el-descriptions-item>
        <el-descriptions-item label="搜索机器人">{{ editingSubmission.search_bot_name }} / {{ editingSubmission.search_bot_username }}</el-descriptions-item>
        <el-descriptions-item label="授予权限">
          <div v-if="adminRightLabels(editingSubmission.applied_admin_rights || editingSubmission.admin_rights).length" class="permission-tags">
            <el-tag v-for="label in adminRightLabels(editingSubmission.applied_admin_rights || editingSubmission.admin_rights)" :key="label" size="small">{{ label }}</el-tag>
          </div>
          <span v-else class="muted-text">最小权限</span>
        </el-descriptions-item>
        <el-descriptions-item label="权限验证">
          <el-tag :type="permissionStatusType(editingSubmission.permission_status)" size="small">{{ permissionStatusLabel(editingSubmission.permission_status) }}</el-tag>
          <span v-if="editingSubmission.permission_last_error" class="permission-error">{{ editingSubmission.permission_last_error }}</span>
        </el-descriptions-item>
      </el-descriptions>
      <el-form :model="statusForm" label-position="top" class="dialog-form form-grid">
        <el-form-item label="审核状态"><el-select v-model="statusForm.review_status"><el-option label="未知" value="unknown" /><el-option label="待审核" value="pending" /><el-option label="审核中" value="reviewing" /><el-option label="已通过" value="approved" /><el-option label="已拒绝" value="rejected" /></el-select></el-form-item>
        <el-form-item label="收录状态"><el-select v-model="statusForm.collection_status"><el-option label="未知" value="unknown" /><el-option label="已收录" value="collected" /><el-option label="未收录" value="not_collected" /></el-select></el-form-item>
        <el-form-item label="拉黑状态"><el-select v-model="statusForm.block_status"><el-option label="未知" value="unknown" /><el-option label="正常" value="normal" /><el-option label="已拉黑" value="blocked" /></el-select></el-form-item>
        <el-form-item label="当前有效收录"><el-switch v-model="statusForm.is_current" :disabled="statusForm.block_status === 'blocked'" active-text="是" inactive-text="否" /></el-form-item>
      </el-form>
      <el-alert v-if="statusForm.block_status === 'blocked'" type="warning" :closable="false" title="标记拉黑后，该记录会自动取消“当前有效”；保存后可点击“改投”选择其他可用机器人。" />
      <template #footer><el-button @click="statusDialogVisible = false">取消</el-button><el-button type="primary" :loading="savingStatus" @click="saveSubmissionStatus">保存状态</el-button></template>
    </el-dialog>

    <el-dialog
      v-model="permissionDialogVisible"
      class="permission-channel-dialog"
      title="调整搜索机器人频道权限"
      width="min(720px, calc(100vw - 24px))"
      append-to-body
      destroy-on-close
    >
      <el-alert type="info" :closable="false" show-icon title="保存后会立即更新 Telegram 频道管理员权限，并回查实际结果。" />
      <el-descriptions v-if="permissionEditingSubmission" :column="1" border class="dialog-form">
        <el-descriptions-item label="频道">{{ permissionEditingSubmission.channel_title }} / {{ permissionEditingSubmission.channel_username || permissionEditingSubmission.channel_chat_id }}</el-descriptions-item>
        <el-descriptions-item label="搜索机器人">{{ permissionEditingSubmission.search_bot_name }} / {{ permissionEditingSubmission.search_bot_username }}</el-descriptions-item>
      </el-descriptions>
      <el-form :model="permissionForm" label-position="top" class="dialog-form">
        <el-form-item label="操作账号（选填）">
          <el-select
            v-model="permissionForm.account_id"
            clearable
            filterable
            :loading="props.accountsLoading"
            placeholder="留空则使用原提交账号或机器人默认账号"
          >
            <el-option v-for="account in enabledAccounts" :key="account.id" :label="accountLabel(account)" :value="account.id" />
          </el-select>
        </el-form-item>
        <div class="permission-panel">
          <div class="permission-heading">
            <div>
              <strong>搜索机器人在频道中的权限</strong>
              <span>只显示当前频道类型可使用的权限。</span>
            </div>
            <el-button-group>
              <el-button size="small" @click="applyAdjustmentPreset('minimal')">最小权限</el-button>
              <el-button size="small" @click="applyAdjustmentPreset('common')">常用权限</el-button>
              <el-button size="small" @click="applyAdjustmentPreset('all')">全部权限</el-button>
            </el-button-group>
          </div>
          <div v-for="section in adjustmentPermissionSections" :key="section.title" class="permission-section">
            <span class="permission-section-title">{{ section.title }}</span>
            <div class="permission-options">
              <el-checkbox v-for="item in section.items" :key="item.key" v-model="permissionForm.admin_rights[item.key]">{{ item.label }}</el-checkbox>
            </div>
          </div>
          <el-alert v-if="permissionForm.admin_rights.add_admins" type="warning" :closable="false" show-icon title="已选择“添加管理员”，机器人将能够继续授权其他管理员。" />
        </div>
      </el-form>
      <template #footer>
        <el-button :disabled="savingPermissions" @click="permissionDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingPermissions" @click="savePermissions">应用并回查</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from "vue"
import { ElMessage, ElMessageBox } from "element-plus"
import { Plus, Refresh, Search } from "@element-plus/icons-vue"
import {
  checkSearchBot,
  createSearchBot,
  createSearchBotSubmission,
  deleteSearchBot,
  getMyChannels,
  getSearchBots,
  getSearchBotSubmissions,
  updateSearchBot,
  updateSearchBotSubmission,
  updateSearchBotSubmissionPermissions,
} from "../api/myChannels"
import CopyText from "./CopyText.vue"
import StatusTag from "./StatusTag.vue"

const props = defineProps({
  accounts: { type: Array, default: () => [] },
  accountsLoading: { type: Boolean, default: false },
})
const emit = defineEmits(["submission-changed"])
const panelView = ref("bots")
const bots = ref([])
const channels = ref([])
const submissions = ref([])
const botLoading = ref(false)
const submissionLoading = ref(false)
const checkingId = ref(null)
const botDialogVisible = ref(false)
const submitDialogVisible = ref(false)
const statusDialogVisible = ref(false)
const permissionDialogVisible = ref(false)
const editingBot = ref(null)
const editingSubmission = ref(null)
const permissionEditingSubmission = ref(null)
const savingBot = ref(false)
const submitting = ref(false)
const savingStatus = ref(false)
const savingPermissions = ref(false)
const botFormRef = ref(null)
const submitFormRef = ref(null)
const manualAccountSource = ref("system")
const botFilters = reactive({ keyword: "", status: "" })
const submissionFilters = reactive({ keyword: "", group_name: "", block_status: "" })
const permissionSections = [
  {
    title: "内容管理",
    items: [
      { key: "post_messages", label: "发布消息" },
      { key: "edit_messages", label: "编辑消息" },
      { key: "delete_messages", label: "删除消息" },
      { key: "pin_messages", label: "置顶消息" },
      { key: "post_stories", label: "发布动态" },
      { key: "edit_stories", label: "编辑动态" },
      { key: "delete_stories", label: "删除动态" },
    ],
  },
  {
    title: "频道管理",
    items: [
      { key: "change_info", label: "修改频道信息" },
      { key: "invite_users", label: "邀请用户" },
      { key: "ban_users", label: "管理用户" },
      { key: "manage_call", label: "管理视频聊天" },
      { key: "manage_topics", label: "管理话题" },
      { key: "manage_direct_messages", label: "管理频道私信" },
    ],
  },
  {
    title: "高级权限",
    items: [
      { key: "add_admins", label: "添加管理员" },
      { key: "anonymous", label: "匿名管理" },
      { key: "manage_ranks", label: "管理管理员头衔" },
    ],
  },
]
const allPermissionOptions = permissionSections.flatMap((section) => section.items)
const botForm = reactive(emptyBotForm())
const submitForm = reactive(emptySubmitForm())
const statusForm = reactive({ review_status: "unknown", collection_status: "unknown", block_status: "unknown", is_current: false })
const permissionForm = reactive({ account_id: null, admin_rights: emptyAdminRights() })
const botRules = {
  name: [{ required: true, message: "请填写机器人名称", trigger: "blur" }],
  username: [{ required: true, message: "请填写机器人 ID 或链接", trigger: "blur" }],
}
const submitRules = {
  my_channel_id: [{ required: true, message: "请选择频道", trigger: "change" }],
  search_bot_id: [{ required: true, message: "请选择搜索机器人", trigger: "change" }],
  account_id: [{
    validator: (_rule, value, callback) => {
      if (submitForm.submission_mode === "manual" && manualAccountSource.value === "system" && !value) {
        callback(new Error("请选择提交收录的系统账号"))
        return
      }
      callback()
    },
    trigger: "change",
  }],
  manual_account_id: [{
    validator: (_rule, value, callback) => {
      if (submitForm.submission_mode !== "manual" || manualAccountSource.value !== "manual") {
        callback()
        return
      }
      if (!String(value || "").trim()) {
        callback(new Error("请填写系统外账号 ID"))
        return
      }
      if (!/^\d+$/.test(String(value).trim())) {
        callback(new Error("账号 ID 只能填写数字"))
        return
      }
      callback()
    },
    trigger: "blur",
  }],
}
const enabledAccounts = computed(() => props.accounts.filter((item) => item.enabled !== false))
const enabledChannels = computed(() => channels.value.filter((item) => item.status !== "disabled" && item.group_name))
const groupOptions = computed(() => Array.from(new Set(channels.value.map((item) => item.group_name).filter(Boolean))).sort((a, b) => a.localeCompare(b, "zh-Hans-CN")))
const visibleBots = computed(() => bots.value)
const selectedChannel = computed(() => channels.value.find((item) => Number(item.id) === Number(submitForm.my_channel_id)))
const selectedSubmitBot = computed(() => bots.value.find((item) => Number(item.id) === Number(submitForm.search_bot_id)))
const availableSubmitBots = computed(() => bots.value.filter((item) => item.status === "enabled"))
const enabledCount = computed(() => bots.value.filter((item) => item.status === "enabled").length)
const currentCount = computed(() => bots.value.reduce((sum, item) => sum + Number(item.current_channel_count || 0), 0))
const blockedCount = computed(() => bots.value.reduce((sum, item) => sum + Number(item.blocked_channel_count || 0), 0))
const selectedAdminRightLabels = computed(() => adminRightLabels(submitForm.admin_rights))
const submitPermissionSections = computed(() => permissionSectionsFor(selectedChannel.value?.channel_type))
const adjustmentPermissionSections = computed(() => permissionSectionsFor(permissionEditingSubmission.value?.channel_type))

onMounted(refreshAll)

function emptyBotForm() { return { name: "", username: "", account_id: null, monthly_active_users: null, status: "enabled", submit_template: "{{channel_link}}", remark: "" } }
function emptyAdminRights() { return Object.fromEntries(allPermissionOptions.map((item) => [item.key, false])) }
function emptySubmitForm() { return { my_channel_id: null, search_bot_id: null, account_id: null, manual_account_id: "", submission_mode: "queue", review_status: "pending", collection_status: "unknown", block_status: "normal", is_current: false, admin_rights: emptyAdminRights() } }
function applyPermissionPreset(preset) {
  const availableOptions = submitPermissionSections.value.flatMap((section) => section.items)
  const enabled = preset === "all"
    ? new Set(availableOptions.map((item) => item.key))
    : preset === "common"
      ? new Set(["post_messages", "edit_messages", "delete_messages"])
      : new Set()
  Object.assign(submitForm.admin_rights, emptyAdminRights())
  for (const key of enabled) submitForm.admin_rights[key] = true
}
function permissionSectionsFor(channelType) {
  const type = String(channelType || "").toLowerCase()
  const isGroup = ["group", "supergroup", "megagroup", "forum"].some((value) => type.includes(value))
  const isBroadcast = !isGroup && ["channel", "broadcast"].some((value) => type.includes(value))
  const unsupported = isGroup
    ? new Set(["post_messages", "edit_messages", "post_stories", "edit_stories", "delete_stories", "manage_direct_messages"])
    : isBroadcast
      ? new Set(["ban_users", "pin_messages", "manage_topics"])
      : new Set()
  return permissionSections
    .map((section) => ({ ...section, items: section.items.filter((item) => !unsupported.has(item.key)) }))
    .filter((section) => section.items.length)
}
function applyAdjustmentPreset(preset) {
  const availableOptions = adjustmentPermissionSections.value.flatMap((section) => section.items)
  const enabled = preset === "all"
    ? new Set(availableOptions.map((item) => item.key))
    : preset === "common"
      ? new Set(["post_messages", "edit_messages", "delete_messages"].filter((key) => availableOptions.some((item) => item.key === key)))
      : new Set()
  Object.assign(permissionForm.admin_rights, emptyAdminRights())
  for (const key of enabled) permissionForm.admin_rights[key] = true
}
function adminRightLabels(rights) {
  const value = rights && typeof rights === "object" ? rights : {}
  return allPermissionOptions.filter((item) => value[item.key]).map((item) => item.label)
}
async function refreshAll() {
  await Promise.all([loadBots(), loadChannels(), loadSubmissions()])
}
async function loadBots() { botLoading.value = true; try { bots.value = (await getSearchBots(botFilters)).data.items || [] } catch (error) { ElMessage.error(readError(error, "加载搜索机器人失败")) } finally { botLoading.value = false } }
async function loadChannels() {
  try {
    channels.value = (await getMyChannels()).data.items || []
  } catch (error) {
    ElMessage.error(readError(error, "加载频道失败"))
  }
}
async function loadSubmissions() { submissionLoading.value = true; try { submissions.value = (await getSearchBotSubmissions(submissionFilters)).data.items || [] } catch (error) { ElMessage.error(readError(error, "加载提交记录失败")) } finally { submissionLoading.value = false } }
function openBotCreate() { editingBot.value = null; Object.assign(botForm, emptyBotForm()); botDialogVisible.value = true }
function openBotEdit(row) { editingBot.value = row; Object.assign(botForm, { ...emptyBotForm(), ...row }); botDialogVisible.value = true }
async function saveBot() { if (!(await botFormRef.value?.validate().catch(() => false))) return; savingBot.value = true; try { if (editingBot.value?.id) await updateSearchBot(editingBot.value.id, botForm); else await createSearchBot(botForm); ElMessage.success(editingBot.value?.id ? "搜索机器人已保存" : "搜索机器人已添加"); botDialogVisible.value = false; await loadBots() } catch (error) { ElMessage.error(readError(error, "保存搜索机器人失败")) } finally { savingBot.value = false } }
async function detectBot(row) { checkingId.value = row.id; try { const res = await checkSearchBot(row.id); res.data.ok ? ElMessage.success(res.data.message) : ElMessage.warning(res.data.message || "检测失败"); await loadBots() } catch (error) { ElMessage.error(readError(error, "检测失败")) } finally { checkingId.value = null } }
async function removeBot(row) { try { await ElMessageBox.confirm(`确定删除“${row.name}”？已有提交历史的机器人只能停用。`, "删除搜索机器人", { type: "warning" }); await deleteSearchBot(row.id); ElMessage.success("搜索机器人已删除"); await loadBots() } catch (error) { if (error !== "cancel" && error !== "close") ElMessage.error(readError(error, "删除失败")) } }
function openSubmitForChannel(channel) {
  const channelId = Number(channel?.id ?? channel)
  if (channel && typeof channel === "object" && !channels.value.some((item) => Number(item.id) === channelId)) {
    channels.value = [channel, ...channels.value]
  }
  Object.assign(submitForm, emptySubmitForm(), { my_channel_id: channelId })
  resetManualAccountSource()
  submitDialogVisible.value = true
}
function openResubmit(row) { Object.assign(submitForm, emptySubmitForm(), { my_channel_id: row.my_channel_id, admin_rights: { ...emptyAdminRights(), ...(row.admin_rights || {}) } }); resetManualAccountSource(); submitDialogVisible.value = true }
async function submitChannel() { if (!(await submitFormRef.value?.validate().catch(() => false))) return; const channel = selectedChannel.value; const bot = selectedSubmitBot.value; if (!channel?.group_name) return ElMessage.warning("频道未设置分组，请先编辑频道"); if (submitForm.submission_mode === "queue" && !submitForm.account_id && !bot?.account_id) return ElMessage.warning("请选择操作账号，或先为搜索机器人配置默认操作账号"); submitting.value = true; try { const response = await createSearchBotSubmission(submitForm); const item = response.data?.item; if (item?.submit_status === "failed") throw new Error(item.last_error || "添加失败"); ElMessage.success(submitForm.submission_mode === "manual" ? "手动提交记录已登记" : "搜索机器人已添加到频道"); submitDialogVisible.value = false; panelView.value = "submissions"; await Promise.all([loadBots(), loadSubmissions()]); emit("submission-changed") } catch (error) { ElMessage.error(readError(error, "提交失败")) } finally { submitting.value = false } }
function openSubmissionEdit(row) { editingSubmission.value = row; Object.assign(statusForm, { review_status: row.review_status || "unknown", collection_status: row.collection_status || "unknown", block_status: row.block_status || "unknown", is_current: Boolean(row.is_current) }); statusDialogVisible.value = true }
async function saveSubmissionStatus() { savingStatus.value = true; try { await updateSearchBotSubmission(editingSubmission.value.id, statusForm); ElMessage.success("提交状态已更新"); statusDialogVisible.value = false; await Promise.all([loadBots(), loadSubmissions()]); emit("submission-changed") } catch (error) { ElMessage.error(readError(error, "保存状态失败")) } finally { savingStatus.value = false } }
function openPermissionEdit(row) {
  permissionEditingSubmission.value = row
  Object.assign(permissionForm, {
    account_id: row.account_id || null,
    admin_rights: {
      ...emptyAdminRights(),
      ...(row.applied_admin_rights || row.admin_rights || {}),
    },
  })
  permissionDialogVisible.value = true
}
async function savePermissions() {
  if (!permissionEditingSubmission.value?.id) return
  savingPermissions.value = true
  try {
    const response = await updateSearchBotSubmissionPermissions(
      permissionEditingSubmission.value.id,
      permissionForm,
    )
    if (!response.data?.ok) throw new Error(response.data?.message || "Telegram 权限回查未通过")
    ElMessage.success("机器人频道权限已更新并通过回查")
    permissionDialogVisible.value = false
    await Promise.all([loadBots(), loadSubmissions()])
    emit("submission-changed")
  } catch (error) {
    ElMessage.error(readError(error, "调整权限失败"))
  } finally {
    savingPermissions.value = false
  }
}
function accountLabel(account) { return `${account.name || `账号 #${account.id}`}${account.username ? ` / ${account.username}` : ""}` }
function submissionAccountLabel(row) {
  if (row.account_name) return `${row.account_name}（系统账号）`
  if (row.account_id) return `系统账号 #${row.account_id}`
  if (row.manual_account_id) return `账号 ID ${row.manual_account_id}`
  return "-"
}
function resetManualAccountSource() {
  manualAccountSource.value = enabledAccounts.value.length ? "system" : "manual"
  handleManualAccountSourceChange(manualAccountSource.value)
}
function handleSubmissionModeChange(mode) {
  if (mode === "manual") {
    resetManualAccountSource()
    return
  }
  submitForm.manual_account_id = ""
}
function handleManualAccountSourceChange(source) {
  if (source === "system") {
    submitForm.manual_account_id = ""
  } else {
    submitForm.account_id = null
  }
  submitFormRef.value?.clearValidate(["account_id", "manual_account_id"])
}
function channelLabel(channel) { return `${channel.title || channel.username || channel.chat_id} / ${channel.group_name} / ${channel.username || channel.chat_id}` }
function formatDateTime(value) { return value ? String(value).replace("T", " ").slice(0, 19) : "-" }
function readError(error, fallback) { return error?.response?.data?.detail || error?.response?.data?.message || error?.message || fallback }
function statusLabel(status) { return ({ queued: "排队中", submitting: "添加中", success: "已添加", manual: "手动登记", failed: "失败", unknown: "未知", pending: "待审核", reviewing: "审核中", approved: "已通过", rejected: "已拒绝", collected: "已收录", not_collected: "未收录", normal: "正常", blocked: "已拉黑" })[status] || status || "未知" }
function statusType(status) { if (["success", "approved", "collected", "normal"].includes(status)) return "success"; if (["failed", "rejected", "blocked"].includes(status)) return "danger"; if (["queued", "submitting", "pending", "reviewing"].includes(status)) return "warning"; return "info" }
function permissionStatusLabel(status) { return ({ pending: "待应用", applying: "应用中", applied: "已验证", mismatch: "权限不一致", failed: "应用失败", unverified: "人工登记" })[status] || "未验证" }
function permissionStatusType(status) { if (status === "applied") return "success"; if (["failed", "mismatch"].includes(status)) return "danger"; if (["pending", "applying"].includes(status)) return "warning"; return "info" }

defineExpose({ openSubmitForChannel, openSubmissionEdit, openPermissionEdit })
</script>

<style scoped>
.search-bot-panel { display: flex; flex-direction: column; gap: 12px; }
.panel-summary { display: flex; flex-wrap: wrap; gap: 8px; }
.panel-summary > div { min-width: 110px; padding: 9px 12px; border: 1px solid var(--el-border-color-light); border-radius: 6px; background: var(--el-fill-color-lighter); }
.panel-summary span { display: block; color: var(--el-text-color-secondary); font-size: 12px; }
.panel-summary strong { display: block; margin-top: 2px; font-size: 18px; }
.success-text { color: var(--el-color-success); }
.danger-text { color: var(--el-color-danger); }
.toolbar, .filters, .row-actions { display: flex; align-items: center; gap: 8px; }
.toolbar { justify-content: space-between; flex-wrap: wrap; margin-bottom: 12px; }
.filters { flex: 1; flex-wrap: wrap; }
.filters .el-input { width: min(340px, 100%); }
.filters .el-select { width: 150px; }
.inner-tabs, .dialog-form { margin-top: 12px; }
.row-actions { justify-content: center; gap: 6px; white-space: nowrap; }
.row-actions .el-button { margin-left: 0; }
.channel-metrics { display: flex; align-items: center; gap: 18px; }
.channel-metrics span { display: inline-flex; align-items: baseline; gap: 6px; white-space: nowrap; }
.channel-metrics small { color: var(--el-text-color-secondary); font-size: 12px; }
.channel-metrics strong { color: var(--el-text-color-primary); font-size: 14px; font-weight: 600; }
.channel-metrics .metric-danger small, .channel-metrics .metric-danger strong { color: var(--el-color-danger); }
.muted-text { color: var(--el-text-color-placeholder); }
.no-wrap { white-space: nowrap; }
:deep(.el-table th.el-table__cell) { background: var(--el-fill-color-light); color: var(--el-text-color-regular); font-weight: 600; }
:deep(.el-table .cell) { line-height: 22px; }
.row-actions :deep(.el-button) { min-width: 42px; padding: 5px 9px; }
.submission-actions :deep(.el-button:first-child) { min-width: 68px; }
.form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 16px; }
.form-grid .el-select, .form-grid .el-input-number, .dialog-form .el-select { width: 100%; }
.field-help { margin-top: 5px; color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; }
.mode-switch { width: 100%; }
.mode-switch :deep(.el-radio-button) { flex: 1; }
.mode-switch :deep(.el-radio-button__inner) { width: 100%; }
.manual-status-grid { padding-top: 2px; }
.permission-panel {
  margin-bottom: 18px;
  padding: 14px;
  border: 1px solid var(--el-border-color);
  border-radius: 6px;
}
.permission-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 12px;
}
.permission-heading > div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.permission-heading span,
.permission-section-title {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.permission-section + .permission-section { margin-top: 10px; }
.permission-section-title { display: block; margin-bottom: 4px; }
.permission-options {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 2px 12px;
}
.permission-options :deep(.el-checkbox) {
  margin-right: 0;
  min-width: 0;
}
.permission-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.permission-error {
  display: block;
  margin-top: 6px;
  color: var(--el-color-danger);
  font-size: 12px;
  line-height: 1.5;
}
.permission-panel .el-alert { margin-top: 12px; }
:global(.search-bot-dialog),
:global(.submit-channel-dialog),
:global(.permission-channel-dialog) {
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 24px);
  margin: 12px auto !important;
}
:global(.search-bot-dialog .el-dialog__body),
:global(.submit-channel-dialog .el-dialog__body),
:global(.permission-channel-dialog .el-dialog__body) {
  min-height: 0;
  overflow-y: auto;
}
:global(.search-bot-dialog .el-dialog__header),
:global(.search-bot-dialog .el-dialog__footer),
:global(.submit-channel-dialog .el-dialog__header),
:global(.submit-channel-dialog .el-dialog__footer),
:global(.permission-channel-dialog .el-dialog__header),
:global(.permission-channel-dialog .el-dialog__footer) {
  flex: 0 0 auto;
}
@media (max-width: 768px) {
  .toolbar, .filters { align-items: stretch; flex-direction: column; }
  .filters .el-input, .filters .el-select, .toolbar > .el-button { width: 100%; }
  .form-grid { grid-template-columns: minmax(0, 1fr); }
  .panel-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .panel-summary > div { min-width: 0; }
  .permission-heading { align-items: stretch; flex-direction: column; }
  .permission-heading .el-button-group { display: flex; }
  .permission-heading .el-button-group .el-button { flex: 1; }
  .permission-options { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 420px) {
  .permission-options { grid-template-columns: minmax(0, 1fr); }
}
</style>
