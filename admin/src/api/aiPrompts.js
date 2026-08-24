import axios from "axios"
import { API } from "./base"

export function getAiPrompts() {
  return axios.get(`${API}/api/ai/prompts`)
}

export function createAiPrompt(data) {
  return axios.post(`${API}/api/ai/prompts`, data)
}

export function updateAiPrompt(id, data) {
  return axios.put(`${API}/api/ai/prompts/${id}`, data)
}

export function setDefaultAiPrompt(id) {
  return axios.post(`${API}/api/ai/prompts/${id}/default`)
}

export function deleteAiPrompt(id) {
  return axios.delete(`${API}/api/ai/prompts/${id}`)
}
