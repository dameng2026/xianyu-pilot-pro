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
 * 获取当前用户店铺数量限制状态。
 * 返回结构：{ planCode, level, levelName, limit, unlimited, accountCount }
 * limit=0 表示无限制；用于「添加账号」前校验与会员中心/个人中心展示店铺数量。
 * 失败降级：返回 { unlimited: true }，避免后端故障锁死添加账号操作（后端仍有最终校验）。
 */
export const getStoreLimitStatus = async () => {
  try {
    const res = await request.get('/feature-switches/store-limit')
    const data = res?.data
    if (data && typeof data === 'object') return data
    return { unlimited: true }
  } catch {
    return { unlimited: true }
  }
}

/**
 * 失效功能开关状态缓存。
 * 用于登录/登出/套餐变更后强制刷新。
 */
export const invalidateFeatureSwitchCache = () => {
  invalidateRequestCache(STATUS_CACHE_NAMESPACE)
  invalidateRequestCache(COMPARISON_CACHE_NAMESPACE)
}

/**
 * 查询当前用户对指定功能的拦截信息。
 * 返回：
 *   { allowed: true, preview: false }  → 允许使用（正常模式）
 *   { allowed: true, preview: true, reason_text }  → 允许进入但预览模式（不可执行业务操作）
 *   { allowed: false, preview: false, reason, required_level, reason_text? }  → 被拦截
 *
 * 内部复用 getFeatureSwitchStatus 缓存，避免重复请求。
 * 失败降级：返回 { allowed: true, preview: false }，避免后端故障锁死用户操作。
 *
 * @param {string} featureKey 功能 key（如 'manual-slider-solve'）
 * @param {object} options { force?: boolean }
 */
export const getFeatureStatus = async (featureKey, options = {}) => {
  try {
    const status = await getFeatureSwitchStatus(options)
    const accessible = status?.accessible || {}
    const blocked = status?.blocked || {}
    const preview = status?.preview || {}
    if (accessible[featureKey] === true) {
      const previewInfo = preview[featureKey]
      return {
        allowed: true,
        preview: !!previewInfo,
        reason_text: previewInfo?.reason_text || ''
      }
    }
    const info = blocked[featureKey]
    if (!info) {
      // 既不在 accessible 也不在 blocked，视为允许（向后兼容）
      return { allowed: true, preview: false }
    }
    return {
      allowed: false,
      preview: false,
      reason: info.reason || 'disabled',
      required_level: info.required_level || 'vip',
      reason_text: info.reason_text || '',
    }
  } catch {
    // 后端故障降级放行
    return { allowed: true, preview: false }
  }
}
