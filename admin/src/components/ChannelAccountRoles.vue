<template>
  <el-popover v-if="members.length" trigger="click" :width="320" placement="bottom-start">
    <template #reference>
      <el-button link type="primary" class="roles-trigger" :aria-label="`查看管理账号：${summary}`">{{ summary }}</el-button>
    </template>
    <div class="role-details">
      <p class="role-note">以下为最近同步的用户号身份，与 Bot 发帖权限无关。</p>
      <section v-for="member in members" :key="member.account_id" class="role-item">
        <strong>{{ member.account_name }}</strong>
        <el-tag size="small" :type="member.role === 'creator' ? 'success' : 'primary'">{{ roleLabel(member.role) }}</el-tag>
        <el-tag v-if="member.status !== 'success'" size="small" type="warning">未确认 · 上次结果</el-tag>
        <div>{{ member.account_username || '未设置用户名' }} · 账号 #{{ member.account_id }}</div>
        <div>{{ permissionSummary(member) }}</div>
        <div class="role-note">同步时间：{{ formatTime(member.checked_at) }}</div>
      </section>
    </div>
  </el-popover>
  <span v-else class="role-note">{{ status === 'checked' ? '未发现管理账号' : '未确认，请同步' }}</span>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({ members: { type: Array, default: () => [] }, status: { type: String, default: 'unknown' } })
const roleLabel = role => role === 'creator' ? '创建者' : '管理员'
const summary = computed(() => {
  const first = props.members[0]
  return first ? `${first.account_name} · ${roleLabel(first.role)}${first.status === 'success' ? '' : '（未确认）'}${props.members.length > 1 ? ` +${props.members.length - 1}` : ''}` : ''
})
const labels = { post_messages: '发布消息', edit_messages: '编辑消息', delete_messages: '删除消息', add_admins: '添加管理员', change_info: '修改频道信息', invite_users: '邀请用户', ban_users: '管理用户', pin_messages: '置顶', manage_call: '管理直播', post_stories: '发布动态', edit_stories: '编辑动态', delete_stories: '删除动态', manage_direct_messages: '管理频道私信' }
function permissionSummary(member) {
  if (member.role === 'creator') return '创建者：全部管理权限'
  return Object.entries(member.rights || {}).filter(([, enabled]) => enabled).map(([key]) => labels[key] || key).join('、') || '无上述管理权限'
}
function formatTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '未同步' }
</script>

<style scoped>
.roles-trigger { display: block; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; text-align: left; }
.role-details { max-height: 360px; overflow: auto; overflow-wrap: anywhere; line-height: 1.6; }
.role-item { padding: 10px 0; border-top: 1px solid var(--el-border-color-lighter); }
.role-item .el-tag { margin-left: 4px; }
.role-note { color: var(--el-text-color-secondary); font-size: 12px; margin: 0 0 6px; }
</style>
