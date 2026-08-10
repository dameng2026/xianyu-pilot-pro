import request from '../utils/request.js'
import { invalidateRequestCache, withRequestCache } from '../utils/requestCache.js'

const AUTO_REPLY_SCOPE_NAMESPACE = 'api:auto-reply-scope'
const SCOPE_STATUS_KEY = 'api:auto-reply-scope/status'
const SCOPE_PRODUCTS_KEY = 'api:auto-reply-scope/products'
const SCOPE_CACHE_TTL_MS = 10000

function invalidateScopeCache() {
  invalidateRequestCache(AUTO_REPLY_SCOPE_NAMESPACE)
}

/**
 * 查询商品列表及每个商品的 effective auto_reply 状态。
 * @param {number} [accountId] 账号ID，不传则返回全部账号商品
 * @param {Object} [options] { force?: boolean, cacheTtlMs?: number }
 */
export function getAutoReplyScopeProducts(accountId, options = {}) {
  const force = options.force === true
  const params = {}
  if (accountId != null) params.accountId = accountId
  return withRequestCache({
    keyParts: [SCOPE_PRODUCTS_KEY, params],
    ttlMs: force ? 0 : (options.cacheTtlMs ?? SCOPE_CACHE_TTL_MS),
    force,
    request: () => request.get('/auto-reply-scope/products', { params }),
  })
}

/**
 * 更新单个商品的 auto_reply_enabled。
 * @param {number} itemId 商品ID
 * @param {boolean} enabled 启用状态
 */
export function updateProductAutoReplyScope(itemIdOrPayload, enabled) {
  const payload = typeof itemIdOrPayload === 'object' && itemIdOrPayload !== null
    ? itemIdOrPayload
    : { itemId: itemIdOrPayload, enabled }
  return request.post('/auto-reply-scope/product', payload).then(result => {
    invalidateScopeCache()
    return result
  })
}

/**
 * 更新账号级 auto_reply 启用状态。
 * @param {number} accountId 账号ID
 * @param {boolean} enabled 启用状态
 */
export function updateAccountAutoReplyScope(accountId, enabled) {
  return request.post('/auto-reply-scope/account', { accountId, enabled }).then(result => {
    invalidateScopeCache()
    return result
  })
}

/**
 * 批量更新商品或账号的 auto_reply 状态。
 * @param {Object} body - {itemIds: [], enabled} 或 {accountIds: [], enabled}
 */
export function batchUpdateAutoReplyScope(body) {
  return request.post('/auto-reply-scope/batch', body).then(result => {
    invalidateScopeCache()
    return result
  })
}

/**
 * 查询全局开关和账号级作用域配置。
 * @param {number} [accountId] 账号ID
 * @param {Object} [options] { force?: boolean, cacheTtlMs?: number }
 */
export function getAutoReplyScopeStatus(accountId, options = {}) {
  const force = options.force === true
  const params = {}
  if (accountId != null) params.accountId = accountId
  return withRequestCache({
    keyParts: [SCOPE_STATUS_KEY, params],
    ttlMs: force ? 0 : (options.cacheTtlMs ?? SCOPE_CACHE_TTL_MS),
    force,
    request: () => request.get('/auto-reply-scope/status', { params }),
  })
}

/**
 * 会话级自动回复手动开关。
 * 用户在网站点击按钮开启/关闭时调用。
 * - enabled=true：手动开启（清除暂停 + 清除手动关闭标记）
 * - enabled=false：手动关闭（设置暂停 + 设置手动关闭标记，禁止自动恢复）
 * @param {Object} payload - { accountId, sid?, peerUserId?, enabled }
 */
export function toggleConversationAutoReply(payload) {
  return request.post('/auto-reply-scope/conversation-toggle', payload)
}

/**
 * 查询会话级自动回复状态。
 * 返回字段：
 *   autoReplyPaused / autoReplyManualDisabled / lastManualReplyAt /
 *   lastAutoReplyAt / effectiveEnabled / runningEnabled / pausedReason
 * @param {Object} params - { accountId, sid?, peerUserId? }
 */
export function getConversationAutoReplyStatus(params) {
  return request.get('/auto-reply-scope/conversation-status', { params })
}
