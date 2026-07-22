import request from '../utils/request'

function buildParams(params, extra = {}) {
  const merged = { ...params, ...extra }
  if (merged.accountId === '' || merged.accountId === 'all' || merged.accountId == null) {
    delete merged.accountId
  }
  return merged
}

export function getDashboardSummary(params) {
  return request({
    url: '/dashboard/summary',
    method: 'get',
    params: buildParams(params)
  })
}

export function getDashboardSalesTrend(params) {
  return request({
    url: '/dashboard/sales-trend',
    method: 'get',
    params: buildParams(params)
  })
}

export function getDashboardOrderMessageTrend(params) {
  return request({
    url: '/dashboard/order-message-trend',
    method: 'get',
    params: buildParams(params)
  })
}

export function getDashboardAccountHealth(params) {
  return request({
    url: '/dashboard/account-health',
    method: 'get',
    params
  })
}

/**
 * 获取最近操作日志（首页"最近动态"用）
 * @param {object} params { limit?: number }
 */
export function getDashboardRecentLogs(params = {}) {
  return request({
    url: '/dashboard/recent-logs',
    method: 'get',
    params: { limit: params.limit ?? 10 }
  })
}

// 向后兼容：DashboardPage.vue 仍使用 getDashboardStats
export const getDashboardStats = getDashboardSummary