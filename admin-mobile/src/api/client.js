import axios from "axios"

export const API_BASE = import.meta.env.VITE_API_BASE || ""
export const TOKEN_STORAGE_KEY = "admin_token"

export const http = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
})

http.interceptors.request.use((config) => {
  const token = window.localStorage.getItem(TOKEN_STORAGE_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 &&
      !error.config?.url?.includes("/api/auth/")
    ) {
      window.localStorage.removeItem(TOKEN_STORAGE_KEY)
      window.location.reload()
    }
    return Promise.reject(error)
  },
)

export function setToken(token) {
  if (token) {
    window.localStorage.setItem(TOKEN_STORAGE_KEY, token)
  } else {
    window.localStorage.removeItem(TOKEN_STORAGE_KEY)
  }
}

export function getToken() {
  return window.localStorage.getItem(TOKEN_STORAGE_KEY) || ""
}

export function getErrorMessage(error, fallback = "请求失败") {
  const data = error?.response?.data
  if (typeof data?.detail === "string") return data.detail
  if (typeof data?.message === "string") return data.message
  if (typeof data?.error === "string") return data.error
  if (typeof error?.message === "string") return error.message
  return fallback
}
