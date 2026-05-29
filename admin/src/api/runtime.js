import axios from "axios"
import { API } from "./base"

export function getRuntimeDashboard() {
  return axios.get(`${API}/api/runtime/dashboard`)
}
