import axios from "axios"
import { API } from "./base"

export function loginAdmin(password) {
  return axios.post(`${API}/api/auth/login`, { password })
}
