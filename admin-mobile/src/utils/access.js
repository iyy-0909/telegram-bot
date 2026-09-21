export const FEATURE_DEFINITIONS = [
  { key: "dashboard", label: "运行首页" },
  { key: "listener_tasks", label: "监听任务", requires: ["accounts", "bots"] },
  { key: "clone_tasks", label: "克隆任务", requires: ["accounts", "bots"] },
  { key: "bots", label: "Bot 管理" },
  { key: "channels", label: "频道管理" },
  { key: "bulk_replace", label: "批量替换", desktopOnly: true },
  { key: "support", label: "客服机器人" },
  { key: "accounts", label: "Telegram 账号" },
  { key: "notifications", label: "消息通知", desktopOnly: true, requires: ["accounts"] },
  { key: "alerts", label: "系统告警" },
  { key: "ai_settings", label: "AI 配置" },
  { key: "system_settings", label: "系统设置" },
]

const ALL_FEATURE_KEYS = FEATURE_DEFINITIONS.map((item) => item.key)
const FEATURE_MAP = Object.fromEntries(FEATURE_DEFINITIONS.map((item) => [item.key, item]))

function enforceFeatureDependencies(values) {
  const effective = new Set(values)
  let changed = true
  while (changed) {
    changed = false
    for (const featureKey of [...effective]) {
      const required = FEATURE_MAP[featureKey]?.requires || []
      if (required.some((dependencyKey) => !effective.has(dependencyKey))) {
        effective.delete(featureKey)
        changed = true
      }
    }
  }
  return ALL_FEATURE_KEYS.filter((key) => effective.has(key))
}

export function userFeatureKeys(user) {
  if (user?.role === "admin") return [...ALL_FEATURE_KEYS]
  const raw = user?.feature_keys ?? user?.features ?? []
  if (!Array.isArray(raw)) return []
  const allowed = new Set(ALL_FEATURE_KEYS)
  return enforceFeatureDependencies(Array.from(new Set(raw.filter((key) => allowed.has(key)))))
}

export function hasFeature(user, featureKey) {
  if (user?.role === "admin") return true
  const state = String(user?.access_state || "active").toLowerCase()
  if (user?.available === false || ["pending", "waiting", "expired", "disabled"].includes(state)) {
    return false
  }
  return userFeatureKeys(user).includes(featureKey)
}

export function hasAnyFeature(user, featureKeys) {
  return featureKeys.some((featureKey) => hasFeature(user, featureKey))
}

export function featureLabel(featureKey) {
  return FEATURE_DEFINITIONS.find((item) => item.key === featureKey)?.label || featureKey
}

export function featureRequirementLabels(featureKey) {
  return (FEATURE_MAP[featureKey]?.requires || []).map(featureLabel)
}

export function accessStateLabel(state) {
  return ({
    active: "使用中",
    permanent: "长期有效",
    pending: "待管理员授权",
    waiting: "待管理员授权",
    expired: "已到期",
    disabled: "已禁用",
  })[state] || "待确认"
}

export function accessStateType(state) {
  if (["active", "permanent"].includes(state)) return "success"
  if (["pending", "waiting"].includes(state)) return "warning"
  if (["expired", "disabled"].includes(state)) return "danger"
  return "info"
}

export function formatAccessTime(value) {
  if (!value) return "长期有效"
  const text = String(value).trim()
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(text) ? text : `${text}Z`
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return text
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date)
}
