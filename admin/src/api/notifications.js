import axios from "axios"
import { API } from "./base"

export function getNotificationSettings() {
  return axios.get(`${API}/api/notification-settings`)
}

export function updateNotificationSetting(accountId, data) {
  return axios.put(`${API}/api/notification-settings/${accountId}`, data)
}

export function generateNotificationSetting(accountId) {
  return axios.post(`${API}/api/notification-settings/${accountId}/generate`)
}

export function testNotificationSetting(accountId) {
  return axios.post(`${API}/api/notification-settings/${accountId}/test`)
}
