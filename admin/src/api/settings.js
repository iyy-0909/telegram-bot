import axios from "axios"

const API = "http://127.0.0.1:8000"

export function getSendSettings() {
  return axios.get(`${API}/api/settings/send`)
}

export function updateSendSettings(data) {
  return axios.put(`${API}/api/settings/send`, data)
}
