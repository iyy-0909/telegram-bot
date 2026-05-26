import axios from "axios"
import { API } from "./base"

export function getListenerTasks() {
  return axios.get(`${API}/api/listener-tasks`)
}

export function createListenerTask(data) {
  return axios.post(`${API}/api/listener-tasks`, data)
}

export function updateListenerTask(id, data) {
  return axios.put(`${API}/api/listener-tasks/${id}`, data)
}

export function deleteListenerTask(id) {
  return axios.delete(`${API}/api/listener-tasks/${id}`)
}

export function startListenerTask(id) {
  return axios.post(`${API}/api/listener-tasks/${id}/start`)
}

export function stopListenerTask(id) {
  return axios.post(`${API}/api/listener-tasks/${id}/stop`)
}

export function getListenerSendEvents(limit = 20) {
  return axios.get(`${API}/api/listener-send-events?limit=${limit}`)
}

export function checkListenerCatchup(id) {
  return axios.post(`${API}/api/listener-tasks/${id}/catchup-check`)
}
