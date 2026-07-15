import request from '../utils/request.js'
import { clearAuth } from '../utils/auth.js'

export const getAuthCapabilities = () => request.get('/login/capabilities')
export const login = data => request.post('/login/login', data)
export const register = data => request.post('/login/register', data)
export const sendEmailCode = data => request.post('/login/sendEmailCode', data)
export const verifyResetCode = data => request.post('/login/verifyResetCode', data)
export const resetPassword = data => request.post('/login/resetPassword', data)
export const createMediaSession = () => request.post('/media/session', {})
export async function logout() {
  try {
    return await request.post('/login/logout', {})
  } finally {
    clearAuth()
  }
}
