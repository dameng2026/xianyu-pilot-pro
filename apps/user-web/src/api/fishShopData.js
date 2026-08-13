import request from '../utils/request'

/**
 * 鱼小铺数据分析 - 卖家数据概览
 *
 * 仅统计鱼小铺账号（fishShopUser=true），普通闲鱼账号不进入统计。
 * 链路：前端 -> Java /api/fish-shop-data/summary -> Python /api/fish-shop-data/summary
 */

/**
 * 拉取鱼小铺卖家数据概览。
 *
 * @param {Object} params
 * @param {number} [params.accountId] 鱼小铺账号 ID，不传表示"全部账号"
 * @param {'recent1d'|'recent7d'|'recent30d'} [params.dateType] 时间范围，默认 recent7d
 * @param {AbortSignal} [options.signal] 可选的请求取消信号，用于防止旧请求覆盖新选择
 * @returns {Promise} 后端返回的 data 字段（已由 request.js 拆包）
 */
export function getFishShopDataSummary(params = {}, options = {}) {
  const query = {}
  if (params.accountId && params.accountId > 0) {
    query.accountId = params.accountId
  }
  query.dateType = params.dateType || 'recent7d'
  return request({
    url: '/fish-shop-data/summary',
    method: 'get',
    params: query,
    signal: options.signal,
    timeout: 60000,
  })
}

/**
 * 拉取鱼小铺流量分布（来源/商品/时间/地域）。
 *
 * @param {Object} params
 * @param {number} [params.accountId] 鱼小铺账号 ID
 * @param {'recent1d'|'recent7d'|'recent30d'|'customDate'} [params.dateType]
 * @param {string} [params.dateRange] 自定义日期，yyyyMMdd|yyyyMMdd
 * @returns {Promise} 后端返回的 data 字段
 */
export function getFishShopBrowseSummary(params = {}, options = {}) {
  const query = { dateType: params.dateType || 'recent7d' }
  if (params.accountId && params.accountId > 0) query.accountId = params.accountId
  if (params.dateRange) query.dateRange = params.dateRange
  return request({
    url: '/fish-shop-data/browse',
    method: 'get',
    params: query,
    signal: options.signal,
    timeout: 60000,
  })
}
