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

export function getSearchBots(params = {}) {
  return axios.get(`${API}/api/search-bots`, { params })
}

export function createSearchBot(data) {
  return axios.post(`${API}/api/search-bots`, data)
}

export function updateSearchBot(id, data) {
  return axios.put(`${API}/api/search-bots/${id}`, data)
}

export function deleteSearchBot(id) {
  return axios.delete(`${API}/api/search-bots/${id}`)
}

export function checkSearchBot(id) {
  return axios.post(`${API}/api/search-bots/${id}/check`)
}

export function getSearchBotSubmissions(params = {}) {
  return axios.get(`${API}/api/search-bot-submissions`, { params })
}

export function createSearchBotSubmission(data) {
  return axios.post(`${API}/api/search-bot-submissions`, data)
}

export function updateSearchBotSubmission(id, data) {
  return axios.put(`${API}/api/search-bot-submissions/${id}`, data)
}

export function updateSearchBotSubmissionPermissions(id, data) {
  return axios.put(`${API}/api/search-bot-submissions/${id}/permissions`, data)
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
