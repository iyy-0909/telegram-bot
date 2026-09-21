import axios from "axios"
import { API } from "./base"

export function getAiCommonRules() {
  return axios.get(`${API}/api/ai/common-rules`)
}

export function updateAiCommonRules(data) {
  return axios.put(`${API}/api/ai/common-rules`, data)
}

export function getAiPrompts() {
  return axios.get(`${API}/api/ai/prompts`)
}

export function getAiPromptPresets() {
  return axios.get(`${API}/api/ai/prompts/presets`)
}

export function previewAiRewrite(data) {
  return axios.post(`${API}/api/ai/prompts/preview`, data, { timeout: 620000 })
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
