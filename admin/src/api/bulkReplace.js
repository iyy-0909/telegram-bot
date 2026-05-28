import axios from "axios"
import { API } from "./base"

export function previewBulkReplace(data) {
  return axios.post(`${API}/api/bulk-replace/preview`, data)
}

export function executeBulkReplace(data) {
  return axios.post(`${API}/api/bulk-replace/execute`, data)
}
