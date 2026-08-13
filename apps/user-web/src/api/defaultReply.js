import request from '../utils/request'

// 默认回复：未命中关键词规则且 AI 客服关闭时，按账号兜底回复

export function listDefaultReplies(params = {}) {
  return request({ url: '/default-reply', method: 'get', params })
}

export function getDefaultReply(accountId) {
  return request({ url: `/default-reply/${accountId}`, method: 'get' })
}

export function saveDefaultReply(accountId, data) {
  return request({ url: `/default-reply/${accountId}`, method: 'post', data })
}

export function deleteDefaultReply(accountId) {
  return request({ url: `/default-reply/${accountId}`, method: 'delete' })
}

export function clearDefaultReplyRecords(accountId) {
  return request({ url: `/default-reply/${accountId}/clear-records`, method: 'post' })
}
