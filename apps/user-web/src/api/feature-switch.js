import request from '../utils/request.js'
import { withRequestCache, invalidateRequestCache } from '../utils/requestCache.js'

const STATUS_CACHE_NAMESPACE = 'api:feature-switches/status'

/**
 * 获取当前用户的功能开关状态。
 * 返回结构：{ level, accessible: {pageKey: true}, blocked: {pageKey: {reason, required_level}} }
 *
 * 失败降级：调用方应捕获异常并默认放行，避免后端故障锁死所有页面。
 * 缓存策略：30 秒前端缓存，可通过 options.force=true 强制刷新。
 */
export const getFeatureSwitchStatus = (options = {}) => withRequestCache({
  keyParts: [STATUS_CACHE_NAMESPACE],
  ttlMs: options.force === true ? 0 : (options.cacheTtlMs ?? 30000),
  force: options.force === true,
  request: () => request.get('/feature-switches/status').then(res => res.data)
})

/**
 * 失效功能开关状态缓存。
 * 用于登录/登出/套餐变更后强制刷新。
 */
export const invalidateFeatureSwitchCache = () => invalidateRequestCache(STATUS_CACHE_NAMESPACE)
