import request from '../utils/request.js'

/** 获取对接凭证（脱敏 prefix，首次自动创建并返回明文） */
export function getApiCredential() {
  return request({ url: '/api-integration/credential', method: 'get' })
}

/** 重置对接密钥，返回新明文（仅本次一次） */
export function resetApiCredential() {
  return request({ url: '/api-integration/credential/reset', method: 'post' })
}

/** 概览：余额 + 单次价格 + 今日消耗 */
export function getApiOverview() {
  return request({ url: '/api-integration/overview', method: 'get' })
}

/** 个人求解记录分页 */
export function getApiRecords(params = {}) {
  return request({ url: '/api-integration/records', method: 'get', params })
}

/** 个人统计（KPI + 趋势） */
export function getApiStats(params = {}) {
  return request({ url: '/api-integration/stats', method: 'get', params })
}
