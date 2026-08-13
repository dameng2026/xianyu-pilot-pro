import request from '../utils/request'

// 发货拦截规则：买家已有订单 / 未确认收货订单时禁止自动发货

export function listDeliveryBlockRules(params = {}) {
  return request({ url: '/delivery-block-rules', method: 'get', params })
}

export function saveDeliveryBlockRule(data) {
  return request({ url: '/delivery-block-rules', method: 'post', data })
}

export function toggleDeliveryBlockRule(id, enabled) {
  return request({ url: `/delivery-block-rules/${id}/toggle`, method: 'post', data: { enabled } })
}

export function deleteDeliveryBlockRule(id) {
  return request({ url: `/delivery-block-rules/${id}`, method: 'delete' })
}
