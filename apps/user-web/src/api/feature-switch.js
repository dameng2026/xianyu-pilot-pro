import request from '../utils/request.js'
import { withRequestCache, invalidateRequestCache } from '../utils/requestCache.js'

const STATUS_CACHE_NAMESPACE = 'api:feature-switches/status'
const COMPARISON_CACHE_NAMESPACE = 'api:feature-switches/comparison'

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
 * 获取功能对比数据，用于个人中心「会员等级功能对比」表格展示。
 * 返回结构：[{ key, title, group, normal, vip, svp }, ...]
 *
 * 数据结构与后台管理端 /admin-api/system/feature-switches 一致，
 * 仅用于只读展示。失败降级：返回空数组，调用方应展示空状态。
 * 缓存策略：60 秒前端缓存（对比数据变化频率较低），可通过 options.force=true 强制刷新。
 */
export const getFeatureSwitchComparison = (options = {}) => withRequestCache({
  keyParts: [COMPARISON_CACHE_NAMESPACE],
  ttlMs: options.force === true ? 0 : (options.cacheTtlMs ?? 60000),
  force: options.force === true,
  request: () => request.get('/feature-switches/comparison').then(res => {
    const data = res?.data
    return Array.isArray(data) ? data : []
  })
})

/**
 * 失效功能开关状态缓存。
 * 用于登录/登出/套餐变更后强制刷新。
 */
export const invalidateFeatureSwitchCache = () => {
  invalidateRequestCache(STATUS_CACHE_NAMESPACE)
  invalidateRequestCache(COMPARISON_CACHE_NAMESPACE)
}
