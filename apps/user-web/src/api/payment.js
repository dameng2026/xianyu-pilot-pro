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
