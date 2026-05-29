import axios from "axios"
import { API } from "./base"

export function getAccounts() {
  return axios.get(`${API}/api/accounts`)
}

export function createAccount(data) {
  return axios.post(`${API}/api/accounts`, data)
}

export function startAccountLogin(data) {
  return axios.post(`${API}/api/accounts/login/start`, data)
}

export function verifyAccountLogin(data) {
  return axios.post(`${API}/api/accounts/login/verify`, data)
}

export function updateAccount(id, data) {
  return axios.put(`${API}/api/accounts/${id}`, data)
}

export function removeAccount(id) {
  return axios.delete(`${API}/api/accounts/${id}`)
}
