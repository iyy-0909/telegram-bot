import axios from "axios"
import { API } from "./base"

export function getSendSettings() {
  return axios.get(`${API}/api/settings/send`)
}

export function updateSendSettings(data) {
  return axios.put(`${API}/api/settings/send`, data)
}

export function getAiSettings() {
  return axios.get(`${API}/api/settings/ai`)
}

export function updateAiSettings(data) {
  return axios.put(`${API}/api/settings/ai`, data)
}
