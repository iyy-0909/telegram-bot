import axios from "axios"
import { API } from "./base"

export function getFeatureCatalog() {
  return axios.get(`${API}/api/admin/features`)
}

export function getAdminUsers() {
  return axios.get(`${API}/api/admin/users`)
}

export function updateAdminUserAccess(id, data) {
  return axios.patch(`${API}/api/admin/users/${id}/access`, data)
}
