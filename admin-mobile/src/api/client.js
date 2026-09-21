import axios from "axios"

export const API_BASE = import.meta.env?.VITE_API_BASE || ""
export const TOKEN_STORAGE_KEY = "admin_token"
export const SESSION_STORAGE_CHANGED_EVENT = "mobile-auth-storage-changed"
export const SESSION_INVALIDATED_EVENT = "mobile-auth-session-invalidated"

const SESSION_CONTEXT_KEY = "__mobileSessionContext"
const STORAGE_LISTENER_SLOT = "__mobileAdminTokenStorageListener"
const SENSITIVE_HEADER_NAMES = new Set([
  "authorization",
  "proxy-authorization",
  "cookie",
  "set-cookie",
  "x-api-key",
  "api-key",
  "x-auth-token",
  "x-access-token",
  "x-session-token",
])

let sessionGeneration = 0
let requestSequence = 0
let reloadScheduled = false
let sessionToken = readStoredToken()
const activeRequests = new Map()

export const http = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
})

function readStoredToken(fallback = "") {
  try {
    return window.localStorage.getItem(TOKEN_STORAGE_KEY) || ""
  } catch {
    return fallback
  }
}

function writeStoredToken(token) {
  try {
    if (token) window.localStorage.setItem(TOKEN_STORAGE_KEY, token)
    else window.localStorage.removeItem(TOKEN_STORAGE_KEY)
  } catch {
    // The in-memory session remains authoritative if storage is unavailable.
  }
}

function cancelInFlightRequests() {
  for (const request of activeRequests.values()) {
    request.detachUpstreamSignal?.()
    request.controller.abort()
  }
  activeRequests.clear()
}

function rotateSession(token, { persist = true } = {}) {
  sessionGeneration += 1
  sessionToken = String(token || "")
  cancelInFlightRequests()
  if (persist) writeStoredToken(sessionToken)
  return sessionGeneration
}

function scheduleReload() {
  if (reloadScheduled) return
  reloadScheduled = true
  window.setTimeout(() => window.location.reload(), 0)
}

function dispatchSessionEvent(name, authenticated) {
  window.dispatchEvent(new CustomEvent(name, {
    detail: {
      authenticated: Boolean(authenticated),
      generation: sessionGeneration,
    },
  }))
}

function handleExternalTokenChange(nextToken) {
  if (String(nextToken || "") === sessionToken) return
  rotateSession(nextToken, { persist: false })
  dispatchSessionEvent(SESSION_STORAGE_CHANGED_EVENT, Boolean(sessionToken))
  scheduleReload()
}

function bindAbortController(config, context) {
  const controller = new AbortController()
  const upstreamSignal = config.signal
  let detachUpstreamSignal = null

  if (upstreamSignal) {
    const abortFromUpstream = () => controller.abort()
    if (upstreamSignal.aborted) controller.abort()
    else {
      upstreamSignal.addEventListener("abort", abortFromUpstream, { once: true })
      detachUpstreamSignal = () => {
        upstreamSignal.removeEventListener("abort", abortFromUpstream)
      }
    }
  }

  config.signal = controller.signal
  activeRequests.set(context.requestId, { controller, detachUpstreamSignal })
}

function requestContext(config) {
  return config?.[SESSION_CONTEXT_KEY] || null
}

function cleanupRequest(config) {
  const context = requestContext(config)
  if (!context) return null
  const request = activeRequests.get(context.requestId)
  request?.detachUpstreamSignal?.()
  activeRequests.delete(context.requestId)
  return context
}

function isCurrentRequest(context) {
  return Boolean(
    context
    && context.generation === sessionGeneration
    && context.token === sessionToken
  )
}

function createSessionCanceledError(context) {
  const error = new axios.CanceledError("请求已因登录账号切换而取消")
  error.isSessionCanceled = true
  error.sessionGeneration = context?.generation
  return error
}

function sanitizeHeaders(headers) {
  if (!headers) return headers
  const values = typeof headers.toJSON === "function"
    ? headers.toJSON()
    : { ...headers }

  Object.keys(values).forEach((name) => {
    if (SENSITIVE_HEADER_NAMES.has(String(name).toLowerCase())) {
      delete values[name]
    } else if (values[name] && typeof values[name] === "object") {
      values[name] = sanitizeHeaders(values[name])
    }
  })
  return values
}

function sanitizeRequestConfig(config) {
  if (!config || typeof config !== "object") return config
  config.headers = sanitizeHeaders(config.headers)
  delete config.data
  delete config.params
  delete config.auth
  delete config.signal
  delete config[SESSION_CONTEXT_KEY]
  return config
}

function sanitizeResponse(response) {
  if (response?.config) sanitizeRequestConfig(response.config)
  if (response && typeof response === "object") delete response.request
  return response
}

function sanitizeError(error) {
  if (error?.config) sanitizeRequestConfig(error.config)
  if (error?.response?.config && error.response.config !== error.config) {
    sanitizeRequestConfig(error.response.config)
  }
  if (error?.response && typeof error.response === "object") delete error.response.request
  if (error && typeof error === "object") delete error.request
  return error
}

http.interceptors.request.use((config) => {
  const storedToken = readStoredToken(sessionToken)
  if (storedToken !== sessionToken) {
    handleExternalTokenChange(storedToken)
    return Promise.reject(createSessionCanceledError())
  }

  const context = {
    requestId: ++requestSequence,
    generation: sessionGeneration,
    token: sessionToken,
  }
  config[SESSION_CONTEXT_KEY] = context
  bindAbortController(config, context)

  if (sessionToken) {
    if (typeof config.headers?.set === "function") {
      config.headers.set("Authorization", `Bearer ${sessionToken}`)
    } else {
      config.headers = {
        ...(config.headers || {}),
        Authorization: `Bearer ${sessionToken}`,
      }
    }
  }
  return config
})

http.interceptors.response.use(
  (response) => {
    const context = cleanupRequest(response?.config)
    sanitizeResponse(response)
    if (!isCurrentRequest(context)) {
      return Promise.reject(createSessionCanceledError(context))
    }
    return response
  },
  (error) => {
    const config = error?.config || error?.response?.config
    const context = cleanupRequest(config)
    const requestUrl = String(config?.url || "")
    const staleRequest = context && !isCurrentRequest(context)
    sanitizeError(error)

    if (staleRequest) {
      return Promise.reject(createSessionCanceledError(context))
    }

    if (isCanceledRequest(error)) {
      return Promise.reject(error)
    }

    if (
      error.response?.status === 401 &&
      !requestUrl.includes("/api/auth/") &&
      isCurrentRequest(context)
    ) {
      const canceledError = createSessionCanceledError(context)
      setToken("")
      dispatchSessionEvent(SESSION_INVALIDATED_EVENT, false)
      scheduleReload()
      return Promise.reject(canceledError)
    }
    if (error.response?.status === 403 && isCurrentRequest(context)) {
      const code = error.response?.data?.code
      if (["ACCESS_PENDING", "ACCESS_EXPIRED", "FEATURE_FORBIDDEN"].includes(code)) {
        window.dispatchEvent(new CustomEvent("mobile-access-restricted", {
          detail: {
            code,
            message: error.response?.data?.detail || "当前账号没有此功能权限",
          },
        }))
      }
    }
    return Promise.reject(error)
  },
)

export function setToken(token) {
  return rotateSession(token)
}

export function getToken() {
  return sessionToken
}

export function getSessionGeneration() {
  return sessionGeneration
}

export function isCurrentSession(generation) {
  return generation === sessionGeneration
}

export function isCanceledRequest(error) {
  return Boolean(
    error?.isSessionCanceled
    || error?.code === "ERR_CANCELED"
    || error?.name === "CanceledError"
    || axios.isCancel(error)
  )
}

export function getErrorMessage(error, fallback = "请求失败") {
  if (isCanceledRequest(error)) return ""
  const data = error?.response?.data
  if (typeof data?.detail === "string") return data.detail
  if (typeof data?.message === "string") return data.message
  if (typeof data?.error === "string") return data.error
  if (typeof error?.message === "string") return error.message
  return fallback
}

if (window[STORAGE_LISTENER_SLOT]) {
  window.removeEventListener("storage", window[STORAGE_LISTENER_SLOT])
}
window[STORAGE_LISTENER_SLOT] = (event) => {
  if (event.key !== TOKEN_STORAGE_KEY) return
  handleExternalTokenChange(event.newValue || "")
}
window.addEventListener("storage", window[STORAGE_LISTENER_SLOT])
