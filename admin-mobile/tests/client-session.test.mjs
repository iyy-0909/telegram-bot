import assert from "node:assert/strict"
import test from "node:test"
import axios from "axios"

const storedValues = new Map()
const listeners = new Map()
let reloadCount = 0

globalThis.CustomEvent = class CustomEvent {
  constructor(type, init = {}) {
    this.type = type
    this.detail = init.detail
  }
}

globalThis.window = {
  localStorage: {
    getItem(key) {
      return storedValues.get(key) ?? null
    },
    setItem(key, value) {
      storedValues.set(key, String(value))
    },
    removeItem(key) {
      storedValues.delete(key)
    },
  },
  addEventListener(type, handler) {
    if (!listeners.has(type)) listeners.set(type, new Set())
    listeners.get(type).add(handler)
  },
  removeEventListener(type, handler) {
    listeners.get(type)?.delete(handler)
  },
  dispatchEvent(event) {
    listeners.get(event.type)?.forEach((handler) => handler(event))
    return true
  },
  setTimeout(callback) {
    callback()
    return 1
  },
  location: {
    reload() {
      reloadCount += 1
    },
  },
}

const {
  getSessionGeneration,
  getToken,
  http,
  isCanceledRequest,
  setToken,
  TOKEN_STORAGE_KEY,
} = await import("../src/api/client.js")

function responseFor(config, data = { ok: true }) {
  return {
    config,
    data,
    headers: {},
    request: { raw: "request metadata" },
    status: 200,
    statusText: "OK",
  }
}

function headerNames(headers) {
  return Object.keys(headers || {}).map((name) => name.toLowerCase())
}

test("会话切换会取消旧请求并清理返回对象中的敏感请求信息", async () => {
  setToken("token-a")
  const response = await http.post(
    "/echo",
    { password: "body-secret" },
    {
      headers: { "X-Api-Key": "header-secret" },
      params: { access_token: "query-secret" },
      adapter: async (config) => responseFor(config),
    },
  )

  assert.equal(response.data.ok, true)
  assert.equal(response.request, undefined)
  assert.equal(response.config.data, undefined)
  assert.equal(response.config.params, undefined)
  assert.equal(response.config.signal, undefined)
  assert.equal(headerNames(response.config.headers).includes("authorization"), false)
  assert.equal(headerNames(response.config.headers).includes("x-api-key"), false)

  let resolveSlowRequest
  let markAdapterStarted
  const adapterStarted = new Promise((resolve) => { markAdapterStarted = resolve })
  const oldGeneration = getSessionGeneration()
  const oldRequest = http.get("/slow", {
    adapter: (config) => {
      markAdapterStarted()
      return new Promise((resolve) => {
        resolveSlowRequest = () => resolve(responseFor(config, { owner: "old" }))
      })
    },
  })

  await adapterStarted
  setToken("token-b")
  resolveSlowRequest()

  await assert.rejects(oldRequest, (error) => isCanceledRequest(error))
  assert.equal(getToken(), "token-b")
  assert.ok(getSessionGeneration() > oldGeneration)

  let exposedError
  await assert.rejects(
    http.post("/failed", { password: "body-secret" }, {
      headers: { Authorization: "Bearer token-b" },
      adapter: async (config) => {
        const response = {
          config,
          data: { detail: "failed" },
          headers: {},
          request: { raw: "response request metadata" },
          status: 500,
          statusText: "Server Error",
        }
        const error = new axios.AxiosError("failed", "ERR_BAD_RESPONSE", config, { raw: "request metadata" }, response)
        throw error
      },
    }),
    (error) => {
      exposedError = error
      return true
    },
  )

  assert.equal(exposedError.request, undefined)
  assert.equal(exposedError.response.request, undefined)
  assert.equal(exposedError.config.data, undefined)
  assert.equal(headerNames(exposedError.config.headers).includes("authorization"), false)

  storedValues.set(TOKEN_STORAGE_KEY, "token-from-another-tab")
  const generationBeforeStorageEvent = getSessionGeneration()
  listeners.get("storage").forEach((handler) => handler({
    key: TOKEN_STORAGE_KEY,
    newValue: "token-from-another-tab",
  }))

  assert.equal(getToken(), "token-from-another-tab")
  assert.ok(getSessionGeneration() > generationBeforeStorageEvent)
  assert.equal(reloadCount, 1)
})

test("当前会话的非认证接口 401 会失效会话且不向页面暴露请求配置", async () => {
  setToken("expired-token")

  await assert.rejects(
    http.get("/api/private", {
      adapter: async (config) => {
        const response = {
          config,
          data: { detail: "登录已过期" },
          headers: {},
          request: { raw: "response request metadata" },
          status: 401,
          statusText: "Unauthorized",
        }
        throw new axios.AxiosError("unauthorized", "ERR_BAD_REQUEST", config, { raw: "request metadata" }, response)
      },
    }),
    (error) => isCanceledRequest(error) && error.config === undefined,
  )

  assert.equal(getToken(), "")
  assert.equal(storedValues.has(TOKEN_STORAGE_KEY), false)
  assert.equal(reloadCount, 1)
})
