import request from '../utils/request'
import { withRequestCache } from '../utils/requestCache.js'
import { withPersistentCache, clearPersistentCache } from '../utils/persistentCache.js'

const NAVIGATION_HOME_CACHE_NAMESPACE = 'api:navigation/home'
export const NAVIGATION_HOME_PERSISTENT_KEY = 'navigation_home'

export function getNavigationHome(options = {}) {
  const force = options.force === true
  const limit = options.limit ?? 5

  // force 刷新时清除持久化缓存，走完整网络请求
  if (force) {
    clearPersistentCache(NAVIGATION_HOME_PERSISTENT_KEY)
  }

  // 先走持久化缓存（stale-while-revalidate），内部网络请求再用内存缓存去重
  return withPersistentCache({
    namespace: NAVIGATION_HOME_PERSISTENT_KEY,
    freshMs: force ? 0 : (options.freshMs ?? 120_000),   // 新鲜期 2 分钟
    staleMs: force ? 0 : (options.staleMs ?? 600_000),   // 过期可用期 10 分钟
    request: () => withRequestCache({
      keyParts: [NAVIGATION_HOME_CACHE_NAMESPACE, { limit }],
      ttlMs: force ? 0 : (options.cacheTtlMs ?? 10_000),
      force,
      request: () => request({
        url: '/navigation/home',
        method: 'get',
        params: { limit }
      })
    })
  })
}

export function getNavigationOverview(params) {
  return request({
    url: '/navigation/overview',
    method: 'get',
    params
  })
}

export function getNavigationNotifications(params) {
  return request({
    url: '/navigation/notifications',
    method: 'get',
    params
  })
}

export function getNavigationSystemStatus(params) {
  return request({
    url: '/navigation/system-status',
    method: 'get',
    params
  })
}
