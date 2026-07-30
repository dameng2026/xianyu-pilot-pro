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
 * - GET    /refunds/detail                查询退款详情（三接口并行 + 缓存优先 + 后台刷新）
 * - POST   /refunds/detail/refresh        手动刷新退款详情（强制失效缓存并重新调用三接口）
 * - POST   /refunds/detail/retry          单独重试某个失败接口（不重新请求成功接口）
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

// ============================================================
// 退款详情（需求第五~二十三节）
// ============================================================
// 三个 MTOP 接口并行调用 + 缓存优先 + 进行中请求去重 + 局部失败处理
// 后端多重校验：账号归属 + 鱼小铺 + 退款归属 + orderId/refundId 关系
// 普通闲鱼账号不得访问详情、不得通过修改 URL 参数绕过

/**
 * 查询退款详情（缓存优先，过期后台刷新）。
 *
 * 后端流程：
 * 1. 校验账号归属 + 鱼小铺 + 退款归属 + orderId/refundId 关系
 * 2. 读取退款列表摘要（立即展示）
 * 3. 读取详情缓存：命中且未过期 → 直接返回
 * 4. 缓存过期 → 返回旧数据 + 后台刷新
 * 5. 无缓存 → 并行调用三接口（service.record / full.info / refund.detail）
 *
 * @param {Object} params
 * @param {number} params.accountId  退款所属账号ID（必须为鱼小铺账号）
 * @param {string} params.orderId    目标订单ID（按字符串处理，避免大整数精度丢失）
 * @param {string} params.refundId   目标退款ID
 * @returns {Promise<{data: {
 *   ok: boolean,
 *   summary?: Object|null,
 *   detail?: {
 *     serviceRecord: {status: 'ok'|'failed'|'skipped', data?: Object, error?: string, lastUpdate: string},
 *     fullInfo: {status: 'ok'|'failed'|'skipped', data?: Object, error?: string, lastUpdate: string},
 *     refundDetail: {status: 'ok'|'failed'|'skipped', data?: Object, error?: string, lastUpdate: string},
 *     lastSuccessAt: string|null,
 *     partialFailure: boolean
 *   }|null,
 *   cached: boolean,
 *   cacheExpired: boolean,
 *   backendBackgroundRefreshTriggered: boolean,
 *   error?: string
 * }}>}
 */
export function getRefundDetail(params) {
  return request({
    url: '/refunds/detail',
    method: 'get',
    params,
    timeout: 50000, // 后端 45s 超时，前端给 50s 余量
  })
}

/**
 * 手动刷新退款详情（强制失效缓存并重新调用三接口）。
 *
 * 需求第十九节第8点：页面提供手动刷新。
 * 需求第十九节第9点：刷新失败保留旧缓存。
 *
 * @param {Object} payload
 * @param {number} payload.accountId  退款所属账号ID
 * @param {string} payload.orderId    目标订单ID
 * @param {string} payload.refundId   目标退款ID
 * @returns {Promise<{data: {ok: boolean, summary?: Object|null, detail?: Object, error?: string}}>}
 */
export function refreshRefundDetail(payload) {
  return request({
    url: '/refunds/detail/refresh',
    method: 'post',
    data: payload,
    timeout: 50000,
  })
}

/**
 * 单独重试某个失败接口（不重新请求成功接口）。
 *
 * 需求第二十节：失败区域显示错误和单独重试，单独重试时只请求失败接口。
 * 返回更新后的完整 detail（含其他接口的旧数据 + 重试接口的新数据）。
 *
 * @param {Object} payload
 * @param {number} payload.accountId  退款所属账号ID
 * @param {string} payload.orderId    目标订单ID
 * @param {string} payload.refundId   目标退款ID
 * @param {'service_record'|'full_info'|'refund_detail'} payload.api  要重试的接口标识
 * @returns {Promise<{data: {ok: boolean, detail?: Object, error?: string}}>}
 */
export function retryRefundDetailApi(payload) {
  return request({
    url: '/refunds/detail/retry',
    method: 'post',
    data: payload,
    timeout: 35000, // 后端 30s 超时，前端给 35s 余量
  })
}
