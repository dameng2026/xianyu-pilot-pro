import request from '../utils/request.js'
import { invalidateRequestCache, withRequestCache } from '../utils/requestCache.js'

const CURRENT_USER_CACHE_NAMESPACE = 'api:system/currentUser'

export const currentUser = (options = {}) => withRequestCache({
  keyParts: [CURRENT_USER_CACHE_NAMESPACE],
  ttlMs: options.force === true ? 0 : (options.cacheTtlMs ?? 15000),
  force: options.force === true,
  request: () => request.post('/system/currentUser', {}),
})
export const changePassword = data => request.post('/system/changePassword', data)
export const runtimeConfig = () => request.get('/system/runtime-config')
export const loginDevices = () => request.post('/loginDevice/list', {})
export const kickLoginDevice = tokenId => request.post('/loginDevice/kick', { token_id: tokenId })
export const invalidateCurrentUserCache = () => invalidateRequestCache(CURRENT_USER_CACHE_NAMESPACE)

// 获取数据保留策略公开信息（前台展示用）
// 返回 { retentionDays: number, chatMessageCleanupEnabled: boolean }
// 缓存 5 分钟，避免每次进入消息页都请求
export const getRetentionInfo = (options = {}) => withRequestCache({
  keyParts: ['api:system/retentionInfo'],
  ttlMs: options.force === true ? 0 : (options.cacheTtlMs ?? 5 * 60 * 1000),
  force: options.force === true,
  request: () => request.get('/system/retention-info'),
})
