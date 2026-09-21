import axios from "axios"

export const AUTH_TOKEN_STORAGE_KEY = "admin_token"
export const AUTH_SESSION_CHANGED_EVENT = "admin-auth-session-changed"
export const ACCESS_RESTRICTED_EVENT = "admin-access-restricted"

const AUTH_CONTEXT_KEY = "__clonebotAuthContext"
const INTERCEPTOR_SLOT = "__clonebotAuthInterceptorCleanup"
const STORAGE_LISTENER_SLOT = "__clonebotAuthStorageListener"
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

let activeToken = readStoredToken()
let generation = 0
let requestSequence = 0
let reloadScheduled = false
const activeRequests = new Map()

function readStoredToken(fallback = "") {
  try {
    return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) || ""
  } catch {
    return fallback
  }
}

function writeStoredToken(token) {
  try {
    if (token) window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token)
    else window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY)
  } catch {
    // Storage can be unavailable in privacy modes; the in-memory session remains authoritative.
  }
}

function cancelActiveRequests() {
  for (const request of activeRequests.values()) {
    request.detachUpstreamSignal?.()
    request.controller.abort()
  }
  activeRequests.clear()
}

function rotateSession(nextToken, { persist = false } = {}) {
  activeToken = String(nextToken || "")
  generation += 1
  cancelActiveRequests()
  if (persist) writeStoredToken(activeToken)
  return generation
}

function syncStoredToken() {
  const storedToken = readStoredToken(activeToken)
  if (storedToken !== activeToken) rotateSession(storedToken)
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
  return config?.[AUTH_CONTEXT_KEY] || null
}

function completeRequest(config) {
  const context = requestContext(config)
  if (!context) return { context: null, isCurrent: null }

  const request = activeRequests.get(context.requestId)
  request?.detachUpstreamSignal?.()
  activeRequests.delete(context.requestId)
  syncStoredToken()

  return {
    context,
    isCurrent: context.generation === generation && context.token === activeToken,
  }
}

function createSessionCanceledError(context) {
  const error = new axios.CanceledError("请求已因登录账号切换而取消")
  error.isSessionCanceled = true
  error.sessionGeneration = context?.generation
  return error
}

function scrubHeaders(headers) {
  if (!headers) return headers
  const values = typeof headers.toJSON === "function"
    ? headers.toJSON()
    : { ...headers }

  Object.keys(values).forEach((name) => {
    if (SENSITIVE_HEADER_NAMES.has(String(name).toLowerCase())) {
      delete values[name]
    } else if (values[name] && typeof values[name] === "object") {
      values[name] = scrubHeaders(values[name])
    }
  })
  return values
}

function scheduleReload() {
  if (reloadScheduled) return
  reloadScheduled = true
  window.setTimeout(() => window.location.reload(), 0)
}

function dispatchAuthSessionChanged(authenticated) {
  window.dispatchEvent(new CustomEvent(AUTH_SESSION_CHANGED_EVENT, {
    detail: {
      authenticated: Boolean(authenticated),
      generation,
    },
  }))
}

export function getAuthToken() {
  syncStoredToken()
  return activeToken
}

export function getAuthGeneration() {
  syncStoredToken()
  return generation
}

export function isAuthGenerationCurrent(value) {
  syncStoredToken()
  return value === generation
}

export function replaceAuthToken(token) {
  return rotateSession(token, { persist: true })
}

export function syncExternalAuthToken(token) {
  const nextToken = String(token || "")
  if (nextToken === activeToken) return generation
  return rotateSession(nextToken)
}

export function bindRequestToAuthSession(config) {
  syncStoredToken()
  const context = {
    requestId: ++requestSequence,
    generation,
    token: activeToken,
  }
  config[AUTH_CONTEXT_KEY] = context
  bindAbortController(config, context)

  config.headers = config.headers || {}
  if (activeToken) {
    if (typeof config.headers.set === "function") {
      config.headers.set("Authorization", `Bearer ${activeToken}`)
    } else {
      config.headers.Authorization = `Bearer ${activeToken}`
    }
  }
  return config
}

export function scrubRequestSecrets(config) {
  if (!config || typeof config !== "object") return config
  config.headers = scrubHeaders(config.headers)
  delete config.data
  delete config.params
  delete config.auth
  delete config.signal
  delete config[AUTH_CONTEXT_KEY]
  return config
}

export function scrubResponseSecrets(response) {
  if (response?.config) scrubRequestSecrets(response.config)
  if (response && typeof response === "object") delete response.request
  return response
}

export function scrubErrorSecrets(error) {
  if (error?.config) scrubRequestSecrets(error.config)
  if (error?.response?.config && error.response.config !== error.config) {
    scrubRequestSecrets(error.response.config)
  }
  if (error?.response && typeof error.response === "object") delete error.response.request
  if (error && typeof error === "object") delete error.request
  return error
}

export function isCanceledAuthRequest(error) {
  return Boolean(
    error?.isSessionCanceled
    || error?.code === "ERR_CANCELED"
    || error?.name === "CanceledError"
    || axios.isCancel(error)
  )
}

function handleResponse(response) {
  const { context, isCurrent } = completeRequest(response?.config)
  scrubResponseSecrets(response)
  if (isCurrent === false) return Promise.reject(createSessionCanceledError(context))
  return response
}

function handleResponseError(error) {
  const config = error?.config || error?.response?.config
  const requestUrl = String(config?.url || "")
  const { context, isCurrent } = completeRequest(config)
  scrubErrorSecrets(error)

  if (isCurrent === false) return Promise.reject(createSessionCanceledError(context))
  if (isCanceledAuthRequest(error)) return Promise.reject(error)

  if (
    error?.response?.status === 401
    && !requestUrl.includes("/api/auth/")
    && isCurrent === true
  ) {
    const canceledError = createSessionCanceledError(context)
    replaceAuthToken("")
    window.localStorage.removeItem("clonebot_clone_task_logs")
    window.localStorage.removeItem("clonebot_listener_task_logs")
    dispatchAuthSessionChanged(false)
    scheduleReload()
    return Promise.reject(canceledError)
  }

  if (error?.response?.status === 403 && isCurrent === true) {
    const code = error.response?.data?.code
    if (["ACCESS_PENDING", "ACCESS_EXPIRED", "FEATURE_FORBIDDEN"].includes(code)) {
      window.dispatchEvent(new CustomEvent(ACCESS_RESTRICTED_EVENT, {
        detail: {
          code,
          message: error.response?.data?.detail || "当前账号没有此功能权限",
        },
      }))
    }
  }

  return Promise.reject(error)
}

export function installAuthSessionInterceptors(client = axios) {
  client[INTERCEPTOR_SLOT]?.()
  const requestInterceptor = client.interceptors.request.use(bindRequestToAuthSession)
  const responseInterceptor = client.interceptors.response.use(handleResponse, handleResponseError)
  const cleanup = () => {
    client.interceptors.request.eject(requestInterceptor)
    client.interceptors.response.eject(responseInterceptor)
    if (client[INTERCEPTOR_SLOT] === cleanup) delete client[INTERCEPTOR_SLOT]
  }
  client[INTERCEPTOR_SLOT] = cleanup
  return cleanup
}

export function installAuthStorageListener() {
  if (window[STORAGE_LISTENER_SLOT]) {
    window.removeEventListener("storage", window[STORAGE_LISTENER_SLOT])
  }

  const listener = (event) => {
    if (event.key !== AUTH_TOKEN_STORAGE_KEY || event.oldValue === event.newValue) return
    syncExternalAuthToken(event.newValue || "")
    dispatchAuthSessionChanged(Boolean(event.newValue))
    scheduleReload()
  }
  window[STORAGE_LISTENER_SLOT] = listener
  window.addEventListener("storage", listener)

  return () => {
    if (window[STORAGE_LISTENER_SLOT] !== listener) return
    window.removeEventListener("storage", listener)
    delete window[STORAGE_LISTENER_SLOT]
  }
}
