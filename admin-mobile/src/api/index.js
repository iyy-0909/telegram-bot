import { http } from "./client"

export function loginAdmin(password) {
  return http.post("/api/auth/login", { password })
}

export function getStatus() {
  return http.get("/api/status")
}

export function getRuntimeDashboard() {
  return http.get("/api/runtime/dashboard")
}

export function getSendSettings() {
  return http.get("/api/settings/send")
}

export function updateSendSettings(data) {
  return http.put("/api/settings/send", data)
}

export function getListenerTasks() {
  return http.get("/api/listener-tasks")
}

export function createListenerTask(data) {
  return http.post("/api/listener-tasks", data)
}

export function startListenerTask(id) {
  return http.post(`/api/listener-tasks/${id}/start`)
}

export function stopListenerTask(id) {
  return http.post(`/api/listener-tasks/${id}/stop`)
}

export function updateListenerTask(id, data) {
  return http.put(`/api/listener-tasks/${id}`, data)
}

export function deleteListenerTask(id) {
  return http.delete(`/api/listener-tasks/${id}`)
}

export function checkListenerCatchup(id) {
  return http.post(`/api/listener-tasks/${id}/catchup-check`)
}

export function catchupListenerTask(id, data = {}) {
  return http.post(`/api/listener-tasks/${id}/catchup-latest`, data)
}

export function getListenerSendEvents(limit = 200) {
  return http.get(`/api/listener-send-events?limit=${limit}`)
}

export function getCloneTasks() {
  return http.get("/api/clone-tasks")
}

export function createCloneTask(data) {
  return http.post("/api/clone-tasks", data)
}

export function startCloneTask(id) {
  return http.post(`/api/clone-tasks/${id}/start`)
}

export function pauseCloneTask(id) {
  return http.post(`/api/clone-tasks/${id}/pause`)
}

export function resumeCloneTask(id) {
  return http.post(`/api/clone-tasks/${id}/resume`)
}

export function stopCloneTask(id) {
  return http.post(`/api/clone-tasks/${id}/stop`)
}

export function updateCloneTask(id, data) {
  return http.put(`/api/clone-tasks/${id}`, data)
}

export function deleteCloneTask(id) {
  return http.delete(`/api/clone-tasks/${id}`)
}

export function getCloneSendEvents(limit = 200) {
  return http.get(`/api/clone-send-events?limit=${limit}`)
}

export function getBots() {
  return http.get("/api/bots")
}

export function createBot(data) {
  return http.post("/api/bots", data)
}

export function updateBot(id, data) {
  return http.put(`/api/bots/${id}`, data)
}

export function deleteBot(id) {
  return http.delete(`/api/bots/${id}`)
}

export function testBot(id) {
  return http.get(`/api/bots/${id}/test`)
}

export function getMyChannels(params = {}) {
  return http.get("/api/my-channels", { params })
}

export function createMyChannel(data) {
  return http.post("/api/my-channels", data)
}

export function updateMyChannel(id, data) {
  return http.put(`/api/my-channels/${id}`, data)
}

export function deleteMyChannel(id) {
  return http.delete(`/api/my-channels/${id}`)
}

export function checkMyChannel(id) {
  return http.post(`/api/my-channels/${id}/check`)
}

export function batchCheckMyChannels() {
  return http.post("/api/my-channels/batch-check")
}

export function getSupportBots() {
  return http.get("/api/support/bots")
}

export function createSupportBot(data) {
  return http.post("/api/support/bots", data)
}

export function updateSupportBot(id, data) {
  return http.put(`/api/support/bots/${id}`, data)
}

export function deleteSupportBot(id) {
  return http.delete(`/api/support/bots/${id}`)
}

export function testSupportBotItem(id) {
  return http.post(`/api/support/bots/${id}/test`)
}

export function uploadSupportMedia(file) {
  const formData = new FormData()
  formData.append("file", file)
  return http.post("/api/support/media/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  })
}

export function getContentTemplates() {
  return http.get("/api/content-templates")
}

export function getContentTemplateRules() {
  return http.get("/api/content-template-rules")
}

export function createContentTemplateRule(data) {
  return http.post("/api/content-template-rules", data)
}

export function updateContentTemplateRule(id, data) {
  return http.put(`/api/content-template-rules/${id}`, data)
}

export function deleteContentTemplateRule(id) {
  return http.delete(`/api/content-template-rules/${id}`)
}

export function createContentTemplate(data) {
  return http.post("/api/content-templates", data)
}

export function updateContentTemplate(id, data) {
  return http.put(`/api/content-templates/${id}`, data)
}

export function deleteContentTemplate(id) {
  return http.delete(`/api/content-templates/${id}`)
}

export function getAccounts() {
  return http.get("/api/accounts")
}

export function createAccount(data) {
  return http.post("/api/accounts", data)
}

export function updateAccount(id, data) {
  return http.put(`/api/accounts/${id}`, data)
}

export function deleteAccount(id) {
  return http.delete(`/api/accounts/${id}`)
}

export function startAccountLogin(data) {
  return http.post("/api/accounts/login/start", data)
}

export function verifyAccountLogin(data) {
  return http.post("/api/accounts/login/verify", data)
}
