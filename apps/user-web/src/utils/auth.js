import { clearSensitiveSessionData, createAuthSessionScope } from './privacySession.js'

export const TOKEN_KEY = 'xianyu_auth_token'
export const USERNAME_KEY = 'xianyu_username'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || ''
}

export function setAuth(token, username = '') {
  const previousScope = createAuthSessionScope(getToken(), getCachedUsername())
  const nextScope = createAuthSessionScope(token, username)
  if (previousScope !== nextScope) clearSensitiveSessionData()
  if (token) localStorage.setItem(TOKEN_KEY, token)
  if (username) localStorage.setItem(USERNAME_KEY, username)
}

export function clearAuth() {
  clearSensitiveSessionData()
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USERNAME_KEY)
}

export function getCachedUsername() {
  return localStorage.getItem(USERNAME_KEY) || ''
}

export function isAuthed() {
  return !!getToken()
}
