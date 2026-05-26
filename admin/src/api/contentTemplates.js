import axios from "axios"
import { API } from "./base"

export function getContentTemplates() {
  return axios.get(`${API}/api/content-templates`)
}

export function getContentTemplateRules() {
  return axios.get(`${API}/api/content-template-rules`)
}

export function createContentTemplateRule(data) {
  return axios.post(`${API}/api/content-template-rules`, data)
}

export function updateContentTemplateRule(id, data) {
  return axios.put(`${API}/api/content-template-rules/${id}`, data)
}

export function deleteContentTemplateRule(id) {
  return axios.delete(`${API}/api/content-template-rules/${id}`)
}

export function createContentTemplate(data) {
  return axios.post(`${API}/api/content-templates`, data)
}

export function updateContentTemplate(id, data) {
  return axios.put(`${API}/api/content-templates/${id}`, data)
}

export function deleteContentTemplate(id) {
  return axios.delete(`${API}/api/content-templates/${id}`)
}
