import request from '../utils/request.js'
import { invalidateRequestCache, withRequestCache } from '../utils/requestCache.js'

const CATEGORIES = ['ai-customer-service', 'message-settings', 'delivery-settings', 'product-op-settings']
const BUSINESS_SETTINGS_CACHE_NAMESPACE = 'api:business-settings'

function invalidateBusinessSettingsCache(category) {
  const safeCategory = category ? String(category) : ''
  invalidateRequestCache(key => key.includes(BUSINESS_SETTINGS_CACHE_NAMESPACE) && (!safeCategory || key.includes(`"${safeCategory}"`)))
}

/**
 * 读取指定分类的业务配置。
 * @param {string} category ai-customer-service | message-settings | delivery-settings | product-op-settings
 */
export function getBusinessSettings(category, options = {}) {
  const safeCategory = String(category || '')
  const force = options.force === true
  return withRequestCache({
    keyParts: [BUSINESS_SETTINGS_CACHE_NAMESPACE, safeCategory],
    ttlMs: force ? 0 : (options.cacheTtlMs ?? 20000),
    force,
    request: () => request.get(`/business-settings/${encodeURIComponent(safeCategory)}`),
  })
}

/**
 * 保存指定分类的业务配置。
 */
export function saveBusinessSettings(category, data) {
  return request.post(`/business-settings/${encodeURIComponent(category)}`, data).then(result => {
    invalidateBusinessSettingsCache(category)
    return result
  })
}

/**
 * 测试 AI 客服回复。
 */
export function testAiCustomerService(message) {
  return request.post('/business-settings/ai-customer-service/test', { message })
}

/**
 * 并发读取所有业务配置分类。
 */
export function getAllBusinessSettings() {
  return Promise.all(CATEGORIES.map(c => getBusinessSettings(c)))
    .then(results => {
      const map = {}
      CATEGORIES.forEach((c, i) => {
        const res = results[i]
        const data = res?.data
        if (!data || typeof data !== 'object' || Array.isArray(data)) {
          throw new Error(`${c} 配置响应格式异常`)
        }
        map[c] = data
      })
      return map
    })
}

export const BUSINESS_SETTING_CATEGORIES = CATEGORIES

/**
 * 获取 AI 客服配置默认值，用于“恢复默认”操作。
 */
export function getAiCsDefaults() {
  return request.get('/business-settings/ai-customer-service/defaults')
}

/**
 * 上传知识库文件，由 AI 提取回复规则。
 * @param {File} file 用户选择的 .md/.ppt/.pptx/.xlsx/.xls/.csv 文件
 */
export function uploadKnowledgeBase(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/business-settings/ai-customer-service/upload-knowledge', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000
  })
}
