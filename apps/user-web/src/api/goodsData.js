import request from '../utils/request.js'

/**
 * 商品数据分析 API
 *
 * 后端：Java core-api /api/goods-data/*
 * 数据源：xianyu_goods + xianyu_trade_order + xianyu_trade_order_item 表（直连 DB，不调闲鱼 API）
 */

/**
 * 全局概览（KPI + 趋势 + TOP 排行）
 * @param {Object} params
 * @param {number} [params.accountId] 闲鱼账号 ID，不传表示"全部账号"
 * @param {1|3|7|30} [params.days] 时间范围，默认 7
 * @param {AbortSignal} [options.signal] 可选的请求取消信号
 */
export function getGoodsDataSummary(params = {}, options = {}) {
  const query = { days: params.days || 7 }
  if (params.accountId && params.accountId > 0) {
    query.accountId = params.accountId
  }
  return request({
    url: '/goods-data/summary',
    method: 'get',
    params: query,
    signal: options.signal,
    timeout: 30000,
  })
}

/**
 * 商品列表（带订单数据），分页
 * @param {Object} params
 * @param {number} [params.accountId]
 * @param {1|3|7|30} [params.days]
 * @param {string} [params.keyword]
 * @param {string} [params.sortBy] exposure/view/want/order/orderAmount/sold/conversion/newest/price
 * @param {number} [params.current]
 * @param {number} [params.size]
 */
export function getGoodsDataProducts(params = {}) {
  const query = {
    days: params.days || 7,
    sortBy: params.sortBy || 'order',
    current: params.current || 1,
    size: params.size || 20,
  }
  if (params.accountId && params.accountId > 0) query.accountId = params.accountId
  if (params.keyword) query.keyword = params.keyword
  return request({
    url: '/goods-data/products',
    method: 'get',
    params: query,
    timeout: 30000,
  })
}

/**
 * 单商品概览
 * @param {number} id 商品本地 ID（xianyu_goods.id）
 * @param {Object} params
 * @param {1|3|7|30} [params.days]
 */
export function getGoodsDataProductSummary(id, params = {}) {
  return request({
    url: `/goods-data/products/${id}/summary`,
    method: 'get',
    params: { days: params.days || 7 },
    timeout: 15000,
  })
}

/**
 * 单商品按日趋势
 * @param {number} id 商品本地 ID
 * @param {Object} params
 * @param {1|3|7|30} [params.days]
 */
export function getGoodsDataProductTrend(id, params = {}) {
  return request({
    url: `/goods-data/products/${id}/trend`,
    method: 'get',
    params: { days: params.days || 7 },
    timeout: 15000,
  })
}

/**
 * 最差商品筛选
 * @param {Object} params
 * @param {number} [params.accountId]
 * @param {1|3|7|30} [params.days]
 * @param {'exposure'|'view'|'conversion'|'order'} [params.metric] 筛选维度
 * @param {number} [params.limit] 返回数量上限，默认 20，最大 200
 */
export function getGoodsDataWorstProducts(params = {}) {
  const query = {
    days: params.days || 7,
    metric: params.metric || 'exposure',
    limit: params.limit || 20,
  }
  if (params.accountId && params.accountId > 0) query.accountId = params.accountId
  return request({
    url: '/goods-data/products/worst',
    method: 'get',
    params: query,
    timeout: 30000,
  })
}
