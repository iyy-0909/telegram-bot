import axios from "axios"
import { API } from "./base"

export function getControlAlerts(params = {}) {
  return axios.get(`${API}/api/control-alerts`, { params })
}

export function acknowledgeControlAlert(alertId) {
  return axios.post(`${API}/api/control-alerts/${alertId}/acknowledge`)
}

export function acknowledgeAllControlAlerts() {
  return axios.post(`${API}/api/control-alerts/acknowledge-all`)
}
