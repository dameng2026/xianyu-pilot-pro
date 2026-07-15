import request from '../utils/request.js'

/** 查询反馈桥接状态（是否已连接商业版后端） */
export function getFeedbackBridgeStatus() {
  return request.get('/feedback/bridge-status')
}

/** 提交反馈 */
export function submitFeedback(data) {
  return request.post('/feedback', data)
}

/** 我的反馈列表（分页 + 筛选） */
export function listMyFeedback(params = {}) {
  return request.get('/feedback', { params })
}

/** 我的反馈状态统计（单次聚合查询） */
export function getFeedbackStats() {
  return request.get('/feedback/stats')
}

/** 反馈详情（含回复列表） */
export function getFeedbackDetail(id) {
  return request.get(`/feedback/${id}`)
}

/** 用户追加补充说明 */
export function appendFeedbackReply(id, content) {
  return request.post(`/feedback/${id}/reply`, { content })
}
