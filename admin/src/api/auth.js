import axios from "axios"
import { API } from "./base"

export function loginAdmin(password, username = "") {
  return axios.post(`${API}/api/auth/login`, { username, password })
}

export function getCaptcha() {
  return axios.get(`${API}/api/auth/captcha`)
}

export function registerUser(data) {
  return axios.post(`${API}/api/auth/register`, data)
}

export function getCurrentUser() {
  return axios.get(`${API}/api/auth/me`)
}

export function logoutUser() {
  return axios.post(`${API}/api/auth/logout`)
}
