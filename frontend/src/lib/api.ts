import axios from 'axios'
import { useAuthStore } from '@/stores/authStore'

export const api = axios.create({
  baseURL: '/api/v1',
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT token to every request
api.interceptors.request.use(config => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Auto-logout on 401
api.interceptors.response.use(
  res => res,
  err => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

// ── WebSocket helper ───────────────────────────────────────────────────────────

export function createScanWebSocket(
  scanId: string,
  token: string,
  onMessage: (data: Record<string, unknown>) => void,
  onClose?: () => void,
): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(
    `${protocol}://${window.location.host}/api/v1/ws/scan/${scanId}?token=${token}`
  )
  ws.onmessage = e => {
    try {
      onMessage(JSON.parse(e.data))
    } catch {}
  }
  ws.onclose = onClose ?? (() => {})
  return ws
}
