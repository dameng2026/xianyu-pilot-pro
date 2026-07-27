import request from '../utils/request.js'

/**
 * 获取当前有效的会员充值活动。
 * 后端：GET /api/promotion/active
 * 返回空对象表示当前无活动。
 */
export function getActivePromotion() {
  return request({ url: '/promotion/active', method: 'get' }).then(res => res?.data || {})
}

/**
 * 下单前预览：服务端实时校验活动状态、价格、名额。
 * 后端：GET /api/promotion/preview?planId=&periodType=
 * 返回 { available, finalPriceYuan, originalPriceYuan, remainCount, ruleVersion, endTime, reason }
 */
export function previewPromotionPlan(planId, periodType) {
  return request({
    url: '/promotion/preview',
    method: 'get',
    params: { planId, periodType }
  }).then(res => res?.data || {})
}
