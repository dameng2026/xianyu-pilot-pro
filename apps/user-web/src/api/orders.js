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
