import axios from "axios"
import { API } from "./base"


// =========================
// Bot 账号管理
// =========================

export function getBots() {
  return axios.get(`${API}/api/bots`)
}

export function createBot(data) {
  return axios.post(`${API}/api/bots`, data)
}

export function updateBot(id, data) {
  return axios.put(`${API}/api/bots/${id}`, data)
}

export function deleteBot(id) {
  return axios.delete(`${API}/api/bots/${id}`)
}


// =========================
// 目标频道绑定 Bot
// =========================

export function getBotBindings() {
  return axios.get(`${API}/api/bot-bindings`)
}

export function createBotBinding(data) {
  return axios.post(`${API}/api/bot-bindings`, data)
}

export function updateBotBinding(id, data) {
  return axios.put(`${API}/api/bot-bindings/${id}`, data)
}

export function deleteBotBinding(id) {
  return axios.delete(`${API}/api/bot-bindings/${id}`)
}

export function testBot(id) {
  return axios.get(`${API}/api/bots/${id}/test`)
}

export function sendBotTest(id, data) {
  return axios.post(`${API}/api/bots/${id}/send-test`, data)
}

export function getBotProfile(id) {
  return axios.get(`${API}/api/bots/${id}/profile`)
}

export function updateBotProfile(id, data) {
  return axios.put(`${API}/api/bots/${id}/profile`, data)
}

export function uploadBotProfilePhoto(id, file) {
  const formData = new FormData()
  formData.append("photo", file)
  return axios.post(`${API}/api/bots/${id}/profile/photo`, formData)
}

export function removeBotProfilePhoto(id) {
  return axios.delete(`${API}/api/bots/${id}/profile/photo`)
}

export function getBotProfilePhoto(id) {
  return axios.get(`${API}/api/bots/${id}/profile/photo`, {
    responseType: "blob",
  })
}

export function getBotDescriptionPhoto(id) {
  return axios.get(`${API}/api/bots/${id}/profile/description-photo`, {
    responseType: "blob",
  })
}

export function uploadBotDescriptionPhoto(id, file) {
  const formData = new FormData()
  formData.append("photo", file)
  return axios.post(`${API}/api/bots/${id}/profile/description-photo`, formData)
}

export function removeBotDescriptionPhoto(id) {
  return axios.delete(`${API}/api/bots/${id}/profile/description-photo`)
}

export function updateBotCommands(id, commands) {
  return axios.put(`${API}/api/bots/${id}/profile/commands`, { commands })
}

export function updateBotPrivacyPolicy(id, url) {
  return axios.put(`${API}/api/bots/${id}/profile/privacy-policy`, { url })
}

export function removeBotPrivacyPolicy(id) {
  return axios.delete(`${API}/api/bots/${id}/profile/privacy-policy`)
}
