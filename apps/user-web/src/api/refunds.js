import request from '../utils/request'

/**
 * 退款管理 API。
 *
 * 后端路由（Java 网关代理至 Python automation-service /api/refunds/*）：
 * - GET    /refunds                       查询本地缓存的退款列表（多账号聚合 + 分类筛选 + 分页）
 * - POST   /refunds/sync                  触发同步（单账号或全部鱼小铺账号）
 * - GET    /refunds/sync-status           查询同步状态（缓存是否过期、是否正在同步）
 * - POST   /refunds/{refundId}/agree      同意退款（资金操作，需二次确认）
 * - GET    /refunds/fish-shop-accounts    列出当前租户下所有鱼小铺账号
 *
 * 仅鱼小铺账号支持退款接口；普通账号由后端拒绝，前端不会主动调用同步接口。
 */

/**
 * 查询本地缓存的退款列表。
 *
 * @param {Object} params
 * @param {number} [params.accountId]  账号ID，不传则聚合全部鱼小铺账号
 * @param {string} [params.category]   退款分类：all/unshipped/shipped/return/freight
 * @param {number} [params.page]       页码（从 1 开始）
 * @param {number} [params.pageSize]   每页条数（1-100）
 * @returns {Promise<{data: {items: Array, total: number, page: number, pageSize: number, category?: string, categoryUnavailable?: boolean, categoryUnavailableReason?: string}}>}
 */
export function getRefunds(params = {}) {
  return request({
    url: '/refunds',
    method: 'get',
    params,
  })
}

/**
 * 触发退款同步。
 *
 * @param {Object} [payload]
 * @param {number} [payload.accountId]  指定账号ID；不传则同步全部鱼小铺账号
 * @param {boolean} [payload.forceFull] 是否强制完整同步（首次同步或定期校验时使用）
 * @returns {Promise<{data: {ok: boolean, syncId?: string, total?: number, new?: number, updated?: number, totalCount?: number, isFullSync?: boolean, alreadyRunning?: boolean}}>}
 */
export function syncRefunds(payload = {}) {
  return request({
    url: '/refunds/sync',
    method: 'post',
    data: payload,
    timeout: 130000, // 后端 120s 超时，前端给 130s 余量
  })
}

/**
 * 查询同步状态（缓存是否过期、是否正在同步、最后同步时间）。
 *
 * @param {Object} [params]
 * @param {number} [params.accountId]  账号ID；不传则查询全部账号聚合状态
 * @returns {Promise<{data: {hasCache: boolean, isSyncing: boolean, lastSyncTime?: string, lastSyncStatus?: string, lastTotalCount?: number, cacheExpired: boolean, accountCount?: number, lastFullSyncTime?: string}}>}
 */
export function getRefundSyncStatus(params = {}) {
  return request({
    url: '/refunds/sync-status',
    method: 'get',
    params,
  })
}

/**
 * 同意退款（资金操作）。
 *
 * 后端会再次校验：账号归属、鱼小铺权限、refundId 归属、当前退款是否仍允许同意退款。
 *
 * @param {string} refundId      退款ID（refundInfoVO.refundId）
 * @param {Object} payload
 * @param {number} payload.accountId  退款所属账号ID
 * @returns {Promise<{data: {ok: boolean, refundId?: string, message?: string}}>}
 */
export function agreeRefund(refundId, payload) {
  return request({
    url: `/refunds/${encodeURIComponent(refundId)}/agree`,
    method: 'post',
    data: payload,
    timeout: 35000, // 后端 30s 超时，前端给 35s 余量
  })
}

/**
 * 列出当前租户下所有鱼小铺账号（用于前端账号选择下拉框）。
 *
 * 普通闲鱼账号不会出现在此列表中（后端按 fish_shop_user=1 过滤）。
 *
 * @returns {Promise<{data: {accounts: Array<{id: number, nickname?: string, externalUid?: string, fishShopUser?: boolean}>}}>}
 */
export function getRefundFishShopAccounts() {
  return request({
    url: '/refunds/fish-shop-accounts',
    method: 'get',
  })
}
