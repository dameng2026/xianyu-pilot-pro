import request from '../utils/request.js'
import { getBusinessSettings, saveBusinessSettings } from './businessSettings.js'
import { invalidateRequestCache, withRequestCache } from '../utils/requestCache.js'

const QUICK_REPLY_CACHE_NAMESPACE = 'api:quick-reply/templates'

// 蹇嵎鍥炲妯℃澘 CRUD
export function listQuickReplyTemplates(params = {}, options = {}) {
  const force = options.force === true
  return withRequestCache({
    keyParts: [QUICK_REPLY_CACHE_NAMESPACE, params],
    ttlMs: force ? 0 : (options.cacheTtlMs ?? 20000),
    force,
    request: () => request({ url: '/quick-reply/templates', method: 'get', params }),
  })
}

export function saveQuickReplyTemplate(data) {
  return request({
    url: '/quick-reply/templates',
    method: 'post',
    data
  }).then(result => {
    invalidateRequestCache(QUICK_REPLY_CACHE_NAMESPACE)
    return result
  })
}

export function deleteQuickReplyTemplate(id) {
  return request({ url: `/quick-reply/templates/${id}`, method: 'delete' }).then(result => {
    invalidateRequestCache(QUICK_REPLY_CACHE_NAMESPACE)
    return result
  })
}

// AI 瀹㈡湇璁剧疆锛岃鍙?user_business_setting 涓殑 ai-customer-service
export function getAiCsSetting(options = {}) {
  return getBusinessSettings('ai-customer-service', options)
}

export function saveAiCsSetting(data) {
  return saveBusinessSettings('ai-customer-service', data)
}

// Token 浣欓鏌ヨ
export function getTokenBalance() {
  return request({ url: '/ai-billing/balance', method: 'get' })
}
