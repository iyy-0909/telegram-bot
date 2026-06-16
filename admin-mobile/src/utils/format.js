export function asArray(value) {
  return Array.isArray(value) ? value : []
}

export function formatDate(value) {
  if (!value) return "-"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const pad = (num) => String(num).padStart(2, "0")
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function compactText(value, fallback = "-") {
  if (value === null || value === undefined || value === "") return fallback
  if (Array.isArray(value)) return value.filter(Boolean).join("、") || fallback
  return String(value)
}

export function enabledLabel(value) {
  return value ? "启用" : "停用"
}

export function statusType(status) {
  const value = String(status || "").toLowerCase()
  if (["running", "enabled", "success", "ok", "active", "done"].includes(value)) return "success"
  if (["error", "failed", "blocked"].includes(value)) return "danger"
  if (["pending", "waiting", "paused"].includes(value)) return "warning"
  return "info"
}

export function sourceTypeLabel(value) {
  const map = {
    clone: "克隆",
    listener: "监听",
    listener_catchup: "监听补齐",
    support: "客服",
    bulk_replace: "批量替换",
    control: "云台",
  }
  return map[value] || value || "-"
}
