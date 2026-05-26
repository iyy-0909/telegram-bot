import axios from "axios"
import { API } from "./base"

export function getSupportConversations(params = {}) {
  return axios.get(`${API}/api/support/conversations`, { params })
}

export function getSupportCustomers(params = {}) {
  return axios.get(`${API}/api/support/customers`, { params })
}

export function getSupportCustomer(id) {
  return axios.get(`${API}/api/support/customers/${id}`)
}

export function getSupportConversation(id) {
  return axios.get(`${API}/api/support/conversations/${id}`)
}

export function getSupportMessages(params = {}) {
  return axios.get(`${API}/api/support/messages`, { params })
}

export function getSupportConversationMessages(id, params = {}) {
  return axios.get(`${API}/api/support/conversations/${id}/messages`, { params })
}

export function replySupportConversation(id, data) {
  return axios.post(`${API}/api/support/conversations/${id}/reply`, data)
}

export function closeSupportConversation(id) {
  return axios.post(`${API}/api/support/conversations/${id}/close`)
}

export function blockSupportCustomer(id) {
  return axios.post(`${API}/api/support/customers/${id}/block`)
}

export function unblockSupportCustomer(id) {
  return axios.post(`${API}/api/support/customers/${id}/unblock`)
}

export function getSupportQuickReplies(params = {}) {
  return axios.get(`${API}/api/support/quick-replies`, { params })
}

export function createSupportQuickReply(data) {
  return axios.post(`${API}/api/support/quick-replies`, data)
}

export function updateSupportQuickReply(id, data) {
  return axios.put(`${API}/api/support/quick-replies/${id}`, data)
}

export function deleteSupportQuickReply(id) {
  return axios.delete(`${API}/api/support/quick-replies/${id}`)
}

export function getSupportSettings() {
  return axios.get(`${API}/api/support/settings`)
}

export function updateSupportSettings(data) {
  return axios.put(`${API}/api/support/settings`, data)
}

export function getSupportBots() {
  return axios.get(`${API}/api/support/bots`)
}

export function createSupportBot(data) {
  return axios.post(`${API}/api/support/bots`, data)
}

export function updateSupportBot(id, data) {
  return axios.put(`${API}/api/support/bots/${id}`, data)
}

export function deleteSupportBot(id) {
  return axios.delete(`${API}/api/support/bots/${id}`)
}

export function testSupportBotItem(id) {
  return axios.post(`${API}/api/support/bots/${id}/test`)
}

export function testSupportBot() {
  return axios.post(`${API}/api/support/bot/test`)
}

export function getRecentSupportUpdates(params = {}) {
  return axios.get(`${API}/api/support/updates/recent`, { params })
}

export function getSupportTags() {
  return axios.get(`${API}/api/support/tags`)
}

export function createSupportTag(data) {
  return axios.post(`${API}/api/support/tags`, data)
}

export function updateSupportCustomerTags(customerId, tagIds) {
  return axios.put(`${API}/api/support/customers/${customerId}/tags`, {
    tag_ids: tagIds,
  })
}
