import axios from "axios"

const API = "http://127.0.0.1:8000"

export function getAccounts() {
  return axios.get(`${API}/api/accounts`)
}

export function createAccount(data) {
  return axios.post(`${API}/api/accounts`, data)
}

export function updateAccount(id, data) {
  return axios.put(`${API}/api/accounts/${id}`, data)
}

export function removeAccount(id) {
  return axios.delete(`${API}/api/accounts/${id}`)
}