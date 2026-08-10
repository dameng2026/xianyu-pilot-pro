import request from '../utils/request.js'
import { getBusinessSettings, saveBusinessSettings } from './businessSettings.js'
import { invalidateRequestCache, withRequestCache } from '../utils/requestCache.js'

const QUICK_REPLY_CACHE_NAMESPACE = 'api:quick-reply/templates'

// 快捷回复模板 CRUD
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

// AI 客服设置，读取 user_business_setting 中的 ai-customer-service
export function getAiCsSetting(options = {}) {
  return getBusinessSettings('ai-customer-service', options)
}

export function saveAiCsSetting(data) {
  return saveBusinessSettings('ai-customer-service', data)
}

// Token 余额查询
// 默认不缓存（aiTokenGuard 余额校验需实时），需要防抖的调用方传 { cacheTtlMs: 30000 }
export function getTokenBalance(options = {}) {
  const force = options.force === true
  return withRequestCache({
    keyParts: ['api:ai-billing/balance'],
    ttlMs: force ? 0 : (options.cacheTtlMs ?? 0),
    force,
    request: () => request({ url: '/ai-billing/balance', method: 'get' }),
  })
}
