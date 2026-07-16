import request from '../utils/request'

export function getOrders(params) {
  return request({
    url: '/orders',
    method: 'get',
    params
  })
}

export function getOrderDetail(id, params) {
  return request({
    url: `/orders/${id}`,
    method: 'get',
    params
  })
}

export function updateOrder(id, data) {
  return request({
    url: `/orders/${id}`,
    method: 'put',
    data
  })
}

export function manualDeliverOrder(id, data) {
  return request({
    url: `/orders/${id}/manual-delivery`,
    method: 'post',
    data
  })
}

export function syncOrder(id) {
  return request({
    url: `/orders/${id}/sync`,
    method: 'post'
  })
}

export function syncOrders(data) {
  return request({
    url: '/orders/sync',
    method: 'post',
    data
  })
}

/**
 * 查询指定买家的近期订单（用于在线消息页客户订单板块）
 * @param {number} accountId 闲鱼账号 ID
 * @param {string} buyerId 买家用户 ID（不带 @goofish 后缀）
 * @param {number} size 返回条数，默认 10
 */
export function getCustomerOrders(accountId, buyerId, size = 10) {
  return request({
    url: '/orders',
    method: 'get',
    params: {
      accountId: accountId || undefined,
      buyerId: buyerId || undefined,
      current: 1,
      size
    }
  })
}
