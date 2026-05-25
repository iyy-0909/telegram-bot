import axios from "axios"

const API = "http://127.0.0.1:8000"

// 获取克隆任务列表
export function getCloneTasks() {
  return axios.get(`${API}/api/clone-tasks`)
}

export function getCloneSendEvents(limit = 20) {
  return axios.get(`${API}/api/clone-send-events?limit=${limit}`)
}

// 创建克隆任务
export function createCloneTask(data) {
  return axios.post(`${API}/api/clone-tasks`, data)
}

// 更新克隆任务
export function updateCloneTask(id, data) {
  return axios.put(`${API}/api/clone-tasks/${id}`, data)
}

// 删除克隆任务
export function deleteCloneTask(id) {
  return axios.delete(`${API}/api/clone-tasks/${id}`)
}

// 开始克隆
export function startCloneTask(id) {
  return axios.post(`${API}/api/clone-tasks/${id}/start`)
}

// 暂停克隆
export function pauseCloneTask(id) {
  return axios.post(`${API}/api/clone-tasks/${id}/pause`)
}

// 继续克隆
export function resumeCloneTask(id) {
  return axios.post(`${API}/api/clone-tasks/${id}/resume`)
}

// 重置进度
export function resetCloneTask(id) {
  return axios.post(`${API}/api/clone-tasks/${id}/reset`)
}
