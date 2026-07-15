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
