import request from '../utils/request'

// 消息过滤规则：按账号+关键词控制是否跳过自动回复 / 消息通知

export function listMessageFilters(params = {}) {
  return request({ url: '/message-filters', method: 'get', params })
}

export function saveMessageFilter(data) {
  return request({ url: '/message-filters', method: 'post', data })
}

export function deleteMessageFilter(id) {
  return request({ url: `/message-filters/${id}`, method: 'delete' })
}

export function batchDeleteMessageFilters(ids) {
  return request({ url: '/message-filters/batch-delete', method: 'post', data: { ids } })
}

export function toggleMessageFilter(id, enabled) {
  return request({ url: `/message-filters/${id}/toggle`, method: 'post', data: { enabled } })
}
