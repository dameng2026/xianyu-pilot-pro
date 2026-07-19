import request from '../utils/request.js'

export function getPaymentMethods() {
  return request({ url: '/payment/methods', method: 'get' }).then(res => res?.data)
}

export function getTokenRechargePlans() {
  return request({ url: '/payment/token-plans', method: 'get' }).then(res => res?.data)
}

export function createPaymentOrder(data) {
  return request({ url: '/payment/orders', method: 'post', data }).then(res => res?.data)
}

export function getPaymentOrder(orderNo) {
  return request({ url: `/payment/orders/${orderNo}`, method: 'get' }).then(res => res?.data)
}

export function closePaymentOrder(orderNo) {
  return request({ url: `/payment/orders/${orderNo}/close`, method: 'post' }).then(res => res?.data)
}

export function mockPayOrder(orderNo) {
  return request({ url: `/payment/orders/${orderNo}/mock-pay`, method: 'post' }).then(res => res?.data)
}

// 管理员强制标记订单为已支付（用于本地开发测试或真实支付但回调丢失的订单补救）
// 不要求沙箱模式，但要求当前用户为超级管理员
export function forceMarkPaidOrder(orderNo, remark) {
  return request({
    url: `/admin-api/payment/orders/${orderNo}/force-paid`,
    method: 'post',
    data: { remark: remark || '' }
  }).then(res => res?.data)
}
