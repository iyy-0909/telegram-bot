const fields = {
  accounts: ['id', 'name', 'username', 'phone_masked', 'remark', 'enabled'],
  bots: ['id', 'name', 'username', 'bot_link', 'remark', 'last_error', 'enabled'],
  support: ['id', 'name', 'bot_id', 'bot_name', 'bot_username', 'support_group_chat_id', 'price', 'status', 'last_error', 'welcome_message'],
  tasks: ['id', 'name', 'source_channel', 'target_channels', 'status', 'account_id', 'bot_id', 'last_error'],
  events: ['id', 'time', 'task_id', 'task_name', 'source_channel', 'target', 'source_message_id', 'target_message_id', 'grouped_id', 'source_message_url', 'target_message_url', 'event_type', 'result', 'status', 'message_type', 'message', 'error', 'bot_name'],
  queue: ['id', 'task_id', 'task_name', 'source_type', 'source_channel', 'target_channel', 'source_message_id', 'grouped_id', 'message_type', 'status', 'reason', 'error', 'queued_at', 'estimated_send_at', 'finished_at'],
  templates: ['id', 'name', 'type', 'content', 'items', 'remark', 'enabled'],
  searchBots: ['id', 'name', 'username', 'bot_link', 'remark', 'status', 'account_id', 'account_name'],
  submissions: ['id', 'my_channel_id', 'channel_title', 'channel_username', 'channel_chat_id', 'search_bot_id', 'search_bot_name', 'search_bot_username', 'group_name', 'account_name', 'account_id', 'manual_account_id', 'submit_status', 'review_status', 'collection_status', 'block_status', 'remark', 'last_error'],
  collections: ['id', 'name', 'username', 'status', 'collectedLinks', 'remark'],
  channels: ['id', 'title', 'username', 'chat_id', 'group_name', 'bot_name', 'creator_username', 'status', 'delivery_status', 'collection_status', 'remark'],
  notifications: ['account_id', 'account_name', 'account_username', 'ntfy_url', 'account_enabled', 'enabled', 'last_test_status', 'last_test_message'],
  bindings: ['id', 'target_channel', 'bot_id', 'remark', 'enabled'],
  rules: ['id', 'source', 'target', 'last_message_id', 'enabled'],
  bulk: ['record_id', 'source_type', 'channel_title', 'target_channel', 'target_message_id', 'message_type', 'original_text', 'replaced_text', 'action_label', 'status', 'reason', 'error_message'],
}

const labels = {
  enabled: '正常 已启用', disabled: '已禁用 已停用', error: '错误 异常',
  pending: '待处理 待审核', reviewing: '审核中', running: '运行中', stopped: '已停止', blocked: '已拉黑',
  unknown: '未知', idle: '空闲', paused: '已暂停', done: '已完成', success: '成功',
  failed: '失败', empty: '空内容', filtered: '过滤', deduped: '去重', waiting: '等待中',
  rate_limited: '限流等待', retrying: '重试中', sending: '发送中', cancelled: '已取消',
  skipped: '已跳过', prepared: '准备', received: '收到', account_error: '账号异常',
  bot_error: 'Bot 异常', permission_error: '权限异常', queued: '排队中', submitting: '提交中 添加中',
  manual: '手动登记', approved: '已通过', rejected: '已拒绝', collected: '已收录',
  not_collected: '未收录', normal: '正常', clone: '克隆', listener: '监听',
  listener_catchup: '监听补齐', support: '客服', bulk_replace: '批量替换', control: '云台',
  head: '头部', body: '正文', footer: '底部', filter: '过滤', link: '链接', contact: '联系方式',
  text: '文字 文本', photo: '图片', video: '视频', document: '文件', album: '相册',
}

export function searchLabel(value) {
  return labels[String(value ?? '').toLowerCase()] || ''
}

// Search only the explicitly selected display fields, never tokens or sessions.
export function matchesRow(row, keyword, kind, extra = []) {
  const keys = Array.isArray(kind) ? kind : fields[kind] || []
  const values = keys.flatMap(key => {
    const value = row?.[key]
    if (typeof value === 'boolean' && (key === 'enabled' || key.endsWith('_enabled'))) {
      return [value ? 'enabled' : 'disabled', searchLabel(value ? 'enabled' : 'disabled')]
    }
    return [value, searchLabel(value), key === 'submit_status' && value === 'success' ? '已添加' : '']
  })
  return matchesSearch([...values, ...extra], keyword)
}

export function searchRows(rows, keyword, kind, extra = () => []) {
  if (!String(keyword ?? '').trim()) return rows || []
  return (rows || []).filter(row => matchesRow(row, keyword, kind, extra(row)))
}

export function buildSearchTerms(value) {
  const raw = String(value ?? '').trim().toLowerCase()
  if (!raw) return []
  const terms = new Set([raw])
  const match = raw.match(/(?:https?:\/\/)?(?:www\.)?(?:t\.me|telegram\.me)\/(?:s\/)?([^/?#\s]+)/i)
  const name = match?.[1]?.replace(/^@/, '') || (raw.startsWith('@') ? raw.slice(1).trim() : '')
  if (name && !name.startsWith('+') && name !== 'c') {
    terms.add(name)
    terms.add(`@${name}`)
    terms.add(`t.me/${name}`)
    terms.add(`https://t.me/${name}`)
  } else if (/^[a-z0-9_]{4,}$/i.test(raw)) {
    terms.add(`@${raw}`)
    terms.add(`t.me/${raw}`)
    terms.add(`https://t.me/${raw}`)
  }
  return [...terms].filter(Boolean)
}

export function matchesSearch(values, keyword) {
  const terms = buildSearchTerms(keyword)
  if (!terms.length) return true
  const haystack = values.flatMap(normalizeValue).join(' ').toLowerCase()
  return terms.some(term => haystack.includes(term))
}

function normalizeValue(value) {
  if (value === null || value === undefined) return []
  if (Array.isArray(value)) return value.flatMap(normalizeValue)
  if (typeof value === 'object') return Object.values(value).flatMap(normalizeValue)
  return [String(value), ...buildSearchTerms(value)]
}
