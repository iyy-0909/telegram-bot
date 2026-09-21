import assert from "node:assert/strict"
import test from "node:test"
import axios from "axios"

let moduleSequence = 0

async function createHarness() {
  const storedValues = new Map()
  const listeners = new Map()
  const dispatchedEvents = []
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
      dispatchedEvents.push(event)
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

  moduleSequence += 1
  const session = await import(`../src/authSession.js?test=${moduleSequence}`)
  const client = axios.create()
  session.installAuthSessionInterceptors(client)

  return {
    client,
    dispatchedEvents,
    listeners,
    reloadCount: () => reloadCount,
    session,
    storedValues,
  }
}

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

test("Token 切换取消全部旧请求且旧 401 不能清除新 Token", { concurrency: false }, async () => {
  const { client, session } = await createHarness()
  session.replaceAuthToken("token-a")

  const response = await client.post(
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

  const upstreamController = new AbortController()
  let boundSignal
  let rejectOldRequest
  let markAdapterStarted
  const adapterStarted = new Promise((resolve) => { markAdapterStarted = resolve })
  const oldRequest = client.get("/api/private", {
    signal: upstreamController.signal,
    adapter: (config) => {
      boundSignal = config.signal
      markAdapterStarted()
      return new Promise((resolve, reject) => {
        rejectOldRequest = () => {
          const unauthorized = {
            config,
            data: { detail: "old session unauthorized" },
            headers: {},
            request: { raw: "old response request" },
            status: 401,
            statusText: "Unauthorized",
          }
          reject(new axios.AxiosError("unauthorized", "ERR_BAD_REQUEST", config, { raw: "old request" }, unauthorized))
        }
      })
    },
  })

  await adapterStarted
  assert.notEqual(boundSignal, upstreamController.signal)
  session.replaceAuthToken("token-b")
  assert.equal(boundSignal.aborted, true)
  assert.equal(upstreamController.signal.aborted, false)
  rejectOldRequest()

  await assert.rejects(oldRequest, (error) => session.isCanceledAuthRequest(error))
  assert.equal(session.getAuthToken(), "token-b")
})

test("异常对象脱敏、当前 401 失效和 storage 跨标签刷新", { concurrency: false }, async () => {
  const harness = await createHarness()
  const { client, dispatchedEvents, listeners, session, storedValues } = harness
  session.replaceAuthToken("active-token")

  let exposedError
  await assert.rejects(
    client.post("/failed", { password: "body-secret" }, {
      headers: { Authorization: "Bearer active-token" },
      adapter: async (config) => {
        const response = {
          config,
          data: { detail: "failed" },
          headers: {},
          request: { raw: "response request metadata" },
          status: 500,
          statusText: "Server Error",
        }
        throw new axios.AxiosError("failed", "ERR_BAD_RESPONSE", config, { raw: "request metadata" }, response)
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

  await assert.rejects(
    client.get("/api/private", {
      adapter: async (config) => {
        const response = {
          config,
          data: { detail: "登录已过期" },
          headers: {},
          status: 401,
          statusText: "Unauthorized",
        }
        throw new axios.AxiosError("unauthorized", "ERR_BAD_REQUEST", config, null, response)
      },
    }),
    (error) => session.isCanceledAuthRequest(error) && error.config === undefined,
  )

  assert.equal(session.getAuthToken(), "")
  assert.equal(storedValues.has(session.AUTH_TOKEN_STORAGE_KEY), false)
  assert.equal(harness.reloadCount(), 1)
  assert.equal(
    dispatchedEvents.some((event) => event.type === session.AUTH_SESSION_CHANGED_EVENT && event.detail?.authenticated === false),
    true,
  )

  const storageHarness = await createHarness()
  storageHarness.session.installAuthStorageListener()
  storageHarness.session.replaceAuthToken("first-tab-token")
  let resolveStorageRequest
  let markStorageRequestStarted
  let storageBoundSignal
  const storageRequestStarted = new Promise((resolve) => { markStorageRequestStarted = resolve })
  const storageRequest = storageHarness.client.get("/slow-storage-request", {
    adapter: (config) => {
      storageBoundSignal = config.signal
      markStorageRequestStarted()
      return new Promise((resolve) => {
        resolveStorageRequest = () => resolve(responseFor(config, { owner: "first-tab" }))
      })
    },
  })
  await storageRequestStarted

  storageHarness.storedValues.set(storageHarness.session.AUTH_TOKEN_STORAGE_KEY, "other-tab-token")
  storageHarness.listeners.get("storage").forEach((handler) => handler({
    key: storageHarness.session.AUTH_TOKEN_STORAGE_KEY,
    oldValue: "first-tab-token",
    newValue: "other-tab-token",
  }))
  assert.equal(storageBoundSignal.aborted, true)
  resolveStorageRequest()
  await assert.rejects(storageRequest, (error) => storageHarness.session.isCanceledAuthRequest(error))

  assert.equal(storageHarness.session.getAuthToken(), "other-tab-token")
  assert.equal(storageHarness.reloadCount(), 1)
  assert.equal(
    storageHarness.dispatchedEvents.some((event) => (
      event.type === storageHarness.session.AUTH_SESSION_CHANGED_EVENT
      && event.detail?.authenticated === true
    )),
    true,
  )
})
