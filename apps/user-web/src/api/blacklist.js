import request from '../utils/request'

// 个人黑名单：命中买家在对应账号/商品下禁止自动发货

export function listPersonalBlacklist(params = {}) {
  return request({ url: '/blacklist/personal', method: 'get', params })
}

export function savePersonalBlacklist(data) {
  return request({ url: '/blacklist/personal', method: 'post', data })
}

export function deletePersonalBlacklist(id) {
  return request({ url: `/blacklist/personal/${id}`, method: 'delete' })
}

export function togglePersonalBlacklist(id, enabled) {
  return request({ url: `/blacklist/personal/${id}/toggle`, method: 'post', data: { enabled } })
}
