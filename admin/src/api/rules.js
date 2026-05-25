import axios from "axios"

const API = "http://127.0.0.1:8000"

export function getStatus() {
  return axios.get(`${API}/api/status`)
}

export function getRules() {
  return axios.get(`${API}/api/rules`)
}

export function createRule(data) {
  return axios.post(`${API}/api/rules`, data)
}

export function updateRule(id, data) {
  return axios.put(`${API}/api/rules/${id}`, data)
}

export function removeRule(id) {
  return axios.delete(`${API}/api/rules/${id}`)
}
export function getLogs() {
  return axios.get(`${API}/api/logs`)
}
export function stopCloneTask(id) {
  return axios.post(`${API}/api/clone-tasks/${id}/stop`)
}
export function cloneRule(id, limit = 50, delay = 5) {
  return axios.post(
    `${API}/api/rules/${id}/clone?limit=${limit}&delay=${delay}`
  )
}

export function updateCloneTask(id, data) {
  return axios.put(`${API}/api/clone-tasks/${id}`, data)
}