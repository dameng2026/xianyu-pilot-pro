import request from '../utils/request'

// 退款关单：账号收到退款订单时，按配置调用外部注销接口

export function getRefundCancelConfig(accountId) {
  return request({ url: `/refund-cancel/${accountId}`, method: 'get' })
}

export function saveRefundCancelConfig(accountId, data) {
  return request({ url: `/refund-cancel/${accountId}`, method: 'put', data })
}
