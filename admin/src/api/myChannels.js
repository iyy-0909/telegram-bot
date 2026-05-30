import axios from "axios"
import { API } from "./base"

export function getMyChannels(params = {}) {
  return axios.get(`${API}/api/my-channels`, { params })
}

export function createMyChannel(data) {
  return axios.post(`${API}/api/my-channels`, data)
}

export function updateMyChannel(id, data) {
  return axios.put(`${API}/api/my-channels/${id}`, data)
}

export function deleteMyChannel(id) {
  return axios.delete(`${API}/api/my-channels/${id}`)
}

export function checkMyChannel(id) {
  return axios.post(`${API}/api/my-channels/${id}/check`)
}

export function batchCheckMyChannels() {
  return axios.post(`${API}/api/my-channels/batch-check`)
}

export function getCloneChannels(params = {}) {
  return axios.get(`${API}/api/clone-channels`, { params })
}

export function createCloneChannel(data) {
  return axios.post(`${API}/api/clone-channels`, data)
}

export function updateCloneChannel(id, data) {
  return axios.put(`${API}/api/clone-channels/${id}`, data)
}

export function deleteCloneChannel(id) {
  return axios.delete(`${API}/api/clone-channels/${id}`)
}
