import request from '../utils/request.js'

export const analyzeOpportunity = data => request.post('/opportunity/analyze', data || {})
export const rewriteOpportunity = data => request.post('/opportunity/rewrite', data || {})
export const listOpportunityHistory = params => request.get('/opportunity/history', { params: params || {} })

export const listOpportunityDrafts = params => request.get('/opportunity/drafts', { params: params || {} })
export const getOpportunityDraft = id => request.get(`/opportunity/drafts/${id}`)

export const getOpportunityAiStatus = () => request.get('/opportunity/ai-status')
export const getOpportunityImageStatus = () => request.get('/opportunity/image-status')

/**
 * 获取可用的生图模型列表
 */
export const getOpportunityImageModels = () => request.get('/opportunity/image-models')

/**
 * 生成商机商品图片（带多重机制和自动重试）。
 * 超时设为240秒，后端有3种生成方法和200秒轮询窗口。
 */
export const generateOpportunityImages = data => request.post('/opportunity/generate-images', data || {}, { timeout: 240000 })

/**
 * 查询生图历史记录列表
 */
export const listOpportunityImageHistory = params => request.get('/opportunity/image-history', { params: params || {} })

/**
 * 查询指定生图历史详情
 */
export const getOpportunityImageHistoryDetail = requestId => request.get(`/opportunity/image-history/${requestId}`)

/**
 * 恢复历史生图图片（当之前生图成功但前端未获取到时使用）
 */
export const recoverOpportunityImages = historyId => request.post(`/opportunity/image-recover/${historyId}`)