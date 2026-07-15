import request from '@/utils/http'
import { requireRecordPayload } from '@/utils/api-payload'
import { containsAsciiControlCharacter } from '@/utils/text-security'

export function fetchLogin(params: Api.Auth.LoginParams) {
  return request.post<Api.Auth.LoginResponse>({
    url: '/auth/login',
    params,
    // The login view owns the single, contextual failure notification.
    showErrorMessage: false
  }).then((value) => {
    const payload = requireRecordPayload<Record<string, unknown>>(value, '登录')
    if (
      typeof payload.token !== 'string'
      || !payload.token.trim()
      || payload.token.length > 8192
      || containsAsciiControlCharacter(payload.token)
      || (payload.refreshToken !== undefined && typeof payload.refreshToken !== 'string')
    ) {
      throw new Error('登录响应格式异常，请稍后重试')
    }
    return payload as unknown as Api.Auth.LoginResponse
  })
}

let mediaSessionRequest: Promise<Record<string, unknown>> | null = null

export function createAdminMediaSession() {
  if (!mediaSessionRequest) {
    mediaSessionRequest = request.post<Record<string, unknown>>({
      url: '/media/session',
      // Callers render a single state-specific message; suppress the generic toast.
      showErrorMessage: false
    }).then((value) => {
      const payload = requireRecordPayload<Record<string, unknown>>(value, '私有媒体会话')
      if (payload.ready !== true) {
        throw new Error('私有媒体会话未被服务端确认')
      }
      return payload
    }).finally(() => {
      mediaSessionRequest = null
    })
  }
  return mediaSessionRequest
}

let logoutRequest: Promise<void> | null = null

/** Revoke the authoritative admin session before local credentials disappear. */
export function revokeAdminSession(token: string) {
  if (!token.trim()) return Promise.resolve()
  if (!logoutRequest) {
    logoutRequest = fetch('/admin-api/auth/logout', {
      method: 'POST',
      credentials: 'same-origin',
      cache: 'no-store',
      keepalive: true,
      headers: { Authorization: `Bearer ${token}` }
    }).then(async (response) => {
      // A 401 means the presented token is already unusable, so revocation is satisfied.
      if (response.status === 401) return
      if (!response.ok) throw new Error('服务端会话撤销失败')
      const payload = await response.json().catch(() => null)
      if (!payload || payload.code !== 200) throw new Error('服务端会话撤销未确认')
    }).finally(() => {
      logoutRequest = null
    })
  }
  return logoutRequest
}

/** 用户信息缓存 5 分钟，避免路由守卫每次刷新都重复请求 */
export function fetchGetUserInfo() {
  return request.get<Api.Auth.UserInfo>({
    url: '/user/info',
    cacheTtl: 5 * 60 * 1000
  }).then((value) => {
    const payload = requireRecordPayload<Record<string, unknown>>(value, '用户信息')
    if (
      !Number.isSafeInteger(Number(payload.userId))
      || Number(payload.userId) <= 0
      || typeof payload.userName !== 'string'
      || !Array.isArray(payload.roles)
      || !payload.roles.every(role => typeof role === 'string')
      || !Array.isArray(payload.buttons)
      || !payload.buttons.every(button => typeof button === 'string')
    ) {
      throw new Error('用户信息响应格式异常，请重新登录')
    }
    return payload as unknown as Api.Auth.UserInfo
  })
}

/**
 * 管理员修改自身登录密码。
 * 修改成功后既有令牌全部失效（含当前会话），调用方需引导用户重新登录。
 */
export function changeAdminPassword(oldPassword: string, newPassword: string) {
  return request.post<void>({
    url: '/auth/change-password',
    data: { oldPassword, newPassword },
    // 成功后由调用方弹出模态框引导重新登录，避免重复 toast
    showSuccessMessage: false
  })
}
