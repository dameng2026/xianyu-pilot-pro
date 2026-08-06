import request from '../utils/request.js'
import { clearAuth, getToken } from '../utils/auth.js'

export const getAuthCapabilities = () => request.get('/login/capabilities')
export const login = data => request.post('/login/login', data)
export const register = data => request.post('/login/register', data)
export const sendEmailCode = data => request.post('/login/sendEmailCode', data)
export const verifyResetCode = data => request.post('/login/verifyResetCode', data)
export const resetPassword = data => request.post('/login/resetPassword', data)
// Media cookies are issued for the page origin (Path=/uploads + SameSite=Strict
// + HttpOnly). They must be created from the same origin, otherwise the browser
// will not store a cross-origin Set-Cookie response.
export function createMediaSession() {
  const token = getToken()
  return fetch('/api/media/session', {
    method: 'POST',
    credentials: 'same-origin',
    cache: 'no-store',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    }
  }).then(async response => {
    if (!response.ok) {
      throw new Error(`Media session issuance failed: HTTP ${response.status}`)
    }
    const payload = await response.json().catch(() => null)
    if (!payload || payload?.data?.ready !== true) {
      throw new Error('Media session was not confirmed by the server')
    }
    return payload.data
  })
}
export async function logout() {
  try {
    return await request.post('/login/logout', {})
  } finally {
    clearAuth()
  }
}
