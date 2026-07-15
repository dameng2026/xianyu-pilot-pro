import request from '../utils/request.js'

export function getAiBillingBalance() {
  return request({ url: '/ai-billing/balance', method: 'get' }).then(res => res?.data)
}

export function estimateAiUsage(payload) {
  return request({ url: '/ai-billing/estimate', method: 'post', data: payload }).then(res => res?.data)
}

export function estimateAiSceneUsage(payload) {
  return request({ url: '/ai-billing/estimate-scene', method: 'post', data: payload }).then(res => res?.data)
}
